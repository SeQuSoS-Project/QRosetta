from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq  
import cirq

app = FastAPI(title="Cirq Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for Cirq simulation.")
    
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        
        cirq_circ = tk_to_cirq(tk_circ)
        
        simulator = cirq.Simulator(dtype=np.complex128, seed=42)
        
        result = simulator.simulate(cirq_circ)
        statevector = result.final_state_vector
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