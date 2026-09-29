"""Background job lifecycle: single-circuit runs, batch suites, and their stored reports.

``ACTIVE_JOBS[job_id]`` holds ``results`` (the copy served to the browser, with oversized
statevectors replaced by a placeholder) and ``full_results`` (the untruncated report,
served by ``GET /jobs/{job_id}/report`` and exported by ``POST /jobs/{job_id}/export``).
Both are evicted together after the job TTL in ``main.py``.
"""

import asyncio
import random
import time
from services.validator import validate_request
from services.dispatcher import (
    STATEVECTOR_RUNNER_URLS,
    NATIVE_SAMPLING_URLS,
    SAMPLED_SV_URLS,
    SEED_DERIVATION,
    EXECUTION_MODE,
    dispatch_to_runners,
    timeout_scope,
    utc_now_iso,
)
from schemas import BatchPayload
from config import settings, server_git_sha, server_image_digests, runner_registry_snapshot
from services.aggregator import compile_comparison_reports, compile_measurement_reports
from qrosetta_commons.helpers import get_logger
from services.circuit_resolver import (
    resolve_circuit_qasm,
    prepare_measured_dispatch,
    prepare_statevector_dispatch,
)

logger = get_logger("rosetta-job-manager")

ACTIVE_JOBS = {}

SEED_MAX = 2**31 - 1

_MAX_DISPLAY_STATEVECTOR_AMPLITUDES = 16384
_MAX_DISPLAY_STATEVECTOR_B64_CHARS = _MAX_DISPLAY_STATEVECTOR_AMPLITUDES * 16 * 4 // 3
_STATEVECTOR_PLACEHOLDER = (
    "<Statevector too large for display. The full vector is kept on the server with this job "
    "and returned by GET /jobs/{job_id}/report and POST /jobs/{job_id}/export "
    "(include_statevectors=true) until the job expires; it is not in this copy.>"
)


def _resolve_seed(seed):
    """The caller's seed, or a generated one when it is None."""
    return seed if seed is not None else random.randint(0, SEED_MAX)


def _display_result(result):
    """Copy of a runner result for the browser: a statevector over
    ``_MAX_DISPLAY_STATEVECTOR_AMPLITUDES`` amplitudes (Base64 or list form) is replaced by
    ``_STATEVECTOR_PLACEHOLDER`` and ``statevector_omitted_for_display`` is set."""
    if not isinstance(result, dict):
        return result
    sv = result.get("statevector")
    too_large = (
        (isinstance(sv, str) and len(sv) > _MAX_DISPLAY_STATEVECTOR_B64_CHARS)
        or (isinstance(sv, list) and len(sv) > _MAX_DISPLAY_STATEVECTOR_AMPLITUDES)
    )
    if too_large:
        return {**result, "statevector": _STATEVECTOR_PLACEHOLDER,
                "statevector_omitted_for_display": True}
    return result


def display_report(report: dict) -> dict:
    """Browser copy of a single-circuit or batch report (see ``_display_result``)."""
    if not isinstance(report, dict):
        return report
    out = dict(report)
    if isinstance(report.get("raw_results"), list):
        out["raw_results"] = [_display_result(r) for r in report["raw_results"]]
    if isinstance(report.get("benchmark_summary"), list):
        out["benchmark_summary"] = [display_report(t) for t in report["benchmark_summary"]]
    return out


def _run_context(optimization_level, runner_config, timeout_seconds, apply_preprocessing,
                 thresholds, runner_phases) -> dict:
    """Run-time configuration recorded at the top level of every report."""
    return {
        "execution_mode": EXECUTION_MODE,
        "platform_version": settings.PLATFORM_VERSION,
        "git_sha": server_git_sha(),
        "image_digests": server_image_digests() or "not recorded (QROSETTA_IMAGE_DIGESTS unset)",
        "apply_preprocessing": apply_preprocessing,
        "optimization_level": optimization_level,
        "runner_config": runner_config or {},
        "runner_phases": runner_phases or {},
        "timeout_seconds": timeout_seconds,
        "timeout_scope": timeout_scope(),
        "agreement_thresholds": thresholds,
        "runner_registry": runner_registry_snapshot(),
    }


def _apply_api_preprocessing(results: list, group: str, circuit: dict) -> None:
    """Prepend the API-side transforms to each result's ``preprocessing_applied`` and
    record which dispatched circuit it received."""
    for result in results:
        if not isinstance(result, dict):
            continue
        result["dispatch_group"] = group
        notes = circuit["api_preprocessing_applied"]
        if notes:
            result["preprocessing_applied"] = list(notes) + list(result.get("preprocessing_applied") or [])


def _dispatched_circuit_record(group: str, circuit: dict, results: list) -> dict:
    return {
        "group": group,
        "qasm": circuit["qasm"],
        "api_preprocessing_applied": list(circuit["api_preprocessing_applied"]),
        "runners": [r.get("simulator") for r in results if isinstance(r, dict)],
    }


async def run_single_circuit_comparison(qasm_string: str, optimization_level: int = 0, runner_config: dict = None, timeout_seconds: int = 60, target_simulators: list = None, runner_statuses: dict = None, runner_phases: dict = None, apply_preprocessing: bool = True, thresholds: dict = None):
    """Run one circuit on the statevector fleet and return the full (untruncated) report."""
    started_at = utc_now_iso()
    context = _run_context(optimization_level, runner_config, timeout_seconds,
                           apply_preprocessing, thresholds, runner_phases)
    try:
        circuit = prepare_statevector_dispatch(qasm_string, apply_preprocessing)
    except Exception as e:
        return {"input_qasm": qasm_string, "error": str(e), **context}

    runner_payload = {
        "circuit_data": circuit["qasm"],
        "optimization_level": optimization_level,
        "runner_config": runner_config or {},
        "runner_phases": runner_phases or {},
        "apply_preprocessing": apply_preprocessing,
    }

    if target_simulators:
        filtered_urls = {k: v for k, v in STATEVECTOR_RUNNER_URLS.items() if k in target_simulators}
    else:
        filtered_urls = STATEVECTOR_RUNNER_URLS

    aggregated_results = await dispatch_to_runners(
        runner_urls=filtered_urls,
        runner_payload=runner_payload,
        timeout_seconds=timeout_seconds,
        runner_statuses=runner_statuses,
    )
    _apply_api_preprocessing(aggregated_results, "statevector", circuit)

    try:
        divergence_report, performance_report, resource_report = await compile_comparison_reports(aggregated_results, thresholds)
    except Exception as e:
        logger.warning(f"Analysis failed (returning raw results only): {e}")
        divergence_report = {"error": f"Analysis failed: {e}"}
        performance_report = {}
        resource_report = {}

    return {
        "input_qasm": qasm_string,
        **context,
        "api_preprocessing_applied": list(circuit["api_preprocessing_applied"]),
        "dispatched_circuits": [_dispatched_circuit_record("statevector", circuit, aggregated_results)],
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "divergence_report": divergence_report,
        "performance_report": performance_report,
        "resource_report": resource_report,
        "raw_results": aggregated_results,
    }


async def run_single_circuit_measurement(qasm_string: str, n_shots: int, optimization_level: int = 0, runner_config: dict = None, timeout_seconds: int = 60, target_simulators: list = None, runner_statuses: dict = None, runner_phases: dict = None, apply_preprocessing: bool = True, seed: int = None, thresholds: dict = None):
    """Run one circuit on the sampling fleet and return the full report.

    ``seed`` is the master seed (generated when None); each runner receives a seed
    derived from it and its result key.
    """
    started_at = utc_now_iso()
    seed = _resolve_seed(seed)
    logger.info(f"Processing measured circuit for {n_shots} shots (seed={seed})...")
    context = _run_context(optimization_level, runner_config, timeout_seconds,
                           apply_preprocessing, thresholds, runner_phases)
    seed_fields = {"n_shots": n_shots, "seed": seed, "seed_derivation": SEED_DERIVATION}

    try:
        circuits = prepare_measured_dispatch(qasm_string, apply_preprocessing)
    except Exception as e:
        return {"input_qasm": qasm_string, **seed_fields, **context, "error": str(e)}

    def payload_for(group):
        return {
            "circuit_data": circuits[group]["qasm"],
            "n_shots": n_shots,
            "optimization_level": optimization_level,
            "runner_config": runner_config or {},
            "runner_phases": runner_phases or {},
            "apply_preprocessing": apply_preprocessing,
            "seed": seed,
        }

    if target_simulators:
        filtered_sampled = {k: v for k, v in SAMPLED_SV_URLS.items() if k in target_simulators}
        filtered_native = {k: v for k, v in NATIVE_SAMPLING_URLS.items() if k in target_simulators}
    else:
        filtered_sampled = SAMPLED_SV_URLS
        filtered_native = NATIVE_SAMPLING_URLS

    results_sampled, results_native = await asyncio.gather(
        dispatch_to_runners(filtered_sampled, payload_for("measured_sampled"), timeout_seconds, runner_statuses),
        dispatch_to_runners(filtered_native, payload_for("measured_native"), timeout_seconds, runner_statuses),
    )
    _apply_api_preprocessing(results_sampled, "measured_sampled", circuits["measured_sampled"])
    _apply_api_preprocessing(results_native, "measured_native", circuits["measured_native"])
    aggregated_results = results_native + results_sampled

    api_notes = []
    for group in ("measured_native", "measured_sampled"):
        api_notes += [f"{note} [{group} runners]" for note in circuits[group]["api_preprocessing_applied"]]

    report = {
        "input_qasm": qasm_string,
        **seed_fields,
        **context,
        "api_preprocessing_applied": api_notes,
        "dispatched_circuits": [
            _dispatched_circuit_record("measured_native", circuits["measured_native"], results_native),
            _dispatched_circuit_record("measured_sampled", circuits["measured_sampled"], results_sampled),
        ],
        "started_at": started_at,
    }

    try:
        divergence_report, performance_report, resource_report = await compile_measurement_reports(aggregated_results, n_shots, thresholds)
    except Exception as e:
        report.update({"finished_at": utc_now_iso(), "error": f"Error during comparison: {str(e)}",
                       "raw_results": aggregated_results})
        return report

    report.update({
        "finished_at": utc_now_iso(),
        "divergence_report": divergence_report,
        "performance_report": performance_report,
        "resource_report": resource_report,
        "raw_results": aggregated_results,
    })
    return report


def _completed_job(target: str, full_report: dict, runner_statuses: dict, **extra) -> dict:
    return {"status": "completed", "target": target, "results": display_report(full_report),
            "full_results": full_report, "runner_statuses": runner_statuses,
            "finished_at": time.time(), **extra}


async def _run_single_job(job_id: str, execution_target: str, runner_statuses: dict, run_coro):
    """Await ``run_coro`` (a run_single_* coroutine) and record the terminal state."""
    ACTIVE_JOBS[job_id]["status"] = "processing"
    ACTIVE_JOBS[job_id]["runner_statuses"] = runner_statuses
    try:
        report = await run_coro
        ACTIVE_JOBS[job_id] = _completed_job(execution_target, report, runner_statuses)
    except Exception as e:
        ACTIVE_JOBS[job_id] = {"status": "failed", "target": execution_target, "error": str(e), "runner_statuses": runner_statuses, "finished_at": time.time()}


async def worker_compare(job_id: str, qasm_string: str, optimization_level: int, runner_config: dict, timeout: int, target_simulators: list, execution_target: str, runner_phases: dict = None, apply_preprocessing: bool = True, thresholds: dict = None):
    """Background task for POST /compare."""
    runner_statuses = {}
    await _run_single_job(job_id, execution_target, runner_statuses,
        run_single_circuit_comparison(qasm_string, optimization_level, runner_config, timeout, target_simulators, runner_statuses, runner_phases, apply_preprocessing, thresholds))


async def worker_compare_measured(job_id: str, qasm_string: str, n_shots: int, optimization_level: int, runner_config: dict, timeout: int, target_simulators: list, execution_target: str, runner_phases: dict = None, apply_preprocessing: bool = True, seed: int = None, thresholds: dict = None):
    """Background task for POST /compare_measured."""
    runner_statuses = {}
    await _run_single_job(job_id, execution_target, runner_statuses,
        run_single_circuit_measurement(qasm_string, n_shots, optimization_level, runner_config, timeout, target_simulators, runner_statuses, runner_phases, apply_preprocessing, seed, thresholds))


async def run_batch_tasks(payload: BatchPayload, runner_statuses: dict, progress: dict = None,
                          batch_seed: int = None, task_offset: int = 0) -> tuple:
    """Run every task in a BatchPayload sequentially; return (benchmark_summary, batch_seed).

    Shared by ``worker_batch_suite`` and ``services.experiment.worker_experiment``. Each
    entry of ``benchmark_summary`` is a full, untruncated report.

    * ``progress`` — when supplied, mutated per task ({total, completed, current_index,
      tasks:[{name,status}]}); ``task_offset`` indexes into a progress list shared by
      several calls.
    * ``batch_seed`` — master seed for every task; resolved here when None.
    """
    benchmark_summary = []
    batch_thresholds = payload.thresholds.model_dump() if payload.thresholds else None
    if batch_seed is None:
        batch_seed = _resolve_seed(payload.seed)

    for idx, task in enumerate(payload.tasks):
        gi = task_offset + idx
        task_name = f"{task.algorithm} ({task.qubits}q)"
        logger.info(f"--- Running task: {task_name} ---")
        if progress is not None:
            progress["current_index"] = gi
            progress["tasks"][gi]["status"] = "running"
        try:
            qasm_string = resolve_circuit_qasm(
                task.source, task.algorithm, task.qubits, task.qasm_string, mode=payload.mode
            )

            validate_request(qasm_string, mode=payload.mode, bypass_limits=payload.bypass_limits)
            timeout = max(1, min(payload.timeout_seconds, settings.RUNNER_TIMEOUT_SEC))
            if payload.mode == 'statevector':
                report = await run_single_circuit_comparison(qasm_string, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, runner_statuses, payload.runner_phases, payload.apply_preprocessing, batch_thresholds)
            elif payload.mode == 'measured':
                report = await run_single_circuit_measurement(qasm_string, payload.n_shots, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, runner_statuses, payload.runner_phases, payload.apply_preprocessing, batch_seed, batch_thresholds)
            else:
                raise ValueError(f"Unknown mode: {payload.mode}")

            report["task_name"] = task_name
            benchmark_summary.append(report)
            if progress is not None:
                progress["tasks"][gi]["status"] = "done"

        except Exception as e:
            benchmark_summary.append({
                "task_name": task_name,
                "error": f"Failed to process task: {str(e)}"
            })
            if progress is not None:
                progress["tasks"][gi]["status"] = "error"

        if progress is not None:
            progress["completed"] += 1

    return benchmark_summary, batch_seed


async def worker_batch_suite(job_id: str, payload: BatchPayload):
    """Background task for POST /run_batch_suite, with live per-task progress."""
    runner_statuses = {}
    ACTIVE_JOBS[job_id]["status"] = "processing"
    ACTIVE_JOBS[job_id]["runner_statuses"] = runner_statuses
    logger.info(f"--- Starting Batch Suite ({payload.mode}) with {len(payload.tasks)} tasks ---")

    progress = {
        "total": len(payload.tasks),
        "completed": 0,
        "current_index": None,
        "tasks": [{"name": f"{t.algorithm} ({t.qubits}q)", "status": "queued"}
                  for t in payload.tasks],
    }
    ACTIVE_JOBS[job_id]["progress"] = progress

    started_at = utc_now_iso()
    benchmark_summary, batch_seed = await run_batch_tasks(payload, runner_statuses, progress)

    progress["current_index"] = None
    logger.info("--- Batch Suite Complete ---")
    full_report = {
        "mode": payload.mode,
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "benchmark_summary": benchmark_summary,
    }
    if payload.mode == "measured":
        full_report["seed"] = batch_seed
        full_report["seed_derivation"] = SEED_DERIVATION
    ACTIVE_JOBS[job_id] = _completed_job(payload.execution_target, full_report, runner_statuses,
                                         progress=progress)
