"""Qiskit runner: executes OpenQASM 2.0 circuits on Qiskit Aer (double precision)."""

from fastapi import FastAPI
import pytket.qasm
from pytket.extensions.qiskit import tk_to_qiskit
from qiskit_aer import AerSimulator
from qiskit import transpile as qiskit_transpile
from qiskit import qasm2
from qrosetta_commons.counts import (
    counts_from_register_keys, parse_measurement_layout, prepare_statevector_qasm,
    unordered_qreg_note,
)
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, with_sdk_versions,
)

logger = get_logger("pytket-qiskit-runner")

app = FastAPI(title="Qiskit Runner")

_SIMULATION_METHOD = "statevector"

_PARSE_NOTE = (
    "pytket.qasm.circuit_from_qasm_str() + tk_to_qiskit(): the QASM is parsed by pytket's "
    "parser, not Qiskit's, and converted to a Qiskit circuit; gate definitions the pytket "
    "parser rejects fail here when apply_preprocessing is False. Required by the adapter, "
    "applied regardless of apply_preprocessing.")
_METHOD_NOTE = (
    "AerSimulator(method='statevector'): the simulation method is fixed, so Aer does not "
    "switch to its stabilizer method on Clifford circuits.")
_COUNTS_KEY_NOTE = (
    "Counts keys: Aer's space-separated per-register fields are re-keyed to one bitstring "
    "over every declared classical bit in declaration order, flat clbit 0 rightmost.")
_SAVE_STATEVECTOR_NOTE = (
    "qiskit_aer save_statevector(): appended so Aer returns the final state; transpiled_qasm "
    "is the circuit before it. Required by the adapter, applied regardless of "
    "apply_preprocessing.")


def _simulator():
    return AerSimulator(method=_SIMULATION_METHOD, precision="double")


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


def _to_qiskit(qasm: str, payload: dict):
    """Parse the QASM via pytket, convert to a Qiskit circuit, and apply the opt level."""
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm)
    qiskit_circ = tk_to_qiskit(tk_circ)

    preprocessing_applied = [_PARSE_NOTE]
    qreg_note = unordered_qreg_note(parse_measurement_layout(qasm))
    if qreg_note:
        preprocessing_applied.append(qreg_note)
    opt_level = payload.get("optimization_level", 0)
    if opt_level > 0:
        qiskit_circ = qiskit_transpile(qiskit_circ, optimization_level=min(opt_level, 3))
        preprocessing_applied.append(
            f"qiskit.compiler.transpile(level={min(opt_level, 3)}): Native Qiskit "
            "transpilation pass applied to optimize the circuit structure for the Aer backend.")
    preprocessing_applied.append(_METHOD_NOTE)

    return tk_circ, qiskit_circ, preprocessing_applied


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qiskit simulation.")
    sim = _simulator()

    def compile_step(payload):
        """Capture the QASM before save_statevector() appends an Aer-only instruction."""
        qasm, strip_notes = prepare_statevector_qasm(payload["circuit_data"])
        tk_circ, qiskit_circ, preprocessing_applied = _to_qiskit(qasm, payload)
        transpiled_qasm = qasm2.dumps(qiskit_circ)
        qiskit_circ.save_statevector()
        return CompileResult(
            circuit=(sim, qiskit_circ),
            n_qubits=tk_circ.n_qubits,
            preprocessing_applied=strip_notes + preprocessing_applied + [_SAVE_STATEVECTOR_NOTE],
            transpiled_qasm=transpiled_qasm)

    def execute(compiled, _payload):
        backend, qiskit_circ = compiled.circuit
        return backend.run(qiskit_circ, optimization_level=0).result()

    def shape_statevector(aer_result, _compiled, _payload):
        backend_fields.update(_backend_fields(aer_result, sim))
        return aer_result.get_statevector()

    backend_fields = {}
    result = run_statevector_job(
        simulator="qiskit", payload=payload, logger=logger, compile_fn=compile_step,
        execute_fn=execute, postprocess_fn=shape_statevector, qubit_ordering="lsb",
        precision="complex128")
    if "error" not in result:
        result.update(backend_fields)
    return result


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qiskit simulation.")
    sim = _simulator()

    def compile_step(payload):
        tk_circ, qiskit_circ, preprocessing_applied = _to_qiskit(payload["circuit_data"], payload)
        return CompileResult(
            circuit=(sim, qiskit_circ),
            n_qubits=tk_circ.n_qubits,
            preprocessing_applied=preprocessing_applied + [_COUNTS_KEY_NOTE])

    def serialize(compiled):
        return qasm2.dumps(compiled.circuit[1])

    def execute(compiled, payload):
        backend, qiskit_circ = compiled.circuit
        return backend.run(
            qiskit_circ, optimization_level=0, shots=payload.get("n_shots", 1024),
            seed_simulator=payload.get("seed")).result()

    def shape_counts(aer_result, compiled, payload):
        """Re-key Aer counts over the circuit's declared classical bits (lsb)."""
        backend_fields.update(_backend_fields(aer_result, sim))
        registers = [(reg.name, reg.size) for reg in compiled.circuit[1].cregs]
        layout = parse_measurement_layout(payload["circuit_data"])
        counts = counts_from_register_keys(layout, aer_result.get_counts(), registers, "lsb")
        return counts, "native"

    backend_fields = {}
    result = run_measured_job(
        simulator="qiskit", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="lsb", precision="complex128")
    if "error" not in result:
        result.update(backend_fields)
    return result


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qiskit")
