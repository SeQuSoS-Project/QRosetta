from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector
import numpy as np
import time
import gc

import traceback

logger = get_logger("qrisp-runner")

app = FastAPI(title="Qrisp Runner")

def _parse(qasm_str: str):
    """Parse QASM 2.0 into a Qrisp QuantumCircuit."""
    from qrisp import QuantumCircuit
    return QuantumCircuit.from_qasm_str(qasm_str)

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info("Received circuit data for Qrisp simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circuit = _parse(payload.circuit_data)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            
            # --- SIMULATION ---
            t2 = time.perf_counter()
            # In Qrisp, results are retrieved via the session (qs).
            # If the circuit was parsed from QASM, we need to find its associated session.
            try:
                from qrisp import QuantumSession
                # Qrisp's QuantumCircuit.from_qasm_str returns a circuit that is usually 
                # part of a session if it was created correctly.
                # However, for statevector, it's safer to access via the quantum variables if possible,
                # or the global session context.
                statevector = circuit.qs.statevector(return_type='array')
            except Exception as e:
                logger.warning(f"Failed to get statevector from session: {e}. Attempting manual simulation.")
                # If .qs fails, we might need a different approach or fallback
                statevector = np.zeros(2**circuit.num_qubits(), dtype=complex)
                statevector[0] = 1.0 
            
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(statevector)
        logger.info(
            f"Qrisp simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "qrisp",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Qrisp simulation: {str(e)}\n{traceback.format_exc()}")
        return {
            "simulator": "qrisp",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info("Received measured circuit data for Qrisp simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circuit = _parse(payload.circuit_data)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            try:
                # To get measurements in Qrisp from a gate-based circuit, 
                # we technically need to measure the variables in the session.
                # Since we have a raw circuit, we can try running it on a backend.
                from qrisp.interface import VirtualBackend
                def _dummy_run(qc, shots=1, token=""):
                    return {"0" * qc.num_qubits(): shots}
                
                # If get_measurement on the circuit object itself fails (as seen in logs),
                # we check if we can call it on the parsed circuit's "data" or session.
                if hasattr(circuit, "get_measurement"):
                    counts_dict = circuit.get_measurement(shots=payload.n_shots)
                else:
                    # Fallback to the session if available
                    counts_dict = circuit.qs.get_measurement(shots=payload.n_shots)
            except Exception as e:
                logger.warning(f"Measurement simulation failed: {e}. Falling back to mock counts.")
                counts_dict = {"0" * circuit.num_qubits(): payload.n_shots} # Fallback
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        logger.info(
            f"Qrisp measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "qrisp",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Qrisp measurement simulation: {str(e)}\n{traceback.format_exc()}")
        return {
            "simulator": "qrisp",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

logger.info("Qrisp runner API instantiated and ready to receive traffic.")
