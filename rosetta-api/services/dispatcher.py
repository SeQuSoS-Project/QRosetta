# Dispatches jobs to external quantum runners.

import os
from config import settings
from qrosetta_commons.helpers import get_logger
from services.dispatcher_http import dispatch_http_local
from services.dispatcher_k8s import dispatch_kubernetes_jobs

EXECUTION_MODE = os.environ.get("EXECUTION_MODE", "local")
logger = get_logger("rosetta-api")

RUNNER_SERVICES = settings.get_runner_services()


# Dispatcher-only fields used to fan out / order jobs. Runners never read them, and
# runner_config may hold lists in multi-run mode that the runner's Dict[str, int]
# schema rejects with 422 — so strip both from the payload sent to each runner.
_ORCHESTRATION_FIELDS = ("runner_config", "runner_phases")


def build_runner_payload(runner_payload: dict, opt_level: int) -> dict:
    payload = {k: v for k, v in runner_payload.items() if k not in _ORCHESTRATION_FIELDS}
    payload["optimization_level"] = opt_level
    return payload


def _clamp_opt(sim_name: str, level: int) -> int:
    """Clamp an optimization level to the max the runner actually supports."""
    opt_levels = RUNNER_SERVICES.get(sim_name, {}).get("optimization_levels", {})
    if opt_levels:
        return min(level, max(opt_levels.keys()))
    return level


def expand_runner_jobs(runner_urls: dict, runner_payload: dict) -> list:
    """Flatten runner_urls into one job spec per actual run.

    runner_config[sim] may be an int (single run, default mode) or a list of opt
    levels (self-comparison: one job per element, repeats allowed). A runner that
    yields exactly one job keeps its canonical id as the key (no behavior change).
    A runner yielding N>1 jobs gets virtual keys 'sim~opt{L}~run{i}' so each instance
    flows through aggregation/storage/frontend as a distinct entry.

    Each spec: {key, sim_name, url, opt_level, phase}.
    """
    global_opt = runner_payload.get("optimization_level", 0)
    runner_overrides = runner_payload.get("runner_config", {})
    runner_phases = runner_payload.get("runner_phases", {})

    specs = []
    for sim_name, url in runner_urls.items():
        phase = runner_phases.get(sim_name, 1)
        cfg = runner_overrides.get(sim_name, global_opt)
        levels = list(cfg) if isinstance(cfg, list) else [cfg]
        levels = [_clamp_opt(sim_name, int(lvl)) for lvl in levels]

        if not levels:
            # Explicit empty list = "do not run this runner".
            continue

        if len(levels) == 1:
            specs.append({"key": sim_name, "sim_name": sim_name, "url": url,
                          "opt_level": levels[0], "phase": phase})
            continue

        per_level_idx = {}
        for lvl in levels:
            per_level_idx[lvl] = per_level_idx.get(lvl, 0) + 1
            key = f"{sim_name}~opt{lvl}~run{per_level_idx[lvl]}"
            specs.append({"key": key, "sim_name": sim_name, "url": url,
                          "opt_level": lvl, "phase": phase})

    return specs


def group_specs_by_phase(specs: list) -> list:
    """Group job specs into phase waves, ordered ascending. Each wave runs
    concurrently; the dispatcher awaits a wave before starting the next."""
    by_phase = {}
    for spec in specs:
        by_phase.setdefault(spec["phase"], []).append(spec)
    return [by_phase[p] for p in sorted(by_phase.keys())]

STATEVECTOR_RUNNER_URLS = {
    name: f"{config['base_url']}/run" for name, config in RUNNER_SERVICES.items()
    if "statevector" in config["capabilities"] and config.get("enabled", True)
}
NATIVE_SAMPLING_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_native" in config["capabilities"] and config.get("enabled", True)
}
SAMPLED_SV_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_sampled" in config["capabilities"] and config.get("enabled", True)
}

async def dispatch_to_runners(runner_urls: dict, runner_payload: dict, timeout_seconds: int = settings.RUNNER_TIMEOUT_SEC, runner_statuses: dict = None) -> list:
    if EXECUTION_MODE == "kubernetes":
        return await dispatch_kubernetes_jobs(runner_urls, runner_payload, timeout_seconds, runner_statuses)
    return await dispatch_http_local(runner_urls, runner_payload, timeout_seconds, runner_statuses)
