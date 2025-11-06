from fastapi import FastAPI
import numpy as np
import pytket.qasm
from pytket.extensions.quest import QuESTBackend
from collections import Counter
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector, ensure_circuit_is_measurable

app = FastAPI(title="QuEST Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """ (This is your existing, unchanged statevector endpoint) """
    print(f"Received circuit data for QuEST simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        tk_circ = ensure_circuit_is_measurable(tk_circ)
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
        
        # 2. Manually sample from the statevector (using shared helper)
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