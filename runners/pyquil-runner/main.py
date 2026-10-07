"""PyQuil runner: converts OpenQASM 2.0 to Quil via pytket and simulates with NumpyWavefunctionSimulator.

The simulator has no shot sampler here, so the measured endpoint samples the statevector.
"""

from fastapi import FastAPI
from qrosetta_commons.counts import (
    PYTKET_QASM_MAXWIDTH,
    prepare_final_state_sampling, prepare_statevector_qasm, strip_identity_gates,
)
from qrosetta_commons.helpers import (
    CompileResult, declare_sdk_packages, get_logger, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, with_sdk_versions,
)
import numpy as np
import pytket.qasm
from pytket.passes import RemoveBarriers, PeepholeOptimise2Q, FullPeepholeOptimise, auto_rebase_pass
from pytket.circuit import OpType
from pytket.transform import Transform
from pytket.extensions.pyquil import tk_to_pyquil
from pyquil import Program
from pyquil.quilbase import Gate
from pyquil.simulation import NumpyWavefunctionSimulator

declare_sdk_packages("pytket", "pytket-pyquil", "pyquil")

logger = get_logger("pyquil-runner")

app = FastAPI(title="PyQuil Runner")

_REMOVE_BARRIERS_NOTE = (
    "pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to "
    "prevent parsing failures in the backend adapter.")
_REBASE_NOTE = (
    "pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Universally decomposes complex "
    "multi-qubit and single-qubit gates (like CU3, CRX) into a standard CX/Rz/Rx basis to "
    "prevent parsing failures in the backend.")
_RZRX_NOTE = (
    "pytket.transform.Transform.RebaseToRzRx(): rewrites single-qubit gates as Rz/Rx "
    "rotations; required by the pytket-to-Quil adapter, applied regardless of "
    "apply_preprocessing.")
_PEEPHOLE_2Q_NOTE = (
    "pytket.passes.PeepholeOptimise2Q() (optimization_level=1): cancels redundant two-qubit "
    "gates and merges single-qubit sequences.")
_FULL_PEEPHOLE_NOTE = (
    "pytket.passes.FullPeepholeOptimise() (optimization_level=2): single-qubit merging and "
    "KAK-based two-qubit reduction.")
_IMPLICIT_SWAPS_NOTE = (
    "pytket Circuit.replace_implicit_wire_swaps(): the optimisation pass left an implicit "
    "qubit permutation (allow_swaps=True removes SWAPs by relabelling wires), which "
    "tk_to_pyquil does not carry over; it is written back as explicit SWAP gates before the "
    "rebase, so the final state is in the input's qubit order.")
_U0_NOTE = (
    "Calls to u0 removed from the QASM: qelib1 defines u0 as the identity and tk_to_pyquil "
    "cannot convert it. Required by the adapter, applied regardless of apply_preprocessing.")
_GLOBAL_PHASE_NOTE = (
    "Global phase: Quil has no global-phase instruction, so tk_to_pyquil drops the pytket "
    "circuit's phase; the returned statevector is multiplied by exp(i*pi*phase) to restore it.")


def _to_quil_program(qasm_str: str, optimization_level: int = 0, apply_preprocessing: bool = True):
    """Parse QASM via pytket, apply the preprocessing and optimisation passes, convert to Quil."""
    qasm_str, removed = strip_identity_gates(qasm_str, ("u0",))
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str, maxwidth=PYTKET_QASM_MAXWIDTH)
    if len(tk_circ.q_registers) > 1:
        raise ValueError(
            "Cannot convert circuit with multiple quantum registers to pyQuil: "
            "tk_to_pyquil needs a single linear register. Enable apply_preprocessing so "
            "the API merges the registers into one.")

    preprocessing_applied = [_U0_NOTE] if removed else []
    if apply_preprocessing:
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)

    if optimization_level >= 2:
        FullPeepholeOptimise().apply(tk_circ)
        preprocessing_applied.append(_FULL_PEEPHOLE_NOTE)
    elif optimization_level == 1:
        PeepholeOptimise2Q().apply(tk_circ)
        preprocessing_applied.append(_PEEPHOLE_2Q_NOTE)
    if tk_circ.implicit_qubit_permutation() != {q: q for q in tk_circ.qubits}:
        tk_circ.replace_implicit_wire_swaps()
        preprocessing_applied.append(_IMPLICIT_SWAPS_NOTE)

    if apply_preprocessing:
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        preprocessing_applied.append(_REBASE_NOTE)
    else:
        Transform.RebaseToRzRx().apply(tk_circ)
        preprocessing_applied.append(_RZRX_NOTE)

    return tk_to_pyquil(tk_circ), tk_circ.n_qubits, preprocessing_applied, tk_circ


def _gates_only(prog: Program) -> Program:
    """Return a Program with only Gate instructions — strips MEASURE, DECLARE, HALT, etc."""
    clean = Program()
    for inst in prog.instructions:
        if isinstance(inst, Gate):
            clean += inst
    return clean


def _simulate_statevector(gate_prog: Program, n_qubits: int) -> np.ndarray:
    """Apply gate instructions sequentially to |0> and return the statevector."""
    sim = NumpyWavefunctionSimulator(n_qubits=n_qubits)
    for inst in gate_prog.instructions:
        if isinstance(inst, Gate):
            sim.do_gate(inst)
    return np.array(sim.wf).flatten()


def _compile(payload: dict, qasm: str, notes=()) -> CompileResult:
    prog, n_qubits, preprocessing_applied, tk_export = _to_quil_program(
        qasm, payload.get("optimization_level", 0), payload.get("apply_preprocessing", True))
    return CompileResult(
        circuit=(_gates_only(prog), tk_export),
        n_qubits=n_qubits,
        preprocessing_applied=[*notes, *preprocessing_applied])


def _serialize(compiled: CompileResult) -> str:
    circ = compiled.circuit[1]
    return pytket.qasm.circuit_to_qasm_str(circ, maxwidth=max(32, len(circ.bits)))


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for PyQuil simulation.")

    def compile_step(payload):
        qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
        compiled = _compile(payload, qasm, notes)
        compiled.preprocessing_applied.append(_GLOBAL_PHASE_NOTE)
        return compiled

    def execute(compiled, _payload):
        gate_prog, _ = compiled.circuit
        return _simulate_statevector(gate_prog, compiled.n_qubits)

    def restore_phase(statevector, compiled, _payload):
        _, tk_circ = compiled.circuit
        return statevector * np.exp(1j * np.pi * float(tk_circ.phase))

    return run_statevector_job(
        simulator="pyquil", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=restore_phase,
        qubit_ordering="msb", precision="complex128")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for PyQuil simulation.")

    def compile_step(payload):
        qasm, layout, notes = prepare_final_state_sampling(payload["circuit_data"])
        compiled = _compile(payload, qasm, notes)
        layouts.append(layout)
        return compiled

    def execute(compiled, payload):
        gate_prog, _ = compiled.circuit
        statevector = _simulate_statevector(gate_prog, compiled.n_qubits)
        probs = np.abs(statevector) ** 2
        probs /= probs.sum()
        rng = np.random.default_rng(payload.get("seed"))
        return rng.choice(len(probs), size=payload.get("n_shots", 1024), p=probs)

    def shape_counts(indices, _compiled, _payload):
        """Map the sampled qubit outcomes (qubit 0 most significant) to classical-bit keys."""
        layout = layouts[0]
        positions = layout.qubit_positions("msb")
        return layout.counts_from_qubit_samples(indices, positions, "msb"), "sv_sample"

    layouts = []
    return run_measured_job(
        simulator="pyquil", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision="complex128")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "PyQuil")
