# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, _counts_from_samples, _draw_statevector_samples, get_logger, get_num_qubits_from_qasm,
    register_runner_endpoints, run_cli_main, run_measured_job, run_statevector_job,
    strip_barriers_from_qasm, with_sdk_versions,
)
import pennylane as qml
import functools

app = FastAPI(title="Pennylane Default Runner")
logger = get_logger("pennylane-default-runner")

_DEVICE = "default.qubit"
_SIMULATOR = "pennylane-default"

_STRIP_BARRIERS_NOTE = (
    "qrosetta_commons.helpers.strip_barriers_from_qasm(): Strips barrier instructions from "
    "the QASM string, as PennyLane's QASM parser does not support them.")
_CANCEL_INVERSES_NOTE = (
    "qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to "
    "reduce gate count.")
_MERGE_ROTATIONS_NOTE = (
    "qml.transforms.merge_rotations: Merges consecutive rotation gates on the same "
    "qubit/axis into a single rotation.")
_COMMUTE_CONTROLLED_NOTE = (
    "qml.transforms.commute_controlled: Pushes single-qubit gates through controlled gates "
    "to enable further cancellations.")


def _optimization_pipeline(level: int):
    """PennyLane transform pipeline for a requested optimization level, with its notes."""
    if level == 1:
        return [qml.transforms.cancel_inverses], [_CANCEL_INVERSES_NOTE]
    if level == 2:
        return ([qml.transforms.cancel_inverses, qml.transforms.merge_rotations],
                [_CANCEL_INVERSES_NOTE, _MERGE_ROTATIONS_NOTE])
    if level >= 3:
        return ([qml.transforms.commute_controlled, qml.transforms.cancel_inverses,
                 qml.transforms.merge_rotations],
                [_COMMUTE_CONTROLLED_NOTE, _CANCEL_INVERSES_NOTE, _MERGE_ROTATIONS_NOTE])
    return [], []


def _compile(payload: dict) -> CompileResult:
    circuit_data = strip_barriers_from_qasm(payload["circuit_data"])
    qasm_op = qml.from_qasm(circuit_data)
    num_qubits = get_num_qubits_from_qasm(payload["circuit_data"])
    dev = qml.device(_DEVICE, wires=num_qubits, shots=None)

    passes, notes = _optimization_pipeline(payload.get("optimization_level", 0))

    @functools.partial(qml.compile, pipeline=passes)
    @qml.qnode(dev)
    def statevector_circuit():
        qasm_op()
        return qml.state()

    return CompileResult(
        circuit=statevector_circuit,
        n_qubits=num_qubits,
        preprocessing_applied=[_STRIP_BARRIERS_NOTE] + notes,
        transpiled_qasm=circuit_data)


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info(f"Received statevector circuit data for {_SIMULATOR} simulation.")

    def execute(compiled, _payload):
        return compiled.circuit()

    return run_statevector_job(
        simulator=_SIMULATOR, payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, qubit_ordering="msb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info(f"Received measured circuit data for {_SIMULATOR} (manual sampling).")

    def execute(compiled, payload):
        statevector = compiled.circuit()
        return _draw_statevector_samples(
            statevector, payload.get("n_shots", 1024), payload.get("seed"))

    def shape_counts(samples, compiled, _payload):
        return _counts_from_samples(samples, compiled.n_qubits), "sv_sample"

    return run_measured_job(
        simulator=_SIMULATOR, payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, postprocess_fn=shape_counts, qubit_ordering="msb")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Pennylane-Default")
