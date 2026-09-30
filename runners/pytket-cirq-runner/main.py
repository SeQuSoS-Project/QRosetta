"""Cirq runner: compiles OpenQASM 2.0 with pytket's Cirq backend and simulates with Cirq."""

import cmath
import logging
import warnings

from fastapi import FastAPI
from qrosetta_commons.counts import (
    parse_measurement_layout, prepare_statevector_qasm, statevector_in_declaration_order,
    unit_pairs, unordered_qreg_note,
)
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, with_sdk_versions,
)
import numpy as np
import pytket.qasm
from pytket.circuit import Circuit, OpType
from pytket.extensions.cirq import tk_to_cirq
from pytket.extensions.cirq.backends.cirq import CirqStateSampleBackend
from pytket.passes import RemoveBarriers, auto_rebase_pass
import cirq

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
_NATIVE_RUN_NOTE = (
    "cirq.Simulator(dtype=complex64, seed).run(): the circuit's own measurements, one Cirq "
    "measurement key per classical bit, are sampled by Cirq, including mid-circuit "
    "measurements. Counts keys hold every declared classical bit in declaration order, flat "
    "clbit 0 leftmost; a classical bit measured more than once takes its last value.")

_PASS_NOTES = {}


def _pass_names(pass_dict):
    kind = pass_dict["pass_class"]
    if kind == "SequencePass":
        return [n for p in pass_dict["SequencePass"]["sequence"] for n in _pass_names(p)]
    if kind == "StandardPass":
        return [pass_dict["StandardPass"]["name"]]
    return [kind]


def _compilation_note(backend, level):
    """Describe the backend's default compilation pass, which runs at every level."""
    key = (type(backend).__name__, level)
    if key not in _PASS_NOTES:
        names = ", ".join(_pass_names(backend.default_compilation_pass(level).to_dict()))
        _PASS_NOTES[key] = (
            f"pytket {key[0]}.get_compiled_circuit(optimisation_level={level}): the "
            f"backend's default compilation pass [{names}], applied at every optimisation "
            "level including 0; rewrites the circuit into the backend's supported gate set.")
    return _PASS_NOTES[key]


def _compile_tket(payload: dict, qasm: str, notes=()):
    """Parse the QASM and run the preprocessing and backend compilation both endpoints share.

    Also returns the parsed circuit's bits and qubits as ``(register, index)`` pairs in
    pytket's sorted order, which the compiled circuit's units follow position for position.
    """
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm)
    preprocessing_applied = list(notes)
    qreg_note = unordered_qreg_note(parse_measurement_layout(qasm))
    if qreg_note:
        preprocessing_applied.append(qreg_note)
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        preprocessing_applied.append(_REBASE_NOTE)

    backend = CirqStateSampleBackend()
    opt_level = min(payload.get("optimization_level", 0), 2)
    compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
    preprocessing_applied.append(_compilation_note(backend, opt_level))
    return (compiled_circ, preprocessing_applied, unit_pairs(tk_circ.bits),
            unit_pairs(tk_circ.qubits))


def _cirq_qubits(tk_circ: Circuit) -> list:
    """The Cirq qubits for every declared pytket qubit, in Cirq's sorted order."""
    ref = Circuit()
    for qb in tk_circ.qubits:
        ref.add_qubit(qb)
    return sorted(tk_to_cirq(ref, copy_all_qubits=True).all_qubits())


_POW_GATE_TYPES = frozenset({
    OpType.Rx, OpType.Ry, OpType.Rz, OpType.PhasedX,
    OpType.XXPhase, OpType.YYPhase, OpType.ZZPhase,
})


def _to_cirq_with_phase(tk_circ: Circuit) -> cirq.Circuit:
    """Convert to Cirq, reproducing the pytket circuit's global phase exactly.

    tk_to_cirq maps each gate in _POW_GATE_TYPES with exponent t to a Cirq PowGate equal
    to the pytket gate times exp(i*pi*t/2), and drops the circuit phase whenever its real
    or imaginary part is negative. The net phase is computed here and appended as one
    global-phase operation.
    """
    body = tk_circ.copy()
    phase = float(body.phase)
    body.add_phase(-phase)
    for command in body:
        if command.op.type in _POW_GATE_TYPES:
            phase -= float(command.op.params[0]) / 2
    circ = tk_to_cirq(body)
    coeff = cmath.exp(1j * cmath.pi * phase)
    if abs(coeff - 1) > 1e-15:
        circ.append(cirq.global_phase_operation(coeff))
    return circ


def _serialize(compiled: CompileResult) -> str:
    """QASM of the compiled pytket circuit; hqslib1 covers the PhasedX gates it contains."""
    return pytket.qasm.circuit_to_qasm_str(compiled.circuit[-1], header="hqslib1")


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Cirq simulation.")

    def compile_step(payload):
        qasm, strip_notes = prepare_statevector_qasm(payload["circuit_data"])
        compiled_circ, preprocessing_applied, _, tk_qubits = _compile_tket(
            payload, qasm, strip_notes)
        cirq_circ = _to_cirq_with_phase(compiled_circ)
        qubits = _cirq_qubits(compiled_circ)
        simulator = cirq.Simulator(dtype=np.complex128)
        return CompileResult(
            circuit=(simulator, cirq_circ, qubits, tk_qubits, compiled_circ),
            n_qubits=compiled_circ.n_qubits,
            preprocessing_applied=preprocessing_applied)

    def execute(compiled, _payload):
        simulator, cirq_circ, qubits, _, _ = compiled.circuit
        return simulator.simulate(cirq_circ, qubit_order=qubits).final_state_vector

    def to_declaration_order(statevector, compiled, payload):
        return statevector_in_declaration_order(
            statevector, payload["circuit_data"], compiled.circuit[3], "msb",
            compiled.preprocessing_applied)

    return run_statevector_job(
        simulator="cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=to_declaration_order,
        qubit_ordering="msb",
        precision="complex128")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Cirq simulation.")

    def compile_step(payload):
        compiled_circ, preprocessing_applied, bits, _ = _compile_tket(
            payload, payload["circuit_data"])
        if len(compiled_circ.bits) != len(bits):
            raise ValueError("backend compilation changed the number of classical bits")
        key_bits = {str(b): pair for b, pair in zip(compiled_circ.bits, bits)}
        simulator = cirq.Simulator(dtype=np.complex64, seed=payload.get("seed"))
        return CompileResult(
            circuit=(simulator, _to_cirq_with_phase(compiled_circ), key_bits, compiled_circ),
            n_qubits=compiled_circ.n_qubits,
            preprocessing_applied=preprocessing_applied + [_NATIVE_RUN_NOTE])

    def execute(compiled, payload):
        simulator, cirq_circ, _, _ = compiled.circuit
        return simulator.run(cirq_circ, repetitions=payload.get("n_shots", 1024))

    def shape_counts(result, compiled, payload):
        """Assemble per-shot keys over the declared classical bits (msb)."""
        _, _, key_bits, _ = compiled.circuit
        layout = parse_measurement_layout(payload["circuit_data"])
        index = {bit: k for k, bit in enumerate(layout.clbits)}
        shots = payload.get("n_shots", 1024)
        table = np.zeros((shots, layout.n_clbits), dtype=np.int8)
        for key, record in result.records.items():
            table[:, index[key_bits[key]]] = record[:, -1, 0]
        rows, counts = np.unique(table, axis=0, return_counts=True)
        return {layout.key(row, "msb"): int(c) for row, c in zip(rows, counts)}, "native"

    return run_measured_job(
        simulator="cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision="complex64")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Cirq")
