"""PennyLane runner: parses QASM with pennylane-qiskit and executes the tape on a PennyLane device."""

from fastapi import FastAPI
from qrosetta_commons.counts import prepare_final_state_sampling, prepare_statevector_qasm
from qrosetta_commons.helpers import (
    CompileResult, _draw_statevector_samples, declare_sdk_packages, get_logger,
    get_num_qubits_from_qasm, register_runner_endpoints, run_cli_main, run_measured_job,
    run_statevector_job, strip_barriers_from_qasm, with_sdk_versions,
)
import numpy as np
import pennylane as qml

declare_sdk_packages("pennylane", "pennylane-lightning", "pennylane-qiskit", "qiskit")

app = FastAPI(title="Pennylane Lightning Runner")
logger = get_logger("pennylane-lightning-runner")

_DEVICE = "lightning.qubit"
_SIMULATOR = "pennylane-lightning"
_PRECISION = "complex128"

_STRIP_BARRIERS_NOTE = (
    "qrosetta_commons.helpers.strip_barriers_from_qasm(): Strips barrier instructions from "
    "the QASM string, as PennyLane's QASM parser does not support them. Required by the "
    "adapter, applied regardless of apply_preprocessing.")
_FROM_QASM_NOTE = (
    "qml.from_qasm(measurements=[qml.state()]) (pennylane-qiskit): Maps each Qiskit "
    "instruction to a PennyLane operation; gates without a direct PennyLane equivalent "
    "(e.g. cu3) become QubitUnitary matrices; the tape ends in a statevector readout. "
    "Required by the adapter, applied regardless of apply_preprocessing.")
_CANCEL_INVERSES_NOTE = (
    "qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to "
    "reduce gate count.")
_MERGE_ROTATIONS_NOTE = (
    "qml.transforms.merge_rotations: Merges consecutive rotation gates on the same "
    "qubit/axis into a single rotation.")
_COMMUTE_CONTROLLED_NOTE = (
    "qml.transforms.commute_controlled: Pushes single-qubit gates through controlled gates "
    "to enable further cancellations.")
_IDLE_WIRES_NOTE = (
    "qml.Identity on each declared wire no operation touches: prepended so the tape and its "
    "qml.state() readout span every declared qubit (a gate-free circuit has no wires "
    "otherwise, and qml.from_qasm then also drops the readout).")
_SERIALIZE_NOTE = (
    "transpiled_qasm is QuantumScript.to_openqasm() of the executed tape's operations; "
    "operations outside the OpenQASM 2.0 gate set (e.g. QubitUnitary) are decomposed in the "
    "text only. An operation to_openqasm cannot decompose (a QubitUnitary on three or more "
    "wires, e.g. from c3x) is written as an opaque gate applied to its wires, preceded by "
    "comments holding its exact matrix. The tape's qml.state() readout is not written as "
    "measure statements, and the creg that to_openqasm always declares holds nothing.")


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


def _compile(payload: dict, qasm: str, notes=()) -> CompileResult:
    """Build the state tape, apply the optimisation pipeline and the device preprocess program.

    Returns (device, tapes, execution_config, device_postprocessing) as the circuit.
    """
    circuit_data = strip_barriers_from_qasm(qasm)
    num_qubits = get_num_qubits_from_qasm(qasm)
    dev = qml.device(_DEVICE, wires=num_qubits, shots=None)
    qasm_op = qml.from_qasm(circuit_data, measurements=[qml.state()])
    tape = qml.tape.make_qscript(qasm_op)()
    notes = [*notes, _STRIP_BARRIERS_NOTE, _FROM_QASM_NOTE]
    idle = [w for w in range(num_qubits) if w not in tape.wires]
    if idle:
        tape = qml.tape.QuantumScript(
            [qml.Identity(w) for w in idle] + list(tape.operations), [qml.state()])
        notes.append(_IDLE_WIRES_NOTE)

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


def _compile_statevector(payload: dict) -> CompileResult:
    qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
    return _compile(payload, qasm, notes)


def _compile_sampled(payload: dict):
    """Compile the measurement-free circuit; returns it with the classical-bit layout."""
    qasm, layout, notes = prepare_final_state_sampling(payload["circuit_data"])
    return _compile(payload, qasm, notes), layout


def _op_lines(op, wires, opaque_names: dict) -> list:
    """QASM lines for one operation; an opaque gate with its matrix in comments if needed."""
    try:
        text = qml.tape.QuantumScript([op]).to_openqasm(wires=wires, measure_all=False)
        return [line for line in text.splitlines()
                if not line.startswith(("OPENQASM", "include", "qreg", "creg"))]
    except ValueError:
        pass
    targets = ",".join(f"q[{wires.index(w)}]" for w in op.wires)
    matrix = np.asarray(qml.matrix(op, wire_order=op.wires), dtype=complex)
    key = (len(op.wires), matrix.tobytes())
    if key in opaque_names:
        return [f"{opaque_names[key]} {targets};"]
    name = f"pl_unitary_{len(opaque_names)}"
    opaque_names[key] = name
    lines = [f"// {name} is a {op.name} with this matrix (one row per line, first operand "
             "most significant, entries re,im):"]
    lines += ["// " + " ".join(f"{z.real!r},{z.imag!r}" for z in row) for row in matrix]
    lines.append(f"opaque {name} " + ",".join(f"a{i}" for i in range(len(op.wires))) + ";")
    lines.append(f"{name} {targets};")
    return lines


def _serialize(compiled) -> str:
    dev, tapes, _config, _post = compiled.circuit
    ops = tapes[0].operations
    try:
        return qml.tape.QuantumScript(ops).to_openqasm(wires=dev.wires, measure_all=False)
    except ValueError:
        pass
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";',
             f"qreg q[{len(dev.wires)}];", f"creg c[{len(dev.wires)}];"]
    opaque_names = {}
    for op in ops:
        lines += _op_lines(op, dev.wires, opaque_names)
    return "\n".join(lines) + "\n"


_GATE_METRICS_BASIS = ("operations of the executed tape after Device.preprocess(), without the "
                       "Identity operations added for idle wires; depth from the tape's specs")


def _gate_metrics(compiled):
    """(gate count, depth, basis) of the tape the device executes."""
    _dev, tapes, _config, _post = compiled.circuit
    ops = [op for op in tapes[0].operations if op.name != "Identity"]
    depth = qml.tape.QuantumScript(ops).specs["resources"].depth if ops else 0
    return len(ops), depth, _GATE_METRICS_BASIS


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
        simulator=_SIMULATOR, payload=payload, logger=logger, compile_fn=_compile_statevector,
        serialize_fn=_serialize, gate_metrics_fn=_gate_metrics, execute_fn=execute, postprocess_fn=shape_statevector,
        qubit_ordering="msb", precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info(f"Received measured circuit data for {_SIMULATOR} (manual sampling).")

    def execute(compiled, payload):
        statevector = _statevector(_execute_tapes(compiled), compiled)
        return _draw_statevector_samples(
            statevector, payload.get("n_shots", 1024), payload.get("seed"))

    def compile_step(payload):
        compiled, layout = _compile_sampled(payload)
        layouts.append(layout)
        return compiled

    def shape_counts(samples, _compiled, _payload):
        """Map the sampled wire outcomes (wire 0 most significant) to classical-bit keys."""
        layout = layouts[0]
        positions = layout.qubit_positions("msb")
        return layout.counts_from_qubit_samples(samples, positions, "msb"), "sv_sample"

    layouts = []
    return run_measured_job(
        simulator=_SIMULATOR, payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, gate_metrics_fn=_gate_metrics, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision=_PRECISION)


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Pennylane-Lightning")
