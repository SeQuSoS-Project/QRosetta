from fastapi import FastAPI
from pydantic import BaseModel
import pytket.qasm
from pytket.extensions.qiskit import tk_to_qiskit
from qiskit_aer import AerSimulator
from qiskit.circuit import QuantumCircuit

app = FastAPI(title="Qiskit Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for simulation.")
    
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        qiskit_circ = tk_to_qiskit(tk_circ)
        qiskit_circ.save_statevector()
        
        backend = AerSimulator(precision="double")
        
        # --- THIS IS THE FIX ---
        # 1. Set a constant seed for reproducibility
        job = backend.run(qiskit_circ, optimization_level=0, seed_simulator=42)
        # --- END OF FIX ---
        
        result = job.result()
        statevector = result.get_statevector()
        statevector_str = [str(c) for c in statevector]
        
        print("Simulation successful.")
        
        return {
            "simulator": "qiskit",
            "statevector": statevector_str
        }

    except Exception as e:
        print(f"Error during simulation: {str(e)}")
        return {
            "simulator": "qiskit",
            "error": str(e)
        }