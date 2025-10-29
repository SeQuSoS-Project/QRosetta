from fastapi import FastAPI
from pydantic import BaseModel
import pytket.qasm
import requests 

app = FastAPI(title="Quantum Rosetta API")

class QasmPayload(BaseModel):
    qasm_string: str

# --- Define the URLs for ALL our runner services ---
RUNNER_URLS = {
    "qiskit": "http://qiskit_runner:8000/run",
    "cirq": "http://cirq_runner:8000/run",
    "qulacs": "http://qulacs_runner:8000/run",
    "braket": "http://braket_runner:8000/run",
    "projectq": "http://projectq_runner:8000/run"  # <-- ADDED THIS LINE
}
# --- ---

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
    
    # --- This is the new aggregation logic ---
    try:
        # Step 1: Validate the QASM
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.qasm_string)
        print(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")
        
        # This is the payload we will send to *each* runner
        runner_payload = {"circuit_data": payload.qasm_string}
        
        # This list will hold all our results
        aggregated_results = []
        
        # Step 2: Loop through our runners and dispatch jobs
        for simulator_name, url in RUNNER_URLS.items():
            print(f"Dispatching job to {simulator_name}-runner at {url}...")
            
            try:
                # Send the HTTP request to the runner
                response = requests.post(url, json=runner_payload, timeout=10)
                response.raise_for_status() # Check for HTTP errors
                
                # Add the successful result to our list
                aggregated_results.append(response.json())
                
            except requests.exceptions.RequestException as e:
                # If one runner fails, log it but don't stop.
                print(f"Error calling {simulator_name}-runner: {str(e)}")
                aggregated_results.append({
                    "simulator": simulator_name,
                    "error": f"Failed to get response: {str(e)}"
                })

    except Exception as e:
        # This catches errors from the initial QASM parsing
        print(f"Error during QASM parsing: {str(e)}")
        return {
            "input_qasm": payload.qasm_string,
            "error": str(e)
        }
    # --- End of new logic ---

    # Return the aggregated results from all runners
    return {
        "input_qasm": payload.qasm_string,
        "results": aggregated_results
    }