"""quimb runner: simulates OpenQASM 2.0 circuits as tensor networks with quimb.tensor.Circuit."""

import importlib
import importlib.util
import re
import warnings

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main, run_measured_job,
    run_statevector_job, runner_error, strip_qasm_comments, with_sdk_versions,
)
import numpy as np

warnings.filterwarnings("ignore", message=".*kahypar.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*optuna.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*cmaes.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*nevergrad.*", category=UserWarning)

logger = get_logger("quimb-runner")

app = FastAPI(title="Quimb Runner")

QUIMB_AVAILABLE = importlib.util.find_spec("quimb") is not None
if not QUIMB_AVAILABLE:
    logger.warning("Quimb is not installed. Runner will return errors for all requests.")

_PRECISION = "complex128"
_DROPPED_STATEMENT = re.compile(r"(barrier|measure|creg)\b")

_STRIP_NOTE = (
    "_strip_unsupported_statements(): Removes every 'barrier', 'measure' and 'creg' statement "
    "(split on ';'), as quimb's QASM parser does not support them. On the measured path "
    "every qubit is sampled. Required by the adapter, applied regardless of "
    "apply_preprocessing.")
_GATE_CONTRACT_NOTE = (
    "quimb.tensor.Circuit(gate_contract='auto-split-gate') (quimb default): While parsing, "
    "each two-qubit gate is contracted into the network and split by SVD when that lowers "
    "the bond dimension. This tensor work happens during parsing and is counted in "
    "compilation_time_sec. Required by the adapter, applied regardless of "
    "apply_preprocessing.")
_SAMPLING_NOTE = (
    "quimb.tensor.Circuit.simulate_counts(): Contracts the network, samples shots and tallies "
    "them in one call, so the tally is inside simulation_time_sec.")


def _qtn():
    """Import quimb.tensor on first use, so only the process that simulates holds it."""
    return importlib.import_module("quimb.tensor")


def _strip_unsupported_statements(qasm_str: str) -> str:
    """Drop barrier/measure/creg statements, splitting after ';', '{' and '}'."""
    kept = []
    for piece in re.split(r"(?<=[;{}])", strip_qasm_comments(qasm_str)):
        s = piece.strip()
        if not s or (s.endswith(";") and _DROPPED_STATEMENT.match(s)):
            continue
        kept.append(s)
    return "\n".join(kept) + "\n"


def _reset_contraction_caches(_compiled, _payload):
    """Clear cotengra's path and expression caches so path finding is repeated each run."""
    ctg_interface = importlib.import_module("cotengra.interface")
    ctg_presets = importlib.import_module("cotengra.presets")
    ctg_interface._PATH_CACHE.clear()
    ctg_interface._CONTRACT_EXPR_CACHE.clear()
    ctg_presets.get_auto_optimizer.cache_clear()
    ctg_presets.get_auto_hq_optimizer.cache_clear()


def _compile(payload: dict, extra_notes=()) -> CompileResult:
    """Parse the cleaned QASM into a quimb Circuit.

    quimb has no circuit-level optimisation passes, so optimization_level is not applied.
    """
    optimization_level = payload.get("optimization_level", 0)
    if optimization_level > 0:
        logger.info(
            f"Quimb: optimization_level={optimization_level} requested "
            "but not applicable to tensor-network simulation; using default contraction.")
    cleaned = _strip_unsupported_statements(payload["circuit_data"])
    return CompileResult(
        circuit=_qtn().Circuit.from_openqasm2_str(cleaned),
        preprocessing_applied=[_STRIP_NOTE, _GATE_CONTRACT_NOTE, *extra_notes],
        transpiled_qasm=cleaned,
        precision=_PRECISION)


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Quimb statevector simulation.")
    if not QUIMB_AVAILABLE:
        return runner_error("quimb", "Quimb is not installed in this environment.")

    def execute(compiled, _payload):
        return compiled.circuit.to_dense()

    def shape_statevector(dense, _compiled, _payload):
        return np.asarray(dense).flatten()

    return run_statevector_job(
        simulator="quimb", payload=payload, logger=logger, compile_fn=_compile,
        pre_execute_fn=_reset_contraction_caches, execute_fn=execute,
        postprocess_fn=shape_statevector, qubit_ordering="msb", theoretical_mb=None,
        precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received circuit data for Quimb measurement simulation.")
    if not QUIMB_AVAILABLE:
        return runner_error("quimb", "Quimb is not installed in this environment.")

    def compile_step(payload):
        return _compile(payload, extra_notes=(_SAMPLING_NOTE,))

    def execute(compiled, payload):
        return compiled.circuit.simulate_counts(
            C=payload.get("n_shots", 1024), seed=payload.get("seed"))

    def shape_counts(counts, _compiled, _payload):
        return dict(counts), "tn_sample"

    return run_measured_job(
        simulator="quimb", payload=payload, logger=logger, compile_fn=compile_step,
        pre_execute_fn=_reset_contraction_caches, execute_fn=execute,
        postprocess_fn=shape_counts, qubit_ordering="msb", theoretical_mb=None,
        precision=_PRECISION)


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("Quimb runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Quimb")
