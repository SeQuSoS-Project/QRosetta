from fastapi import FastAPI
from pydantic import BaseModel
import pytket.qasm
import requests 

# --- STEP 1: IMPORT OUR NEW MODULE ---
import comparator 
# --- ---

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

@app.get("/")
def read_root():
    """A simple health check endpoint."""
    return {"status": "ok", "message": "Quantum Rosetta API is running"}

@app.post("/compare")
async def compare_circuits(payload: QasmPayload):
    """
    Accepts an OpenQASM 2.0 string, validates it, dispatches it
    to ALL runners, aggregates the results, and returns them.
    """
    
    print(f"Received QASM: {payload.qasm_string}")
    
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.qasm_string)
        print(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")
        
        runner_payload = {"circuit_data": payload.qasm_string}
        aggregated_results = []
        
        for simulator_name, url in RUNNER_URLS.items():
            print(f"Dispatching job to {simulator_name}-runner at {url}...")
            
            try:
                response = requests.post(url, json=runner_payload, timeout=10)
                response.raise_for_status()
                aggregated_results.append(response.json())
                
            except requests.exceptions.RequestException as e:
                print(f"Error calling {simulator_name}-runner: {str(e)}")
                aggregated_results.append({
                    "simulator": simulator_name,
                    "error": f"Failed to get response: {str(e)}"
                })

    except Exception as e:
        print(f"Error during processing: {str(e)}")
        return {
            "input_qasm": payload.qasm_string,
            "error": str(e)
        }

    # --- STEP 2: CALL THE COMPARATOR ---
    # After getting all results, generate the fidelity report
    print("Generating divergence report...")
    divergence_report = comparator.create_divergence_report(aggregated_results)
    # --- ---

    # --- STEP 3: RETURN THE NEW JSON FORMAT ---
    return {
        "input_qasm": payload.qasm_string,
        "divergence_report": divergence_report,
        "raw_results": aggregated_results  # We move the old list here
    }