"""Cirq runner: compiles OpenQASM 2.0 with pytket's Cirq backend and simulates with Cirq."""

import cmath
import logging
import warnings

from fastapi import FastAPI
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
_STRIP_MEASUREMENTS_NOTE = (
    "Measurement operations removed before statevector simulation, applied regardless of "
    "apply_preprocessing, so the returned state is the pre-measurement state.")

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


def _compile_tket(payload: dict):
    """Parse the QASM and run the preprocessing and backend compilation both endpoints share."""
    tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
    preprocessing_applied = []
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        preprocessing_applied.append(_REBASE_NOTE)

    backend = CirqStateSampleBackend()
    opt_level = min(payload.get("optimization_level", 0), 2)
    compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
    preprocessing_applied.append(_compilation_note(backend, opt_level))
    return backend, compiled_circ, preprocessing_applied


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
        _, compiled_circ, preprocessing_applied = _compile_tket(payload)
        cirq_circ = _to_cirq_with_phase(compiled_circ)
        if cirq_circ.has_measurements():
            cirq_circ = cirq.drop_terminal_measurements(cirq_circ)
            if cirq_circ.has_measurements():
                raise ValueError(
                    "Statevector simulation needs every measurement to be terminal.")
            preprocessing_applied.append(_STRIP_MEASUREMENTS_NOTE)
        qubits = _cirq_qubits(compiled_circ)
        simulator = cirq.Simulator(dtype=np.complex128)
        return CompileResult(
            circuit=(simulator, cirq_circ, qubits, compiled_circ),
            n_qubits=compiled_circ.n_qubits,
            preprocessing_applied=preprocessing_applied)

    def execute(compiled, _payload):
        simulator, cirq_circ, qubits, _ = compiled.circuit
        return simulator.simulate(cirq_circ, qubit_order=qubits).final_state_vector

    return run_statevector_job(
        simulator="cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, qubit_ordering="msb",
        precision="complex128")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Cirq simulation.")

    def compile_step(payload):
        backend, compiled_circ, preprocessing_applied = _compile_tket(payload)
        return CompileResult(
            circuit=(backend, compiled_circ),
            n_qubits=compiled_circ.n_qubits,
            preprocessing_applied=preprocessing_applied)

    def seed_rng(_compiled, payload):
        """CirqStateSampleBackend samples from numpy's global RNG, so seed that."""
        if payload.get("seed") is not None:
            np.random.seed(payload["seed"])

    def execute(compiled, payload):
        backend, compiled_circ = compiled.circuit
        handle = backend.process_circuit(compiled_circ, n_shots=payload.get("n_shots", 1024))
        return backend.get_result(handle)

    def shape_counts(result, _compiled, _payload):
        counts = result.get_counts()
        return {"".join(map(str, k)): int(v) for k, v in counts.items()}, "native"

    return run_measured_job(
        simulator="cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, pre_execute_fn=seed_rng, execute_fn=execute,
        postprocess_fn=shape_counts, qubit_ordering="msb", precision="complex64")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Cirq")
