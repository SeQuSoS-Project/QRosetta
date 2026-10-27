"""Server-wide record of runner runs, for counting runs of other jobs that overlapped a run,
and the gate that lets an exclusive job run with no other runs on the server."""

import asyncio
import contextvars
import itertools
import threading
import time

EXCLUSIVE = contextvars.ContextVar("qrosetta_exclusive", default=False)
DISPATCH_TOKEN = contextvars.ContextVar("qrosetta_dispatch_token", default=None)
GATE_HELD = contextvars.ContextVar("qrosetta_gate_held", default=None)

_KEEP_SEC = 3600.0


class RunRegistry:
    """Start and end times of every run dispatched in the last hour, by dispatch token."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ids = itertools.count()
        self._runs = {}

    def start(self, token) -> int:
        with self._lock:
            run_id = next(self._ids)
            self._runs[run_id] = [token, time.time(), None]
            return run_id

    def finish(self, run_id) -> int:
        """Mark ``run_id`` finished; return how many runs of other tokens overlapped it."""
        now = time.time()
        with self._lock:
            entry = self._runs[run_id]
            entry[2] = now
            token, start, end = entry
            overlapping = sum(
                1 for other, (tok, s, e) in self._runs.items()
                if other != run_id and tok != token and s < end and (e is None or e > start))
            cutoff = now - _KEEP_SEC
            for other in [k for k, (_t, _s, e) in self._runs.items() if e is not None and e < cutoff]:
                del self._runs[other]
            return overlapping

    def active(self) -> int:
        with self._lock:
            return sum(1 for _t, _s, e in self._runs.values() if e is None)


REGISTRY = RunRegistry()


class ServicesInFlight:
    """Runner and compiler ids with a dispatch in flight, from its gate request to its
    release, counted per id."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counts = {}

    def enter(self, ids) -> list:
        ids = list(ids)
        with self._lock:
            for i in ids:
                self._counts[i] = self._counts.get(i, 0) + 1
        return ids

    def leave(self, ids) -> None:
        with self._lock:
            for i in ids:
                left = self._counts.get(i, 0) - 1
                if left > 0:
                    self._counts[i] = left
                else:
                    self._counts.pop(i, None)

    def busy(self) -> set:
        with self._lock:
            return set(self._counts)


IN_FLIGHT = ServicesInFlight()


class ExclusiveWaitTimeout(RuntimeError):
    """An exclusive dispatch waited longer than its cap for the server to become idle."""


class ExclusiveGate:
    """Shared/exclusive admission for dispatches: an exclusive dispatch waits until no other
    dispatch is running and holds new ones back until it ends."""

    def __init__(self):
        self._cond = None
        self._shared = 0
        self._exclusive = False
        self._waiting_exclusive = 0

    def _condition(self):
        if self._cond is None:
            self._cond = asyncio.Condition()
        return self._cond

    def status(self) -> dict:
        """Dispatches running and waiting at this moment."""
        return {"exclusive_running": self._exclusive, "exclusive_waiting": self._waiting_exclusive,
                "shared_running": self._shared}

    async def acquire(self, exclusive: bool, max_wait: float = None) -> float:
        """Wait for admission; return the seconds waited. An exclusive dispatch that is not
        admitted within ``max_wait`` seconds raises ExclusiveWaitTimeout."""
        started = time.monotonic()
        cond = self._condition()
        async with cond:
            if exclusive:
                self._waiting_exclusive += 1
                try:
                    await asyncio.wait_for(
                        cond.wait_for(lambda: not self._exclusive and self._shared == 0),
                        timeout=max_wait)
                except asyncio.TimeoutError:
                    raise ExclusiveWaitTimeout(
                        f"exclusive run not started: other runs kept the server busy for "
                        f"{max_wait:g} s (the exclusive wait cap); submit it again later") from None
                finally:
                    self._waiting_exclusive -= 1
                    cond.notify_all()
                self._exclusive = True
            else:
                await cond.wait_for(lambda: not self._exclusive and self._waiting_exclusive == 0)
                self._shared += 1
        return time.monotonic() - started

    def try_acquire_shared(self) -> bool:
        """Admit a shared dispatch only if that needs no wait: no exclusive dispatch is running
        or waiting. Release it with ``release(False)``."""
        if self._exclusive or self._waiting_exclusive:
            return False
        self._shared += 1
        return True

    async def release(self, exclusive: bool) -> None:
        """End one admission. The count changes before the first await and the waiters are
        woken in a shielded task, so a release cancelled while it waits for the condition's
        lock still frees the gate."""
        if exclusive:
            self._exclusive = False
        else:
            self._shared -= 1
        await asyncio.shield(self._notify_waiters())

    async def _notify_waiters(self) -> None:
        cond = self._condition()
        async with cond:
            cond.notify_all()


GATE = ExclusiveGate()


def releases_exclusive(worker):
    """Decorator for a background job worker whose first argument is the job id: forget the
    job's exclusive claim when the worker ends."""
    import functools

    @functools.wraps(worker)
    async def wrapper(job_id, *args, **kwargs):
        try:
            return await worker(job_id, *args, **kwargs)
        finally:
            release_exclusive(job_id)
    return wrapper


_EXCLUSIVE_OWNERS: dict = {}
_OWNERS_LOCK = threading.Lock()


def claim_exclusive(client: str, job_id: str) -> str:
    """Record ``job_id`` as ``client``'s exclusive job; return the job id the client already
    holds instead, if any."""
    with _OWNERS_LOCK:
        held = _EXCLUSIVE_OWNERS.get(client)
        if held is not None:
            return held
        _EXCLUSIVE_OWNERS[client] = job_id
        return None


def release_exclusive(job_id: str) -> None:
    """Forget ``job_id`` as an exclusive job."""
    with _OWNERS_LOCK:
        for client in [c for c, j in _EXCLUSIVE_OWNERS.items() if j == job_id]:
            del _EXCLUSIVE_OWNERS[client]


class circuit_section:
    """Async context for dispatching one circuit: its runs share one registry token, and in an
    exclusive job the gate is held for the whole circuit. ``waited`` is the seconds spent
    waiting for exclusive admission (None when not exclusive)."""

    def __init__(self, max_wait: float = None):
        self.max_wait = max_wait
        self.waited = None
        self._exclusive = False
        self._tokens = []

    async def __aenter__(self):
        self._tokens.append(DISPATCH_TOKEN.set(object()))
        self._exclusive = bool(EXCLUSIVE.get())
        if self._exclusive:
            self.waited = await GATE.acquire(True, self.max_wait)
            self._tokens.append(GATE_HELD.set(self.waited))
        return self

    async def __aexit__(self, *exc):
        if self._exclusive:
            GATE_HELD.reset(self._tokens.pop())
            await GATE.release(True)
        DISPATCH_TOKEN.reset(self._tokens.pop())
        return False
