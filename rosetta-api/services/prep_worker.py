"""Circuit preparation in a separate process, under a memory and wall-clock limit.

``call(func, *args)`` runs ``func(*args)`` in one spawned worker process that the API starts
on first use and reuses, one call at a time in arrival order. While a call runs, the
worker's resident memory is read every ``POLL_SEC``; above ``settings.PREP_MAX_MIB``, or
after ``settings.PREP_TIMEOUT_SEC``, the worker is killed and the call raises
``PreparationLimitExceeded``. A worker that exits during a call raises
``PreparationWorkerFailed``. The next call starts a new worker. An exception raised by
``func`` is raised in the caller with the same type and message. ``func`` and its arguments
are pickled, so ``func`` must be a module-level function. The worker returns freed heap
memory to the system after a call that leaves it more than ``TRIM_ABOVE_MIB`` above its
starting size, and sets its OOM score to the maximum so that the kernel, when the container
runs out of memory, ends the worker before the API process.

``prepare`` runs a dispatch preparation (``prepare_statevector_dispatch`` /
``prepare_measured_dispatch``): in the worker when preprocessing applies the pytket
round-trip, in a thread otherwise. With ``IN_PROCESS = True`` every call runs in a thread of
the API process instead.
"""

import asyncio
import ctypes
import gc
import importlib
import multiprocessing
import pickle
import signal
import threading
import time
import traceback

import psutil

from config import settings
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-prep-worker")

POLL_SEC = 0.1
TRIM_ABOVE_MIB = 64
START_TIMEOUT_SEC = 120
IN_PROCESS = False

_WARM_IMPORTS = ("services.circuit_resolver", "services.quirk_converter")
_MIB = 1024 * 1024

DISPATCH_HINT = ("Run it with apply_preprocessing=false, which dispatches the circuit text "
                 "without the pytket round-trip, or submit a smaller circuit.")


class PreparationFailed(RuntimeError):
    """Circuit preparation was stopped or its process ended before it returned."""


class PreparationLimitExceeded(PreparationFailed):
    """Circuit preparation exceeded the memory or time limit and was stopped."""


class PreparationWorkerFailed(PreparationFailed):
    """The preparation process ended during a call."""


class _RemoteTraceback(Exception):
    def __init__(self, text: str):
        super().__init__(text)
        self.text = text

    def __str__(self):
        return self.text


def _malloc_trim():
    try:
        return ctypes.CDLL("libc.so.6").malloc_trim
    except (OSError, AttributeError):
        return lambda _pad: 0


def _rebuilt_exception(cls, args, state):
    exc = cls.__new__(cls)
    exc.args = args
    exc.__dict__.update(state)
    return exc


class _ExceptionCopy:
    """Pickles as an exception of ``cls`` built without calling its ``__init__``."""

    def __init__(self, cls, args, state):
        self.cls, self.args, self.state = cls, args, state

    def __reduce__(self):
        return _rebuilt_exception, (self.cls, self.args, self.state)


def _picklable(value) -> bool:
    try:
        pickle.dumps(value)
        return True
    except Exception:
        return False


def _round_trips(candidate, exc: BaseException) -> bool:
    try:
        copy = pickle.loads(pickle.dumps(candidate))
    except Exception:
        return False
    return type(copy) is type(exc) and str(copy) == str(exc)


def _portable(exc: BaseException):
    """``exc``, or a copy of it, that unpickles to the same type and message; a
    PreparationFailed naming both when neither does."""
    message = str(exc)
    if _round_trips(exc, exc):
        return exc
    args = exc.args if _picklable(exc.args) else tuple(str(a) for a in exc.args)
    state = {k: (v if _picklable(v) else None) for k, v in vars(exc).items()}
    copy = _ExceptionCopy(type(exc), args, state)
    if _round_trips(copy, exc):
        return copy
    return PreparationFailed(f"{type(exc).__name__}: {message}")


def _worker_main(conn) -> None:
    try:
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("1000")
    except OSError:
        pass
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    for name in _WARM_IMPORTS:
        importlib.import_module(name)
    trim = _malloc_trim()
    me = psutil.Process()
    settled = me.memory_info().rss + TRIM_ABOVE_MIB * _MIB
    conn.send_bytes(b"ready")
    while True:
        try:
            data = conn.recv_bytes()
        except (EOFError, OSError):
            return
        try:
            func, args = pickle.loads(data)
            reply = ("ok", func(*args))
        except Exception as exc:
            reply = ("error", _portable(exc), traceback.format_exc())
        del data
        try:
            out = pickle.dumps(reply, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as exc:
            out = pickle.dumps(("error", PreparationFailed(
                f"the preparation result could not be returned ({type(exc).__name__})"),
                traceback.format_exc()))
        del reply
        conn.send_bytes(out)
        del out
        if me.memory_info().rss > settled:
            gc.collect()
            trim(0)


def _ended(process) -> str:
    code = process.exitcode
    if code is None:
        return "still running"
    if code < 0:
        try:
            name = signal.Signals(-code).name
        except ValueError:
            name = f"signal {-code}"
        if -code == signal.SIGKILL:
            return f"killed by {name}, which the kernel sends when memory runs out"
        return f"killed by {name}"
    return f"exit code {code}"


class _Worker:
    def __init__(self):
        self._lock = threading.Lock()
        self._process = None
        self._conn = None

    def pid(self):
        return self._process.pid if self._process is not None and self._process.is_alive() else None

    def _start(self) -> None:
        ctx = multiprocessing.get_context("spawn")
        parent_end, child_end = ctx.Pipe()
        process = ctx.Process(target=_worker_main, args=(child_end,), name="qrosetta-prep",
                              daemon=True)
        process.start()
        child_end.close()
        try:
            ready = parent_end.poll(START_TIMEOUT_SEC) and parent_end.recv_bytes() == b"ready"
        except (EOFError, OSError):
            ready = False
        if not ready:
            process.kill()
            process.join(5)
            parent_end.close()
            raise PreparationWorkerFailed(
                f"The circuit preparation process did not start ({_ended(process)}).")
        self._process, self._conn = process, parent_end
        logger.info(f"Circuit preparation process started (pid {process.pid})")

    def _discard(self) -> None:
        if self._process is not None:
            if self._process.is_alive():
                self._process.kill()
            self._process.join(5)
        if self._conn is not None:
            self._conn.close()
        self._process, self._conn = None, None

    def stop(self) -> None:
        with self._lock:
            self._discard()

    def _send(self, payload: bytes) -> None:
        if self._process is None or not self._process.is_alive():
            self._discard()
            self._start()
        try:
            self._conn.send_bytes(payload)
        except (BrokenPipeError, OSError):
            self._discard()
            self._start()
            self._conn.send_bytes(payload)

    def call(self, payload: bytes, max_mib: int, timeout_sec: float, hint: str):
        """The unpickled reply to ``payload``; raises PreparationFailed when the call is stopped
        or the worker ends."""
        suffix = f" {hint}" if hint else ""
        with self._lock:
            self._send(payload)
            process, conn = self._process, self._conn
            watched = psutil.Process(process.pid)
            deadline = time.monotonic() + timeout_sec
            peak = 0
            while not conn.poll(POLL_SEC):
                try:
                    rss = watched.memory_info().rss
                except psutil.Error:
                    continue
                peak = max(peak, rss)
                if rss > max_mib * _MIB:
                    self._discard()
                    logger.warning(f"Circuit preparation stopped at {rss / _MIB:.0f} MiB "
                                   f"(limit {max_mib} MiB)")
                    raise PreparationLimitExceeded(
                        f"Preparing this circuit used more than {max_mib} MiB, the server's "
                        f"memory limit for circuit preparation, and was stopped.{suffix}")
                if time.monotonic() > deadline:
                    self._discard()
                    logger.warning(f"Circuit preparation stopped after {timeout_sec:g} s "
                                   f"(peak {peak / _MIB:.0f} MiB)")
                    raise PreparationLimitExceeded(
                        f"Preparing this circuit took longer than {timeout_sec:g} s, the "
                        f"server's time limit for circuit preparation, and was stopped.{suffix}")
            try:
                data = conn.recv_bytes()
            except (EOFError, OSError):
                process.join(5)
                how = _ended(process)
                self._discard()
                logger.warning(f"Circuit preparation process ended during a call ({how})")
                raise PreparationWorkerFailed(
                    f"The circuit preparation process ended while preparing this circuit "
                    f"({how}).{suffix}")
        return pickle.loads(data)


_WORKER = _Worker()


def worker_pid():
    """The running worker's pid, or None when none is running."""
    return _WORKER.pid()


def stop() -> None:
    """Kill the worker; the next call starts a new one."""
    _WORKER.stop()


async def call(func, *args, hint: str = None):
    """``func(*args)`` in the preparation worker (see the module docstring); ``hint`` is
    appended to the message of a PreparationFailed."""
    if IN_PROCESS:
        return await asyncio.to_thread(func, *args)
    payload = pickle.dumps((func, args), protocol=pickle.HIGHEST_PROTOCOL)
    status, value, *remote = await asyncio.to_thread(
        _WORKER.call, payload, settings.PREP_MAX_MIB, settings.PREP_TIMEOUT_SEC, hint)
    if status == "ok":
        return value
    value.__cause__ = _RemoteTraceback(remote[0])
    raise value


async def prepare(func, qasm: str, apply_preprocessing: bool):
    """``func(qasm, apply_preprocessing)`` for a dispatch preparation: in the worker with
    preprocessing, in a thread without it (no pytket call)."""
    if not apply_preprocessing:
        return await asyncio.to_thread(func, qasm, apply_preprocessing)
    return await call(func, qasm, apply_preprocessing, hint=DISPATCH_HINT)
