from fastapi import FastAPI
import numpy as np
import pytket.qasm
from pytket.extensions.projectq import ProjectQBackend
from collections import Counter
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector
# ...

# --- THIS IS THE FIX ---
# We must instantiate the FastAPI app
app = FastAPI(title="ProjectQ Runner")
# --- END OF FIX ---


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """ (This is your existing, unchanged statevector endpoint) """
    print(f"Received circuit data for ProjectQ simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = ProjectQBackend()
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
        return { "simulator": "projectq", "error": str(e) }

# --- MODIFIED ENDPOINT ---
@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    """
    Accepts QASM, simulates for statevector, and samples manually.
    """
    print(f"Received measured circuit data for ProjectQ (manual sampling).")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits # We need this for formatting
        
        # 1. Run for statevector (n_shots=None)
        backend = ProjectQBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        handle = backend.process_circuit(compiled_circ)
        statevector = backend.get_result(handle).get_state()
        
        # 2. Manually sample from the statevector
        counts_dict = _sample_from_statevector(statevector, 
                                               payload.n_shots, 
                                               n_qubits)

        print("ProjectQ manual sampling successful.")
        
        return {
            "simulator": "projectq",
            "counts": counts_dict
        }
    except Exception as e:
        print(f"Error during ProjectQ measurement simulation: {str(e)}")
        return {
            "simulator": "projectq",
            "error": str(e)
        }