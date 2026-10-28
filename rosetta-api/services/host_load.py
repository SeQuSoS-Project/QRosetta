"""Host-load notices (POST /local/host-load): intervals in which the qrosetta command loads this
host (start, stop, remove, build, pull, image load and save, image probes). An open notice is a
registry interval of kind ``host_load``, which runs overlapping it count as
``server_overlapping_host_load``, and it
holds the run gate like a shared dispatch, so an exclusive run waits until it ends. A notice
ends with its end request, or NOTICE_TTL_SEC after its last heartbeat. A stop or remove notice
marks its services: a run that then loses its connection to one of them records
``stopped_by_user``. Interval ends are wall-clock times, like run intervals; whether a notice
has expired is decided on the monotonic clock, so a step of the wall clock does not end it."""

import asyncio
import time
import uuid
from dataclasses import dataclass, field

from services.run_registry import GATE, REGISTRY

KINDS = ("start", "stop", "remove", "build", "pull", "load", "save", "probe")
STOPPING_KINDS = frozenset({"stop", "remove"})
NOTICE_TTL_SEC = 30.0
HEARTBEAT_SEC = 10
STOP_GRACE_SEC = 60.0
STOP_KEEP_SEC = 3600.0
MAX_OPEN = 16

_clock = time.time
_ticks = time.monotonic


class NoticeNotFound(KeyError):
    """No open notice has this id (it ended, expired, or never existed)."""


class TooManyNotices(RuntimeError):
    """MAX_OPEN notices are already open."""


@dataclass
class Notice:
    id: str
    kind: str
    services: tuple
    started: float
    last_beat: float
    beat_ticks: float
    run_id: int
    gate_held: bool
    token: object = field(default_factory=object)

    def public(self) -> dict:
        return {"notice_id": self.id, "kind": self.kind, "services": list(self.services) or None,
                "gate_held": self.gate_held, "ttl_sec": NOTICE_TTL_SEC,
                "heartbeat_every_sec": HEARTBEAT_SEC}


_OPEN: dict = {}
_STOPS: list = []
_expiry = {"task": None}


def _record_stop(notice: Notice, ended: float = None) -> None:
    for entry in _STOPS:
        if entry["id"] == notice.id:
            entry["ended"] = ended
            return
    _STOPS.append({"id": notice.id, "services": set(notice.services), "started": notice.started,
                   "ended": ended})


async def _close(notice: Notice, ended: float) -> None:
    _OPEN.pop(notice.id, None)
    REGISTRY.end(notice.run_id, ended)
    if notice.kind in STOPPING_KINDS:
        _record_stop(notice, ended)
    if notice.gate_held:
        notice.gate_held = False
        await GATE.release_host_load()


async def expire_due() -> list:
    """End every notice whose last heartbeat is NOTICE_TTL_SEC or more ago on the monotonic
    clock, as of its expiry time; return their ids."""
    ticks = _ticks()
    due = [n for n in list(_OPEN.values()) if ticks - n.beat_ticks >= NOTICE_TTL_SEC]
    for notice in due:
        await _close(notice, notice.last_beat + NOTICE_TTL_SEC)
    cutoff = _clock() - STOP_KEEP_SEC
    _STOPS[:] = [s for s in _STOPS if s["ended"] is None or s["ended"] >= cutoff]
    return [n.id for n in due]


async def _expiry_loop() -> None:
    while _OPEN:
        nearest = min(n.beat_ticks for n in _OPEN.values()) + NOTICE_TTL_SEC
        await asyncio.sleep(max(0.5, nearest - _ticks()))
        await expire_due()


def _ensure_expiry() -> None:
    task = _expiry["task"]
    if task is None or task.done():
        _expiry["task"] = asyncio.get_running_loop().create_task(_expiry_loop())


async def begin(kind: str, services=None) -> dict:
    """Open a notice of ``kind`` for ``services`` (ids; none means the whole stack)."""
    await expire_due()
    if len(_OPEN) >= MAX_OPEN:
        raise TooManyNotices()
    now = _clock()
    notice = Notice(id=uuid.uuid4().hex, kind=kind, services=tuple(services or ()), started=now,
                    last_beat=now, beat_ticks=_ticks(), run_id=0, gate_held=GATE.hold_host_load())
    notice.run_id = REGISTRY.start(notice.token, kind="host_load", started=now)
    _OPEN[notice.id] = notice
    if kind in STOPPING_KINDS:
        _record_stop(notice)
    _ensure_expiry()
    return notice.public()


async def heartbeat(notice_id: str) -> dict:
    """Keep an open notice alive; NoticeNotFound when it is not open."""
    await expire_due()
    notice = _OPEN.get(notice_id)
    if notice is None:
        raise NoticeNotFound(notice_id)
    notice.last_beat, notice.beat_ticks = _clock(), _ticks()
    _ensure_expiry()
    return notice.public()


async def end(notice_id: str) -> dict:
    """End an open notice; NoticeNotFound when it is not open."""
    await expire_due()
    notice = _OPEN.get(notice_id)
    if notice is None:
        raise NoticeNotFound(notice_id)
    await _close(notice, _clock())
    return {**notice.public(), "ended": True}


def stopped_by_user(result_key: str, at: float = None) -> bool:
    """True when a stop or remove notice covers the service of ``result_key`` (its id before
    any ``~opt`` suffix) at ``at``: begun by then and open, or ended at most STOP_GRACE_SEC
    before."""
    at = _clock() if at is None else at
    service = str(result_key).split("~", 1)[0]
    for stop in _STOPS:
        if stop["services"] and service not in stop["services"]:
            continue
        if stop["started"] <= at and (stop["ended"] is None or at <= stop["ended"] + STOP_GRACE_SEC):
            return True
    return False


def open_notices() -> list:
    """The open notices."""
    return [n.public() for n in _OPEN.values()]


async def reset() -> None:
    """End every notice and forget stops (tests)."""
    for notice in list(_OPEN.values()):
        await _close(notice, _clock())
    _STOPS.clear()
    task = _expiry["task"]
    if task is not None and not task.done():
        task.cancel()
    _expiry["task"] = None
