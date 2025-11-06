from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector 
import pennylane as qml
import numpy as np
import functools # <-- We still need this

app = FastAPI(title="Pennylane Runner")

# --- Helper Function ---
def get_num_qubits_from_qasm(qasm_string: str) -> int:
    """A simple helper to find the number of qubits in a QASM string."""
    for line in qasm_string.split('\n'):
        if line.strip().startswith("qreg"):
            try:
                # e.g., "qreg q[3];"
                return int(line.split('[')[1].split(']')[0])
            except Exception:
                pass
    raise ValueError("Could not determine number of qubits from QASM.")


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """
    Accepts QASM, simulates for statevector, and returns it.
    """
    print("Received statevector circuit data for Pennylane simulation.")
    try:
        qasm_op = qml.from_qasm(payload.circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

        # --- THIS IS THE FIX ---
        # Pass an empty pipeline to truly disable optimization,
        # the equivalent of optimization_level=0.
        @functools.partial(qml.compile, pipeline=[])
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state()

        statevector = statevector_circuit()
        statevector_str = [str(c) for c in statevector]

        print("Pennylane statevector simulation successful.")
        
        return {
            "simulator": "pennylane",
            "statevector": statevector_str
        }
    except Exception as e:
        print(f"Error during Pennylane statevector simulation: {str(e)}")
        return {"simulator": "pennylane", "error": str(e)}


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    """
    Accepts QASM, simulates for statevector, and samples manually.
    """
    print("Received measured circuit data for Pennylane (manual sampling).")
    try:
        # 1. Load the QASM string
        qasm_op = qml.from_qasm(payload.circuit_data)

        # 2. Get the *actual* number of qubits
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)

        # 3. Create the device with the *correct* number of wires
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

        # 4. Define the QNode
        # --- THIS IS THE FIX ---
        # Pass an empty pipeline to truly disable optimization,
        # the equivalent of optimization_level=0.
        @functools.partial(qml.compile, pipeline=[])
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state() 

        # 5. Execute the QNode
        statevector = statevector_circuit()

        # 6. Manually sample from the statevector (using shared helper)
        counts_dict = _sample_from_statevector(statevector, 
                                               payload.n_shots, 
                                               num_qubits)

        print("Pennylane manual sampling successful.")
        
        return {
            "simulator": "pennylane",
            "counts": counts_dict
        }
    except Exception as e:
        print(f"Error during Pennylane measurement simulation: {str(e)}")
        return {"simulator": "pennylane", "error": str(e)}