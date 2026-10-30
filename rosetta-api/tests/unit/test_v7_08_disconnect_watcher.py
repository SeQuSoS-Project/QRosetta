"""V7-08: a request whose HTTP client goes away (the API process died, or its connection
dropped) leaves the runner's or compiler's queue without starting, or has its run stopped: the
child process is killed and reaped and the execution slot released. Connected requests, the
handler's own cancellation and the one-job CLI path behave as before. The HTTP tests serve the
shared scaffolding with uvicorn in its own process, with both event loops and both HTTP
implementations the images can pick."""

import asyncio
import http.client
import json
import os
import signal
import socket
import struct
import time

import pytest

from qrosetta_commons import helpers
from qrosetta_commons.helpers import DISCONNECT_POLL_SEC, ExecutionSlots, run_while_connected
from tests.unit import _isolated_fixture as fx
from tests.unit._real_runner import ScaffoldServer

SERVERS = [("runner", "asyncio", "h11"), ("runner", "uvloop", "httptools"),
           ("compiler", "asyncio", "h11"), ("compiler", "uvloop", "httptools")]
DETECTED_WITHIN = DISCONNECT_POLL_SEC + 1.5


@pytest.fixture(scope="module", params=SERVERS, ids=["-".join(s) for s in SERVERS])
def served(request):
    kind, loop, impl = request.param
    if loop == "uvloop":
        pytest.importorskip("uvloop")
        pytest.importorskip("httptools")
    server = ScaffoldServer(kind, loop, impl)
    server.path = "/run" if kind == "runner" else "/compile"
    try:
        yield server
    finally:
        server.close()


def _body(pid_file, sleep, **extra):
    return {"circuit_data": json.dumps({"pid_file": str(pid_file), "sleep": sleep}),
            "hard_timeout_seconds": 120, "max_queue_wait_seconds": 60, **extra}


def _send(server, body):
    """The request sent on its own connection, the response not read."""
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=120)
    conn.request("POST", server.path, body=json.dumps(body), headers={"Content-Type": "application/json"})
    return conn


def _read(conn):
    try:
        return json.loads(conn.getresponse().read())
    finally:
        conn.close()


def _drop(conn, reset=False):
    if reset:
        conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    conn.close()


def _first_pid(path, seconds=30.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists() and path.read_text().strip():
            return int(path.read_text().split()[0])
        time.sleep(0.02)
    raise AssertionError(f"{path} was not written")


def _gone_within(pid, seconds):
    t0 = time.monotonic()
    while fx.process_alive(pid) and time.monotonic() - t0 < seconds:
        time.sleep(0.02)
    return None if fx.process_alive(pid) else time.monotonic() - t0


@pytest.mark.parametrize("reset", [False, True], ids=["closed", "reset"])
def test_a_disconnect_during_a_run_kills_its_child_and_frees_the_slot(served, tmp_path, reset):
    conn = _send(served, _body(tmp_path / "a", 60))
    pid = _first_pid(tmp_path / "a")
    _drop(conn, reset)
    gone = _gone_within(pid, 10)
    try:
        assert gone is not None, "the abandoned run's child kept running"
        assert gone < DETECTED_WITHIN, f"the child was reaped {gone:.2f} s after the disconnect"
        after = _read(_send(served, _body(tmp_path / "b", 0)))
        assert not after.get("error"), after.get("error")
        assert after["queue_wait_sec"] < 0.5, f"the next run waited {after['queue_wait_sec']:.2f} s"
    finally:
        if fx.process_alive(pid):
            os.kill(pid, signal.SIGKILL)


def test_a_disconnect_while_queued_leaves_the_queue(served, tmp_path):
    first = _send(served, _body(tmp_path / "a", 3))
    _first_pid(tmp_path / "a")
    queued = _send(served, _body(tmp_path / "b", 0))
    time.sleep(0.3)
    _drop(queued)
    result = _read(first)
    assert not result.get("error") and result["result"] == 3
    time.sleep(DISCONNECT_POLL_SEC + 1.0)
    assert not (tmp_path / "b").exists(), "the abandoned request ran after it left"
    after = _read(_send(served, _body(tmp_path / "c", 0)))
    assert after["queue_wait_sec"] < 0.5, f"the next run waited {after['queue_wait_sec']:.2f} s"


def test_a_connected_run_over_several_polls_returns_what_the_slot_returns(served, tmp_path):
    sleep = 2 * DISCONNECT_POLL_SEC + 0.5
    over_http = _read(_send(served, _body(tmp_path / "a", sleep)))
    measured = served.path == "/run"
    direct = asyncio.run(ExecutionSlots(1).run(
        fx.sleeps_from_circuit, _body(tmp_path / "b", sleep), measured=measured))
    assert not over_http.get("error"), over_http.get("error")
    assert sorted(over_http) == sorted(direct)
    assert over_http["result"] == direct["result"] == sleep
    assert len((tmp_path / "a").read_text().split()) == len((tmp_path / "b").read_text().split())


class _Request:
    """What ``run_while_connected`` reads of a Starlette request."""

    def __init__(self, gone_after=None):
        self._gone_at = None if gone_after is None else time.monotonic() + gone_after
        self.url = type("Url", (), {"path": "/run"})()

    async def is_disconnected(self):
        return self._gone_at is not None and time.monotonic() >= self._gone_at


def test_a_disconnected_request_returns_none_after_the_child_is_reaped(tmp_path):
    async def main():
        slots = ExecutionSlots(1)
        result = await run_while_connected(_Request(gone_after=0.5), slots.run(
            fx.slow_records_pid, {"pid_file": str(tmp_path / "pid"), "sleep": 30, "hard_timeout_seconds": 60}))
        pid = int((tmp_path / "pid").read_text())
        return result, fx.process_alive(pid), slots.running, slots.waiting

    result, alive, running, waiting = asyncio.run(main())
    assert result is None and not alive and running == 0 and waiting == 0


def test_cancelling_the_handler_still_kills_the_child_before_raising(tmp_path):
    async def main():
        slots = ExecutionSlots(1)
        task = asyncio.create_task(run_while_connected(_Request(), slots.run(
            fx.slow_records_pid, {"pid_file": str(tmp_path / "pid"), "sleep": 30, "hard_timeout_seconds": 60})))
        while not ((tmp_path / "pid").exists() and (tmp_path / "pid").read_text()):
            await asyncio.sleep(0.02)
        pid = int((tmp_path / "pid").read_text())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return fx.process_alive(pid), slots.running

    alive, running = asyncio.run(main())
    assert not alive and running == 0


def test_a_task_that_absorbs_one_cancellation_is_cancelled_again():
    async def stubborn():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(30)

    async def main():
        task = asyncio.create_task(stubborn())
        await asyncio.sleep(0)
        t0 = time.monotonic()
        await helpers._cancel_until_done(task)
        return task.cancelled(), time.monotonic() - t0

    cancelled, took = asyncio.run(main())
    assert cancelled and took < DISCONNECT_POLL_SEC + 0.5


def test_the_one_job_cli_path_does_not_use_the_watcher(monkeypatch, capsys):
    async def refuse(*args, **kwargs):
        raise AssertionError("the CLI path reached run_while_connected")

    monkeypatch.setattr(helpers, "run_while_connected", refuse)
    monkeypatch.setattr("sys.argv", ["main.py", "--endpoint", "run", "--payload", '{"x": 21}'])
    helpers.run_cli_main(None, fx.fast, fx.fast, "Test")
    assert json.loads(capsys.readouterr().out.strip())["result"] == 42
