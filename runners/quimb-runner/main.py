# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, runner_error, with_sdk_versions,
)
import numpy as np
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

_PREPROCESS_NOTE = (
    "_preprocess_qasm(): Strips 'barrier', 'measure', and 'creg' statements from the QASM "
    "source, as quimb's tensor-network QASM parser does not support these instructions.")


def _preprocess_qasm(qasm_str: str) -> str:
    """Strip barrier and measure/creg lines — quimb's parser does not support them."""
    cleaned = []
    for line in qasm_str.splitlines():
        s = line.strip()
        if s.startswith('barrier') or s.startswith('measure') or s.startswith('creg'):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


def _compile(payload: dict) -> CompileResult:
    """Parse cleaned QASM 2.0 into a quimb Circuit.

    Quimb represents circuits as tensor networks; optimization is an internal
    contraction path problem, not a circuit-level gate pass. No user-configurable
    circuit optimization is available through the standard quimb API.
    """
    optimization_level = payload.get("optimization_level", 0)
    if optimization_level > 0:
        logger.info(
            f"Quimb: optimization_level={optimization_level} requested "
            "but not applicable to tensor-network simulation; using default contraction."
        )
    cleaned = _preprocess_qasm(payload["circuit_data"])
    return CompileResult(
        circuit=qtn.Circuit.from_openqasm2_str(cleaned),
        preprocessing_applied=[_PREPROCESS_NOTE],
        transpiled_qasm=cleaned)


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Quimb statevector simulation.")
    if not QUIMB_AVAILABLE:
        return runner_error("quimb", "Quimb is not installed in this environment.")

    def execute(compiled, _payload):
        """Contract the tensor network and return the statevector as a numpy array."""
        return np.asarray(compiled.circuit.to_dense()).flatten()

    return run_statevector_job(
        simulator="quimb", payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, qubit_ordering="msb", theoretical_mb=None)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received circuit data for Quimb measurement simulation.")
    if not QUIMB_AVAILABLE:
        return runner_error("quimb", "Quimb is not installed in this environment.")

    def execute(compiled, payload):
        # seed=None keeps quimb's default non-deterministic sampling.
        counts = compiled.circuit.simulate_counts(
            C=payload.get("n_shots", 1024), seed=payload.get("seed"))
        return dict(counts), "tn_sample"

    return run_measured_job(
        simulator="quimb", payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, qubit_ordering="msb", theoretical_mb=None)


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("Quimb runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Quimb")
