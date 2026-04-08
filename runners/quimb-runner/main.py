from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, get_num_qubits_from_qasm
import numpy as np
import time
import gc
import traceback

logger = get_logger("quimb-runner")

app = FastAPI(title="Quimb Runner")

try:
    import quimb.tensor as qtn
    QUIMB_AVAILABLE = True
    logger.info("Quimb loaded successfully.")
except ImportError as e:
    QUIMB_AVAILABLE = False
    logger.warning(f"Quimb import failed: {e}. Runner will return errors for all requests.")


def _preprocess_qasm(qasm_str: str) -> str:
    """Strip barrier and measure/creg lines — quimb's parser does not support them."""
    cleaned = []
    for line in qasm_str.splitlines():
        s = line.strip()
        if s.startswith('barrier') or s.startswith('measure') or s.startswith('creg'):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


def _compile(qasm_str: str, optimization_level: int = 0):
    """Parse cleaned QASM 2.0 into a quimb Circuit.

    Quimb represents circuits as tensor networks; optimization is an internal
    contraction path problem, not a circuit-level gate pass. No user-configurable
    circuit optimization is available through the standard quimb API.
    """
    if optimization_level > 0:
        logger.info(
            f"Quimb: optimization_level={optimization_level} requested "
            "but not applicable to tensor-network simulation; using default contraction."
        )
    return qtn.Circuit.from_openqasm2_str(_preprocess_qasm(qasm_str))


def _run_sv(circ) -> np.ndarray:
    """Contract the tensor network and return the statevector as a numpy array."""
    sv = circ.to_dense()
    return np.asarray(sv).flatten()


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info("Received circuit data for Quimb statevector simulation.")
    if not QUIMB_AVAILABLE:
        return {
            "simulator": "quimb",
            "error": "Quimb is not installed in this environment.",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0,
        }
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circ = _compile(payload.circuit_data, payload.optimization_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP (excluded from reported timing) ---
        _run_sv(circ)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            # --- SIMULATION ---
            t2 = time.perf_counter()
            sv = _run_sv(circ)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(sv)
        logger.info(
            f"Quimb simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "quimb",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": None
        }
    except Exception as e:
        logger.error(f"Error during Quimb simulation: {str(e)}\n{traceback.format_exc()}")
        return {
            "simulator": "quimb",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0,
        }


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info("Received circuit data for Quimb measurement simulation.")
    if not QUIMB_AVAILABLE:
        return {
            "simulator": "quimb",
            "error": "Quimb is not installed in this environment.",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0,
        }
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circ = _compile(payload.circuit_data, payload.optimization_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP (excluded from reported timing) ---
        dict(circ.simulate_counts(C=10))

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            # --- SIMULATION ---
            t2 = time.perf_counter()
            counts_counter = circ.simulate_counts(C=payload.n_shots)
            counts = dict(counts_counter)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        logger.info(
            f"Quimb measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "quimb",
            "counts": counts,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": None
        }
    except Exception as e:
        logger.error(f"Error during Quimb measurement simulation: {str(e)}\n{traceback.format_exc()}")
        return {
            "simulator": "quimb",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0,
        }


logger.info("Quimb runner API instantiated and ready to receive traffic.")
