# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
import numpy as np
import time
import gc
import traceback
import warnings

warnings.filterwarnings("ignore", message=".*kahypar.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*optuna.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*cmaes.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*nevergrad.*", category=UserWarning)

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

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Quimb statevector simulation.")
    if not QUIMB_AVAILABLE:
        return runner_error("quimb", "Quimb is not installed in this environment.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        circ = _compile(payload["circuit_data"], payload.get("optimization_level", 0))
        transpiled_qasm = _preprocess_qasm(payload["circuit_data"])
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            sv = _run_sv(circ)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(
            f"Quimb simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return statevector_result(
            simulator="quimb", statevector=sv, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="msb",
            theoretical_mb=None,
            preprocessing_applied=["_preprocess_qasm(): Strips 'barrier', 'measure', and 'creg' statements from the QASM source, as quimb's tensor-network QASM parser does not support these instructions."],
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Quimb simulation: {str(e)}\n{traceback.format_exc()}")
        return runner_error("quimb", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received circuit data for Quimb measurement simulation.")
    if not QUIMB_AVAILABLE:
        return runner_error("quimb", "Quimb is not installed in this environment.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        circ = _compile(payload["circuit_data"], payload.get("optimization_level", 0))
        transpiled_qasm = _preprocess_qasm(payload["circuit_data"])
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        n_shots = payload.get("n_shots", 1024)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            # seed=None keeps quimb's default non-deterministic sampling.
            counts_counter = circ.simulate_counts(C=n_shots, seed=payload.get("seed"))
            counts = dict(counts_counter)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(
            f"Quimb measurement simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return counts_result(
            simulator="quimb", counts=counts, sampling_method="tn_sample",
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="msb", theoretical_mb=None,
            preprocessing_applied=["_preprocess_qasm(): Strips 'barrier', 'measure', and 'creg' statements from the QASM source, as quimb's tensor-network QASM parser does not support these instructions."],
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Quimb measurement simulation: {str(e)}\n{traceback.format_exc()}")
        return runner_error("quimb", e)

register_runner_endpoints(app, process_run, process_run_measured)

logger.info("Quimb runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Quimb")
