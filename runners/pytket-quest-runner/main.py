# Execution script for the quantum simulator runner.

from fastapi import FastAPI
import pytket.qasm
from pytket.extensions.quest import QuESTBackend
from qrosetta_commons.helpers import (
    CompileResult, _counts_from_samples, _draw_statevector_samples, get_logger, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, with_sdk_versions,
)
from pytket.passes import RemoveBarriers

app = FastAPI(title="QuEST Runner")
logger = get_logger("pytket-quest-runner")

_REMOVE_BARRIERS_NOTE = (
    "pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to "
    "prevent parsing failures in the QuEST backend adapter.")


def _compile(payload: dict) -> CompileResult:
    tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
    preprocessing_applied = []
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)

    backend = QuESTBackend()
    opt_level = min(payload.get("optimization_level", 0), 2)
    compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
    if opt_level > 0:
        preprocessing_applied.append(
            f"pytket QuESTBackend.get_compiled_circuit(level={opt_level}): pytket's native "
            "compilation pass for the QuEST backend, decomposing gates into the backend's "
            "supported gate set.")

    return CompileResult(
        circuit=(backend, compiled_circ, tk_circ),
        n_qubits=tk_circ.n_qubits,
        preprocessing_applied=preprocessing_applied)


def _serialize(compiled: CompileResult) -> str:
    return pytket.qasm.circuit_to_qasm_str(compiled.circuit[-1])


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for QuEST simulation.")

    def execute(compiled, _payload):
        backend, compiled_circ, _ = compiled.circuit
        handle = backend.process_circuit(compiled_circ)
        return backend.get_result(handle).get_state()

    return run_statevector_job(
        simulator="quest", payload=payload, logger=logger, compile_fn=_compile,
        serialize_fn=_serialize, execute_fn=execute, qubit_ordering="msb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for QuEST (manual sampling).")

    def execute(compiled, payload):
        backend, compiled_circ, _ = compiled.circuit
        handle = backend.process_circuit(compiled_circ)
        statevector = backend.get_result(handle).get_state()
        # QuEST exposes the statevector but no native shot sampler here, so shots come from
        # sampling that statevector.
        return _draw_statevector_samples(
            statevector, payload.get("n_shots", 1024), payload.get("seed"))

    def shape_counts(samples, compiled, _payload):
        return _counts_from_samples(samples, compiled.n_qubits), "sv_sample"

    return run_measured_job(
        simulator="quest", payload=payload, logger=logger, compile_fn=_compile,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "QuEST")
