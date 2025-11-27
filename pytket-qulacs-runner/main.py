from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, calculate_theoretical_memory_mb, get_logger, encode_statevector
import numpy as np
import pytket.qasm
from pytket.extensions.qulacs import QulacsBackend
import time
import gc

logger = get_logger("pytket-qulacs-runner")

app = FastAPI(title="Qulacs Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info(f"Received circuit data for Qulacs simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = QulacsBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        # --- WARM-UP ---
        _ = backend.process_circuit(compiled_circ)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            start_time = time.perf_counter()
            
            handle = backend.process_circuit(compiled_circ) # n_shots=None
            statevector = backend.get_result(handle).get_state()
            
            end_time = time.perf_counter()
        
        execution_time = end_time - start_time
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(tk_circ.n_qubits)
        
        statevector_str = encode_statevector(np.array(statevector))
        
        logger.info(f"Qulacs simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "qulacs",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Qulacs simulation: {str(e)}")
        return { 
            "simulator": "qulacs", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "theoretical_memory_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info(f"Received measured circuit data for Qulacs simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = QulacsBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        # --- WARM-UP ---
        _ = backend.process_circuit(compiled_circ, n_shots=payload.n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            start_time = time.perf_counter()
            
            handle = backend.process_circuit(compiled_circ, 
                                             n_shots=payload.n_shots)
            counts = backend.get_result(handle).get_counts()
                                             
            end_time = time.perf_counter()
        
        execution_time = end_time - start_time
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(tk_circ.n_qubits)
        
        counts_dict = { "".join(map(str, k)): int(v) for k, v in counts.items() }

        logger.info(f"Qulacs measurement simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "qulacs",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Qulacs measurement simulation: {str(e)}")
        return {
            "simulator": "qulacs",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "theoretical_memory_mb": 0.0,
            "process_peak_mb": 0.0
        }