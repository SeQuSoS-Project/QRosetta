from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
import pytket.qasm
import numpy as np
from pytket.extensions.qiskit import tk_to_qiskit
from qiskit_aer import AerSimulator
from qiskit.circuit import QuantumCircuit
from qiskit import transpile as qiskit_transpile
import time
import gc
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb

logger = get_logger("pytket-qiskit-runner")

app = FastAPI(title="Qiskit Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info(f"Received circuit data for Qiskit simulation.")
    try:
        # --- COMPILATION (includes transpilation) ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        qiskit_circ = tk_to_qiskit(tk_circ)
        if payload.optimization_level > 0:
            qiskit_circ = qiskit_transpile(qiskit_circ, optimization_level=min(payload.optimization_level, 3))
        qiskit_circ.save_statevector()
        backend = AerSimulator(precision="double")
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = backend.run(qiskit_circ, optimization_level=0)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION (circuit already transpiled — no re-compilation) ---
            t2 = time.perf_counter()
            job = backend.run(qiskit_circ, optimization_level=0)
            result = job.result()
            statevector = result.get_statevector()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(np.array(statevector))
        logger.info(f"Qiskit simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "qiskit",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
        }
    except Exception as e:
        logger.error(f"Error during Qiskit simulation: {str(e)}")
        return { 
            "simulator": "qiskit", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info(f"Received measured circuit data for Qiskit simulation.")
    try:
        # --- COMPILATION (includes transpilation) ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        qiskit_circ = tk_to_qiskit(tk_circ)
        if payload.optimization_level > 0:
            qiskit_circ = qiskit_transpile(qiskit_circ, optimization_level=min(payload.optimization_level, 3))
        backend = AerSimulator(precision="double")
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = backend.run(qiskit_circ, optimization_level=0, shots=payload.n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION (circuit already transpiled — no re-compilation) ---
            t2 = time.perf_counter()
            job = backend.run(qiskit_circ, optimization_level=0, shots=payload.n_shots)
            result = job.result()
            counts = result.get_counts()
            t3 = time.perf_counter()
            simulation_time = t3 - t2
            
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time
        
        num_clbits = qiskit_circ.num_clbits
        counts_dict = {}
        if num_clbits > 0:
            for k, v in counts.items():
                if k.startswith('0x'):
                    binary_key = format(int(k, 16), f'0{num_clbits}b')
                else:
                    binary_key = k.zfill(num_clbits)
                counts_dict[binary_key] = v
        else:
            counts_dict = counts

        logger.info(f"Qiskit measurement simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        
        return {
            "simulator": "qiskit",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
        }
    except Exception as e:
        logger.error(f"Error during Qiskit measurement simulation: {str(e)}")
        return {
            "simulator": "qiskit",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }