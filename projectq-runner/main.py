from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np

# --- Our Core Quantum Imports ---
import pytket.qasm
from pytket.extensions.projectq import ProjectQBackend
# --- ---

app = FastAPI(title="ProjectQ Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """
    Accepts a QASM string, converts it to a Pytket circuit, 
    simulates it on the ProjectQ simulator, and returns the statevector.
    """
    print(f"Received circuit data for ProjectQ simulation.")
    
    try:
        # Step 1: Deserialize the QASM string
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        
        # Step 2: Get the ProjectQ simulator backend
        backend = ProjectQBackend()
        
        # Step 3: Run the simulation
        handle = backend.process_circuit(tk_circ)
        
        # Step 4: Extract the statevector
        statevector = backend.get_result(handle).get_state()
        
        # Step 5: Format the output (convert numpy complex to strings)
        statevector_str = [str(c) for c in statevector]
        
        print("ProjectQ simulation successful.")
        
        return {
            "simulator": "projectq",
            "statevector": statevector_str
        }

    except Exception as e:
        print(f"Error during ProjectQ simulation: {str(e)}")
        return {
            "simulator": "projectq",
            "error": str(e)
        }