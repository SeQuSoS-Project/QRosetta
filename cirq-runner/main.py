from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import CirqBackend  # <-- IMPORT THE BACKEND

app = FastAPI(title="Cirq Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for Cirq simulation.")
    
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        
        # --- THIS IS THE NEW, CORRECT LOGIC ---
        
        # 1. Instantiate the Pytket backend for Cirq
        backend = CirqBackend(use_statevector_simulator=True)
        
        # 2. Compile with optimization_level=0, just like all other runners
        compiled_circ = backend.get_compiled_circuit(tk_circ, 
                                                     optimisation_level=0)
        
        # 3. Process the circuit using the Pytket backend
        handle = backend.process_circuit(compiled_circ)
        
        # 4. Get the result from the backend
        statevector = backend.get_result(handle).get_state()
        
        # --- END OF NEW LOGIC ---
        
        statevector_str = [str(c) for c in statevector]
        
        print("Cirq simulation successful.")
        
        return {
            "simulator": "cirq",
            "statevector": statevector_str
        }

    except Exception as e:
        print(f"Error during Cirq simulation: {str(e)}")
        return {
            "simulator": "cirq",
            "error": str(e)
        }