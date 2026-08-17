# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, with_sdk_versions,
)
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq
import cirq
from pytket.extensions.cirq.backends.cirq import CirqStateSampleBackend
from pytket.passes import RemoveBarriers, auto_rebase_pass
from pytket.circuit import OpType
from pytket.transform import Transform
import warnings
import logging

warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core")

logging.getLogger("root").setLevel(logging.ERROR)

class _SuppressGlobalPhaseWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "Global phase is dependent on a symbolic parameter" not in record.getMessage()

logging.getLogger().addFilter(_SuppressGlobalPhaseWarning())

logger = get_logger("pytket-cirq-runner")

app = FastAPI(title="Cirq Runner")

_REMOVE_BARRIERS_NOTE = (
    "pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to "
    "prevent parsing failures in the backend adapter.")
_REBASE_NOTE = (
    "pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Universally decomposes complex "
    "multi-qubit and single-qubit gates (like CU3, CRX) into a standard CX/Rz/Rx basis to "
    "prevent parsing failures in the backend.")


def _condition_circuit(payload: dict):
    """Parse the QASM and apply the gate-level conditioning both endpoints share."""
    tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
    preprocessing_applied = []
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        preprocessing_applied.append(_REBASE_NOTE)
    else:
        Transform.RebaseToRzRx().apply(tk_circ)
    return tk_circ, preprocessing_applied


def _serialize(compiled: CompileResult) -> str:
    return pytket.qasm.circuit_to_qasm_str(compiled.circuit[-1])


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Cirq simulation.")

    def compile_step(payload):
        tk_circ, preprocessing_applied = _condition_circuit(payload)
        cirq_circ = tk_to_cirq(tk_circ)
        simulator = cirq.Simulator(dtype=np.complex128)
        return CompileResult(
            circuit=(simulator, cirq_circ, tk_circ),
            n_qubits=tk_circ.n_qubits,
            preprocessing_applied=preprocessing_applied)

    def execute(compiled, _payload):
        simulator, cirq_circ, _ = compiled.circuit
        return simulator.simulate(cirq_circ).final_state_vector

    return run_statevector_job(
        simulator="cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, qubit_ordering="lsb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Cirq simulation.")

    def compile_step(payload):
        tk_circ, preprocessing_applied = _condition_circuit(payload)
        backend = CirqStateSampleBackend()
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
        return CompileResult(
            circuit=(backend, compiled_circ, tk_circ),
            n_qubits=tk_circ.n_qubits,
            preprocessing_applied=preprocessing_applied)

    def seed_rng(_compiled, payload):
        # pytket's CirqBackend ignores a seed kwarg but samples via numpy's global
        # RNG, so reproducibility is achieved by seeding numpy directly (verified).
        # seed=None leaves it non-deterministic (prior behaviour).
        if payload.get("seed") is not None:
            np.random.seed(payload["seed"])

    def execute(compiled, payload):
        backend, compiled_circ, _ = compiled.circuit
        handle = backend.process_circuit(compiled_circ, n_shots=payload.get("n_shots", 1024))
        counts = backend.get_result(handle).get_counts()
        return {"".join(map(str, k)): int(v) for k, v in counts.items()}, "native"

    return run_measured_job(
        simulator="cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, pre_execute_fn=seed_rng, execute_fn=execute,
        qubit_ordering="msb")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Cirq")
