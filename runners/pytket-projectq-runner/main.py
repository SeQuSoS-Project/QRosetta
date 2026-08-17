# Execution script for the quantum simulator runner.

from fastapi import FastAPI
import pytket.qasm
from pytket.extensions.projectq import ProjectQBackend
from pytket.passes import RemoveBarriers
from pytket.transform import Transform
from qrosetta_commons.helpers import (
    CompileResult, _sample_from_statevector, get_logger, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, with_sdk_versions,
)

app = FastAPI(title="ProjectQ Runner")
logger = get_logger("pytket-projectq-runner")

from projectq.types._qubit import Qubit

_original_del = Qubit.__del__

def _quiet_del(self):
    try:
        _original_del(self)
    except RuntimeError as e:
        if "Qubit has not been measured / uncomputed" in str(e):

            pass
        else:
            raise e

Qubit.__del__ = _quiet_del

_REMOVE_BARRIERS_NOTE = (
    "pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to "
    "prevent parsing failures in the backend adapter.")


def _compile(payload: dict) -> CompileResult:
    tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
    preprocessing_applied = []
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)

    # Serialized inside the compilation window: RebaseToTket rewrites tk_circ in place
    # below, so capturing afterwards would record the rebased form instead.
    transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_circ)

    Transform.RebaseToTket().apply(tk_circ)

    backend = ProjectQBackend()
    opt_level = min(payload.get("optimization_level", 0), 2)
    compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)

    return CompileResult(
        circuit=(backend, compiled_circ),
        n_qubits=tk_circ.n_qubits,
        preprocessing_applied=preprocessing_applied,
        transpiled_qasm=transpiled_qasm)


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for ProjectQ simulation.")

    def execute(compiled, _payload):
        backend, compiled_circ = compiled.circuit
        handle = backend.process_circuit(compiled_circ)
        return backend.get_result(handle).get_state()

    return run_statevector_job(
        simulator="projectq", payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, qubit_ordering="lsb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for ProjectQ (manual sampling).")

    def execute(compiled, payload):
        backend, compiled_circ = compiled.circuit
        handle = backend.process_circuit(compiled_circ)
        statevector = backend.get_result(handle).get_state()
        counts = _sample_from_statevector(
            statevector, payload.get("n_shots", 1024), compiled.n_qubits, payload.get("seed"))
        # This runner does not label a sampling_method (None omits the key).
        return counts, None

    return run_measured_job(
        simulator="projectq", payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, qubit_ordering="lsb")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "ProjectQ")
