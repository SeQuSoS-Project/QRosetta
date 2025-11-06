from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import ensure_circuit_is_measurable
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq  
import cirq
# --- NEW IMPORT ---
# This is the correct backend for measurement-based simulation
from pytket.extensions.cirq.backends.cirq import CirqStateSampleBackend

app = FastAPI(title="Cirq Runner")



@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """ (This is your existing, unchanged statevector endpoint) """
    # ... (existing code, no changes) ...
    print(f"Received circuit data for Cirq simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        tk_circ = ensure_circuit_is_measurable(tk_circ)
        cirq_circ = tk_to_cirq(tk_circ)
        simulator = cirq.Simulator(dtype=np.complex128)
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
        return { "simulator": "cirq", "error": str(e) }

# --- NEW ENDPOINT ---
@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    """
    Accepts QASM, simulates it for n_shots, and returns counts
    using the Pytket Backend path.
    """
    print(f"Received measured circuit data for Cirq simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        
        # 1. Instantiate the Pytket backend for sampling
        backend = CirqStateSampleBackend()
        
        # 2. Compile with optimization_level=0
        compiled_circ = backend.get_compiled_circuit(tk_circ, 
                                                     optimisation_level=0)
        
        # 3. Process the circuit with n_shots (this is required)
        handle = backend.process_circuit(compiled_circ, 
                                          n_shots=payload.n_shots)
        
        # 4. Get the counts from the result
        counts = backend.get_result(handle).get_counts()
        
        # 5. Convert Pytket's tuple-keys (e.g., (1, 0)) to string-keys (e.g., "10")
        counts_dict = { "".join(map(str, k)): v for k, v in counts.items() }

        print("Cirq measurement simulation successful.")
        
        return {
            "simulator": "cirq",
            "counts": counts_dict
        }
    except Exception as e:
        print(f"Error during Cirq measurement simulation: {str(e)}")
        return {
            "simulator": "cirq",
            "error": str(e)
        }