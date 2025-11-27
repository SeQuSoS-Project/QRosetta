from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pytket.qasm
import httpx
import asyncio
import os
import glob
import comparator 
import gc
from qrosetta_commons.helpers import get_logger
import library
from config import settings
import cachetools

logger = get_logger("rosetta-api")

# --- NEW IMPORTS ---
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, JSONResponse, FileResponse
import json
# --- END NEW IMPORTS ---

from pytket.circuit import Circuit

from pytket.passes import RemoveBarriers


app = FastAPI(title="Quantum Rosetta API")
app.add_middleware(GZipMiddleware, minimum_size=1000)

RESULT_CACHE = cachetools.TTLCache(maxsize=10, ttl=3600) # Kept for backward compatibility if needed, but unused for download
REPORTS_DIR = "export/reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

# This serves all files from the 'static' folder (like index.html)
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- PAYLOADS ---
class QasmPayload(BaseModel):
    qasm_string: str
class MeasuredQasmPayload(BaseModel):
    qasm_string: str
    n_shots: int = 1024
class MeasuredBenchmarkPayload(BaseModel):
    n_shots: int = 1024
class GenerateCircuitPayload(BaseModel):
    algorithm: str
    qubits: int

class BenchmarkTask(BaseModel):
    algorithm: str
    qubits: int

class BatchPayload(BaseModel):
    tasks: List[BenchmarkTask]
    n_shots: int = 1024
    mode: str  # 'statevector' or 'measured'

# --- CONFIGURATION (8 Runners, 2 Categories) ---
RUNNER_SERVICES = settings.get_runner_services()

# --- DYNAMIC URL BUILDERS (2 Groups) ---
STATEVECTOR_RUNNER_URLS = {
    name: f"{config['base_url']}/run" for name, config in RUNNER_SERVICES.items() 
    if "statevector" in config["capabilities"]
}
# Group 1: Native samplers that get MODIFIED QASM
NATIVE_SAMPLING_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_native" in config["capabilities"]
}
# Group 2: Statevector samplers that get ORIGINAL QASM
SAMPLED_SV_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_sampled" in config["capabilities"]
}


# --- MODULAR DISPATCH LOGIC ---
async def _dispatch_to_runners(runner_urls: dict, runner_payload: dict) -> list:
    async with httpx.AsyncClient(timeout=60.0) as client:
        dispatch_tasks = []
        for sim_name, url in runner_urls.items():
            logger.info(f"Dispatching job to {sim_name}...") 
            dispatch_tasks.append(client.post(url, json=runner_payload))

        responses = await asyncio.gather(*dispatch_tasks, return_exceptions=True)

    aggregated_results = []
    for i, res in enumerate(responses):
        sim_name = list(runner_urls.keys())[i]
        if isinstance(res, httpx.Response):
            try:
                aggregated_results.append(res.json())
            except Exception as e:
                aggregated_results.append({
                    "simulator": sim_name,
                    "error": f"Failed to decode JSON response: {str(e)}. Response text: {res.text}"
                })
        else:
            aggregated_results.append({
                "simulator": sim_name,
                "error": f"Failed to get response: {str(res)}"
            })
    return aggregated_results


# --- CORE LOGIC FUNCTIONS ---
async def run_single_circuit_comparison(qasm_string: str):
    logger.info(f"Processing circuit...")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        logger.info(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")
        # Remove barriers (Pass)
        RemoveBarriers().apply(tk_circ)
        modified_qasm_string = pytket.qasm.circuit_to_qasm_str(tk_circ)
        runner_payload = {"circuit_data": modified_qasm_string}
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    gc.collect() # Clean up before dispatch
    aggregated_results = await _dispatch_to_runners(
        runner_urls=STATEVECTOR_RUNNER_URLS,
        runner_payload=runner_payload
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
    try:
        with open(os.path.join(REPORTS_DIR, "latest_full_report.json"), "w") as f:
            json.dump(full_report_data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write report to disk: {e}")
    
    RESULT_CACHE["latest_full_report"] = full_report_data

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


async def run_single_circuit_measurement(qasm_string: str, n_shots: int):
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
        "n_shots": n_shots
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
            "n_shots": n_shots
        }
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    # --- Dispatch both sets of jobs in parallel ---
    gc.collect() # Clean up before dispatch
    sampled_task = _dispatch_to_runners(SAMPLED_SV_URLS, sampled_payload)
    native_task = _dispatch_to_runners(NATIVE_SAMPLING_URLS, native_payload)

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

# --- USER-FACING ENDPOINTS ---

# --- UPDATED ENDPOINT ---
@app.get("/")
async def read_index():
    """Serves the main HTML page."""
    return FileResponse('static/index.html')

@app.get("/download_latest_report")
def download_latest_report():
    report_path = os.path.join(REPORTS_DIR, "latest_full_report.json")
    if not os.path.exists(report_path):
        return JSONResponse(content={"error": "No report available"}, status_code=404)
    return FileResponse(report_path, media_type="application/json", filename="full_quantum_report.json")

@app.get("/algorithms")
async def get_algorithms():
    return [
        {"id": "bell", "name": "Bell State (Simple)", "min_qubits": 2, "max_qubits": 2, "default_qubits": 2, "description": "Maximally entangled state on 2 qubits."},
        {"id": "ghz", "name": "GHZ State (Entanglement)", "min_qubits": 2, "max_qubits": 20, "default_qubits": 3, "description": "Greenberger-Horne-Zeilinger state on N qubits."},
        {"id": "qft", "name": "Quantum Fourier Transform", "min_qubits": 1, "max_qubits": 20, "default_qubits": 3, "description": "Standard QFT circuit (without inverse)."},
        {"id": "grover", "name": "Grover Search (Oracle)", "min_qubits": 2, "max_qubits": 14, "default_qubits": 3, "description": "Grover's algorithm with a dummy oracle (limited to 14 qubits for browser safety due to depth)."},
        {"id": "bv", "name": "Bernstein-Vazirani", "min_qubits": 2, "max_qubits": 20, "default_qubits": 4, "description": "BV algorithm with 'all-ones' secret string."},
        {"id": "vqe", "name": "VQE Ansatz", "min_qubits": 2, "max_qubits": 20, "default_qubits": 4, "description": "Hardware Efficient Ansatz with rotation layers."},
        {"id": "random", "name": "Random Circuit", "min_qubits": 2, "max_qubits": 20, "default_qubits": 5, "description": "Random gates to defeat compiler optimizations."}
    ]

# --- ALGORITHM HANDLERS ---
ALGORITHM_HANDLERS = {
    "ghz": library.generate_ghz,
    "bell": library.generate_bell_state,
    "qft": library.generate_qft,
    "grover": library.generate_grover_search,
    "bv": library.generate_bernstein_vazirani,
    "vqe": library.generate_vqe_ansatz,
    "random": library.generate_random_circuit
}

@app.post("/generate_circuit")
async def generate_circuit_endpoint(payload: GenerateCircuitPayload):
    try:
        handler = ALGORITHM_HANDLERS.get(payload.algorithm)
        if not handler:
            return JSONResponse(content={"error": f"Unknown algorithm: {payload.algorithm}"}, status_code=400)
        
        qasm = handler(payload.qubits)
        return {"qasm": qasm}
    except Exception as e:
        logger.error(f"CRITICAL ERROR in generate_circuit: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/compare")
async def compare_circuits_endpoint(payload: QasmPayload):
    return await run_single_circuit_comparison(payload.qasm_string)

@app.post("/compare_measured")
async def compare_measured_circuits_endpoint(payload: MeasuredQasmPayload):
    return await run_single_circuit_measurement(payload.qasm_string, 
                                                payload.n_shots)

@app.post("/run_batch_suite")
async def run_batch_suite_endpoint(payload: BatchPayload):
    logger.info(f"--- Starting Batch Suite ({payload.mode}) with {len(payload.tasks)} tasks ---")
    benchmark_summary = []

    for task in payload.tasks:
        task_name = f"{task.algorithm} ({task.qubits}q)"
        logger.info(f"--- Running task: {task_name} ---")
        try:
            # Generate QASM for the task
            qasm_payload = GenerateCircuitPayload(algorithm=task.algorithm, qubits=task.qubits)
            qasm_response = await generate_circuit_endpoint(qasm_payload)

            # Error handling if the circuit generation fails
            if isinstance(qasm_response, JSONResponse):
                error_content = json.loads(qasm_response.body)
                raise Exception(f"Circuit generation failed: {error_content.get('error', 'Unknown error')}")

            qasm_string = qasm_response["qasm"]

            report = None
            if payload.mode == 'statevector':
                report = await run_single_circuit_comparison(qasm_string)
            elif payload.mode == 'measured':
                report = await run_single_circuit_measurement(qasm_string, payload.n_shots)
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