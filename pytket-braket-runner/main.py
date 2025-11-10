from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
import numpy as np
import pytket.qasm
from pytket.extensions.braket import BraketBackend
import time

app = FastAPI(title="Braket Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for Braket simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = BraketBackend(local=True)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        start_time = time.perf_counter()
        handle = backend.process_circuit(compiled_circ)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        statevector = backend.get_result(handle).get_state()
        statevector_str = [str(c) for c in statevector]
        
        print(f"Braket simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "braket",
            "statevector": statevector_str,
            "execution_time_sec": execution_time
        }
    except Exception as e:
        print(f"Error during Braket simulation: {str(e)}")
        return { 
            "simulator": "braket", 
            "error": str(e),
            "execution_time_sec": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    print(f"Received measured circuit data for Braket simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = BraketBackend(local=True)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=0)
        
        start_time = time.perf_counter()
        handle = backend.process_circuit(compiled_circ, 
                                         n_shots=payload.n_shots)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        counts = backend.get_result(handle).get_counts()
        counts_dict = { "".join(map(str, k)): v for k, v in counts.items() }

        print(f"Braket measurement simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "braket",
            "counts": counts_dict,
            "execution_time_sec": execution_time
        }
    except Exception as e:
        print(f"Error during Braket measurement simulation: {str(e)}")
        return {
            "simulator": "braket",
            "error": str(e),
            "execution_time_sec": 0.0
        }