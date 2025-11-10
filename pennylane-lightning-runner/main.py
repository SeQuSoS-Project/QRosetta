from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector 
import pennylane as qml
import numpy as np
import functools
import time

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
    print("Received statevector circuit data for Pennylane simulation.")
    try:
        qasm_op = qml.from_qasm(payload.circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

        @functools.partial(qml.compile, pipeline=[])
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state()

        start_time = time.perf_counter()
        statevector = statevector_circuit()
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        statevector_str = [str(c) for c in statevector]

        print(f"Pennylane statevector simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "pennylane",
            "statevector": statevector_str,
            "execution_time_sec": execution_time
        }
    except Exception as e:
        print(f"Error during Pennylane statevector simulation: {str(e)}")
        return {
            "simulator": "pennylane", 
            "error": str(e),
            "execution_time_sec": 0.0
        }


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    print("Received measured circuit data for Pennylane (manual sampling).")
    try:
        qasm_op = qml.from_qasm(payload.circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

        @functools.partial(qml.compile, pipeline=[])
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state() 

        start_time = time.perf_counter()
        statevector = statevector_circuit()
        end_time = time.perf_counter()
        execution_time = end_time - start_time

        counts_dict = _sample_from_statevector(statevector, 
                                               payload.n_shots, 
                                               num_qubits)

        print(f"Pennylane manual sampling successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "pennylane",
            "counts": counts_dict,
            "execution_time_sec": execution_time
        }
    except Exception as e:
        print(f"Error during Pennylane measurement simulation: {str(e)}")
        return {
            "simulator": "pennylane", 
            "error": str(e),
            "execution_time_sec": 0.0
        }