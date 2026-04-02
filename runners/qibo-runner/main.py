from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector
import numpy as np
import time
import gc

from qibo.models import Circuit
from qibo import gates, set_backend

set_backend("numpy")

logger = get_logger("qibo-runner")

app = FastAPI(title="Qibo Runner")


def _parse(qasm_str: str) -> Circuit:
    """Parse QASM 2.0 into a Qibo Circuit."""
    return Circuit.from_qasm(qasm_str)


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info("Received circuit data for Qibo simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circuit = _parse(payload.circuit_data)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        circuit()

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            result = circuit()
            statevector = np.array(result.state())
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(statevector)
        logger.info(
            f"Qibo simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "qibo",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Qibo simulation: {str(e)}")
        return {
            "simulator": "qibo",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info("Received measured circuit data for Qibo simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circuit = _parse(payload.circuit_data)
        # Ensure all qubits are measured (add terminal measurement if absent)
        if not circuit.measurements:
            circuit.add(gates.M(*range(circuit.nqubits)))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        circuit(nshots=payload.n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            result = circuit(nshots=payload.n_shots)
            counts_dict = dict(result.frequencies())
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        logger.info(
            f"Qibo measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "qibo",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Qibo measurement simulation: {str(e)}")
        return {
            "simulator": "qibo",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }
