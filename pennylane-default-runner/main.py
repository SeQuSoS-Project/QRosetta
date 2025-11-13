from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, calculate_theoretical_memory_mb
import pennylane as qml
import numpy as np
import functools
import time

app = FastAPI(title="Pennylane Default Runner")

# --- Helper Function (Unchanged) ---
def get_num_qubits_from_qasm(qasm_string: str) -> int:
    for line in qasm_string.split('\n'):
        if line.strip().startswith("qreg"):
            try:
                return int(line.split('[')[1].split(']')[0])
            except Exception:
                pass
    raise ValueError("Could not determine number of qubits from QASM.")


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print("Received statevector circuit data for Pennylane-Default simulation.")
    try:
        qasm_op = qml.from_qasm(payload.circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        dev = qml.device("default.qubit", wires=num_qubits, shots=None)

        @functools.partial(qml.compile, pipeline=[])
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state()

        with MemoryMonitor(interval=0.001) as monitor:
            start_time = time.perf_counter()
            
            statevector = statevector_circuit()
            
            end_time = time.perf_counter()
        
        execution_time = end_time - start_time
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(num_qubits)

        statevector_str = [str(c) for c in statevector]

        print(f"Pennylane-Default simulation successful in {execution_time:.4f}s.")

        return {
            "simulator": "pennylane-default",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        print(f"Error during Pennylane-Default simulation: {str(e)}")
        return {
            "simulator": "pennylane-default",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "theoretical_memory_mb": 0.0,
            "process_peak_mb": 0.0
        }


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    print("Received measured circuit data for Pennylane-Default (manual sampling).")
    try:
        qasm_op = qml.from_qasm(payload.circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        dev = qml.device("default.qubit", wires=num_qubits, shots=None)

        @functools.partial(qml.compile, pipeline=[])
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state() 

        with MemoryMonitor(interval=0.001) as monitor:
            start_time = time.perf_counter()
            
            statevector = statevector_circuit()
            
            end_time = time.perf_counter()

        execution_time = end_time - start_time
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(num_qubits)
        
        counts_dict = _sample_from_statevector(statevector, 
                                               payload.n_shots, 
                                               num_qubits)

        print(f"Pennylane-Default manual sampling successful in {execution_time:.4f}s.")

        return {
            "simulator": "pennylane-default",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        print(f"Error during Pennylane-Default measurement simulation: {str(e)}")
        return {
            "simulator": "pennylane-default",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "theoretical_memory_mb": 0.0,
            "process_peak_mb": 0.0
        }