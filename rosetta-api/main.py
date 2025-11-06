from fastapi import FastAPI
from pydantic import BaseModel
import pytket.qasm
import httpx
import asyncio
import os
import glob
import comparator 

from pytket.circuit import Circuit

app = FastAPI(title="Quantum Rosetta API")

# --- PAYLOADS ---

class QasmPayload(BaseModel):
    qasm_string: str

class MeasuredQasmPayload(BaseModel):
    qasm_string: str
    n_shots: int = 1024

class MeasuredBenchmarkPayload(BaseModel):
    n_shots: int = 1024

# --- CONFIGURATION (Includes Rec 3 & 4) ---

RUNNER_SERVICES = {
    "qiskit": {
        "base_url": os.getenv("QISKIT_RUNNER_URL", "http://qiskit_runner:8000"),
        "capabilities": ["statevector", "measured_native"]
    },
    "cirq":   {
        "base_url": os.getenv("CIRQ_RUNNER_URL", "http://cirq_runner:8000"),
        "capabilities": ["statevector", "measured_native"]
    },
    "qulacs": {
        "base_url": os.getenv("QULACS_RUNNER_URL", "http://qulacs_runner:8000"),
        "capabilities": ["statevector", "measured_native"]
    },
    "braket": {
        "base_url": os.getenv("BRAKET_RUNNER_URL", "http://braket_runner:8000"),
        "capabilities": ["statevector", "measured_native"]
    },
    "projectq": {
        "base_url": os.getenv("PROJECTQ_RUNNER_URL", "http://projectq_runner:8000"),
        "capabilities": ["statevector", "measured_sampled"]
    },
    "quest":  {
        "base_url": os.getenv("QUEST_RUNNER_URL", "http://quest_runner:8000"),
        "capabilities": ["statevector", "measured_sampled"]
    }
}

# Our dynamic URL builders are now "capability-aware"
STATEVECTOR_RUNNER_URLS = {
    name: f"{config['base_url']}/run" for name, config in RUNNER_SERVICES.items() 
    if "statevector" in config["capabilities"]
}

MEASURED_RUNNER_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_native" in config["capabilities"] or "measured_sampled" in config["capabilities"]
}

# --- MODULAR DISPATCH LOGIC ---

async def _dispatch_to_runners(runner_urls: dict, runner_payload: dict) -> list:
    """
    Internal helper to handle all async dispatch and aggregation.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        dispatch_tasks = []
        for sim_name, url in runner_urls.items():
            print(f"Dispatching job to {sim_name}-runner...")
            dispatch_tasks.append(client.post(url, json=runner_payload))

        responses = await asyncio.gather(*dispatch_tasks, return_exceptions=True)

    # Aggregate results
    aggregated_results = []
    for i, res in enumerate(responses):
        sim_name = list(runner_urls.keys())[i]
        if isinstance(res, httpx.Response):
            aggregated_results.append(res.json())
        else:
            aggregated_results.append({
                "simulator": sim_name,
                "error": f"Failed to get response: {str(res)}"
            })
    return aggregated_results


# --- CORE LOGIC FUNCTIONS ---

async def run_single_circuit_comparison(qasm_string: str):
    """
    (REFACTORED - Statevector)
    Prepares the payload, calls the dispatcher, and calls the comparator.
    """
    print(f"Processing circuit...")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        print(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")
        runner_payload = {"circuit_data": qasm_string}
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    # 1. Call the generic dispatcher
    aggregated_results = await _dispatch_to_runners(
        runner_urls=STATEVECTOR_RUNNER_URLS,
        runner_payload=runner_payload
    )

    # 2. Call the specific comparator
    print("Generating divergence report...")
    divergence_report = comparator.create_divergence_report(aggregated_results)

    return {
        "input_qasm": qasm_string,
        "divergence_report": divergence_report,
        "raw_results": aggregated_results
    }


async def run_single_circuit_measurement(qasm_string: str, n_shots: int):
    """
    (REVERTED - Counts)
    Prepares the *modified* payload, calls the dispatcher, and calls the comparator.
    This logic MUST live in the API to create a standard, measurable
    QASM contract for all runners.
    """
    print(f"Processing measured circuit for {n_shots} shots...")
    try:
        # 1. Parse and MODIFY the QASM
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        n_qubits = tk_circ.n_qubits
        c_reg_name = "c"
        if c_reg_name not in [reg.name for reg in tk_circ.c_registers]:
            tk_circ.add_c_register(c_reg_name, n_qubits)
        
        all_qubits = tk_circ.qubits
        c_register = tk_circ.get_c_register(c_reg_name)
        
        for i in range(n_qubits):
            tk_circ.Measure(all_qubits[i], c_register[i])

        modified_qasm_string = pytket.qasm.circuit_to_qasm_str(tk_circ)
        runner_payload = {
            "circuit_data": modified_qasm_string,
            "n_shots": n_shots
        }
    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    # 2. Call the generic dispatcher
    aggregated_results = await _dispatch_to_runners(
        runner_urls=MEASURED_RUNNER_URLS,
        runner_payload=runner_payload
    )

    # 3. Call the specific comparator
    try:
        print("Generating counts divergence report...")
        divergence_report = comparator.create_counts_report(aggregated_results, n_shots)
    except Exception as e:
        return {
            "input_qasm": qasm_string, "n_shots": n_shots,
            "error": f"Error during comparison: {str(e)}",
            "raw_results": aggregated_results
        }
    
    return {
        "input_qasm": qasm_string,
        "modified_qasm": modified_qasm_string, # <-- This key is restored
        "n_shots": n_shots,
        "divergence_report": divergence_report,
        "raw_results": aggregated_results
    }

# --- USER-FACING ENDPOINTS ---

@app.get("/")
def read_root():
    """A simple health check endpoint."""
    return {"status": "ok", "message": "Quantum Rosetta API is running"}


@app.post("/compare")
async def compare_circuits_endpoint(payload: QasmPayload):
    """
    (USER-FACING ENDPOINT 1 - Statevector)
    Runs a single QASM string provided in a JSON payload.
    """
    return await run_single_circuit_comparison(payload.qasm_string)


@app.post("/compare_measured")
async def compare_measured_circuits_endpoint(payload: MeasuredQasmPayload):
    """
    (USER-FACING ENDPOINT 2 - Counts)
    Runs a single QASM string, adds measurements, and compares counts.
    """
    return await run_single_circuit_measurement(payload.qasm_string, 
                                                payload.n_shots)


@app.post("/run_benchmark_suite")
async def run_benchmark_suite_endpoint():
    """
    (USER-FACING ENDPOINT 3 - Statevector Benchmark)
    Runs all .qasm files in 'benchmarks/' against the statevector comparator.
    """
    benchmark_dir = "benchmarks/"
    qasm_files = glob.glob(os.path.join(benchmark_dir, "*.qasm"))
    
    if not qasm_files:
        return {"error": f"No .qasm files found in {benchmark_dir}"}
        
    print(f"--- Starting Statevector Benchmark Suite ---")
    benchmark_summary = []
    
    for qasm_file_path in qasm_files:
        print(f"--- Running test: {qasm_file_path} ---")
        try:
            with open(qasm_file_path, 'r') as f:
                qasm_string = f.read()
            
            report = await run_single_circuit_comparison(qasm_string)
            report["benchmark_file"] = qasm_file_path
            benchmark_summary.append(report)
            
        except Exception as e:
            benchmark_summary.append({
                "benchmark_file": qasm_file_path,
                "error": f"Failed to read or process file: {str(e)}"
            })
            
    print(f"--- Statevector Benchmark Suite Complete ---")
    return {"benchmark_summary": benchmark_summary}


@app.post("/run_measured_benchmark_suite")
async def run_measured_benchmark_suite_endpoint(payload: MeasuredBenchmarkPayload):
    """
    (USER-FACING ENDPOINT 4 - Counts Benchmark)
    Runs all .qasm files in 'benchmarks/' against the counts comparator.
    Accepts a payload to define n_shots (defaults to 1024).
    """
    benchmark_dir = "benchmarks/"
    qasm_files = glob.glob(os.path.join(benchmark_dir, "*.qasm"))
    n_shots = payload.n_shots # Get n_shots from the payload
    
    if not qasm_files:
        return {"error": f"No .qqasm files found in {benchmark_dir}"}
        
    print(f"--- Starting Measured Benchmark Suite ({n_shots} shots) ---")
    benchmark_summary = []
    
    for qasm_file_path in qasm_files:
        print(f"--- Running test: {qasm_file_path} ---")
        try:
            with open(qasm_file_path, 'r') as f:
                qasm_string = f.read()
            
            # Call the measurement comparison function
            report = await run_single_circuit_measurement(qasm_string, n_shots)
            report["benchmark_file"] = qasm_file_path
            benchmark_summary.append(report)
            
        except Exception as e:
            benchmark_summary.append({
                "benchmark_file": qasm_file_path,
                "error": f"Failed to read or process file: {str(e)}"
            })
            
    print(f"--- Measured Benchmark Suite Complete ---")
    return {"benchmark_summary": benchmark_summary}