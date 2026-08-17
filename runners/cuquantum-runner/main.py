# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, runner_error, with_sdk_versions,
)
import numpy as np

logger = get_logger("cuquantum-runner")

app = FastAPI(title="cuQuantum Runner")

try:
    from qiskit import QuantumCircuit, transpile as qiskit_transpile
    from qiskit import qasm2
    from qiskit_aer import AerSimulator, AerError
    AERSIM_AVAILABLE = True
    logger.info("qiskit-aer loaded successfully.")
except ImportError as e:
    AERSIM_AVAILABLE = False
    logger.warning(f"qiskit-aer import failed: {e}. Runner will return errors.")

_GPU_AVAILABLE = False
if AERSIM_AVAILABLE:
    try:
        from qiskit import QuantumCircuit as _QC
        _probe_qc = _QC(1)
        _probe_qc.h(0)
        _probe_qc.save_statevector()
        _probe_sim = AerSimulator(method='statevector', device='GPU')
        _probe_sim.run(_probe_qc).result()
        _GPU_AVAILABLE = True
    except Exception:
        _GPU_AVAILABLE = False
    logger.info(f"GPU/cuQuantum available: {_GPU_AVAILABLE}")

def _run_safe(sim, qc, **kwargs):
    """Run a circuit, falling back to CPU if GPU execution fails."""
    try:
        return sim.run(qc, **kwargs).result()
    except AerError as e:
        if _GPU_AVAILABLE:
            logger.warning(f"GPU run failed ({e}), retrying on CPU.")
            cpu_sim = AerSimulator(method='statevector')
            return cpu_sim.run(qc, **kwargs).result()
        raise

def _transpile(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 into a Qiskit QuantumCircuit and apply Qiskit transpiler passes.

    Level 0: no optimization
    Level 1: basic gate cancellation and 1Q consolidation
    Level 2: unitary synthesis + gate cancellation
    Level 3: heavy optimization (slowest compile, fewest gates)
    """
    preprocessing_applied = []
    qc = QuantumCircuit.from_qasm_str(qasm_str)
    if optimization_level > 0:
        qc = qiskit_transpile(qc, optimization_level=min(optimization_level, 3))
        preprocessing_applied.append(f"qiskit.compiler.transpile(level={min(optimization_level, 3)}): Native Qiskit transpilation pass applied to decompose and optimize the circuit for the Aer backend.")
    return qc, preprocessing_applied


def _simulator():
    return (AerSimulator(method='statevector', device='GPU') if _GPU_AVAILABLE
            else AerSimulator(method='statevector'))


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info(f"Received statevector request (GPU={_GPU_AVAILABLE}).")
    if not AERSIM_AVAILABLE:
        return runner_error("cuquantum", "qiskit-aer not installed.")

    def compile_step(payload):
        qc, preprocessing_applied = _transpile(
            payload["circuit_data"], payload.get("optimization_level", 0))
        # Serialized inside the compilation window: the circuit is rewritten below
        # (measurements removed, save_statevector added) and capturing afterwards would
        # record instructions the user never sent.
        transpiled_qasm = qasm2.dumps(qc)
        qc.remove_final_measurements(inplace=True)
        qc.save_statevector()
        return CompileResult(
            circuit=(_simulator(), qc),
            n_qubits=qc.num_qubits,
            preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)

    def execute(compiled, _payload):
        sim, qc = compiled.circuit
        return np.asarray(_run_safe(sim, qc).get_statevector())

    return run_statevector_job(
        simulator="cuquantum", payload=payload, logger=logger, compile_fn=compile_step,
        execute_fn=execute, qubit_ordering="lsb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info(f"Received measurement request (GPU={_GPU_AVAILABLE}).")
    if not AERSIM_AVAILABLE:
        return runner_error("cuquantum", "qiskit-aer not installed.")

    def compile_step(payload):
        qc, preprocessing_applied = _transpile(
            payload["circuit_data"], payload.get("optimization_level", 0))
        return CompileResult(
            circuit=(_simulator(), qc),
            n_qubits=qc.num_qubits,
            preprocessing_applied=preprocessing_applied,
            transpiled_qasm=qasm2.dumps(qc))

    def execute(compiled, payload):
        sim, qc = compiled.circuit
        # seed_simulator=None keeps Aer's default non-deterministic sampling.
        result = _run_safe(sim, qc, shots=payload.get("n_shots", 1024),
                           seed_simulator=payload.get("seed"))
        return dict(result.get_counts()), "native"

    return run_measured_job(
        simulator="cuquantum", payload=payload, logger=logger, compile_fn=compile_step,
        execute_fn=execute, qubit_ordering="lsb")


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("cuQuantum runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "cuQuantum")
