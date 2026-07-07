# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
import numpy as np
import pytket.qasm
from pytket.passes import RemoveBarriers, PeepholeOptimise2Q, FullPeepholeOptimise, auto_rebase_pass
from pytket.circuit import OpType
from pytket.transform import Transform
from pytket.extensions.pyquil import tk_to_pyquil
from pyquil import Program
from pyquil.quilbase import Gate
from pyquil.simulation import NumpyWavefunctionSimulator
import time
import gc

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

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for PyQuil simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        prog, n_qubits, preprocessing_applied, tk_export = _to_quil_program(payload["circuit_data"], payload.get("optimization_level", 0), payload.get("apply_preprocessing", True))
        gate_prog = _gates_only(prog)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # Provenance only — serialized after t1 so it does not inflate compilation_time.
        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_export)

        _simulate_statevector(gate_prog, n_qubits)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = _simulate_statevector(gate_prog, n_qubits)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(
            f"PyQuil simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return statevector_result(
            simulator="pyquil", statevector=statevector, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="msb",
            n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during PyQuil simulation: {str(e)}")
        return runner_error("pyquil", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for PyQuil simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        prog, n_qubits, preprocessing_applied, tk_export = _to_quil_program(payload["circuit_data"], payload.get("optimization_level", 0), payload.get("apply_preprocessing", True))
        gate_prog = _gates_only(prog)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # Provenance only — serialized after t1 so it does not inflate compilation_time.
        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_export)

        _simulate_statevector(gate_prog, n_qubits)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = _simulate_statevector(gate_prog, n_qubits)
            probs = np.abs(statevector) ** 2
            probs /= probs.sum()
            rng = np.random.default_rng(payload.get("seed"))
            indices = rng.choice(len(probs), size=payload.get("n_shots", 1024), p=probs)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        counts_dict = {}
        for idx in indices:
            bitstring = format(idx, f"0{n_qubits}b")
            counts_dict[bitstring] = counts_dict.get(bitstring, 0) + 1

        logger.info(
            f"PyQuil measurement simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return counts_result(
            simulator="pyquil", counts=counts_dict, sampling_method="sv_sample",
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="msb", n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during PyQuil measurement simulation: {str(e)}")
        return runner_error("pyquil", e)

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "PyQuil")
