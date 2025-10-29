from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import pytket.qasm
from pytket.extensions.projectq import ProjectQBackend

app = FastAPI(title="ProjectQ Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for ProjectQ simulation.")
    
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        
        # --- THIS IS THE FIX ---
        # The seed argument is removed as it's not supported
        backend = ProjectQBackend()
        # --- END OF FIX ---
        
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        handle = backend.process_circuit(compiled_circ)

        statevector = backend.get_result(handle).get_state()
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