"""GET /runners?fresh=true and GET /compilers?fresh=true: probe every service now instead of
reading the 60 s availability cache.

Only a signed-in account or the local lifecycle token may ask, at most FRESH_RATE_LIMIT times a
minute per account (all holders of the lifecycle token count as one client). A probe round younger than REUSE_SEC is served again. A service with a
dispatch in flight is not probed (``reason`` "busy"). The round takes the run gate as a shared
dispatch only when that needs no wait; while an exclusive run holds or waits for the gate,
the last cached entries are served with ``fresh`` false and ``reason`` "exclusive_run".
"""

import asyncio
import collections
import threading
import time
from datetime import datetime, timezone

from fastapi import HTTPException

from config import settings
from services import availability
from services.lifecycle_token import matches_lifecycle_token
from services.run_registry import GATE, IN_FLIGHT

FRESH_RATE_LIMIT = 6
FRESH_RATE_WINDOW_SEC = 60.0
REUSE_SEC = 5.0
FRESH_PROBE_TIMEOUT_SEC = 5.0
NOT_PROBED_DURING_EXCLUSIVE = "not probed yet: an exclusive run holds the server"

_hits: dict = collections.defaultdict(collections.deque)
_hits_lock = threading.Lock()
_rounds: dict = {}
_round_locks: dict = {}


def check_rate(client: str, now: float = None) -> None:
    """429 with Retry-After once ``client`` has asked FRESH_RATE_LIMIT times in the window."""
    now = time.monotonic() if now is None else now
    with _hits_lock:
        hits = _hits[client]
        while hits and now - hits[0] >= FRESH_RATE_WINDOW_SEC:
            hits.popleft()
        if len(hits) >= FRESH_RATE_LIMIT:
            retry = max(1, int(FRESH_RATE_WINDOW_SEC - (now - hits[0])) + 1)
            raise HTTPException(status_code=429, headers={"Retry-After": str(retry)}, detail=(
                f"Rate limit exceeded: fresh probes are limited to {FRESH_RATE_LIMIT} a minute "
                f"per client."))
        hits.append(now)


def _bearer(request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def _account_for(token: str):
    from db.database import SessionLocal
    from services.security import get_current_user
    db = SessionLocal()
    try:
        return get_current_user(token, db)
    finally:
        db.close()


async def authorize(request) -> str:
    """``"lifecycle"`` or ``"account"`` for a request that may ask for fresh probes; 401
    without a bearer token, or with one that is neither the lifecycle token nor a valid
    sign-in; 403 for a deactivated account."""
    token = _bearer(request)
    if token and matches_lifecycle_token(token):
        return "lifecycle"
    if not token:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"}, detail=(
            "fresh=true needs a signed-in account or the local lifecycle token."))
    await asyncio.to_thread(_account_for, token)
    return "account"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _wanted(services: dict) -> list:
    return [n for n, svc in services.items()
            if svc.get("enabled", True) and n not in settings.NOT_DEPLOYED]


def _cached_round(services: dict, reason: str) -> dict:
    out = {}
    for name in _wanted(services):
        entry = availability.cached_entry(name) or {
            "available": False, "reason": NOT_PROBED_DURING_EXCLUSIVE, "device": None}
        out[name] = {"entry": entry, "fresh": False, "reason": reason, "error_kind": None,
                     "probed_at": None}
    return out


async def _probe_round(services: dict) -> dict:
    names = _wanted(services)
    busy = IN_FLIGHT.busy()
    probed_at = _utc_now()
    probed = await availability.probe_now([n for n in names if n not in busy], services,
                                          FRESH_PROBE_TIMEOUT_SEC)
    out = {}
    for name in names:
        if name in busy:
            cached = availability.cached_entry(name) or {}
            out[name] = {"entry": {"available": True, "reason": None,
                                   "device": cached.get("device"),
                                   **({"versions": cached["versions"]} if cached.get("versions") else {})},
                         "fresh": False, "reason": "busy", "error_kind": None, "probed_at": None}
        else:
            entry, kind = probed[name]
            out[name] = {"entry": entry, "fresh": True, "reason": None, "error_kind": kind,
                         "probed_at": probed_at}
    return out


async def fresh_round(kind: str, services: dict) -> dict:
    """``{id: {entry, fresh, reason, error_kind, probed_at}}`` for the enabled, deployed
    services of ``services``. In Kubernetes mode no service is long-lived: the registry
    entries are served with ``reason`` "no_long_lived_services"."""
    if settings.EXECUTION_MODE != "local":
        entries = await availability.runner_availability(services=services)
        return {n: {"entry": entries[n], "fresh": False, "reason": "no_long_lived_services",
                    "error_kind": None, "probed_at": None} for n in _wanted(services)}
    lock = _round_locks.setdefault(kind, asyncio.Lock())
    async with lock:
        last = _rounds.get(kind)
        if last and time.monotonic() - last[0] < REUSE_SEC:
            return last[1]
        if not GATE.try_acquire_shared():
            return _cached_round(services, "exclusive_run")
        try:
            out = await _probe_round(services)
        finally:
            await GATE.release(False)
        _rounds[kind] = (time.monotonic(), out)
        return out


def reset() -> None:
    """Forget rounds and rate-limit counts (tests)."""
    _rounds.clear()
    _round_locks.clear()
    with _hits_lock:
        _hits.clear()
