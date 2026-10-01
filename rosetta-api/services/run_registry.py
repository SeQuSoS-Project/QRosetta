"""Server-wide record of runner runs, for counting runs of other jobs that overlapped a run,
and the gate that lets an exclusive job run with no other runs on the server."""

import asyncio
import contextvars
import itertools
import threading
import time

EXCLUSIVE = contextvars.ContextVar("qrosetta_exclusive", default=False)

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

    async def acquire(self, exclusive: bool) -> float:
        """Wait for admission; return the seconds waited."""
        started = time.monotonic()
        cond = self._condition()
        async with cond:
            if exclusive:
                self._waiting_exclusive += 1
                try:
                    await cond.wait_for(lambda: not self._exclusive and self._shared == 0)
                finally:
                    self._waiting_exclusive -= 1
                self._exclusive = True
            else:
                await cond.wait_for(lambda: not self._exclusive and self._waiting_exclusive == 0)
                self._shared += 1
        return time.monotonic() - started

    async def release(self, exclusive: bool) -> None:
        cond = self._condition()
        async with cond:
            if exclusive:
                self._exclusive = False
            else:
                self._shared -= 1
            cond.notify_all()


GATE = ExclusiveGate()
