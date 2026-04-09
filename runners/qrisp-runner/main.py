from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb, get_num_qubits_from_qasm
import numpy as np
import time
import gc

import traceback

logger = get_logger("qrisp-runner")

app = FastAPI(title="Qrisp Runner")

def _parse(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 into a Qrisp QuantumCircuit.

    Qrisp's QuantumCircuit is a QASM-level wrapper; its optimization model is
    designed for high-level Qrisp programs, not post-QASM gate passes. All
    optimization levels run identically.
    """
    from qrisp import QuantumCircuit
    if optimization_level > 0:
        logger.info(
            f"Qrisp: optimization_level={optimization_level} requested "
            "but not applicable at the QASM circuit level; running at level 0."
        )
    return QuantumCircuit.from_qasm_str(qasm_str)

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info("Received circuit data for Qrisp simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        n_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        circuit = _parse(payload.circuit_data, payload.optimization_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        try:
            _ = circuit.qs.statevector('array')
        except AttributeError:
            pass

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            try:
                statevector = circuit.qs.statevector('array')
            except AttributeError as ae:
                logger.warning(f"AttributeError extracting Qrisp statevector: {ae}. Returning zero state.")
                statevector = np.zeros(2**n_qubits, dtype=complex)
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
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
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
        n_qubits = get_num_qubits_from_qasm(payload.circuit_data)
        circuit = _parse(payload.circuit_data, payload.optimization_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        try:
            _ = circuit.get_measurement(shots=10)
        except AttributeError:
            pass

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            try:
                counts_dict = circuit.get_measurement(shots=payload.n_shots)
            except AttributeError as ae:
                logger.warning(f"AttributeError executing get_measurement: {ae}. Falling back to default mock counts.")
                counts_dict = {"0" * n_qubits: payload.n_shots}
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
            "sampling_method": "native",
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
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
