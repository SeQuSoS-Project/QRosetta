from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, get_logger, encode_statevector
import pennylane as qml
import numpy as np
import functools
import time
import gc

app = FastAPI(title="Pennylane Default Runner")
logger = get_logger("pennylane-default-runner")

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
    logger.info("Received statevector circuit data for Pennylane-Default simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        qasm_op = qml.from_qasm(payload.circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        dev = qml.device("default.qubit", wires=num_qubits, shots=None)

        # Optimization Pipeline
        level = payload.optimization_level
        passes = []
        if level == 1:
            passes = [qml.transforms.cancel_inverses]
        elif level == 2:
            passes = [qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
        elif level >= 3:
            passes = [qml.transforms.commute_controlled, qml.transforms.cancel_inverses, qml.transforms.merge_rotations]

        @functools.partial(qml.compile, pipeline=passes)
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = statevector_circuit()

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            
            # --- SIMULATION ---
            t2 = time.perf_counter()
            statevector = statevector_circuit()
            t3 = time.perf_counter()
            simulation_time = t3 - t2
        
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(np.array(statevector))

        logger.info(f"Pennylane-Default simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "pennylane-default",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Pennylane-Default simulation: {str(e)}")
        return {
            "simulator": "pennylane-default",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info("Received measured circuit data for Pennylane-Default (manual sampling).")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        qasm_op = qml.from_qasm(payload.circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        dev = qml.device("default.qubit", wires=num_qubits, shots=None)

        # Optimization Pipeline
        level = payload.optimization_level
        passes = []
        if level == 1:
            passes = [qml.transforms.cancel_inverses]
        elif level == 2:
            passes = [qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
        elif level >= 3:
            passes = [qml.transforms.commute_controlled, qml.transforms.cancel_inverses, qml.transforms.merge_rotations]

        @functools.partial(qml.compile, pipeline=passes)
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state() 
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = statevector_circuit() # Warm up the JIT/Compilation if any

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            
            # --- SIMULATION ---
            t2 = time.perf_counter()
            statevector = statevector_circuit()
            # --- BENCHMARKING FIX: Sampling is now timed ---
            counts_dict = _sample_from_statevector(statevector, payload.n_shots, num_qubits)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        
        execution_time = compilation_time + simulation_time
        
        logger.info(f"Pennylane-Default manual sampling successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "pennylane-default",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Pennylane-Default measurement simulation: {str(e)}")
        return {
            "simulator": "pennylane-default",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }