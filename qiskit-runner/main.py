from fastapi import FastAPI
from pydantic import BaseModel
import pytket.qasm
from pytket.extensions.qiskit import tk_to_qiskit
from qiskit_aer import AerSimulator
from qiskit.circuit import QuantumCircuit

app = FastAPI(title="Qiskit Runner")

class CircuitPayload(BaseModel):
    circuit_data: str 

# --- NEW PAYLOAD ---
class MeasuredCircuitPayload(BaseModel):
    circuit_data: str
    n_shots: int

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """ (This is your existing, unchanged statevector endpoint) """
    # ... (existing code, no changes) ...
    print(f"Received circuit data for simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        qiskit_circ = tk_to_qiskit(tk_circ)
        qiskit_circ.save_statevector()
        backend = AerSimulator(precision="double")
        job = backend.run(qiskit_circ, optimization_level=0)
        result = job.result()
        statevector = result.get_statevector()
        statevector_str = [str(c) for c in statevector]
        print("Simulation successful.")
        return {
            "simulator": "qiskit",
            "statevector": statevector_str
        }
    except Exception as e:
        print(f"Error during simulation: {str(e)}")
        return { "simulator": "qiskit", "error": str(e) }

# --- NEW ENDPOINT ---
@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    """
    Accepts QASM, simulates it for n_shots, and returns counts.
    """
    print(f"Received measured circuit data for simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        qiskit_circ = tk_to_qiskit(tk_circ)
        
        # We DO NOT call qiskit_circ.save_statevector()
        
        backend = AerSimulator(precision="double")
        
        # We run with optimization_level=0 and the specified number of shots
        job = backend.run(qiskit_circ, 
                          optimization_level=0, 
                          shots=payload.n_shots)
        
        result = job.result()
        counts = result.get_counts() # This returns a dict
        
        # Qiskit's counts keys are hex strings (e.g., '0x1') or binary
        # strings '01'. We must standardize them to binary bitstrings.
        # We also need to know the number of classical bits to pad with zeros.
        num_clbits = qiskit_circ.num_clbits
        
        counts_dict = {}
        if num_clbits > 0:
            for k, v in counts.items():
                if k.startswith('0x'):
                    # It's a hex key, convert it
                    binary_key = format(int(k, 16), f'0{num_clbits}b')
                else:
                    # It's already a binary string, just pad it
                    binary_key = k.zfill(num_clbits)
                counts_dict[binary_key] = v
        else:
            counts_dict = counts # Fallback if no classical bits

        print("Measurement simulation successful.")
        
        return {
            "simulator": "qiskit",
            "counts": counts_dict
        }
    except Exception as e:
        print(f"Error during measurement simulation: {str(e)}")
        return {
            "simulator": "qiskit",
            "error": str(e)
        }