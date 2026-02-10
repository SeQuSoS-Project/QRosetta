from fastapi import FastAPI
import numpy as np
import pytket.qasm
from pytket.extensions.projectq import ProjectQBackend
from pytket.passes import RemoveBarriers
from pytket.transform import Transform
from collections import Counter
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, get_logger, encode_statevector
import time
import gc

app = FastAPI(title="ProjectQ Runner")
logger = get_logger("pytket-projectq-runner")

# --- MONKEY PATCH: Suppress ProjectQ's noisy __del__ error ---
import projectq.types._qubit
from projectq.types._qubit import Qubit

_original_del = Qubit.__del__

def _quiet_del(self):
    try:
        _original_del(self)
    except RuntimeError as e:
        if "Qubit has not been measured / uncomputed" in str(e):
            # Log a clean warning instead of letting the exception bubble up
            pass
        else:
            raise e

Qubit.__del__ = _quiet_del
# -------------------------------------------------------------

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info("Received circuit data for ProjectQ simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        RemoveBarriers().apply(tk_circ)
        # Rebase to standard TK1/CX gateset (decomposes SWAPs automatically)
        Transform.RebaseToTket().apply(tk_circ)
        
        backend = ProjectQBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        t1 = time.perf_counter()
        compilation_time = t1 - t0
        
        # --- WARM-UP ---
        h_warm = backend.process_circuit(compiled_circ)
        _ = backend.get_result(h_warm).get_state()

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
        logger.info(f"ProjectQ simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        
        return {
            "simulator": "projectq",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during ProjectQ simulation: {str(e)}")
        return { 
            "simulator": "projectq", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info("Received measured circuit data for ProjectQ (manual sampling).")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        
        RemoveBarriers().apply(tk_circ)
        # Rebase to standard TK1/CX gateset (decomposes SWAPs automatically)
        Transform.RebaseToTket().apply(tk_circ)
        
        backend = ProjectQBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        t1 = time.perf_counter()
        compilation_time = t1 - t0
        
        # --- WARM-UP ---
        h_warm = backend.process_circuit(compiled_circ)
        _ = backend.get_result(h_warm).get_state() # ProjectQ backend returns state even for measured? Wait.

        with MemoryMonitor(interval=0.001) as monitor:
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

        logger.info(f"ProjectQ manual sampling successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        
        return {
            "simulator": "projectq",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during ProjectQ measurement simulation: {str(e)}")
        return {
            "simulator": "projectq",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }