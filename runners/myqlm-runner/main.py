# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
import re
import numpy as np
import time
import gc
import pytket.qasm
from pytket.passes import auto_rebase_pass
from pytket.circuit import OpType

from qat.interop.openqasm import OqasmParser
from qat.qpus import PyLinalg

logger = get_logger("myqlm-runner")

app = FastAPI(title="myQLM Runner")

_qpu = PyLinalg()

def _preprocess_qasm(qasm_str: str, apply_preprocessing: bool) -> tuple[str, list[str]]:
    """Substitute gates unsupported by myQLM's PyLinalg before parsing.

    If apply_preprocessing is True, use pytket to universally decompose 
    complex gates into CX, Rz, Rx since myQLM rejects multi-controlled gates 
    like CU3 and CRX.
    """
    preprocessing_applied = []
    transpiled_qasm = qasm_str
    
    if apply_preprocessing:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str)
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_circ)
        preprocessing_applied.append("pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Universally decomposes complex multi-qubit and single-qubit gates (like CU3, CRX) into a standard CX/Rz/Rx basis to prevent OqasmParser from rejecting unsupported gates.")
    else:
        # Fallback to string regex for basic tdg substitution when transpilation is disabled
        transpiled_qasm = re.sub(r'\btdg\b', 'rz(-pi/4)', qasm_str)
        preprocessing_applied.append("Regex substitution: Replaced 'tdg' with 'rz(-pi/4)' because myQLM's PyLinalg lacks a native TDG matrix but preserves the equivalent transformation.")
        
    return transpiled_qasm, preprocessing_applied

def _compile_circuit(transpiled_qasm: str, optimization_level: int = 0):
    """Parse QASM 2.0 into a myQLM Circuit. Fresh parser per call — OqasmParser is stateful.

    myQLM's PyLinalg QPU does not expose configurable circuit-level optimization
    passes through its standard API. All optimization levels run identically.
    """
    if optimization_level > 0:
        logger.info(
            f"myQLM: optimization_level={optimization_level} requested "
            "but not supported by PyLinalg; running at level 0."
        )
    return OqasmParser().compile(transpiled_qasm)

def _get_statevector(circuit) -> np.ndarray:
    """Run PyLinalg with nbshots=0 and return the statevector."""
    n_qubits = circuit.nbqbits
    job = circuit.to_job(job_type="SAMPLE", nbshots=0)
    result = _qpu.submit(job)
    sv = np.zeros(2 ** n_qubits, dtype=complex)
    for sample in result:
        if sample.amplitude is not None:
            sv[sample.state.int] = sample.amplitude
    return sv

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for myQLM simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        transpiled_qasm, preprocessing_applied = _preprocess_qasm(payload["circuit_data"], payload.get("apply_preprocessing", True))
        circuit = _compile_circuit(transpiled_qasm, payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        _get_statevector(circuit)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = _get_statevector(circuit)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(
            f"myQLM simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        n_qubits = circuit.nbqbits
        return statevector_result(
            simulator="myqlm", statevector=statevector, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="msb",
            n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during myQLM simulation: {str(e)}")
        return runner_error("myqlm", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for myQLM simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        transpiled_qasm, preprocessing_applied = _preprocess_qasm(payload["circuit_data"], payload.get("apply_preprocessing", True))
        circuit = _compile_circuit(transpiled_qasm, payload.get("optimization_level", 0))
        n_qubits = circuit.nbqbits
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        n_shots = payload.get("n_shots", 1024)

        job = circuit.to_job(job_type="SAMPLE", nbshots=n_shots)

        _qpu.submit(job)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # PyLinalg samples via numpy's global RNG (the QPU/job expose no seed);
            # seeding it makes the run reproducible. seed=None leaves it
            # non-deterministic (prior behaviour).
            if payload.get("seed") is not None:
                np.random.seed(payload["seed"])
            t2 = time.perf_counter()
            result = _qpu.submit(job)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        # myQLM's SAMPLE job samples natively (finite-shot, hence real shot noise),
        # but returns per-state *frequencies* rather than integer tallies. Counts are
        # reconstructed as round(frequency * n_shots). This is lossless: frequencies are
        # exact k/n_shots, so rounding recovers the true integer counts and they sum to
        # n_shots (verified across 2-10 qubits, incl. non-power-of-2 shot counts; max
        # rounding error ~1e-13). The residual top-up below is a defensive guard that
        # does not fire under current myQLM behaviour.
        counts_dict = {
            format(sample.state.int, f"0{n_qubits}b"): round(sample.probability * n_shots)
            for sample in result
            if round(sample.probability * n_shots) > 0
        }

        diff = n_shots - sum(counts_dict.values())
        if diff != 0 and counts_dict:
            top = max(counts_dict, key=counts_dict.get)
            counts_dict[top] += diff

        logger.info(
            f"myQLM measurement simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        # Native PyLinalg sampling; counts reconstructed from reported frequencies
        # (documented at the reconstruction site above).
        return counts_result(
            simulator="myqlm", counts=counts_dict, sampling_method="native",
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="msb", n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during myQLM measurement simulation: {str(e)}")
        return runner_error("myqlm", e)

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "myQLM")
