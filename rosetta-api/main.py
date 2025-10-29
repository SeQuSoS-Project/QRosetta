from fastapi import FastAPI
from pydantic import BaseModel
import pytket.qasm
import requests # This is the library for making HTTP calls

# Create the main FastAPI application
app = FastAPI(title="Quantum Rosetta API")

# This defines the "shape" of the user's input.
class QasmPayload(BaseModel):
    qasm_string: str

# --- This is the key to our architecture ---
# Inside the Docker network, containers can find each other
# by their service name (from 'docker-compose.yml').
# We are NOT using 'localhost'.
QISKIT_RUNNER_URL = "http://qiskit_runner:8000/run"
# --- ---

@app.get("/")
def read_root():
    """A simple health check endpoint."""
    return {"status": "ok", "message": "Quantum Rosetta API is running"}

@app.post("/compare")
async def compare_circuits(payload: QasmPayload):
    """
    Accepts an OpenQASM 2.0 string, validates it, dispatches it
    to the qiskit-runner, and returns the result.
    """
    
    print(f"Received QASM: {payload.qasm_string}")
    
    try:
        # Step 1: "Validate" the QASM.
        # We parse it here to "fail fast." If the QASM is bad,
        # we find out now, before we bother the runner.
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.qasm_string)
        print(f"Successfully parsed QASM into {tk_circ.n_qubits} qubit circuit.")
        
        # Step 2: "Package" the payload.
        # We create the JSON object that the 'qiskit-runner' expects.
        runner_payload = {"circuit_data": payload.qasm_string}
        
        # Step 3: "Dispatch" the job.
        # We use 'requests' to send an HTTP POST request to the
        # 'qiskit_runner' URL, along with our JSON payload.
        print("Dispatching job to qiskit-runner...")
        response = requests.post(QISKIT_RUNNER_URL, json=runner_payload)
        
        # This will automatically raise an error if the runner
        # returned a 4xx or 5xx status code.
        response.raise_for_status() 
        
        # Step 4: "Receive" the result.
        # We get the JSON response from the runner.
        qiskit_result = response.json()
        
    except Exception as e:
        # This catches errors from parsing (Step 1) OR
        # from the HTTP request (Step 3).
        print(f"Error during processing: {str(e)}")
        return {
            "input_qasm": payload.qasm_string,
            "error": str(e)
        }

    # "Aggregate" and return the final response to the user.
    return {
        "input_qasm": payload.qasm_string,
        "results": [
            qiskit_result  # We just nest the runner's result right in.
        ]
    }