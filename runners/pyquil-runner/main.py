"""PyQuil runner: converts OpenQASM 2.0 to Quil via pytket and simulates with NumpyWavefunctionSimulator.

The simulator has no shot sampler here, so the measured endpoint samples the statevector.
"""

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, with_sdk_versions,
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
_GLOBAL_PHASE_NOTE = (
    "Global phase: Quil has no global-phase instruction, so tk_to_pyquil drops the pytket "
    "circuit's phase; the returned statevector is multiplied by exp(i*pi*phase) to restore it.")
_STRIP_MEASUREMENTS_NOTE = (
    "Measurement operations removed before statevector simulation, applied regardless of "
    "apply_preprocessing, so the returned state is the pre-measurement state.")


def _to_quil_program(qasm_str: str, optimization_level: int = 0, apply_preprocessing: bool = True):
    """Parse QASM via pytket, apply the preprocessing and optimisation passes, convert to Quil."""
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str)

    preprocessing_applied = []
    if apply_preprocessing:
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)

    if optimization_level >= 2:
        FullPeepholeOptimise().apply(tk_circ)
        preprocessing_applied.append(_FULL_PEEPHOLE_NOTE)
    elif optimization_level == 1:
        PeepholeOptimise2Q().apply(tk_circ)
        preprocessing_applied.append(_PEEPHOLE_2Q_NOTE)

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


def _compile(payload: dict) -> CompileResult:
    prog, n_qubits, preprocessing_applied, tk_export = _to_quil_program(
        payload["circuit_data"], payload.get("optimization_level", 0),
        payload.get("apply_preprocessing", True))
    return CompileResult(
        circuit=(_gates_only(prog), tk_export),
        n_qubits=n_qubits,
        preprocessing_applied=preprocessing_applied)


def _serialize(compiled: CompileResult) -> str:
    return pytket.qasm.circuit_to_qasm_str(compiled.circuit[1])


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for PyQuil simulation.")

    def compile_step(payload):
        compiled = _compile(payload)
        if compiled.circuit[1].n_gates_of_type(OpType.Measure):
            compiled.preprocessing_applied.append(_STRIP_MEASUREMENTS_NOTE)
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

    def execute(compiled, payload):
        gate_prog, _ = compiled.circuit
        statevector = _simulate_statevector(gate_prog, compiled.n_qubits)
        probs = np.abs(statevector) ** 2
        probs /= probs.sum()
        rng = np.random.default_rng(payload.get("seed"))
        return rng.choice(len(probs), size=payload.get("n_shots", 1024), p=probs)

    def shape_counts(indices, compiled, _payload):
        counts_dict = {}
        for idx in indices:
            bitstring = format(idx, f"0{compiled.n_qubits}b")
            counts_dict[bitstring] = counts_dict.get(bitstring, 0) + 1
        return counts_dict, "sv_sample"

    return run_measured_job(
        simulator="pyquil", payload=payload, logger=logger, compile_fn=_compile,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision="complex128")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "PyQuil")
