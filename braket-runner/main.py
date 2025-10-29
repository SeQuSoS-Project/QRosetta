from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np

# --- Our Core Quantum Imports ---
import pytket.qasm
# 1. Import the MAIN BraketBackend
from pytket.extensions.braket import BraketBackend
# --- ---

app = FastAPI(title="Braket Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """
    Accepts a QASM string, converts it to a Pytket circuit, 
    simulates it on the local Braket simulator, and returns the statevector.
    """
    print(f"Received circuit data for Braket simulation.")
    
    try:
        # Step 1: Deserialize the QASM string
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        
        # Step 2: Get the Braket local simulator backend
        # 2. Instantiate it with local=True
        backend = BraketBackend(local=True)
        
        # Step 3: Run the simulation
        handle = backend.process_circuit(tk_circ)
        
        # Step 4: Extract the statevector
        statevector = backend.get_result(handle).get_state()
        
        # Step 5: Format the output (convert numpy complex to strings)
        statevector_str = [str(c) for c in statevector]
        
        print("Braket simulation successful.")
        
        return {
            "simulator": "braket",
            "statevector": statevector_str
        }

    except Exception as e:
        print(f"Error during Braket simulation: {str(e)}")
        return {
            "simulator": "braket",
            "error": str(e)
        }