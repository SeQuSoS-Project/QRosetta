"""Runner dispatch: job fan-out, per-runner payloads and seeds, and result annotation.

Routes each dispatch to the HTTP (Docker Compose) or Kubernetes Jobs backend.
"""

from datetime import datetime, timezone

from config import settings
from qrosetta_commons.helpers import TIMING_STATISTIC, get_logger
from qrosetta_commons.seeds import derive_runner_seed
from services.dispatcher_http import dispatch_http_local
from services.dispatcher_k8s import dispatch_kubernetes_jobs

EXECUTION_MODE = settings.EXECUTION_MODE
logger = get_logger("rosetta-api")

RUNNER_SERVICES = settings.get_runner_services()

SEED_DERIVATION = (
    "runner_seed = first 4 bytes of sha256(f'{master_seed}:{runner_key}') read big-endian, "
    "top bit cleared (0 <= runner_seed < 2**31); runner_key is the result's simulator key, "
    "including ~opt<L>~run<N> suffixes"
)

DISPATCH_STATUSES = ("ok", "error", "timeout", "offline")

TIMEOUT_SCOPE = {
    "local": (
        "whole isolated runner child process: process spawn, SDK import, warm-up run and every "
        "timed run (timing_repeats), killed at hard_timeout_seconds. The budget starts when the run leaves the "
        "runner's queue (one run per runner at a time), so time spent queued does not count "
        "against it. The queue wait has its own server-wide cap, RUNNER_QUEUE_MAX_WAIT_SEC "
        "(recorded as queue_max_wait_sec), independent of timeout_seconds; a run still queued "
        "at that cap is reported as never_started. Each result reports queue_wait_sec. The "
        "API waits queue cap + timeout + RUNNER_DEADLINE_BUFFER_SEC"
    ),
    "kubernetes": (
        "whole Kubernetes Job measured from job creation: pod scheduling, image pull, container "
        "start, SDK import, warm-up run, every timed run (timing_repeats) and S3 upload"
    ),
}

_ORCHESTRATION_FIELDS = ("runner_config", "runner_phases")

_RUNNER_TIMEOUT_PREFIX = "TIMEOUT ("


def utc_now_iso() -> str:
    """Current UTC time as ISO 8601 with millisecond precision."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def timeout_scope() -> str:
    """What the per-runner timeout covers in the current execution mode."""
    return TIMEOUT_SCOPE.get(EXECUTION_MODE, TIMEOUT_SCOPE["local"])


def queue_wait_budget() -> float:
    """Seconds a run may wait for a runner's execution slot (RUNNER_QUEUE_MAX_WAIT_SEC),
    independent of the run's own timeout."""
    return float(settings.RUNNER_QUEUE_MAX_WAIT_SEC)


def runner_seed_for(master_seed, runner_key: str):
    """Seed passed to ``runner_key`` for ``master_seed``; None when there is no master seed."""
    if master_seed is None:
        return None
    return derive_runner_seed(int(master_seed), runner_key)


def build_runner_payload(runner_payload: dict, spec: dict) -> dict:
    """Payload sent to one runner job: orchestration fields removed, the job's effective
    optimization level set, and the master seed replaced by the job's derived seed.

    runner_config/runner_phases are dropped because a multi-run runner_config holds lists
    that the runner's ``Dict[str, int]`` schema rejects.
    """
    payload = {k: v for k, v in runner_payload.items() if k not in _ORCHESTRATION_FIELDS}
    payload["optimization_level"] = spec["opt_level"]
    if payload.get("seed") is not None:
        payload["seed"] = runner_seed_for(payload["seed"], spec["key"])
    return payload


def classify_runner_result(result: dict) -> str:
    """Dispatch status of a result the runner itself returned: ok, timeout or error."""
    if not isinstance(result, dict) or not result.get("error"):
        return "ok"
    if result.get("timed_out") or str(result["error"]).startswith(_RUNNER_TIMEOUT_PREFIX):
        return "timeout"
    return "error"


def annotate_result(result: dict, spec: dict, sent_payload: dict, dispatched_at: str,
                    dispatch_status: str = None, runner_image: str = None) -> dict:
    """Stamp one runner result with its key, dispatch outcome, seed and timing metadata.

    Fields: simulator, optimization_level (applied), optimization_level_requested,
    dispatch_status, timeout_kind (``"queue"`` for a run that never left the runner's
    queue, ``"run"`` otherwise; only on timeouts), dispatched_at, completed_at,
    timing_samples, timing_statistic, runner_image, and for seeded runs runner_seed, seed,
    seed_honoured. ``seed_honoured`` is None for a failed run, which sampled nothing.
    """
    result["simulator"] = spec["key"]
    result["optimization_level"] = spec["opt_level"]
    result["optimization_level_requested"] = spec.get("requested_level", spec["opt_level"])
    result["dispatch_status"] = dispatch_status or classify_runner_result(result)
    if result["dispatch_status"] == "timeout":
        result["timeout_kind"] = "queue" if result.get("never_started") else "run"
    result["dispatched_at"] = dispatched_at
    result["completed_at"] = utc_now_iso()
    result["timing_samples"] = int(result.get("timing_repeats") or 1)
    result.setdefault("timing_statistic", TIMING_STATISTIC)
    result["runner_image"] = runner_image or "not recorded"
    seed = sent_payload.get("seed")
    if seed is not None:
        result["runner_seed"] = seed
        result["seed"] = seed
        result["seed_honoured"] = (
            None if result.get("error")
            else RUNNER_SERVICES.get(spec["sim_name"], {}).get("honours_seed"))
    return result


def _clamp_opt(sim_name: str, level: int) -> int:
    """Clamp an optimization level to [0, the max the runner supports]."""
    level = max(0, level)
    opt_levels = RUNNER_SERVICES.get(sim_name, {}).get("optimization_levels", {})
    if opt_levels:
        return min(level, max(opt_levels.keys()))
    return level


def expand_runner_jobs(runner_urls: dict, runner_payload: dict) -> list:
    """Flatten runner_urls into one job spec per run.

    runner_config[sim] is an int (one run) or a list of opt levels (one job per element,
    repeats allowed; an empty list skips the runner). A runner with one job keeps its
    canonical id as the key; N>1 jobs get keys ``sim~opt{L}~run{i}``.

    Each spec: {key, sim_name, url, opt_level (clamped to the runner's max),
    requested_level, phase}.
    """
    global_opt = runner_payload.get("optimization_level", 0)
    runner_overrides = runner_payload.get("runner_config", {})
    runner_phases = runner_payload.get("runner_phases", {})

    specs = []
    for sim_name, url in runner_urls.items():
        phase = runner_phases.get(sim_name, 1)
        cfg = runner_overrides.get(sim_name, global_opt)
        requested = [int(lvl) for lvl in (list(cfg) if isinstance(cfg, list) else [cfg])]

        if not requested:
            continue

        if len(requested) == 1:
            specs.append({"key": sim_name, "sim_name": sim_name, "url": url,
                          "opt_level": _clamp_opt(sim_name, requested[0]),
                          "requested_level": requested[0], "phase": phase})
            continue

        per_level_idx = {}
        for req in requested:
            lvl = _clamp_opt(sim_name, req)
            per_level_idx[lvl] = per_level_idx.get(lvl, 0) + 1
            key = f"{sim_name}~opt{lvl}~run{per_level_idx[lvl]}"
            specs.append({"key": key, "sim_name": sim_name, "url": url,
                          "opt_level": lvl, "requested_level": req, "phase": phase})

    return specs


def group_specs_by_phase(specs: list) -> list:
    """Group job specs into phase waves in ascending order; each wave runs concurrently."""
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
    """Run every job for ``runner_urls`` and return the annotated results."""
    if EXECUTION_MODE == "kubernetes":
        return await dispatch_kubernetes_jobs(runner_urls, runner_payload, timeout_seconds, runner_statuses)
    return await dispatch_http_local(runner_urls, runner_payload, timeout_seconds, runner_statuses)
