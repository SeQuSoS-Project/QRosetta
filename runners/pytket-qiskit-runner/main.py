"""Qiskit runner: executes OpenQASM 2.0 circuits on Qiskit Aer (double precision)."""

from fastapi import FastAPI
import pytket.qasm
from pytket.extensions.qiskit import tk_to_qiskit
from qiskit_aer import AerSimulator
from qiskit import transpile as qiskit_transpile
from qiskit import qasm2
from qiskit.circuit import Instruction
from qiskit.circuit.library import CHGate
from qrosetta_commons.counts import (
    PYTKET_BROADCAST_REASON, PYTKET_QASM_MAXWIDTH, expand_register_broadcasts,
    counts_from_register_keys, parse_measurement_layout, prepare_statevector_qasm,
    statevector_in_declaration_order, unordered_qreg_note,
)
from qrosetta_commons.helpers import (
    CompileResult, declare_sdk_packages, get_logger, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, with_sdk_versions,
)

declare_sdk_packages("pytket", "pytket-qiskit", "qiskit", "qiskit-aer")

logger = get_logger("pytket-qiskit-runner")

app = FastAPI(title="Qiskit Runner")

_SIMULATION_METHOD = "statevector"

_PARSE_NOTE = (
    "pytket.qasm.circuit_from_qasm_str() + tk_to_qiskit(): the QASM is parsed by pytket's "
    "parser, not Qiskit's, and converted to a Qiskit circuit; gate definitions the pytket "
    "parser rejects fail here when apply_preprocessing is False. Required by the adapter, "
    "applied regardless of apply_preprocessing.")
_FUSION_NOTE = (
    "Aer gate fusion (AerSimulator default fusion_enable=True): above Aer's qubit threshold "
    "Aer fuses neighbouring gates inside its simulation, at every optimization level; "
    "gate_fusion records what Aer reported for the run, and transpiled_qasm is the circuit "
    "before fusion.")
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


_AER_OPERATIONS = frozenset(_simulator().target.operation_names)


def _fusion(metadata) -> dict:
    """Aer's gate-fusion report for the experiment: whether fusion was applied, the qubit
    threshold above which it is enabled and the largest fused gate."""
    fusion = metadata.get("fusion") or {}
    return {"source": "Aer result metadata",
            **{k: fusion.get(k) for k in ("enabled", "applied", "threshold", "max_fused_qubits")}}


def _backend_fields(result, sim) -> dict:
    """Method and device Aer reports for the executed experiment."""
    metadata = result.results[0].metadata
    method = metadata.get("method", sim.options.method)
    device = metadata.get("device", sim.options.device)
    return {
        "device": device,
        "simulation_method": method,
        "gate_fusion": _fusion(metadata),
        "simulator_backend": (
            f"qiskit-aer AerSimulator(method={method}, precision={sim.options.precision}, "
            f"device={device})"),
    }


def _define_opaque(qiskit_circ, preprocessing_applied):
    """Replace the definition-less instructions tk_to_qiskit emits for ch and u0.

    ch becomes Qiskit's CHGate; u0 (the qelib1 identity) is dropped.
    """
    replaced, kept = set(), []
    for inst in qiskit_circ.data:
        op = inst.operation
        name = op.name.split("(")[0]
        if type(op) is Instruction and op.definition is None and name in ("ch", "u0"):
            replaced.add(name)
            if name == "u0":
                continue
            inst = inst.replace(operation=CHGate())
        kept.append(inst)
    if replaced:
        qiskit_circ.data = kept
        preprocessing_applied.append(
            f"tk_to_qiskit emits {', '.join(sorted(replaced))} as instructions without a "
            "definition; ch is replaced by qiskit.circuit.library.CHGate and u0 (the qelib1 "
            "identity) is removed. Required by the adapter, applied regardless of "
            "apply_preprocessing.")
    return qiskit_circ


def _to_aer_basis(qiskit_circ, preprocessing_applied):
    """Decompose instructions Aer cannot execute (e.g. ch) at optimization_level 0."""
    missing = sorted({inst.operation.name for inst in qiskit_circ.data} - _AER_OPERATIONS)
    if not missing:
        return qiskit_circ
    preprocessing_applied.append(
        f"qiskit.compiler.transpile(backend=AerSimulator, optimization_level=0): decomposes "
        f"{', '.join(missing)}, which Aer does not execute, into gates it does. Required by "
        "the adapter, applied regardless of apply_preprocessing.")
    return qiskit_transpile(qiskit_circ, _simulator(), optimization_level=0)


def _qubit_pairs(qiskit_circ) -> list:
    """``(register, index)`` for each qubit of a Qiskit circuit, in its qubit order."""
    pairs = []
    for qubit in qiskit_circ.qubits:
        register, index = qiskit_circ.find_bit(qubit).registers[0]
        pairs.append((register.name, index))
    return pairs


def _to_qiskit(qasm: str, payload: dict):
    """Parse the QASM via pytket, convert to a Qiskit circuit, and apply the opt level."""
    layout = parse_measurement_layout(qasm)
    qasm, broadcast_note = expand_register_broadcasts(qasm, PYTKET_BROADCAST_REASON)
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm, maxwidth=PYTKET_QASM_MAXWIDTH)
    qiskit_circ = tk_to_qiskit(tk_circ)

    preprocessing_applied = [_PARSE_NOTE] + ([broadcast_note] if broadcast_note else [])
    qreg_note = unordered_qreg_note(layout)
    if qreg_note:
        preprocessing_applied.append(qreg_note)
    qiskit_circ = _define_opaque(qiskit_circ, preprocessing_applied)
    opt_level = payload.get("optimization_level", 0)
    if opt_level > 0:
        qiskit_circ = qiskit_transpile(qiskit_circ, optimization_level=min(opt_level, 3))
        preprocessing_applied.append(
            f"qiskit.compiler.transpile(level={min(opt_level, 3)}): Native Qiskit "
            "transpilation pass applied to optimize the circuit structure for the Aer backend.")
    qiskit_circ = _to_aer_basis(qiskit_circ, preprocessing_applied)
    preprocessing_applied.extend([_METHOD_NOTE, _FUSION_NOTE])

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
        backend_qubits = _qubit_pairs(qiskit_circ)
        qiskit_circ.save_statevector()
        return CompileResult(
            circuit=(sim, qiskit_circ, backend_qubits),
            n_qubits=tk_circ.n_qubits,
            preprocessing_applied=strip_notes + preprocessing_applied + [_SAVE_STATEVECTOR_NOTE],
            transpiled_qasm=transpiled_qasm)

    def execute(compiled, _payload):
        backend, qiskit_circ, _ = compiled.circuit
        return backend.run(qiskit_circ, optimization_level=0).result()

    def shape_statevector(aer_result, compiled, payload):
        backend_fields.update(_backend_fields(aer_result, sim))
        return statevector_in_declaration_order(
            aer_result.get_statevector(), payload["circuit_data"], compiled.circuit[2], "lsb",
            compiled.preprocessing_applied)

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
