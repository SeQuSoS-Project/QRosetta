from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import pytket.qasm
from pytket.extensions.qulacs import QulacsBackend

app = FastAPI(title="Qulacs Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for Qulacs simulation.")
    
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = QulacsBackend()
        
        # --- THIS IS THE CORRECT FIX ---
        # 1. Get the circuit, compiled only for compatibility (level 0)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        # 2. Run the *compiled*, un-optimized circuit
        handle = backend.process_circuit(compiled_circ)
        # --- END OF FIX ---
        
        statevector = backend.get_result(handle).get_state()
        statevector_str = [str(c) for c in statevector]
        
        print("Qulacs simulation successful.")
        
        return {
            "simulator": "qulacs",
            "statevector": statevector_str
        }

    except Exception as e:
        print(f"Error during Qulacs simulation: {str(e)}")
        return {
            "simulator": "qulacs",
            "error": str(e)
        }