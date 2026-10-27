"""Runner availability: whether an enabled runner can execute on this deployment.

Each entry is ``{"available": bool, "reason": str | None, "device": str | None}``.

* local mode: ``GET <base_url>/capabilities`` on the runner, cached for
  ``AVAILABILITY_TTL_SEC``. A runner without the endpoint (404/405) is available unless its
  registry entry has ``requires_gpu`` and QROSETTA_GPU_AVAILABLE is false. A runner that
  cannot be reached is unavailable with reason ``"unreachable"``.
* kubernetes mode: no runner is long-lived, so a runner with ``requires_gpu`` is available
  only when QROSETTA_GPU_AVAILABLE is true; every other enabled runner is available.

In both modes a service listed in QROSETTA_NOT_DEPLOYED (comma-separated ids) is unavailable
with reason ``NOT_DEPLOYED``.
"""

import asyncio
import socket
import time

import httpx
from fastapi import HTTPException

from config import settings
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-availability")

AVAILABILITY_TTL_SEC = 60.0
PROBE_TIMEOUT_SEC = 2.0
UNREACHABLE = "unreachable"
NOT_DEPLOYED = "not deployed on this server"

_cache: dict = {}


def _gpu_reason() -> str:
    return ("requires a GPU; this deployment has none (QROSETTA_GPU_AVAILABLE is not set "
            "to true)")


def _registry_entry(svc: dict) -> dict:
    if svc.get("requires_gpu") and not settings.GPU_AVAILABLE:
        return {"available": False, "reason": _gpu_reason(), "device": None}
    return {"available": True, "reason": None, "device": None}


_DNS_MESSAGES = ("name or service not known", "temporary failure in name resolution",
                 "nodename nor servname", "no address associated", "name does not resolve")


def error_kind(exc: BaseException) -> str:
    """Why a probe got no answer: ``dns`` (the name did not resolve), ``timeout`` or
    ``connect`` (refused, reset, or any other transport failure)."""
    seen = set()
    node = exc
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        if isinstance(node, socket.gaierror) or any(m in str(node).lower() for m in _DNS_MESSAGES):
            return "dns"
        node = node.__cause__ or node.__context__
    return "timeout" if isinstance(exc, httpx.TimeoutException) else "connect"


async def _probe(client: httpx.AsyncClient, svc: dict) -> dict:
    return (await probe_with_kind(client, svc))[0]


async def probe_with_kind(client: httpx.AsyncClient, svc: dict) -> tuple:
    """``(availability entry, error kind)`` from ``GET <base_url>/capabilities``; the kind is
    ``dns``, ``connect`` or ``timeout`` when no answer came, ``http`` for an error status
    other than 404/405, else None."""
    try:
        response = await client.get(f"{svc['base_url']}/capabilities")
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException, httpx.NetworkError) as exc:
        return {"available": False, "reason": UNREACHABLE, "device": None}, error_kind(exc)
    except Exception as exc:
        logger.warning(f"Capability probe of {svc['base_url']} failed: {type(exc).__name__}")
        return {"available": False, "reason": UNREACHABLE, "device": None}, error_kind(exc)
    if response.status_code in (404, 405):
        return _registry_entry(svc), None
    if response.status_code != 200:
        return {"available": True, "reason": None, "device": None}, "http"
    try:
        body = response.json()
    except ValueError:
        return {"available": True, "reason": None, "device": None}, None
    if not isinstance(body, dict):
        return {"available": True, "reason": None, "device": None}, None
    available = bool(body.get("available", True))
    reason = body.get("reason")
    info = {"available": available,
            "reason": (str(reason) if reason else None) if not available else None,
            "device": str(body["device"]) if body.get("device") else None}
    versions = _reported_versions(body)
    if versions:
        info["versions"] = versions
    return info, None


def _string_map(value) -> dict:
    return ({str(k): v for k, v in value.items() if isinstance(v, str)}
            if isinstance(value, dict) else {})


def _reported_versions(body: dict) -> dict:
    """The version and image fields a service's /capabilities reports, type-checked."""
    out = {}
    if isinstance(body.get("image_identity"), dict):
        out["image_identity"] = {key: value for key, value in body["image_identity"].items()
                                 if key in ("source", "release", "git_sha")
                                 and (value is None or isinstance(value, str))}
    if isinstance(body.get("sdk_versions"), dict):
        out["sdk_versions"] = _string_map(body["sdk_versions"])
    if isinstance(body.get("native_components"), list):
        out["native_components"] = [
            {str(k): v for k, v in entry.items()
             if isinstance(v, str) or (isinstance(v, list) and all(isinstance(x, str) for x in v))}
            for entry in body["native_components"] if isinstance(entry, dict)]
    if isinstance(body.get("build_files"), dict):
        out["build_files"] = _string_map(body["build_files"])
    if isinstance(body.get("image_git_sha"), str):
        out["image_git_sha"] = body["image_git_sha"]
    return out


async def runner_availability(names=None, services=None) -> dict:
    """``{runner_id: {available, reason, device}}`` for the enabled runners in ``names``
    (default: every enabled runner). ``services`` replaces the runner registry, e.g. with
    the compiler registry."""
    services = services if services is not None else settings.get_runner_services()
    wanted = [n for n in (names if names is not None else services)
              if n in services and services[n].get("enabled", True)]
    out = {n: {"available": False, "reason": NOT_DEPLOYED, "device": None}
           for n in wanted if n in settings.NOT_DEPLOYED}
    wanted = [n for n in wanted if n not in out]
    if settings.EXECUTION_MODE != "local":
        return {**out, **{n: _registry_entry(services[n]) for n in wanted}}

    now = time.monotonic()
    stale = []
    for name in wanted:
        cached = _cache.get(name)
        if cached and now - cached[0] < AVAILABILITY_TTL_SEC:
            out[name] = dict(cached[1])
        else:
            stale.append(name)
    if stale:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SEC) as client:
            probed = await asyncio.gather(*(_probe(client, services[n]) for n in stale))
        for name, info in zip(stale, probed):
            _cache[name] = (now, info)
            out[name] = dict(info)
    return out


def clear_cache() -> None:
    _cache.clear()


async def probe_now(names, services: dict, timeout: float) -> dict:
    """``{name: (entry, error kind)}``: probe ``names`` now, ignoring the cache, and store the
    entries in it as fresh."""
    now = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        probed = await asyncio.gather(*(probe_with_kind(client, services[n]) for n in names))
    out = {}
    for name, (info, kind) in zip(names, probed):
        _cache[name] = (now, info)
        out[name] = (dict(info), kind)
    return out


def cached_entry(name: str):
    """The last probe result for ``name`` whatever its age, or None."""
    cached = _cache.get(name)
    return dict(cached[1]) if cached else None


async def require_available(target_simulators) -> None:
    """400 naming every runner in ``target_simulators`` that is unavailable, with reasons."""
    if not target_simulators:
        return
    status = await runner_availability(list(dict.fromkeys(target_simulators)))
    missing = [(n, info["reason"] or "unavailable") for n, info in status.items()
               if not info["available"]]
    if missing:
        listed = "; ".join(f"{n}: {reason}" for n, reason in missing)
        raise HTTPException(status_code=400, detail=f"Unavailable runner(s) requested: {listed}.")


async def filter_available(runner_urls: dict, target_simulators) -> tuple:
    """``(urls, skipped)``: with explicit ``target_simulators`` every url is kept; with none,
    unavailable runners are dropped and listed in ``skipped`` as ``{id, reason}``."""
    if target_simulators or not runner_urls:
        return runner_urls, []
    status = await runner_availability(list(runner_urls))
    kept = {n: u for n, u in runner_urls.items() if status.get(n, {}).get("available", True)}
    skipped = [{"id": n, "reason": status[n]["reason"] or "unavailable"}
               for n in runner_urls if n not in kept]
    return kept, skipped
