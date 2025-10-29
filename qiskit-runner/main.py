from fastapi import FastAPI
from pydantic import BaseModel

# --- Our Core Quantum Imports ---
import pytket.qasm
from pytket.extensions.qiskit import tk_to_qiskit
from qiskit_aer import AerSimulator
# --- ---

# Create the FastAPI application
app = FastAPI(title="Qiskit Runner")

# This Pydantic model defines the "shape" of our input data.
# We expect a JSON object like: {"circuit_data": "..."}
class CircuitPayload(BaseModel):
    circuit_data: str 

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    """
    Accepts a QASM string, converts it using Pytket, 
    simulates it on Qiskit Aer, and returns the statevector.
    """
    print(f"Received circuit data for simulation.")
    
    # We wrap all logic in a try...except block to catch errors
    try:
        # Step 1: "Deserialize" the QASM string.
        # This turns the plain text QASM into a Pytket circuit object.
        # This is the updated function name from our verification.
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        
        # Step 2: "Translate" the circuit.
        # This converts the general Pytket object into a Qiskit-specific object.
        qiskit_circ = tk_to_qiskit(tk_circ)
        
        # Step 3: "Instruct" the simulator.
        # It tells Qiskit "I want the final statevector,
        # not just measurement counts."
        qiskit_circ.save_statevector()
        
        # Step 4: "Get" the simulator.
        # We load the modern AerSimulator.
        backend = AerSimulator()
        
        # Step 5: "Run" the simulation.
        job = backend.run(qiskit_circ)
        result = job.result()
        
        # Step 6: "Extract" the final statevector.
        statevector = result.get_statevector()
        
        # Step 7: "Format" the output.
        # JSON can't handle Python's complex numbers, so we convert them to strings.
        statevector_str = [str(c) for c in statevector]
        
        print("Simulation successful.")
        
        # This is the JSON response we send back to the 'rosetta-api'
        return {
            "simulator": "qiskit",
            "statevector": statevector_str
        }

    except Exception as e:
        # If any step fails, report the error.
        print(f"Error during simulation: {str(e)}")
        return {
            "simulator": "qiskit",
            "error": str(e)
        }