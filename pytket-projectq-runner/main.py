from fastapi import FastAPI
import numpy as np
import pytket.qasm
from pytket.extensions.projectq import ProjectQBackend
from pytket.passes import RemoveBarriers
from pytket.transform import Transform
from collections import Counter
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, calculate_theoretical_memory_mb, get_logger
import time

logger = get_logger("pytket-projectq-runner")

app = FastAPI(title="ProjectQ Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info(f"Received circuit data for ProjectQ simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        RemoveBarriers().apply(tk_circ)
        # Rebase to standard TK1/CX gateset (decomposes SWAPs automatically)
        Transform.RebaseToTket().apply(tk_circ)
        
        backend = ProjectQBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        with MemoryMonitor(interval=0.001) as monitor:
            start_time = time.perf_counter()
            
            handle = backend.process_circuit(compiled_circ)
            statevector = backend.get_result(handle).get_state()
            
            end_time = time.perf_counter()
        
        execution_time = end_time - start_time
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(tk_circ.n_qubits)
        
        statevector_str = [str(c) for c in statevector]
        logger.info(f"ProjectQ simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "projectq",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during ProjectQ simulation: {str(e)}")
        return { 
            "simulator": "projectq", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "theoretical_memory_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info(f"Received measured circuit data for ProjectQ (manual sampling).")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        
        RemoveBarriers().apply(tk_circ)
        # Rebase to standard TK1/CX gateset (decomposes SWAPs automatically)
        Transform.RebaseToTket().apply(tk_circ)
        
        backend = ProjectQBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        with MemoryMonitor(interval=0.001) as monitor:
            start_time = time.perf_counter()
            
            handle = backend.process_circuit(compiled_circ)
            statevector = backend.get_result(handle).get_state()
            
            end_time = time.perf_counter()
        
        execution_time = end_time - start_time
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(tk_circ.n_qubits)
        
        counts_dict = _sample_from_statevector(statevector, 
                                               payload.n_shots, 
                                               n_qubits)

        logger.info(f"ProjectQ manual sampling successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "projectq",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during ProjectQ measurement simulation: {str(e)}")
        return {
            "simulator": "projectq",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "theoretical_memory_mb": 0.0,
            "process_peak_mb": 0.0
        }