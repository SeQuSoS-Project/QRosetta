from fastapi import FastAPI
from pydantic import BaseModel
import pytket.qasm
import httpx
import asyncio
import os
import glob
import comparator 

# --- NEW IMPORT ---
from pytket.circuit import Circuit # We need this to add measurements

app = FastAPI(title="Quantum Rosetta API")

class QasmPayload(BaseModel):
    qasm_string: str

# --- NEW PAYLOAD FOR MEASUREMENT ---
class MeasuredQasmPayload(BaseModel):
    qasm_string: str
    n_shots: int = 1024 # Default to 1024 shots

# --- Our 2 sets of runner URLs ---
STATEVECTOR_RUNNER_URLS = {
    "qiskit": "http://qiskit_runner:8000/run",
    "cirq": "http://cirq_runner:8000/run",
    "qulacs": "http://qulacs_runner:8000/run",
    "braket": "http://braket_runner:8000/run",
    "projectq": "http://projectq_runner:8000/run",
    "quest": "http://quest_runner:8000/run"
}

MEASURED_RUNNER_URLS = {
    "qiskit": "http://qiskit_runner:8000/run_measured",
    "cirq": "http://cirq_runner:8000/run_measured",
    "qulacs": "http://qulacs_runner:8000/run_measured",
    "braket": "http://braket_runner:8000/run_measured",
    "projectq": "http://projectq_runner:8000/run_measured",
    "quest": "http://quest_runner:8000/run_measured"
}


async def run_single_circuit_comparison(qasm_string: str):
    """
    (This is your existing statevector comparison function)
    It takes a QASM string and returns a full divergence report.
    """
    print(f"Processing circuit...")
    
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        print(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")
        
        runner_payload = {"circuit_data": qasm_string}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            dispatch_tasks = []
            # --- Use the correct URL dict ---
            for sim_name, url in STATEVECTOR_RUNNER_URLS.items():
                print(f"Dispatching job to {sim_name}-runner...")
                dispatch_tasks.append(client.post(url, json=runner_payload))

            responses = await asyncio.gather(*dispatch_tasks, return_exceptions=True)

        aggregated_results = []
        for i, res in enumerate(responses):
            sim_name = list(STATEVECTOR_RUNNER_URLS.keys())[i]
            if isinstance(res, httpx.Response):
                aggregated_results.append(res.json())
            else:
                aggregated_results.append({
                    "simulator": sim_name,
                    "error": f"Failed to get response: {str(res)}"
                })

    except Exception as e:
        return { "input_qasm": qasm_string, "error": str(e) }

    print("Generating divergence report...")
    # --- This correctly calls the statevector comparator ---
    divergence_report = comparator.create_divergence_report(aggregated_results)

    return {
        "input_qasm": qasm_string,
        "divergence_report": divergence_report,
        "raw_results": aggregated_results
    }

# --- NEW CORE LOGIC FUNCTION ---
async def run_single_circuit_measurement(qasm_string: str, n_shots: int):
    """
    Takes a QASM string, ADDS MEASUREMENTS, runs it for n_shots,
    and returns a comparison of the counts.
    """
    
    print(f"Processing measured circuit for {n_shots} shots...")
    
    try:
        # 1. Parse the input QASM
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_string)
        n_qubits = tk_circ.n_qubits
        
        # 2. Add classical registers and measurements
        c_reg_name = "c"
        if c_reg_name not in [reg.name for reg in tk_circ.c_registers]:
            tk_circ.add_c_register(c_reg_name, n_qubits)
        
        # Get the list of all qubits in the circuit
        all_qubits = tk_circ.qubits
        
        # --- THIS IS THE FIX ---
        # Get the classical register by its name using the correct method
        c_register = tk_circ.get_c_register(c_reg_name)
        
        for i in range(n_qubits):
            tk_circ.Measure(all_qubits[i], c_register[i])
        # --- END OF FIX ---

        # 3. Convert the *modified* circuit back to QASM
        modified_qasm_string = pytket.qasm.circuit_to_qasm_str(tk_circ)

        runner_payload = {
            "circuit_data": modified_qasm_string,
            "n_shots": n_shots
        }
        
        # 4. Dispatch to all runners (using the new URLs)
        async with httpx.AsyncClient(timeout=10.0) as client:
            dispatch_tasks = []
            for sim_name, url in MEASURED_RUNNER_URLS.items():
                print(f"Dispatching measured job to {sim_name}-runner...")
                dispatch_tasks.append(client.post(url, json=runner_payload))

            responses = await asyncio.gather(*dispatch_tasks, return_exceptions=True)

        # 5. Aggregate results
        aggregated_results = []
        for i, res in enumerate(responses):
            sim_name = list(MEASURED_RUNNER_URLS.keys())[i]
            if isinstance(res, httpx.Response):
                aggregated_results.append(res.json())
            else:
                aggregated_results.append({
                    "simulator": sim_name,
                    "error": f"Failed to get response: {str(res)}"
                })

    except Exception as e:
        print(f"Error during QASM parsing or dispatch: {str(e)}")
        # Return the error in the JSON response
        return {
            "input_qasm": qasm_string,
            "error": str(e)
        }

    # 6. Call the new counts comparator
    try:
        print("Generating counts divergence report...")
        divergence_report = comparator.create_counts_report(aggregated_results, n_shots)
    except Exception as e:
        print(f"Error during counts comparison: {str(e)}")
        return {
            "input_qasm": qasm_string,
            "n_shots": n_shots,
            "error": f"Error during comparison: {str(e)}",
            "raw_results": aggregated_results
        }
    
    return {
        "input_qasm": qasm_string,
        "modified_qasm": modified_qasm_string,
        "n_shots": n_shots,
        "divergence_report": divergence_report,
        "raw_results": aggregated_results
    }

# --- (existing @app.get("/") endpoint) ---
@app.get("/")
def read_root():
    """A simple health check endpoint."""
    return {"status": "ok", "message": "Quantum Rosetta API is running"}


# --- (existing @app.post("/compare") endpoint) ---
@app.post("/compare")
async def compare_circuits_endpoint(payload: QasmPayload):
    """
    (USER-FACING ENDPOINT 1 - Statevector)
    Runs a single QASM string provided in a JSON payload.
    """
    return await run_single_circuit_comparison(payload.qasm_string)


# --- NEW USER-FACING ENDPOINT ---
@app.post("/compare_measured")
async def compare_measured_circuits_endpoint(payload: MeasuredQasmPayload):
    """
    (USER-FACING ENDPOINT 2 - Counts)
    Runs a single QASM string, adds measurements, and compares counts.
    """
    return await run_single_circuit_measurement(payload.qasm_string, 
                                                payload.n_shots)


# --- (existing @app.post("/run_benchmark_suite") endpoint) ---
# Note: This still uses the statevector comparison.
# We could add a new /run_measured_benchmark_suite endpoint next.
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
            
            # Run the statevector comparison
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