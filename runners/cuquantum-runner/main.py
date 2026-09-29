"""cuQuantum runner: simulates OpenQASM 2.0 circuits with qiskit-aer's statevector method, on GPU when available."""

from fastapi import FastAPI
from qrosetta_commons.counts import (
    counts_from_register_keys, parse_measurement_layout, prepare_statevector_qasm,
)
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


_SAVE_STATEVECTOR_NOTE = (
    "qiskit_aer save_statevector(): appended so Aer returns the final state; transpiled_qasm "
    "is the circuit before it. Required by the adapter, applied regardless of "
    "apply_preprocessing.")
_METHOD_NOTE = (
    "AerSimulator(method='statevector'): the simulation method is fixed, so Aer does not "
    "switch to its stabilizer method on Clifford circuits. The device (GPU when "
    "qiskit-aer's cuStateVec build and a GPU are present, else CPU) is reported in the "
    "result's device field.")
_COUNTS_KEY_NOTE = (
    "Counts keys: Aer's space-separated per-register fields are re-keyed to one bitstring "
    "over every declared classical bit in declaration order, flat clbit 0 rightmost.")


def _backend_fields(result, sim) -> dict:
    """Method and device Aer reports for the executed experiment."""
    metadata = result.results[0].metadata
    method = metadata.get("method", sim.options.method)
    device = metadata.get("device", sim.options.device)
    return {
        "device": device,
        "simulation_method": method,
        "simulator_backend": (
            f"qiskit-aer AerSimulator(method={method}, precision={sim.options.precision}, "
            f"device={device})"),
    }


def _precision(sim) -> str:
    return "complex128" if sim.options.precision == "double" else "complex64"


def _serialize(compiled) -> str:
    return qasm2.dumps(compiled.circuit[2])


def _simulator():
    return (AerSimulator(method='statevector', device='GPU') if _GPU_AVAILABLE
            else AerSimulator(method='statevector'))


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info(f"Received statevector request (GPU={_GPU_AVAILABLE}).")
    if not AERSIM_AVAILABLE:
        return runner_error("cuquantum", "qiskit-aer not installed.")

    def compile_step(payload):
        qasm, strip_notes = prepare_statevector_qasm(payload["circuit_data"])
        qc, preprocessing_applied = _transpile(qasm, payload.get("optimization_level", 0))
        executed_qc = qc.copy()
        executed_qc.save_statevector()
        sim = _simulator()
        return CompileResult(
            circuit=(sim, executed_qc, qc),
            n_qubits=qc.num_qubits,
            preprocessing_applied=(strip_notes + preprocessing_applied
                                   + [_METHOD_NOTE, _SAVE_STATEVECTOR_NOTE]),
            precision=_precision(sim))

    def execute(compiled, _payload):
        sim, executed_qc, _qc = compiled.circuit
        return _run_safe(sim, executed_qc)

    def shape_statevector(result, compiled, _payload):
        backend_fields.update(_backend_fields(result, compiled.circuit[0]))
        return np.asarray(result.get_statevector())

    backend_fields = {}
    result = run_statevector_job(
        simulator="cuquantum", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_statevector,
        qubit_ordering="lsb")
    if "error" not in result:
        result.update(backend_fields)
    return result


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info(f"Received measurement request (GPU={_GPU_AVAILABLE}).")
    if not AERSIM_AVAILABLE:
        return runner_error("cuquantum", "qiskit-aer not installed.")

    def compile_step(payload):
        qc, preprocessing_applied = _transpile(
            payload["circuit_data"], payload.get("optimization_level", 0))
        sim = _simulator()
        return CompileResult(
            circuit=(sim, qc, qc),
            n_qubits=qc.num_qubits,
            preprocessing_applied=preprocessing_applied + [_METHOD_NOTE, _COUNTS_KEY_NOTE],
            precision=_precision(sim))

    def execute(compiled, payload):
        sim, qc, _qc = compiled.circuit
        return _run_safe(sim, qc, shots=payload.get("n_shots", 1024),
                         seed_simulator=payload.get("seed"))

    def shape_counts(result, compiled, payload):
        """Re-key Aer counts over the circuit's declared classical bits (lsb)."""
        sim, qc, _qc = compiled.circuit
        backend_fields.update(_backend_fields(result, sim))
        registers = [(reg.name, reg.size) for reg in qc.cregs]
        layout = parse_measurement_layout(payload["circuit_data"])
        return counts_from_register_keys(layout, result.get_counts(), registers, "lsb"), "native"

    backend_fields = {}
    result = run_measured_job(
        simulator="cuquantum", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="lsb")
    if "error" not in result:
        result.update(backend_fields)
    return result


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("cuQuantum runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "cuQuantum")
