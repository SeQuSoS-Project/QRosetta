from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import pytket.qasm
from pytket.extensions.quest import QuESTBackend

app = FastAPI(title="QuEST Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """
    Accepts a QASM string, converts it to a Pytket circuit, 
    simulates it on the QuEST simulator, and returns the statevector.
    """
    print(f"Received circuit data for QuEST simulation.")
    
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        
        backend = QuESTBackend()
        
        # Get the circuit, compiled only for compatibility (level 0)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        # Run the compiled, un-optimized circuit
        handle = backend.process_circuit(compiled_circ)

        statevector = backend.get_result(handle).get_state()
        statevector_str = [str(c) for c in statevector]
        
        print("QuEST simulation successful.")
        
        return {
            "simulator": "quest",
            "statevector": statevector_str
        }

    except Exception as e:
        print(f"Error during QuEST simulation: {str(e)}")
        return {
            "simulator": "quest",
            "error": str(e)
        }