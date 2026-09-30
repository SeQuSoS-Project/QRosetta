"""cuQuantum runner: simulates OpenQASM 2.0 circuits with qiskit-aer-gpu using NVIDIA cuStateVec.

Requires an NVIDIA GPU. Without one the runner reports itself unavailable and refuses runs;
it never falls back to CPU Aer, which would duplicate the qiskit runner's engine.
"""

from fastapi import FastAPI
from qrosetta_commons.counts import (
    counts_from_register_keys, parse_measurement_layout, prepare_statevector_qasm,
)
from qrosetta_commons.helpers import (
    CompileResult, declare_sdk_packages, get_logger, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, runner_error, with_sdk_versions,
)
import json
import os

import numpy as np

declare_sdk_packages("qiskit", "qiskit-aer-gpu", "custatevec-cu12")

logger = get_logger("cuquantum-runner")

app = FastAPI(title="cuQuantum Runner")

try:
    from qiskit import QuantumCircuit, transpile as qiskit_transpile
    from qiskit import qasm2
    from qiskit_aer import AerSimulator
    AERSIM_AVAILABLE = True
    logger.info("qiskit-aer loaded successfully.")
except ImportError as e:
    AERSIM_AVAILABLE = False
    logger.warning(f"qiskit-aer-gpu import failed: {e}. Runner will report itself unavailable.")

_CAPABILITIES = None
_CAPABILITIES_ENV = "QROSETTA_CUQUANTUM_CAPABILITIES"


def _gpu_name():
    import subprocess
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else None
    except Exception:
        return None


def capabilities() -> dict:
    """Probe once for a GPU on which Aer runs with cuStateVec enabled."""
    global _CAPABILITIES
    if _CAPABILITIES is not None:
        return _CAPABILITIES
    inherited = os.environ.get(_CAPABILITIES_ENV)
    if inherited:
        _CAPABILITIES = json.loads(inherited)
        return _CAPABILITIES
    if not AERSIM_AVAILABLE:
        _CAPABILITIES = {"available": False, "reason": "qiskit-aer-gpu is not installed",
                         "device": None, "gpu_name": None}
        return _CAPABILITIES
    try:
        probe = QuantumCircuit(1)
        probe.h(0)
        probe.save_statevector()
        metadata = _simulator().run(probe).result().results[0].metadata
        if metadata.get("device") != "GPU" or not metadata.get("cuStateVec_enable"):
            raise RuntimeError(f"Aer ran on {metadata.get('device')} with "
                               f"cuStateVec_enable={metadata.get('cuStateVec_enable')}")
        _CAPABILITIES = {"available": True, "reason": None, "device": "GPU",
                         "gpu_name": _gpu_name()}
    except Exception as e:
        _CAPABILITIES = {"available": False,
                         "reason": f"requires an NVIDIA GPU with cuStateVec; none usable ({e})"[:300],
                         "device": None, "gpu_name": None}
    os.environ[_CAPABILITIES_ENV] = json.dumps(_CAPABILITIES)
    logger.info(f"cuQuantum capabilities: {_CAPABILITIES}")
    return _CAPABILITIES


def _unavailable_error():
    return runner_error("cuquantum", f"cuQuantum runner unavailable: {capabilities()['reason']}")


_AER_OPERATIONS = {}


def _aer_operations(sim) -> frozenset:
    """Instruction names the simulator executes, cached per device."""
    device = sim.options.device
    if device not in _AER_OPERATIONS:
        _AER_OPERATIONS[device] = frozenset(sim.target.operation_names)
    return _AER_OPERATIONS[device]


def _to_aer_basis(qc, sim, preprocessing_applied):
    """Decompose instructions Aer cannot execute (e.g. ch, u0) at optimization_level 0."""
    missing = sorted({inst.operation.name for inst in qc.data} - _aer_operations(sim))
    if not missing:
        return qc
    preprocessing_applied.append(
        f"qiskit.compiler.transpile(backend=AerSimulator, optimization_level=0): decomposes "
        f"{', '.join(missing)}, which Aer does not execute, into gates it does. Required by "
        "the adapter, applied regardless of apply_preprocessing.")
    return qiskit_transpile(qc, sim, optimization_level=0)


def _transpile(qasm_str: str, optimization_level: int, sim):
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
    return _to_aer_basis(qc, sim, preprocessing_applied), preprocessing_applied


_SAVE_STATEVECTOR_NOTE = (
    "qiskit_aer save_statevector(): appended so Aer returns the final state; transpiled_qasm "
    "is the circuit before it. Required by the adapter, applied regardless of "
    "apply_preprocessing.")
_METHOD_NOTE = (
    "AerSimulator(method='statevector', device='GPU', cuStateVec_enable=True): NVIDIA "
    "cuStateVec on the GPU; the method is fixed, so Aer does not switch to its stabilizer "
    "method on Clifford circuits. Memory fields are host RSS; GPU device memory is not "
    "measured. The GPU is not under the runners' CPU quota.")
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
        "custatevec_enabled": bool(metadata.get("cuStateVec_enable")),
        "gpu_name": capabilities().get("gpu_name"),
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
    return AerSimulator(method='statevector', device='GPU', cuStateVec_enable=True)


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received statevector request.")
    if not capabilities()["available"]:
        return _unavailable_error()

    def compile_step(payload):
        qasm, strip_notes = prepare_statevector_qasm(payload["circuit_data"])
        sim = _simulator()
        qc, preprocessing_applied = _transpile(qasm, payload.get("optimization_level", 0), sim)
        executed_qc = qc.copy()
        executed_qc.save_statevector()
        return CompileResult(
            circuit=(sim, executed_qc, qc),
            n_qubits=qc.num_qubits,
            preprocessing_applied=(strip_notes + preprocessing_applied
                                   + [_METHOD_NOTE, _SAVE_STATEVECTOR_NOTE]),
            precision=_precision(sim))

    def execute(compiled, _payload):
        sim, executed_qc, _qc = compiled.circuit
        return sim.run(executed_qc).result()

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
    logger.info("Received measurement request.")
    if not capabilities()["available"]:
        return _unavailable_error()

    def compile_step(payload):
        sim = _simulator()
        qc, preprocessing_applied = _transpile(
            payload["circuit_data"], payload.get("optimization_level", 0), sim)
        return CompileResult(
            circuit=(sim, qc, qc),
            n_qubits=qc.num_qubits,
            preprocessing_applied=preprocessing_applied + [_METHOD_NOTE, _COUNTS_KEY_NOTE],
            precision=_precision(sim))

    def execute(compiled, payload):
        sim, qc, _qc = compiled.circuit
        return sim.run(qc, shots=payload.get("n_shots", 1024),
                       seed_simulator=payload.get("seed")).result()

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


@app.get("/capabilities")
def get_capabilities():
    return capabilities()


if __name__ != "__mp_main__":
    capabilities()

logger.info("cuQuantum runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "cuQuantum")
