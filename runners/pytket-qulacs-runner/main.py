"""Qulacs runner: executes OpenQASM 2.0 circuits on pytket's QulacsBackend."""

from random import Random

from fastapi import FastAPI
from qrosetta_commons.counts import (
    PYTKET_BROADCAST_REASON, PYTKET_QASM_MAXWIDTH, expand_register_broadcasts,
    counts_from_pytket_result, parse_measurement_layout, prepare_statevector_qasm,
    statevector_in_declaration_order, unit_pairs, unordered_qreg_note,
)
from qrosetta_commons.helpers import (
    CompileResult, declare_sdk_packages, get_logger, register_runner_endpoints,
    require_distribution_version, run_cli_main, run_measured_job, run_statevector_job,
    with_sdk_versions,
)
import numpy as np
import pytket.qasm
from pytket.backends.backendresult import BackendResult
from pytket.circuit import OpType
from pytket.extensions.qulacs import QulacsBackend, tk_to_qulacs
from pytket.passes import RemoveBarriers
from pytket.utils.outcomearray import OutcomeArray

declare_sdk_packages("pytket", "pytket-qulacs", "qulacs")
require_distribution_version("pytket-qulacs", "0.38.0", "QulacsBackend.process_circuits")

logger = get_logger("pytket-qulacs-runner")

app = FastAPI(title="Qulacs Runner")

_REMOVE_BARRIERS_NOTE = (
    "pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to "
    "prevent parsing failures in the Qulacs backend adapter.")

_CONVERT_NOTE = (
    "pytket QulacsBackend's circuit checks and tk_to_qulacs(reverse_index=True, "
    "replace_implicit_swaps=True) run after the default compilation pass, inside "
    "compilation_time; the timed run applies the converted circuit to a fresh |0...0> "
    "QuantumState, as QulacsBackend.process_circuits does, and reads the result. In "
    "statevector mode the global phase of the pytket circuit is restored after the timed run.")

_MEASURED_NOTE = (
    "Measured mode: which qubits the circuit's measurements read (through the circuit's "
    "implicit wire permutation, as QulacsBackend.process_circuits finds them) is worked out in "
    "compilation_time; the timed run applies the converted circuit and draws the shots with "
    "QuantumState.sampling, seeded as QulacsBackend does with a given seed (seed 0 included).")

_COUNTS_KEY_NOTE = (
    "Counts keys: BackendResult.get_counts() tuples are re-keyed to one bitstring over every "
    "declared classical bit in declaration order, flat clbit 0 leftmost.")

_PASS_NOTES = {}


def _pass_names(pass_dict):
    kind = pass_dict["pass_class"]
    if kind == "SequencePass":
        return [n for p in pass_dict["SequencePass"]["sequence"] for n in _pass_names(p)]
    if kind == "StandardPass":
        return [pass_dict["StandardPass"]["name"]]
    return [kind]


def _compilation_note(backend, level):
    """Describe the backend's default compilation pass, which runs at every level."""
    key = (type(backend).__name__.lstrip("_"), level)
    if key not in _PASS_NOTES:
        names = ", ".join(_pass_names(backend.default_compilation_pass(level).to_dict()))
        _PASS_NOTES[key] = (
            f"pytket {key[0]}.get_compiled_circuit(optimisation_level={level}): the "
            f"backend's default compilation pass [{names}], applied at every optimisation "
            "level including 0; rewrites the circuit into the backend's supported gate set.")
    return _PASS_NOTES[key]


def _compile(payload: dict, qasm: str, notes=()) -> CompileResult:
    qasm, broadcast_note = expand_register_broadcasts(qasm, PYTKET_BROADCAST_REASON)
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm, maxwidth=PYTKET_QASM_MAXWIDTH)
    preprocessing_applied = list(notes) + ([broadcast_note] if broadcast_note else [])
    qreg_note = unordered_qreg_note(parse_measurement_layout(qasm))
    if qreg_note:
        preprocessing_applied.append(qreg_note)
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)

    backend = QulacsBackend()
    opt_level = min(payload.get("optimization_level", 0), 2)
    compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
    preprocessing_applied.append(_compilation_note(backend, opt_level))
    backend._check_all_circuits([compiled_circ], nomeasure_warn=False)
    qulacs_circ = tk_to_qulacs(compiled_circ, reverse_index=True, replace_implicit_swaps=True)
    preprocessing_applied.append(_CONVERT_NOTE)

    return CompileResult(
        circuit=(backend, compiled_circ, unit_pairs(tk_circ.bits), unit_pairs(tk_circ.qubits),
                 qulacs_circ),
        n_qubits=tk_circ.n_qubits,
        preprocessing_applied=preprocessing_applied)


def _final_state(compiled):
    """Apply the converted circuit to a fresh |0...0> state (QulacsBackend.process_circuits)."""
    backend, compiled_circ, qulacs_circ = compiled.circuit[0], compiled.circuit[1], compiled.circuit[4]
    state = backend._sim(compiled_circ.n_qubits)
    state.set_zero_state()
    qulacs_circ.update_quantum_state(state)
    return state


def _with_global_phase(vector, compiled_circ):
    return vector * np.exp(float(compiled_circ.phase) * np.pi * 1j)


def _measured_bits(compiled_circ):
    """(classical bits, qubit positions) read out, through the implicit wire permutation,
    as QulacsBackend.process_circuits computes them."""
    qubits = sorted(compiled_circ.qubits, reverse=False)
    wire_map = compiled_circ.implicit_qubit_permutation()
    pairs = [(com.bits[0], qubits.index(wire_map[com.qubits[0]]))
             for com in compiled_circ if com.op.type == OpType.Measure]
    if not pairs:
        return None, None
    bits, positions = zip(*pairs)
    return list(bits), list(positions)


def _compile_statevector(payload: dict) -> CompileResult:
    qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
    return _compile(payload, qasm, notes)


def _compile_measured(payload: dict) -> CompileResult:
    """Compile with the circuit's own measurements; the backend samples them at the end."""
    parse_measurement_layout(payload["circuit_data"]).require_terminal()
    compiled = _compile(payload, payload["circuit_data"])
    compiled.circuit = (*compiled.circuit, _measured_bits(compiled.circuit[1]))
    compiled.preprocessing_applied.append(_MEASURED_NOTE)
    compiled.preprocessing_applied.append(_COUNTS_KEY_NOTE)
    return compiled


def _serialize(compiled: CompileResult) -> str:
    circ = compiled.circuit[1]
    return pytket.qasm.circuit_to_qasm_str(circ, maxwidth=max(32, len(circ.bits)))


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qulacs simulation.")

    def execute(compiled, _payload):
        return _final_state(compiled).get_vector()

    def to_state(vector, compiled, payload):
        compiled_circ = compiled.circuit[1]
        result = BackendResult(state=_with_global_phase(vector, compiled_circ),
                               q_bits=sorted(compiled_circ.qubits, reverse=False))
        return statevector_in_declaration_order(
            result.get_state(), payload["circuit_data"], compiled.circuit[3], "msb",
            compiled.preprocessing_applied)

    return run_statevector_job(
        simulator="qulacs", payload=payload, logger=logger, compile_fn=_compile_statevector,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=to_state,
        qubit_ordering="msb", precision="complex128")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qulacs simulation.")

    def execute(compiled, payload):
        """Sample the final state as QulacsBackend.process_circuits does (seed 0 honoured)."""
        n_shots = payload.get("n_shots", 1024)
        if compiled.circuit[5][0] is None:
            return None
        state = _final_state(compiled)
        seed = payload.get("seed")
        if seed is None:
            return state.sampling(n_shots)
        return state.sampling(n_shots, Random(seed).randint(0, 2**32 - 1))

    def shape_counts(samples, compiled, payload):
        """Re-key the counts over the declared classical bits (msb)."""
        _, compiled_circ, bits, _, _, (measured, positions) = compiled.circuit
        if measured is None:
            measured = compiled_circ.bits
            shots = OutcomeArray.from_ints([0] * payload.get("n_shots", 1024), len(measured))
        else:
            shots = OutcomeArray.from_ints(samples, compiled_circ.n_qubits).choose_indices(positions)
        result = BackendResult(shots=shots, c_bits=measured,
                               q_bits=sorted(compiled_circ.qubits, reverse=False))
        layout = parse_measurement_layout(payload["circuit_data"])
        return counts_from_pytket_result(
            layout, result, compiled_circ.bits, bits, "msb"), "native"

    return run_measured_job(
        simulator="qulacs", payload=payload, logger=logger, compile_fn=_compile_measured,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision="complex128")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qulacs")
