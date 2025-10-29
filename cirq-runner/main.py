from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np

# --- Our Core Quantum Imports ---
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq
import cirq
# --- ---

app = FastAPI(title="Cirq Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """
    Accepts a QASM string, converts it using Pytket, 
    simulates it on Cirq, and returns the statevector.
    """
    print(f"Received circuit data for Cirq simulation.")
    
    try:
        # Step 1: Deserialize the QASM string
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        
        # Step 2: Translate the Pytket circuit to a Cirq circuit
        cirq_circ = tk_to_cirq(tk_circ)
        
        # Step 3: Get the Cirq simulator
        simulator = cirq.Simulator()
        
        # Step 4: Run the simulation
        # Note: Cirq's statevector is on the result object
        result = simulator.simulate(cirq_circ)
        statevector = result.final_state_vector
        
        # Step 5: Format the output (convert numpy complex to strings)
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