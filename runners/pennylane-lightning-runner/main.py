from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, get_logger, encode_statevector, check_qubits_limit, get_num_qubits_from_qasm, theoretical_statevector_mb
import pennylane as qml
import numpy as np
import functools
import time
import gc

app = FastAPI(title="Pennylane Lightning Runner")
logger = get_logger("pennylane-lightning-runner")

@app.post("/run")
def run_circuit(payload: CircuitPayload):
    logger.info("Received statevector circuit data for Pennylane-Lightning simulation.")
    try:
        check_qubits_limit(payload.circuit_data, 24)

        # --- COMPILATION (includes first JIT trace) ---
        t0 = time.perf_counter()
        qasm_op = qml.from_qasm(payload.circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

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

        # First call triggers actual JIT compilation — attributed to compile phase
        _ = statevector_circuit()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP (second call, circuit already JIT-compiled) ---
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

        logger.info(f"Pennylane-Lightning statevector simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "pennylane-lightning",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(num_qubits)
        }
    except Exception as e:
        logger.error(f"Error during Pennylane-Lightning statevector simulation: {str(e)}")
        return {
            "simulator": "pennylane-lightning", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }


@app.post("/run_measured")
def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info("Received measured circuit data for Pennylane-Lightning (manual sampling).")
    try:
        check_qubits_limit(payload.circuit_data, 24)

        # --- COMPILATION (includes first JIT trace) ---
        t0 = time.perf_counter()
        qasm_op = qml.from_qasm(payload.circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

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

        # First call triggers actual JIT compilation — attributed to compile phase
        _ = statevector_circuit()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP (second call, circuit already JIT-compiled) ---
        _ = statevector_circuit()

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            statevector = statevector_circuit()
            counts_dict = _sample_from_statevector(statevector, payload.n_shots, num_qubits)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

        logger.info(f"Pennylane-Lightning manual sampling successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "pennylane-lightning",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(num_qubits)
        }
    except Exception as e:
        logger.error(f"Error during Pennylane-Lightning measurement simulation: {str(e)}")
        return {
            "simulator": "pennylane-lightning", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }