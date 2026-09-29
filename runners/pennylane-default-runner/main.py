"""PennyLane runner: parses QASM with pennylane-qiskit and executes the tape on a PennyLane device."""

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, _counts_from_samples, _draw_statevector_samples, get_logger, get_num_qubits_from_qasm,
    register_runner_endpoints, run_cli_main, run_measured_job, run_statevector_job,
    strip_barriers_from_qasm, with_sdk_versions,
)
import numpy as np
import pennylane as qml

app = FastAPI(title="Pennylane Default Runner")
logger = get_logger("pennylane-default-runner")

_DEVICE = "default.qubit"
_SIMULATOR = "pennylane-default"
_PRECISION = "complex128"

_STRIP_BARRIERS_NOTE = (
    "qrosetta_commons.helpers.strip_barriers_from_qasm(): Strips barrier instructions from "
    "the QASM string, as PennyLane's QASM parser does not support them. Required by the "
    "adapter, applied regardless of apply_preprocessing.")
_FROM_QASM_NOTE = (
    "qml.from_qasm(measurements=[qml.state()]) (pennylane-qiskit): Maps each Qiskit "
    "instruction to a PennyLane operation; gates without a direct PennyLane equivalent "
    "(e.g. cu3) become QubitUnitary matrices, and terminal measure statements are replaced "
    "by a statevector readout (counts are sampled from that statevector). Required by the "
    "adapter, applied regardless of apply_preprocessing.")
_CANCEL_INVERSES_NOTE = (
    "qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to "
    "reduce gate count.")
_MERGE_ROTATIONS_NOTE = (
    "qml.transforms.merge_rotations: Merges consecutive rotation gates on the same "
    "qubit/axis into a single rotation.")
_COMMUTE_CONTROLLED_NOTE = (
    "qml.transforms.commute_controlled: Pushes single-qubit gates through controlled gates "
    "to enable further cancellations.")
_SERIALIZE_NOTE = (
    "transpiled_qasm is QuantumScript.to_openqasm() of the executed tape; operations "
    "outside the OpenQASM 2.0 gate set (e.g. QubitUnitary) are decomposed in the text only.")


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
    """Build the state tape, apply the optimisation pipeline and the device preprocess program.

    Returns (device, tapes, execution_config, device_postprocessing) as the circuit.
    """
    circuit_data = strip_barriers_from_qasm(payload["circuit_data"])
    num_qubits = get_num_qubits_from_qasm(payload["circuit_data"])
    dev = qml.device(_DEVICE, wires=num_qubits, shots=None)
    qasm_op = qml.from_qasm(circuit_data, measurements=[qml.state()])
    tape = qml.tape.make_qscript(qasm_op)()
    notes = [_STRIP_BARRIERS_NOTE, _FROM_QASM_NOTE]

    passes, pass_notes = _optimization_pipeline(payload.get("optimization_level", 0))
    if passes:
        [tape], _ = qml.compile(tape, pipeline=passes)
        notes.append("qml.compile: Applies the transform pipeline below to the tape.")
        notes.extend(pass_notes)

    program, config = dev.preprocess()
    tapes, device_post = program([tape])
    notes.append(
        f"{_DEVICE} Device.preprocess() transform program "
        f"({', '.join(t.transform.__name__ for t in program)}): Validates the tape and "
        "decomposes operations the device does not support natively. Required by the "
        "device, applied regardless of apply_preprocessing.")
    notes.append(_SERIALIZE_NOTE)

    return CompileResult(
        circuit=(dev, tapes, config, device_post),
        n_qubits=num_qubits,
        preprocessing_applied=notes,
        precision=_PRECISION)


def _serialize(compiled) -> str:
    dev, tapes, _config, _post = compiled.circuit
    return tapes[0].to_openqasm(wires=dev.wires, measure_all=False)


def _execute_tapes(compiled):
    dev, tapes, config, _post = compiled.circuit
    return dev.execute(tapes, config)


def _statevector(results, compiled):
    _dev, _tapes, _config, device_post = compiled.circuit
    return np.asarray(device_post(results)[0])


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info(f"Received statevector circuit data for {_SIMULATOR} simulation.")

    def execute(compiled, _payload):
        return _execute_tapes(compiled)

    def shape_statevector(results, compiled, _payload):
        return _statevector(results, compiled)

    return run_statevector_job(
        simulator=_SIMULATOR, payload=payload, logger=logger, compile_fn=_compile,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_statevector,
        qubit_ordering="msb", precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info(f"Received measured circuit data for {_SIMULATOR} (manual sampling).")

    def execute(compiled, payload):
        statevector = _statevector(_execute_tapes(compiled), compiled)
        return _draw_statevector_samples(
            statevector, payload.get("n_shots", 1024), payload.get("seed"))

    def shape_counts(samples, compiled, _payload):
        return _counts_from_samples(samples, compiled.n_qubits), "sv_sample"

    return run_measured_job(
        simulator=_SIMULATOR, payload=payload, logger=logger, compile_fn=_compile,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision=_PRECISION)


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Pennylane-Default")
