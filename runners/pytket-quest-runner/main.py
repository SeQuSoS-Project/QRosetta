from fastapi import FastAPI
import numpy as np
import pytket.qasm
from pytket.extensions.quest import QuESTBackend
from collections import Counter
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb
import time
import gc

app = FastAPI(title="QuEST Runner")
logger = get_logger("pytket-quest-runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info("Received circuit data for QuEST simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        backend = QuESTBackend()
        opt_level = min(payload.optimization_level, 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = backend.process_circuit(compiled_circ)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            handle = backend.process_circuit(compiled_circ)
            statevector = backend.get_result(handle).get_state()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(np.array(statevector))
        logger.info(f"QuEST simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "quest",
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
        logger.error(f"Error during QuEST simulation: {str(e)}")
        return { 
            "simulator": "quest", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info("Received measured circuit data for QuEST (manual sampling).")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        
        backend = QuESTBackend()
        opt_level = min(payload.optimization_level, 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0
        
        # --- WARM-UP ---
        _ = backend.process_circuit(compiled_circ)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            
            # --- SIMULATION ---
            t2 = time.perf_counter()
            handle = backend.process_circuit(compiled_circ)
            statevector = backend.get_result(handle).get_state()
            
            # --- BENCHMARKING FIX: Sampling is now timed ---
            counts_dict = _sample_from_statevector(statevector, payload.n_shots, n_qubits)
            t3 = time.perf_counter()
            simulation_time = t3 - t2
        
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        
        execution_time = compilation_time + simulation_time

        logger.info(f"QuEST manual sampling successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        
        return {
            "simulator": "quest",
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
        logger.error(f"Error during QuEST measurement simulation: {str(e)}")
        return {
            "simulator": "quest",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }