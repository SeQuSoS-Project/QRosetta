# Manages quantum job lifecycle and status.

import asyncio
import gc
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
import services.circuit_library as circuit_library
from schemas import BatchPayload
from config import settings
import services.analysis as comparator
from services.aggregator import compile_comparison_reports, compile_measurement_reports
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-job-manager")

ACTIVE_JOBS = {}

async def run_single_circuit_comparison(qasm_string: str, optimization_level: int = 0, runner_config: dict = None, timeout_seconds: int = 60, target_simulators: list = None, runner_statuses: dict = None, runner_phases: dict = None):
    logger.info(f"Processing circuit...")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        logger.info(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")

        RemoveBarriers().apply(tk_circ)
        modified_qasm_string = pytket.qasm.circuit_to_qasm_str(tk_circ)
        runner_payload = {
            "circuit_data": modified_qasm_string,
            "optimization_level": optimization_level,
            "runner_config": runner_config or {},
            "runner_phases": runner_phases or {},
        }
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    gc.collect()

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
        divergence_report, performance_report, resource_report = await compile_comparison_reports(aggregated_results)
    except Exception as e:
        logger.warning(f"Analysis failed (returning raw results only): {e}")
        divergence_report = {"error": f"Analysis failed: {e}"}
        performance_report = {}
        resource_report = {}

    full_report_data = [res.copy() for res in aggregated_results]
    save_report_to_disk(full_report_data)

    display_results = []
    for result in aggregated_results:
        if "statevector" in result and isinstance(result["statevector"], list) and len(result["statevector"]) > 16384:
            display_results.append({**result, "statevector": "<Statevector too large for display. Analysis included in reports.>"})
        else:
            display_results.append(result)

    return {
        "input_qasm": qasm_string,
        "divergence_report": divergence_report,
        "performance_report": performance_report,
        "resource_report": resource_report,
        "raw_results": display_results
    }

async def run_single_circuit_measurement(qasm_string: str, n_shots: int, optimization_level: int = 0, runner_config: dict = None, timeout_seconds: int = 60, target_simulators: list = None, runner_statuses: dict = None, runner_phases: dict = None):
    logger.info(f"Processing measured circuit for {n_shots} shots...")

    sampled_payload = {
        "circuit_data": qasm_string,
        "n_shots": n_shots,
        "optimization_level": optimization_level,
        "runner_config": runner_config or {},
        "runner_phases": runner_phases or {},
    }

    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
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
        }
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    gc.collect()

    if target_simulators:
        filtered_sampled = {k: v for k, v in SAMPLED_SV_URLS.items() if k in target_simulators}
        filtered_native = {k: v for k, v in NATIVE_SAMPLING_URLS.items() if k in target_simulators}
    else:
        filtered_sampled = SAMPLED_SV_URLS
        filtered_native = NATIVE_SAMPLING_URLS

    sampled_task = dispatch_to_runners(filtered_sampled, sampled_payload, timeout_seconds, runner_statuses)
    native_task = dispatch_to_runners(filtered_native, native_payload, timeout_seconds, runner_statuses)

    results_sampled, results_native = await asyncio.gather(sampled_task, native_task)

    aggregated_results = results_native + results_sampled

    save_report_to_disk(aggregated_results)

    try:
        divergence_report, performance_report, resource_report = await compile_measurement_reports(aggregated_results, n_shots)

    except Exception as e:
        return {
            "input_qasm": qasm_string, "n_shots": n_shots,
            "error": f"Error during comparison: {str(e)}",
            "raw_results": aggregated_results
        }

    return {
        "input_qasm": qasm_string,
        "modified_qasm_for_native_runners": modified_qasm_string,
        "n_shots": n_shots,
        "divergence_report": divergence_report,
        "performance_report": performance_report,
        "resource_report": resource_report,
        "raw_results": aggregated_results
    }

async def worker_compare(job_id: str, qasm_string: str, optimization_level: int, runner_config: dict, timeout: int, target_simulators: list, execution_target: str, runner_phases: dict = None):
    runner_statuses = {}
    ACTIVE_JOBS[job_id]["status"] = "processing"
    ACTIVE_JOBS[job_id]["runner_statuses"] = runner_statuses
    try:
        report = await run_single_circuit_comparison(qasm_string, optimization_level, runner_config, timeout, target_simulators, runner_statuses, runner_phases)
        ACTIVE_JOBS[job_id] = {"status": "completed", "target": execution_target, "results": report, "runner_statuses": runner_statuses, "finished_at": time.time()}
    except Exception as e:
        ACTIVE_JOBS[job_id] = {"status": "failed", "target": execution_target, "error": str(e), "runner_statuses": runner_statuses, "finished_at": time.time()}

async def worker_compare_measured(job_id: str, qasm_string: str, n_shots: int, optimization_level: int, runner_config: dict, timeout: int, target_simulators: list, execution_target: str, runner_phases: dict = None):
    runner_statuses = {}
    ACTIVE_JOBS[job_id]["status"] = "processing"
    ACTIVE_JOBS[job_id]["runner_statuses"] = runner_statuses
    try:
        report = await run_single_circuit_measurement(qasm_string, n_shots, optimization_level, runner_config, timeout, target_simulators, runner_statuses, runner_phases)
        ACTIVE_JOBS[job_id] = {"status": "completed", "target": execution_target, "results": report, "runner_statuses": runner_statuses, "finished_at": time.time()}
    except Exception as e:
        ACTIVE_JOBS[job_id] = {"status": "failed", "target": execution_target, "error": str(e), "runner_statuses": runner_statuses, "finished_at": time.time()}

async def worker_batch_suite(job_id: str, payload: BatchPayload):
    runner_statuses = {}
    ACTIVE_JOBS[job_id]["status"] = "processing"
    ACTIVE_JOBS[job_id]["runner_statuses"] = runner_statuses
    logger.info(f"--- Starting Batch Suite ({payload.mode}) with {len(payload.tasks)} tasks ---")
    benchmark_summary = []

    for task in payload.tasks:
        task_name = f"{task.algorithm} ({task.qubits}q)"
        logger.info(f"--- Running task: {task_name} ---")
        try:
            if task.qasm_string:
                qasm_string = task.qasm_string
            else:
                if task.qubits > settings.MAX_QUBITS_MEASURED:
                    raise ValueError(f"Qubit count {task.qubits} exceeds limit of {settings.MAX_QUBITS_MEASURED}")
                qasm_string = circuit_library.generate_circuit(task.algorithm, task.qubits)

            validate_request(qasm_string, mode=payload.mode)
            report = None
            timeout = max(1, min(payload.timeout_seconds, settings.RUNNER_TIMEOUT_SEC))
            if payload.mode == 'statevector':
                report = await run_single_circuit_comparison(qasm_string, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, runner_statuses, payload.runner_phases)
            elif payload.mode == 'measured':
                report = await run_single_circuit_measurement(qasm_string, payload.n_shots, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, runner_statuses, payload.runner_phases)
            else:
                raise ValueError(f"Unknown mode: {payload.mode}")

            report["task_name"] = task_name
            benchmark_summary.append(report)

        except Exception as e:
            benchmark_summary.append({
                "task_name": task_name,
                "error": f"Failed to process task: {str(e)}"
            })

    logger.info(f"--- Batch Suite Complete ---")
    ACTIVE_JOBS[job_id] = {"status": "completed", "target": payload.execution_target, "results": {"benchmark_summary": benchmark_summary}, "runner_statuses": runner_statuses, "finished_at": time.time()}
