from fastapi import FastAPI
import numpy as np
import pytket.qasm
from pytket.extensions.quest import QuESTBackend
from collections import Counter
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector
import time

app = FastAPI(title="QuEST Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for QuEST simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = QuESTBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        start_time = time.perf_counter()
        handle = backend.process_circuit(compiled_circ) 
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        statevector = backend.get_result(handle).get_state()
        statevector_str = [str(c) for c in statevector]
        print(f"QuEST simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "quest",
            "statevector": statevector_str,
            "execution_time_sec": execution_time
        }
    except Exception as e:
        print(f"Error during QuEST simulation: {str(e)}")
        return { 
            "simulator": "quest", 
            "error": str(e),
            "execution_time_sec": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    print(f"Received measured circuit data for QuEST (manual sampling).")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        
        backend = QuESTBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        start_time = time.perf_counter()
        handle = backend.process_circuit(compiled_circ)
        statevector = backend.get_result(handle).get_state()
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        counts_dict = _sample_from_statevector(statevector, 
                                               payload.n_shots, 
                                               n_qubits)
        
        print(f"QuEST manual sampling successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "quest",
            "counts": counts_dict,
            "execution_time_sec": execution_time
        }
    except Exception as e:
        print(f"Error during QuEST measurement simulation: {str(e)}")
        return {
            "simulator": "quest",
            "error": str(e),
            "execution_time_sec": 0.0
        }