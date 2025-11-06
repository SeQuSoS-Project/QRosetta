from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import ensure_circuit_is_measurable
import numpy as np
import pytket.qasm
from pytket.extensions.braket import BraketBackend

app = FastAPI(title="Braket Runner")


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """ (This is your existing, unchanged statevector endpoint) """
    print(f"Received circuit data for Braket simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        tk_circ = ensure_circuit_is_measurable(tk_circ)
        backend = BraketBackend(local=True)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        handle = backend.process_circuit(compiled_circ)
        statevector = backend.get_result(handle).get_state()
        statevector_str = [str(c) for c in statevector]
        
        print("Braket simulation successful.")
        
        return {
            "simulator": "braket",
            "statevector": statevector_str
        }
    except Exception as e:
        print(f"Error during Braket simulation: {str(e)}")
        return { "simulator": "braket", "error": str(e) }

# --- NEW ENDPOINT ---
@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    """
    Accepts QASM, simulates it for n_shots, and returns counts.
    """
    print(f"Received measured circuit data for Braket simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = BraketBackend(local=True)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        # Process the circuit with n_shots
        handle = backend.process_circuit(compiled_circ, 
                                          n_shots=payload.n_shots)
        
        # Get the counts from the result
        counts = backend.get_result(handle).get_counts()
        
        # Convert Pytket's tuple-keys (e.g., (1, 0)) to string-keys (e.g., "10")
        counts_dict = { "".join(map(str, k)): v for k, v in counts.items() }

        print("Braket measurement simulation successful.")
        
        return {
            "simulator": "braket",
            "counts": counts_dict
        }
    except Exception as e:
        print(f"Error during Braket measurement simulation: {str(e)}")
        return {
            "simulator": "braket",
            "error": str(e)
        }