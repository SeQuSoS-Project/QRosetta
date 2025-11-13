from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, calculate_theoretical_memory_mb
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq  
import cirq
from pytket.extensions.cirq.backends.cirq import CirqStateSampleBackend
from pytket.passes import RemoveBarriers
from pytket.transform import Transform
import time

app = FastAPI(title="Cirq Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for Cirq simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        RemoveBarriers().apply(tk_circ)
        
        # --- COMPATIBILITY LAYER ---
        # Convert generic gates (TK1, U3) into Rx and Rz rotations.
        # Cirq's converter natively understands these specific gates.
        Transform.RebaseToRzRx().apply(tk_circ)
        # ---------------------------
        
        cirq_circ = tk_to_cirq(tk_circ)
        simulator = cirq.Simulator(dtype=np.complex128)
        
        with MemoryMonitor(interval=0.001) as monitor:
            start_time = time.perf_counter()
            
            result = simulator.simulate(cirq_circ)
            statevector = result.final_state_vector
            
            end_time = time.perf_counter()
        
        execution_time = end_time - start_time
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(tk_circ.n_qubits)
        
        statevector_str = [str(c) for c in statevector]
        print(f"Cirq simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "cirq",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        print(f"Error during Cirq simulation: {str(e)}")
        return { 
            "simulator": "cirq", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "theoretical_memory_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    print(f"Received measured circuit data for Cirq simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        RemoveBarriers().apply(tk_circ)
        
        # --- COMPATIBILITY LAYER ---
        Transform.RebaseToRzRx().apply(tk_circ)
        # ---------------------------
        
        backend = CirqStateSampleBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        with MemoryMonitor(interval=0.001) as monitor:
            start_time = time.perf_counter()
            
            handle = backend.process_circuit(compiled_circ, n_shots=payload.n_shots)
            counts = backend.get_result(handle).get_counts()
            
            end_time = time.perf_counter()
        
        execution_time = end_time - start_time
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(tk_circ.n_qubits)
        
        counts_dict = { "".join(map(str, k)): v for k, v in counts.items() }

        print(f"Cirq measurement simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "cirq",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        print(f"Error during Cirq measurement simulation: {str(e)}")
        return {
           "simulator": "cirq",
           "error": str(e),
           "execution_time_sec": 0.0,
           "memory_usage_mb": 0.0,
           "theoretical_memory_mb": 0.0,
           "process_peak_mb": 0.0
        }