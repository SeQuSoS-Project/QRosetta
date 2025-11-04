from fastapi import FastAPI
from pydantic import BaseModel
import pytket.qasm
import httpx  # The async-compatible requests library
import asyncio # For running runners in parallel
import os
import glob     # For finding files

# --- STEP 1: RE-INTRODUCE THE COMPARATOR ---
import comparator 

app = FastAPI(title="Quantum Rosetta API")

class QasmPayload(BaseModel):
    qasm_string: str

# Our full list of 6 runners
RUNNER_URLS = {
    "qiskit": "http://qiskit_runner:8000/run",
    "cirq": "http://cirq_runner:8000/run",
    "qulacs": "http://qulacs_runner:8000/run",
    "braket": "http://braket_runner:8000/run",
    "projectq": "http://projectq_runner:8000/run",
    "quest": "http://quest_runner:8000/run"
}


async def run_single_circuit_comparison(qasm_string: str):
    """
    This is our core logic. It takes a QASM string and
    returns a full divergence report.
    """
    
    print(f"Processing circuit...")
    
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        print(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")
        
        runner_payload = {"circuit_data": qasm_string}
        
        # This 'async with' block creates a new, local client
        # for each call, preventing race conditions.
        async with httpx.AsyncClient(timeout=10.0) as client:
            dispatch_tasks = []
            for sim_name, url in RUNNER_URLS.items():
                print(f"Dispatching job to {sim_name}-runner...")
                dispatch_tasks.append(client.post(url, json=runner_payload))

            responses = await asyncio.gather(*dispatch_tasks, return_exceptions=True)

        # Aggregate results
        aggregated_results = []
        for i, res in enumerate(responses):
            sim_name = list(RUNNER_URLS.keys())[i]
            if isinstance(res, httpx.Response):
                aggregated_results.append(res.json())
            else:
                print(f"Error calling {sim_name}-runner: {str(res)}")
                aggregated_results.append({
                    "simulator": sim_name,
                    "error": f"Failed to get response: {str(res)}"
                })

    except Exception as e:
        print(f"Error during QASM parsing: {str(e)}")
        return {
            "input_qasm": qasm_string,
            "error": str(e)
        }

    # --- STEP 2: CALL THE NEW COMPARATOR ---
    print("Generating divergence report...")
    divergence_report = comparator.create_divergence_report(aggregated_results)

    # Return the full report for this single circuit
    return {
        "input_qasm": qasm_string,
        "divergence_report": divergence_report,
        "raw_results": aggregated_results
    }


@app.get("/")
def read_root():
    """A simple health check endpoint."""
    return {"status": "ok", "message": "Quantum Rosetta API is running"}


@app.post("/compare")
async def compare_circuits_endpoint(payload: QasmPayload):
    """
    (USER-FACING ENDPOINT 1)
    Runs a single QASM string provided in a JSON payload.
    """
    return await run_single_circuit_comparison(payload.qasm_string)


@app.post("/run_benchmark_suite")
async def run_benchmark_suite_endpoint():
    """
    (USER-FACING ENDPOINT 2)
    Runs all .qasm files found in the 'benchmarks/' directory.
    """
    benchmark_dir = "benchmarks/"
    qasm_files = glob.glob(os.path.join(benchmark_dir, "*.qasm"))
    
    if not qasm_files:
        return {"error": f"No .qasm files found in {benchmark_dir}"}
        
    print(f"--- Starting Benchmark Suite: Found {len(qasm_files)} circuits ---")
    
    benchmark_summary = []
    
    for qasm_file_path in qasm_files:
        print(f"--- Running test: {qasm_file_path} ---")
        try:
            with open(qasm_file_path, 'r') as f:
                qasm_string = f.read()
            
            # Run the comparison
            report = await run_single_circuit_comparison(qasm_string)
            report["benchmark_file"] = qasm_file_path
            benchmark_summary.append(report)
            
        except Exception as e:
            benchmark_summary.append({
                "benchmark_file": qasm_file_path,
                "error": f"Failed to read or process file: {str(e)}"
            })
            
    print(f"--- Benchmark Suite Complete ---")
    
    return {"benchmark_summary": benchmark_summary}