from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq  
import cirq
from pytket.extensions.cirq.backends.cirq import CirqStateSampleBackend
import time

app = FastAPI(title="Cirq Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    print(f"Received circuit data for Cirq simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        cirq_circ = tk_to_cirq(tk_circ)
        simulator = cirq.Simulator(dtype=np.complex128)
        
        start_time = time.perf_counter()
        result = simulator.simulate(cirq_circ)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        statevector = result.final_state_vector
        statevector_str = [str(c) for c in statevector]
        print(f"Cirq simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "cirq",
            "statevector": statevector_str,
            "execution_time_sec": execution_time
        }
    except Exception as e:
        print(f"Error during Cirq simulation: {str(e)}")
        return { 
            "simulator": "cirq", 
            "error": str(e),
            "execution_time_sec": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    print(f"Received measured circuit data for Cirq simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        backend = CirqStateSampleBackend()
        compiled_circ = backend.get_compiled_circuit(tk_circ, 
                                                     optimisation_level=0)
        
        start_time = time.perf_counter()
        handle = backend.process_circuit(compiled_circ, 
                                         n_shots=payload.n_shots)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        
        counts = backend.get_result(handle).get_counts()
        counts_dict = { "".join(map(str, k)): v for k, v in counts.items() }

        print(f"Cirq measurement simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "cirq",
            "counts": counts_dict,
            "execution_time_sec": execution_time
        }
    except Exception as e:
        print(f"Error during Cirq measurement simulation: {str(e)}")
        return {
           "simulator": "cirq",
           "error": str(e),
           "execution_time_sec": 0.0
        }