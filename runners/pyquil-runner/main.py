# Execution script for the quantum simulator runner.

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

def _to_quil_program(qasm_str: str, optimization_level: int = 0, apply_preprocessing: bool = True):
    """Parse QASM via pytket and convert to a Quil Program."""
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str)

    preprocessing_applied = []
    if apply_preprocessing:
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the backend adapter.")

    if optimization_level >= 2:
        FullPeepholeOptimise().apply(tk_circ)
    elif optimization_level == 1:
        PeepholeOptimise2Q().apply(tk_circ)

    if apply_preprocessing:
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        preprocessing_applied.append("pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Universally decomposes complex multi-qubit and single-qubit gates (like CU3, CRX) into a standard CX/Rz/Rx basis to prevent parsing failures in the backend.")
    else:
        Transform.RebaseToRzRx().apply(tk_circ)

    # Return the pytket Circuit (not its QASM string) so the caller can serialize it
    # for provenance outside the timed compilation window.
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

    def execute(compiled, _payload):
        gate_prog, _ = compiled.circuit
        return _simulate_statevector(gate_prog, compiled.n_qubits)

    return run_statevector_job(
        simulator="pyquil", payload=payload, logger=logger, compile_fn=_compile,
        serialize_fn=_serialize, execute_fn=execute, qubit_ordering="msb")


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
        qubit_ordering="msb")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "PyQuil")
