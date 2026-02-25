from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from qrosetta_commons.helpers import get_logger
import asyncio
import gc
import json
import pytket.qasm
from pytket.passes import RemoveBarriers
from services.validator import validate_request
from services.report_manager import save_report_to_disk
from services.dispatcher import (
    STATEVECTOR_RUNNER_URLS,
    NATIVE_SAMPLING_URLS,
    SAMPLED_SV_URLS,
    dispatch_to_runners
)
from schemas import QasmPayload, MeasuredQasmPayload, BatchPayload, GenerateCircuitPayload
from routers.generation import generate_circuit_endpoint
import comparator
from config import settings
from security import limiter

logger = get_logger("rosetta-api")
router = APIRouter()

# ... (CORE LOGIC FUNCTIONS untouched) ...
# I will supply the full file content for the import section if I can't match it easily, 
# but here I'll try to just edit the imports and the endpoint defs.
# Actually I'll just use MultiReplace or Replace big chunk.
# Let's replace the top imports first.

# Wait, I can use multi_replace to do imports separate from decorators.
# But replacing the whole top and the endpoint lines is easier with replace_content if I'm careful.
# I'll replace the top section to add imports.


# --- CORE LOGIC FUNCTIONS ---
async def run_single_circuit_comparison(qasm_string: str, optimization_level: int = 0, timeout_seconds: int = 60, target_simulators: list = None):
    logger.info(f"Processing circuit...")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        logger.info(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")
        # Remove barriers (Pass)
        RemoveBarriers().apply(tk_circ)
        modified_qasm_string = pytket.qasm.circuit_to_qasm_str(tk_circ)
        runner_payload = {
            "circuit_data": modified_qasm_string,
            "optimization_level": optimization_level
        }
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    gc.collect() # Clean up before dispatch
    
    if target_simulators:
        filtered_urls = {k: v for k, v in STATEVECTOR_RUNNER_URLS.items() if k in target_simulators}
    else:
        filtered_urls = STATEVECTOR_RUNNER_URLS
        
    aggregated_results = await dispatch_to_runners(
        runner_urls=filtered_urls,
        runner_payload=runner_payload,
        timeout_seconds=timeout_seconds
    )

    loop = asyncio.get_event_loop()

    gc.collect() # Clean up before heavy reporting
    logger.info("Generating divergence report...")
    divergence_report_task = loop.run_in_executor(
        None, comparator.create_divergence_report, aggregated_results
    )
    
    logger.info("Generating performance report...")
    performance_report_task = loop.run_in_executor(
        None, comparator.create_performance_report, aggregated_results
    )

    logger.info("Generating resource report...")
    resource_report_task = loop.run_in_executor(
        None, comparator.create_resource_report, aggregated_results
    )

    divergence_report, performance_report, resource_report = await asyncio.gather(
        divergence_report_task, performance_report_task, resource_report_task
    )

    # --- Cache full results to disk ---
    full_report_data = [res.copy() for res in aggregated_results]
    save_report_to_disk(full_report_data)

    # --- Browser Safety Valve ---
    for result in aggregated_results:
        if "statevector" in result and isinstance(result["statevector"], list):
            if len(result["statevector"]) > 16384:
                result["statevector"] = "<Statevector too large for display. Analysis included in reports.>"

    return {
        "input_qasm": qasm_string,
        "divergence_report": divergence_report,
        "performance_report": performance_report,
        "resource_report": resource_report,
        "raw_results": aggregated_results
    }


async def run_single_circuit_measurement(qasm_string: str, n_shots: int, optimization_level: int = 0, timeout_seconds: int = 60, target_simulators: list = None):
    """
    (REFACTO RED - Counts)
    Dispatches TWO types of payloads:
    1. ORIGINAL QASM to sampled runners.
    2. MODIFIED QASM to native runners.
    """
    logger.info(f"Processing measured circuit for {n_shots} shots...")

    # --- Payload 1: For SAMPLED_SV_URLS ---
    sampled_payload = {
        "circuit_data": qasm_string,
        "n_shots": n_shots,
        "optimization_level": optimization_level
    }

    # --- Payload 2: For NATIVE_SAMPLING_URLS ---
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        # Remove barriers (Pass)
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
            "optimization_level": optimization_level
        }
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    # --- Dispatch both sets of jobs in parallel ---
    gc.collect() # Clean up before dispatch
    
    if target_simulators:
        filtered_sampled = {k: v for k, v in SAMPLED_SV_URLS.items() if k in target_simulators}
        filtered_native = {k: v for k, v in NATIVE_SAMPLING_URLS.items() if k in target_simulators}
    else:
        filtered_sampled = SAMPLED_SV_URLS
        filtered_native = NATIVE_SAMPLING_URLS
        
    sampled_task = dispatch_to_runners(filtered_sampled, sampled_payload, timeout_seconds)
    native_task = dispatch_to_runners(filtered_native, native_payload, timeout_seconds)

    results_sampled, results_native = await asyncio.gather(sampled_task, native_task)

    # Combine all results
    aggregated_results = results_native + results_sampled

    # --- Call the comparators ---
    try:
        loop = asyncio.get_event_loop()
        gc.collect() # Clean up before heavy reporting
        logger.info("Generating counts divergence report...")
        divergence_report_task = loop.run_in_executor(
            None, comparator.create_counts_report, aggregated_results, n_shots
        )
        
        logger.info("Generating performance report...")
        performance_report_task = loop.run_in_executor(
            None, comparator.create_performance_report, aggregated_results
        )
        
        logger.info("Generating resource report...")
        resource_report_task = loop.run_in_executor(
            None, comparator.create_resource_report, aggregated_results
        )

        divergence_report, performance_report, resource_report = await asyncio.gather(
            divergence_report_task, performance_report_task, resource_report_task
        )
        
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

@router.post("/compare")
@limiter.limit("10/minute")
async def compare_circuits_endpoint(request: Request, payload: QasmPayload):
    validate_request(payload.qasm_string, mode="statevector")
    timeout = max(1, min(payload.timeout_seconds, 300))
    return await run_single_circuit_comparison(payload.qasm_string, payload.optimization_level, timeout, payload.target_simulators)

@router.post("/compare_measured")
@limiter.limit("10/minute")
async def compare_measured_circuits_endpoint(request: Request, payload: MeasuredQasmPayload):
    validate_request(payload.qasm_string, mode="measured")
    timeout = max(1, min(payload.timeout_seconds, 300))
    return await run_single_circuit_measurement(payload.qasm_string, 
                                                payload.n_shots,
                                                payload.optimization_level,
                                                timeout,
                                                payload.target_simulators)

@router.post("/run_batch_suite")
@limiter.limit("10/minute")
async def run_batch_suite_endpoint(request: Request, payload: BatchPayload):
    logger.info(f"--- Starting Batch Suite ({payload.mode}) with {len(payload.tasks)} tasks ---")
    benchmark_summary = []

    for task in payload.tasks:
        task_name = f"{task.algorithm} ({task.qubits}q)"
        logger.info(f"--- Running task: {task_name} ---")
        try:
            if task.qasm_string:
                qasm_string = task.qasm_string
            else:
                # Generate QASM for the task
                qasm_payload = GenerateCircuitPayload(algorithm=task.algorithm, qubits=task.qubits)
                qasm_response = await generate_circuit_endpoint(request, qasm_payload)

                # Error handling if the circuit generation fails
                if isinstance(qasm_response, JSONResponse):
                    error_content = json.loads(qasm_response.body)
                    raise Exception(f"Circuit generation failed: {error_content.get('error', 'Unknown error')}")

                qasm_string = qasm_response["qasm"]

            validate_request(qasm_string, mode=payload.mode)

            report = None
            timeout = max(1, min(payload.timeout_seconds, 300))
            if payload.mode == 'statevector':
                report = await run_single_circuit_comparison(qasm_string, payload.optimization_level, timeout, payload.target_simulators)
            elif payload.mode == 'measured':
                report = await run_single_circuit_measurement(qasm_string, payload.n_shots, payload.optimization_level, timeout, payload.target_simulators)
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
    return {"benchmark_summary": benchmark_summary}
