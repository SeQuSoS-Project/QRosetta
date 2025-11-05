from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import pytket.qasm
from pytket.extensions.quest import QuESTBackend
# --- NEW IMPORT ---
from collections import Counter

app = FastAPI(title="QuEST Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

class MeasuredCircuitPayload(BaseModel):
    circuit_data: str
    n_shots: int

# --- NEW HELPER FUNCTION ---
def _sample_from_statevector(statevector, n_shots, n_qubits):
    """
    Manually samples from a statevector's probability distribution.
    """
    # 1. Get probabilities
    probabilities = np.abs(statevector)**2
    
    # 2. Get samples
    samples = np.random.choice(
        range(len(statevector)), 
        size=n_shots, 
        p=probabilities
    )
    
    # 3. Count the samples
    sample_counts = Counter(samples)
    
    # 4. Convert integer keys (e.g., 3) to bitstring keys (e.g., "11")
    counts_dict = {
        format(k, f'0{n_qubits}b'): v 
        for k, v in sample_counts.items()
    }
    return counts_dict

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """ (This is your existing, unchanged statevector endpoint) """
    # ... (no changes to this function) ...
    print(f"Received circuit data for QuEST simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = QuESTBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
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
        return { "simulator": "quest", "error": str(e) }

# --- MODIFIED ENDPOINT ---
@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    """
    Accepts QASM, simulates for statevector, and samples manually.
    """
    print(f"Received measured circuit data for QuEST (manual sampling).")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits # We need this for formatting
        
        # 1. Run for statevector (n_shots=None)
        backend = QuESTBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        handle = backend.process_circuit(compiled_circ)
        statevector = backend.get_result(handle).get_state()
        
        # 2. Manually sample from the statevector
        counts_dict = _sample_from_statevector(statevector, 
                                               payload.n_shots, 
                                               n_qubits)
        
        print("QuEST manual sampling successful.")
        
        return {
            "simulator": "quest",
            "counts": counts_dict
        }
    except Exception as e:
        print(f"Error during QuEST measurement simulation: {str(e)}")
        return {
            "simulator": "quest",
            "error": str(e)
        }