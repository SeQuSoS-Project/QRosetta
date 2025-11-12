from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq  
import cirq
from pytket.extensions.cirq.backends.cirq import CirqStateSampleBackend
import time
import psutil
import os
import gc

app = FastAPI(title="Cirq Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for Cirq simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        cirq_circ = tk_to_cirq(tk_circ)
        simulator = cirq.Simulator(dtype=np.complex128)
        
        process = psutil.Process(os.getpid())
        gc.collect()
        mem_before = process.memory_info().rss
        
        start_time = time.perf_counter()
        
        result = simulator.simulate(cirq_circ)
        statevector = result.final_state_vector
        
        end_time = time.perf_counter()
        mem_after = process.memory_info().rss
        
        execution_time = end_time - start_time
        memory_usage_mb = (mem_after - mem_before) / (1024 * 1024)
        
        statevector_str = [str(c) for c in statevector]
        print(f"Cirq simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "cirq",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb
        }
    except Exception as e:
        print(f"Error during Cirq simulation: {str(e)}")
        return { 
            "simulator": "cirq", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    print(f"Received measured circuit data for Cirq simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = CirqStateSampleBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, 
                                                     optimisation_level=0)
        
        process = psutil.Process(os.getpid())
        gc.collect()
        mem_before = process.memory_info().rss
        
        start_time = time.perf_counter()
        
        handle = backend.process_circuit(compiled_circ, 
                                         n_shots=payload.n_shots)
        counts = backend.get_result(handle).get_counts()
        
        end_time = time.perf_counter()
        mem_after = process.memory_info().rss
        
        execution_time = end_time - start_time
        memory_usage_mb = (mem_after - mem_before) / (1024 * 1024)
        
        counts_dict = { "".join(map(str, k)): v for k, v in counts.items() }

        print(f"Cirq measurement simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "cirq",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb
        }
    except Exception as e:
        print(f"Error during Cirq measurement simulation: {str(e)}")
        return {
           "simulator": "cirq",
           "error": str(e),
           "execution_time_sec": 0.0,
           "memory_usage_mb": 0.0
        }