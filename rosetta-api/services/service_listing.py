"""The rows of GET /runners and GET /compilers: registry entries with their availability."""

from config import settings
from services import fresh_probes
from services.availability import NOT_DEPLOYED, runner_availability
from services.compilation import COMPILER_SERVICES
from services.profiles import (compiler_default_selected, compiler_profiles,
                               runner_default_selected, runner_profiles)


def _unavailable_reason(enabled: bool, info: dict):
    return None if (enabled and info["available"]) else (info["reason"] or "unavailable")


def runner_row(name: str, config: dict, info: dict) -> dict:
    """One runner as GET /runners lists it."""
    opt_levels = config.get("optimization_levels", {})
    enabled = config.get("enabled", True)
    return {
        "id": name,
        "enabled": enabled,
        "available": bool(enabled and info["available"]),
        "unavailable_reason": _unavailable_reason(enabled, info),
        "device": info.get("device"),
        "requires_gpu": bool(config.get("requires_gpu", False)),
        "max_level": max(opt_levels.keys()) if opt_levels else 0,
        "optimization_levels": {str(k): v for k, v in opt_levels.items()},
        "precision": dict(config["precision"]),
        "qubit_ordering": dict(config["qubit_ordering"]),
        "default_selected": runner_default_selected(config),
        "profiles": runner_profiles(name, config),
        "versions": info.get("versions"),
        "backend": None,
        "version": None,
    }


def compiler_row(cid: str, svc: dict, info: dict) -> dict:
    """One compile-only service as GET /compilers lists it."""
    enabled = svc.get("enabled", True)
    return {
        "id": cid,
        "name": svc["name"],
        "enabled": enabled,
        "available": bool(enabled and info["available"]),
        "unavailable_reason": _unavailable_reason(enabled, info),
        "optimization_levels": {str(k): v for k, v in svc["optimization_levels"].items()},
        "versions": info.get("versions"),
        "default_selected": compiler_default_selected(svc),
        "profiles": compiler_profiles(svc),
        "backend": None,
        "version": None,
    }


async def runner_rows() -> list:
    """Every registered runner, in registry order."""
    services = settings.get_runner_services()
    availability = await runner_availability()
    disabled = {"available": False, "reason": "disabled", "device": None}
    return [runner_row(name, config, availability.get(name) or disabled)
            for name, config in services.items()]


def _with_probe(row: dict, probe) -> dict:
    if probe is None:
        return {**row, "fresh": False, "reason": "disabled" if not row["enabled"] else "not_deployed",
                "error_kind": None, "probed_at": None}
    return {**row, "fresh": probe["fresh"], "reason": probe["reason"],
            "error_kind": probe["error_kind"], "probed_at": probe["probed_at"]}


async def fresh_rows(kind: str, request, client: str) -> list:
    """The rows of GET /runners?fresh=true (``kind`` "runners") or GET /compilers?fresh=true
    ("compilers") from a fresh probe round, each with ``fresh``, ``reason``, ``error_kind``
    and ``probed_at``. 401/403 for a caller that may not ask, 429 over the rate limit."""
    await fresh_probes.authorize(request)
    fresh_probes.check_rate(client)
    if kind == "runners":
        services = settings.get_runner_services()
        probes = await fresh_probes.fresh_round(kind, services)
        disabled = {"available": False, "reason": "disabled", "device": None}
        not_deployed = {"available": False, "reason": NOT_DEPLOYED, "device": None}
        return [_with_probe(runner_row(n, c, probes[n]["entry"] if n in probes else
                                       not_deployed if c.get("enabled", True) else disabled),
                            probes.get(n)) for n, c in services.items()]
    probes = await fresh_probes.fresh_round(kind, COMPILER_SERVICES)
    disabled = {"available": False, "reason": "disabled"}
    not_deployed = {"available": False, "reason": NOT_DEPLOYED}
    return [_with_probe(compiler_row(c, svc, probes[c]["entry"] if c in probes else
                                     not_deployed if svc.get("enabled", True) else disabled),
                        probes.get(c)) for c, svc in COMPILER_SERVICES.items()]


async def compiler_rows() -> list:
    """Every registered compile-only service, in registry order."""
    availability = await runner_availability(services=COMPILER_SERVICES)
    disabled = {"available": False, "reason": "disabled"}
    return [compiler_row(cid, svc, availability.get(cid) or disabled)
            for cid, svc in COMPILER_SERVICES.items()]
