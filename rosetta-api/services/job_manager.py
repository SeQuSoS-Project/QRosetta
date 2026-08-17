# Manages quantum job lifecycle and status.

import asyncio
import random
import time
import pytket.qasm
from pytket.passes import RemoveBarriers
from services.validator import validate_request
from services.storage import save_report_to_disk
from services.dispatcher import (
    STATEVECTOR_RUNNER_URLS,
    NATIVE_SAMPLING_URLS,
    SAMPLED_SV_URLS,
    dispatch_to_runners
)
from schemas import BatchPayload
from config import settings
from services.aggregator import compile_comparison_reports, compile_measurement_reports
from qrosetta_commons.helpers import get_logger
from services.circuit_resolver import resolve_circuit_qasm

logger = get_logger("rosetta-job-manager")

ACTIVE_JOBS = {}

# A measured run always carries a seed: if the caller supplies none, one is generated and
# recorded in the report/provenance. Statevector mode is exact and needs none.
SEED_MAX = 2**31 - 1


def _resolve_seed(seed):
    return seed if seed is not None else random.randint(0, SEED_MAX)


def _attach_request_seed(results: list, seed: int = None) -> list:
    """Attach the measured request seed to every runner result for provenance."""
    for result in results:
        if isinstance(result, dict):
            result.setdefault("seed", seed)
    return results


# Statevectors above this amplitude count are dropped from the copy returned to the browser:
# a 2**14-amplitude vector is already ~350 KB of Base64, and the client never renders raw
# amplitudes (the analysis is computed server-side). The full vectors are kept in the
# on-disk report and the export path.
_MAX_DISPLAY_STATEVECTOR_AMPLITUDES = 16384  # 2**14
_MAX_DISPLAY_STATEVECTOR_B64_CHARS = _MAX_DISPLAY_STATEVECTOR_AMPLITUDES * 16 * 4 // 3
_STATEVECTOR_PLACEHOLDER = "<Statevector too large for display. Analysis included in reports; full data in the exported report.>"


def _display_result(result):
    """Return a copy of a runner result safe to send to the browser, replacing an
    oversized statevector with a placeholder. Handles the Base64-string wire format and
    the legacy list format; leaves error/counts results untouched."""
    if not isinstance(result, dict):
        return result
    sv = result.get("statevector")
    too_large = (
        (isinstance(sv, str) and len(sv) > _MAX_DISPLAY_STATEVECTOR_B64_CHARS)
        or (isinstance(sv, list) and len(sv) > _MAX_DISPLAY_STATEVECTOR_AMPLITUDES)
    )
    if too_large:
        return {**result, "statevector": _STATEVECTOR_PLACEHOLDER}
    return result

async def run_single_circuit_comparison(qasm_string: str, optimization_level: int = 0, runner_config: dict = None, timeout_seconds: int = 60, target_simulators: list = None, runner_statuses: dict = None, runner_phases: dict = None, apply_preprocessing: bool = True, thresholds: dict = None):
    logger.info("Processing circuit...")
    try:
        if apply_preprocessing:
            tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
            logger.info(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")
            RemoveBarriers().apply(tk_circ)
            modified_qasm_string = pytket.qasm.circuit_to_qasm_str(tk_circ)
        else:
            modified_qasm_string = qasm_string
            
        runner_payload = {
            "circuit_data": modified_qasm_string,
            "optimization_level": optimization_level,
            "runner_config": runner_config or {},
            "runner_phases": runner_phases or {},
            "apply_preprocessing": apply_preprocessing,
        }
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

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

    try:
        divergence_report, performance_report, resource_report = await compile_comparison_reports(aggregated_results, thresholds)
    except Exception as e:
        logger.warning(f"Analysis failed (returning raw results only): {e}")
        divergence_report = {"error": f"Analysis failed: {e}"}
        performance_report = {}
        resource_report = {}

    full_report_data = [res.copy() for res in aggregated_results]
    # Offload the (potentially large, statevector-carrying) disk write so it does not block
    # the event loop while the client is polling for status.
    await asyncio.to_thread(save_report_to_disk, full_report_data)

    display_results = [_display_result(result) for result in aggregated_results]

    return {
        "input_qasm": qasm_string,
        "divergence_report": divergence_report,
        "performance_report": performance_report,
        "resource_report": resource_report,
        "raw_results": display_results
    }

async def run_single_circuit_measurement(qasm_string: str, n_shots: int, optimization_level: int = 0, runner_config: dict = None, timeout_seconds: int = 60, target_simulators: list = None, runner_statuses: dict = None, runner_phases: dict = None, apply_preprocessing: bool = True, seed: int = None, thresholds: dict = None):
    seed = _resolve_seed(seed)  # never None — generated-and-recorded if the caller omitted it
    logger.info(f"Processing measured circuit for {n_shots} shots (seed={seed})...")

    sampled_payload = {
        "circuit_data": qasm_string,
        "n_shots": n_shots,
        "optimization_level": optimization_level,
        "runner_config": runner_config or {},
        "runner_phases": runner_phases or {},
        "apply_preprocessing": apply_preprocessing,
        "seed": seed,
    }

    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        if apply_preprocessing:
            RemoveBarriers().apply(tk_circ)
        n_qubits = tk_circ.n_qubits
        c_reg_name = "c"
        if c_reg_name not in [reg.name for reg in tk_circ.c_registers]:
            tk_circ.add_c_register(c_reg_name, n_qubits)

        all_qubits = tk_circ.qubits
        c_register = tk_circ.get_c_register(c_reg_name)

        for i in range(n_qubits):
            tk_circ.Measure(all_qubits[i], c_register[i])

        modified_qasm_string = pytket.qasm.circuit_to_qasm_str(tk_circ)
        native_payload = {
            "circuit_data": modified_qasm_string,
            "n_shots": n_shots,
            "optimization_level": optimization_level,
            "runner_config": runner_config or {},
            "runner_phases": runner_phases or {},
            "apply_preprocessing": apply_preprocessing,
            "seed": seed,
        }
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    if target_simulators:
        filtered_sampled = {k: v for k, v in SAMPLED_SV_URLS.items() if k in target_simulators}
        filtered_native = {k: v for k, v in NATIVE_SAMPLING_URLS.items() if k in target_simulators}
    else:
        filtered_sampled = SAMPLED_SV_URLS
        filtered_native = NATIVE_SAMPLING_URLS

    sampled_task = dispatch_to_runners(filtered_sampled, sampled_payload, timeout_seconds, runner_statuses)
    native_task = dispatch_to_runners(filtered_native, native_payload, timeout_seconds, runner_statuses)

    results_sampled, results_native = await asyncio.gather(sampled_task, native_task)

    aggregated_results = _attach_request_seed(results_native + results_sampled, seed)

    await asyncio.to_thread(save_report_to_disk, aggregated_results)

    try:
        divergence_report, performance_report, resource_report = await compile_measurement_reports(aggregated_results, n_shots, thresholds)

    except Exception as e:
        return {
            "input_qasm": qasm_string,
            "n_shots": n_shots,
            "seed": seed,
            "error": f"Error during comparison: {str(e)}",
            "raw_results": aggregated_results
        }

    return {
        "input_qasm": qasm_string,
        "modified_qasm_for_native_runners": modified_qasm_string,
        "n_shots": n_shots,
        "seed": seed,
        "divergence_report": divergence_report,
        "performance_report": performance_report,
        "resource_report": resource_report,
        "raw_results": aggregated_results
    }

async def _run_single_job(job_id: str, execution_target: str, runner_statuses: dict, run_coro):
    """Drive one single-circuit job: mark it processing, await ``run_coro`` (the
    already-built run_single_* coroutine), and record the terminal state in ACTIVE_JOBS."""
    ACTIVE_JOBS[job_id]["status"] = "processing"
    ACTIVE_JOBS[job_id]["runner_statuses"] = runner_statuses
    try:
        report = await run_coro
        ACTIVE_JOBS[job_id] = {"status": "completed", "target": execution_target, "results": report, "runner_statuses": runner_statuses, "finished_at": time.time()}
    except Exception as e:
        ACTIVE_JOBS[job_id] = {"status": "failed", "target": execution_target, "error": str(e), "runner_statuses": runner_statuses, "finished_at": time.time()}

async def worker_compare(job_id: str, qasm_string: str, optimization_level: int, runner_config: dict, timeout: int, target_simulators: list, execution_target: str, runner_phases: dict = None, apply_preprocessing: bool = True, thresholds: dict = None):
    runner_statuses = {}
    await _run_single_job(job_id, execution_target, runner_statuses,
        run_single_circuit_comparison(qasm_string, optimization_level, runner_config, timeout, target_simulators, runner_statuses, runner_phases, apply_preprocessing, thresholds))

async def worker_compare_measured(job_id: str, qasm_string: str, n_shots: int, optimization_level: int, runner_config: dict, timeout: int, target_simulators: list, execution_target: str, runner_phases: dict = None, apply_preprocessing: bool = True, seed: int = None, thresholds: dict = None):
    runner_statuses = {}
    await _run_single_job(job_id, execution_target, runner_statuses,
        run_single_circuit_measurement(qasm_string, n_shots, optimization_level, runner_config, timeout, target_simulators, runner_statuses, runner_phases, apply_preprocessing, seed, thresholds))

async def run_batch_tasks(payload: BatchPayload, runner_statuses: dict, progress: dict = None,
                          batch_seed: int = None, task_offset: int = 0) -> tuple:
    """Run every task in a BatchPayload sequentially and return (benchmark_summary, batch_seed).

    The reusable core shared by ``worker_batch_suite`` and the experiment runner
    (``services.experiment.worker_experiment``). Behavior is identical to the previous
    inline loop; it is only factored out so multiple axes can reuse it.

    * ``progress`` — when supplied, the live dict in ACTIVE_JOBS is mutated per task
      ({total, completed, current_index, tasks:[{name,status}]}). ``task_offset`` lets a
      caller running several batches into one cumulative progress index the right slot.
    * ``batch_seed`` — one seed shared across every task (and, for the experiment runner,
      across every axis); resolved here when None so a run is never left un-seeded.
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
            report = None
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
    runner_statuses = {}
    ACTIVE_JOBS[job_id]["status"] = "processing"
    ACTIVE_JOBS[job_id]["runner_statuses"] = runner_statuses
    logger.info(f"--- Starting Batch Suite ({payload.mode}) with {len(payload.tasks)} tasks ---")

    # Live progress so the UI can show which circuit is running / done without waiting for
    # the whole suite. Mutated in place; ACTIVE_JOBS holds the reference the poller reads.
    progress = {
        "total": len(payload.tasks),
        "completed": 0,
        "current_index": None,
        "tasks": [{"name": f"{t.algorithm} ({t.qubits}q)", "status": "queued"}
                  for t in payload.tasks],
    }
    ACTIVE_JOBS[job_id]["progress"] = progress

    benchmark_summary, _ = await run_batch_tasks(payload, runner_statuses, progress)

    progress["current_index"] = None
    logger.info("--- Batch Suite Complete ---")
    ACTIVE_JOBS[job_id] = {"status": "completed", "target": payload.execution_target, "results": {"benchmark_summary": benchmark_summary}, "runner_statuses": runner_statuses, "progress": progress, "finished_at": time.time()}
