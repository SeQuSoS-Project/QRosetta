"""Following a job (spec §6.18 progress, Q7): polling GET /jobs/{id} (first after 1.5 s, then
every 3 s; after a poll that gets no answer, 3, 6, 12, 24, then 30 s, for up to 5 minutes), one
stderr line whenever the live statuses change, labelled through /config status_labels; a 404
for the job is JobLost; SIGINT, SIGTERM and SIGHUP stop the waiting and leave the job running;
a SIGINT during a submit request waits for the answer, up to 10 s, so the job id is not lost."""

import _thread
import signal
import threading
import time
from contextlib import contextmanager

from qrosetta_cli import output
from qrosetta_cli.client.transport import Transient
from qrosetta_cli.errors import CliError, Exit

POLL_FIRST_SEC = 1.5
POLL_EVERY_SEC = 3.0
POLL_BACKOFF_MAX_SEC = 30.0
POLL_OUTAGE_PATIENCE_SEC = 300.0
SUBMIT_GRACE_SEC = 10
FINISHED = ("completed", "failed", "cancelled")


def pause(seconds):
    time.sleep(seconds)


def clock():
    return time.monotonic()


class Stopped(Exception):
    """Waiting stopped by a signal; `code` is its exit code."""

    def __init__(self, code):
        super().__init__(int(code))
        self.code = Exit(code)


class WaitTimeout(Exception):
    pass


def _label(labels, kind, status):
    entry = ((labels or {}).get(kind) or {}).get(status)
    if isinstance(entry, dict) and entry.get("label"):
        return entry["label"]
    return str(status).upper()


def status_line(env, labels, title):
    """One line for a job envelope: phase, playlist position and each run's status."""
    phase = env.get("phase") or env.get("status") or "queued"
    parts = [f"{title}: {_label(labels, 'phases', phase)}"]
    progress = env.get("progress") or {}
    tasks = progress.get("tasks") or []
    index = progress.get("current_index")
    if isinstance(index, int) and 0 <= index < len(tasks):
        task = tasks[index] or {}
        parts.append(
            f"circuit {index + 1} of {progress.get('total') or len(tasks)}: {task.get('name', '')}".rstrip(": ")
        )
    elif tasks:
        parts.append(f"{progress.get('completed', 0)} of {progress.get('total') or len(tasks)} circuits")
    runs = env.get("runner_statuses") or {}
    if runs:
        parts.append(", ".join(f"{key} {_label(labels, 'runs', status)}" for key, status in runs.items()))
    return " · ".join(parts)


def _poll_failure(exc):
    return isinstance(exc, Transient) or exc.http_status in (502, 503, 504)


def poll_retry_delay(failures):
    """Seconds before the next poll after `failures` failed polls in a row: 3, 6, 12, 24, then 30."""
    return min(POLL_EVERY_SEC * 2 ** max(0, failures - 1), POLL_BACKOFF_MAX_SEC)


class JobLost(CliError):
    """The server answered 404 for a job this client submitted: a restart lost it, or it expired."""


def wait_job(conn, job_id, title, wait_timeout=None):
    """Poll until the job finishes and return its final envelope. WaitTimeout after
    `wait_timeout` seconds; a 404 raises JobLost (exit 14). A poll that gets no answer or a
    502/503/504 (after the request's own retries) is repeated after `poll_retry_delay`, for up to
    POLL_OUTAGE_PATIENCE_SEC from the first failure in a row, then exit 11."""
    labels = conn.config.get("status_labels") or {}
    start = clock()
    delay = POLL_FIRST_SEC
    last = None
    failures = 0
    failing_since = None
    while True:
        if wait_timeout is not None:
            left = wait_timeout - (clock() - start)
            if left <= 0:
                raise WaitTimeout()
            delay = min(delay, left)
        pause(delay)
        try:
            env = conn.get(f"/jobs/{job_id}", what=f"job {job_id[:8]}", hint="qrosetta jobs")
        except CliError as exc:
            if exc.code == Exit.NOT_FOUND:
                raise JobLost(
                    exc.message, Exit.NOT_FOUND, "job_lost", http_status=exc.http_status, detail=exc.detail
                ) from None
            if not _poll_failure(exc):
                raise
            failures += 1
            failing_since = clock() if failing_since is None else failing_since
            if clock() - failing_since >= POLL_OUTAGE_PATIENCE_SEC:
                raise CliError(
                    f"No answer from {getattr(conn, 'url', 'the server')} for {POLL_OUTAGE_PATIENCE_SEC / 60:g} minutes while waiting for "
                    f"job {job_id[:8]} (last: {exc.message}). The job may still be running there.",
                    Exit.UNREACHABLE,
                    "unreachable",
                    hint=f"qrosetta wait job:{job_id[:8]} once the server answers",
                    http_status=exc.http_status,
                ) from None
            delay = poll_retry_delay(failures)
            output.progress(f"{title}: {exc.message} Polling again in {delay:g} s.")
            continue
        failures = 0
        failing_since = None
        line = status_line(env, labels, title)
        if line != last:
            output.progress(line)
            last = line
        if env.get("status") in FINISHED:
            return env
        delay = POLL_EVERY_SEC


def _main_thread():
    return threading.current_thread() is threading.main_thread()


@contextmanager
def stop_signals():
    """While waiting: SIGTERM and SIGHUP raise Stopped (143, 129), SIGINT KeyboardInterrupt."""
    if not _main_thread():
        yield
        return
    previous = {}

    def handler(signum, frame):
        raise Stopped(Exit.SIGTERM if signum == getattr(signal, "SIGTERM", None) else Exit.SIGHUP)

    for name in ("SIGTERM", "SIGHUP"):
        sig = getattr(signal, name, None)
        if sig is not None:
            previous[sig] = signal.signal(sig, handler)
    try:
        yield
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)


@contextmanager
def submitting():
    """Around a submit request: the first SIGINT is noted and the answer awaited (up to
    SUBMIT_GRACE_SEC); a second SIGINT, or no answer in time, raises CliError 130 saying a job
    may exist without a known id. The yielded dict's `interrupted` is True after a first SIGINT."""
    state: dict = {"interrupted": False, "timer": None}
    if not _main_thread():
        yield state
        return

    def handler(signum, frame):
        if state["interrupted"]:
            raise CliError(
                "Stopped before the server answered; a job may exist on the server without a known id.",
                Exit.SIGINT,
                "submit_interrupted",
                hint="qrosetta jobs",
            )
        state["interrupted"] = True
        output.progress(
            f"Waiting up to {SUBMIT_GRACE_SEC} s for the server's answer, so the job id is not lost; "
            "Ctrl-C again stops now."
        )
        timer = threading.Timer(SUBMIT_GRACE_SEC, _thread.interrupt_main)
        timer.daemon = True
        timer.start()
        state["timer"] = timer

    previous = signal.signal(signal.SIGINT, handler)
    try:
        yield state
    finally:
        signal.signal(signal.SIGINT, previous)
        if state["timer"] is not None:
            state["timer"].cancel()
