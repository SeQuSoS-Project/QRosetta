"""qsim runner: converts OpenQASM 2.0 to Cirq via pytket and simulates with qsimcirq.

qsim computes in single precision (complex64); qsimcirq 0.22 exposes no double-precision
option.
"""

import cmath
import warnings

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, runner_error, with_sdk_versions,
)
import pytket.qasm
from pytket.circuit import Circuit, OpType
from pytket.extensions.cirq import tk_to_cirq
from pytket.passes import RemoveBarriers, auto_rebase_pass
from pytket.transform import Transform
import cirq

try:
    import qsimcirq
    QSIM_AVAILABLE = True
except ImportError:
    QSIM_AVAILABLE = False

logger = get_logger("qsim-cirq-runner")

app = FastAPI(title="qsim-Cirq Runner")

_REMOVE_BARRIERS_NOTE = (
    "pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to "
    "prevent parsing failures in the backend adapter.")
_REBASE_NOTE = (
    "pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Universally decomposes complex "
    "multi-qubit and single-qubit gates (like CU3, CRX) into a standard CX/Rz/Rx basis to "
    "prevent parsing failures in the backend.")
_RZRX_NOTE = (
    "pytket.transform.Transform.RebaseToRzRx(): rewrites single-qubit gates as Rz/Rx "
    "rotations; required by the pytket-to-Cirq adapter, applied regardless of "
    "apply_preprocessing.")
_LEVEL_1_NOTE = (
    "cirq.drop_empty_moments, cirq.align_left (optimization_level>=1): reschedule the Cirq "
    "circuit's moments; gates are unchanged.")
_LEVEL_2_NOTE = (
    "cirq.eject_z, cirq.eject_phased_paulis, cirq.merge_single_qubit_gates_to_phxz, "
    "cirq.drop_empty_moments (optimization_level=2): rewrite single-qubit gates into "
    "PhasedXZ form; the circuit is preserved up to global phase.")
_STRIP_MEASUREMENTS_NOTE = (
    "Measurement operations removed before statevector simulation, applied regardless of "
    "apply_preprocessing, so the returned state is the pre-measurement state.")
_MEASURE_ALL_NOTE = (
    "The circuit's measurements are replaced by one measurement of every declared qubit "
    "(key 'result', qubits in ascending index order), applied regardless of "
    "apply_preprocessing.")

_POW_GATE_TYPES = frozenset({
    OpType.Rx, OpType.Ry, OpType.Rz, OpType.PhasedX,
    OpType.XXPhase, OpType.YYPhase, OpType.ZZPhase,
})


def _cirq_qubits(tk_circ: Circuit) -> list:
    """The Cirq qubits for every declared pytket qubit, in Cirq's sorted order."""
    ref = Circuit()
    for qb in tk_circ.qubits:
        ref.add_qubit(qb)
    return sorted(tk_to_cirq(ref, copy_all_qubits=True).all_qubits())


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


def _strip_measurements(circ: cirq.Circuit) -> cirq.Circuit:
    """Return a copy of the circuit with all measurement gates removed."""
    return cirq.Circuit(
        op for op in circ.all_operations()
        if not isinstance(op.gate, cirq.MeasurementGate)
    )


def _to_cirq_circuit(payload: dict):
    """Parse the QASM via pytket, convert to Cirq, then apply the Cirq optimisation passes.

    Measurements are removed before the passes: cirq.eject_phased_paulis folds a trailing
    Pauli into a measurement's invert mask, which would lose the gate once the measurement
    is removed. Returns the measurement-free Cirq circuit, the declared qubits in Cirq's
    order, whether measurements were removed, and the preprocessing list.
    """
    tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
    optimization_level = payload.get("optimization_level", 0)

    preprocessing_applied = []
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        preprocessing_applied.append(_REBASE_NOTE)
    else:
        Transform.RebaseToRzRx().apply(tk_circ)
        preprocessing_applied.append(_RZRX_NOTE)

    circ = _to_cirq_with_phase(tk_circ)
    had_measurements = circ.has_measurements()
    circ = _strip_measurements(circ)

    if optimization_level >= 1:
        circ = cirq.drop_empty_moments(circ)
        circ = cirq.align_left(circ)
        preprocessing_applied.append(_LEVEL_1_NOTE)

    if optimization_level >= 2:
        circ = cirq.eject_z(circ)
        circ = cirq.eject_phased_paulis(circ)
        circ = cirq.merge_single_qubit_gates_to_phxz(circ)
        circ = cirq.drop_empty_moments(circ)
        preprocessing_applied.append(_LEVEL_2_NOTE)

    return circ, _cirq_qubits(tk_circ), had_measurements, preprocessing_applied


def _serialize(compiled: CompileResult) -> str:
    """OpenQASM export of the executed Cirq circuit (QASM 2.0 carries no global phase)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return cirq.qasm(compiled.circuit[1])


@with_sdk_versions
def process_run(payload: dict) -> dict:
    if not QSIM_AVAILABLE:
        return runner_error("qsim-cirq", "qsimcirq package not installed")

    logger.info("Received circuit data for qsim-Cirq simulation.")

    def compile_step(payload):
        cirq_circ, qubits, had_measurements, preprocessing_applied = _to_cirq_circuit(payload)
        if had_measurements:
            preprocessing_applied.append(_STRIP_MEASUREMENTS_NOTE)
        return CompileResult(
            circuit=(qsimcirq.QSimSimulator(), cirq_circ, qubits),
            n_qubits=len(qubits),
            preprocessing_applied=preprocessing_applied)

    def execute(compiled, _payload):
        simulator, circ, qubits = compiled.circuit
        return simulator.simulate(circ, qubit_order=qubits).final_state_vector

    return run_statevector_job(
        simulator="qsim-cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, qubit_ordering="msb",
        precision="complex64")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    if not QSIM_AVAILABLE:
        return runner_error("qsim-cirq", "qsimcirq package not installed")

    logger.info("Received measured circuit data for qsim-Cirq simulation.")

    def compile_step(payload):
        cirq_circ, qubits, _, preprocessing_applied = _to_cirq_circuit(payload)
        circ_with_meas = cirq_circ + cirq.measure(*qubits, key="result")
        preprocessing_applied.append(_MEASURE_ALL_NOTE)
        return CompileResult(
            circuit=(qsimcirq.QSimSimulator(seed=payload.get("seed")), circ_with_meas),
            n_qubits=len(qubits),
            preprocessing_applied=preprocessing_applied)

    def execute(compiled, payload):
        simulator, circ = compiled.circuit
        return simulator.run(circ, repetitions=payload.get("n_shots", 1024))

    def shape_counts(run_result, _compiled, _payload):
        counts_dict: dict = {}
        for shot in run_result.measurements["result"]:
            bitstring = "".join(str(int(b)) for b in shot)
            counts_dict[bitstring] = counts_dict.get(bitstring, 0) + 1
        return counts_dict, "native"

    return run_measured_job(
        simulator="qsim-cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision="complex64")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "qsim-Cirq")
