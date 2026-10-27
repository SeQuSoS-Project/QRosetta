"""Gated saves (``?gated=true`` on GET /jobs/{id}/report and POST /jobs/{id}/export): the
report or crate of a finished job is written and sent only while no dispatch is in flight, and
new dispatches wait for the gate until it has been sent (``run_registry.ExclusiveGate``). Each
job records its save requests under ``saves``."""

import asyncio
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from starlette.background import BackgroundTask
from starlette.concurrency import iterate_in_threadpool

from services.run_registry import GATE

GATE_BUSY = "gate_busy"
RETRY_AFTER_SEC = 5
LEASE_MAX_SEC = 3600
KINDS = ("report", "crate")


def _utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="milliseconds")


def dispatches_in_flight() -> int:
    """Dispatches running or waiting for exclusive admission at this moment."""
    gate = GATE.status()
    return gate["shared_running"] + int(gate["exclusive_running"]) + gate["exclusive_waiting"]


def _record(job: dict, kind: str) -> dict:
    saves = job.setdefault("saves", {})
    return saves.setdefault(kind, {
        "gate_busy_refusals": 0, "first_refused_at": None, "gated_admitted_at": None,
        "deferred_sec": None, "ungated_requests": 0, "ungated_with_dispatches_in_flight": 0,
        "_first_refused": None})


def public_record(job: dict):
    """The job's ``saves`` as GET /jobs/{id} shows it, or None before any save request."""
    saves = job.get("saves")
    if not isinstance(saves, dict):
        return None
    return {kind: {k: v for k, v in entry.items() if not k.startswith("_")}
            for kind, entry in saves.items()}


def note_ungated(job: dict, kind: str) -> None:
    """Record a save request sent without ``gated=true`` and whether dispatches were in flight."""
    entry = _record(job, kind)
    entry["ungated_requests"] += 1
    if dispatches_in_flight():
        entry["ungated_with_dispatches_in_flight"] += 1


class SaveLease:
    """The gate held for one gated save; ``release`` is idempotent. A lease not released
    within LEASE_MAX_SEC (a response that was never sent) releases itself."""

    def __init__(self):
        self._released = False
        self._timer = asyncio.get_running_loop().call_later(
            LEASE_MAX_SEC, lambda: asyncio.ensure_future(self.release()))

    @property
    def released(self) -> bool:
        return self._released

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._timer.cancel()
        await GATE.release_save()

    async def _chunks(self, chunks):
        try:
            async for chunk in iterate_in_threadpool(chunks):
                yield chunk
        finally:
            await self.release()

    def body(self, chunks) -> dict:
        """StreamingResponse arguments that send ``chunks`` and then release the gate, also
        when the client goes away first."""
        return {"content": self._chunks(chunks), "background": BackgroundTask(self.release)}


def admit(job: dict, kind: str) -> SaveLease:
    """Take the gate for a gated save of ``job`` (``kind`` report or crate) and record it;
    409 ``gate_busy`` with Retry-After while a dispatch is running or waiting for exclusive
    admission."""
    entry = _record(job, kind)
    now = time.time()
    if not GATE.try_acquire_save():
        entry["gate_busy_refusals"] += 1
        if entry["_first_refused"] is None:
            entry["_first_refused"] = now
            entry["first_refused_at"] = _utc(now)
        raise HTTPException(status_code=409, headers={"Retry-After": str(RETRY_AFTER_SEC)}, detail=(
            f"{GATE_BUSY}: {dispatches_in_flight()} dispatch(es) in flight on this server; a gated "
            f"save runs only while none is. Retry after Retry-After seconds, or send the request "
            f"without gated=true."))
    entry["gated_admitted_at"] = _utc(now)
    if entry["_first_refused"] is not None:
        entry["deferred_sec"] = round(now - entry["_first_refused"], 3)
    return SaveLease()


async def build_gated(job: dict, kind: str, build, *args):
    """``(lease, build(*args))`` with ``build`` run in a thread under a gated save; the lease
    is released when ``build`` raises."""
    lease = admit(job, kind)
    try:
        return lease, await asyncio.to_thread(build, *args)
    except BaseException:
        await lease.release()
        raise
