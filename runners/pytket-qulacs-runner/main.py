"""Qulacs runner: executes OpenQASM 2.0 circuits on pytket's QulacsBackend."""

from random import Random

from fastapi import FastAPI
from qrosetta_commons.counts import (
    counts_from_pytket_result, parse_measurement_layout, prepare_statevector_qasm,
    statevector_in_declaration_order, unit_pairs, unordered_qreg_note,
)
from qrosetta_commons.helpers import (
    CompileResult, declare_sdk_packages, get_logger, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, with_sdk_versions,
)
import pytket.qasm
from pytket.extensions.qulacs import QulacsBackend
from pytket.passes import RemoveBarriers

declare_sdk_packages("pytket", "pytket-qulacs", "qulacs")

logger = get_logger("pytket-qulacs-runner")

app = FastAPI(title="Qulacs Runner")

_REMOVE_BARRIERS_NOTE = (
    "pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to "
    "prevent parsing failures in the Qulacs backend adapter.")

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


class _QulacsBackend(QulacsBackend):
    """QulacsBackend that honours seed=0.

    pytket-qulacs builds its RNG with ``Random(seed) if seed else None``, which discards a
    seed of 0; this supplies ``Random(seed)`` whenever a seed was given.
    """

    _seed = None

    def process_circuits(self, circuits, n_shots=None, valid_check=True, **kwargs):
        self._seed = kwargs.get("seed")
        return super().process_circuits(circuits, n_shots, valid_check, **kwargs)

    def _sample_quantum_state(self, quantum_state, n_shots, rng):
        if rng is None and self._seed is not None:
            rng = Random(self._seed)
        return super()._sample_quantum_state(quantum_state, n_shots, rng)


def _compile(payload: dict, qasm: str, notes=()) -> CompileResult:
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm)
    preprocessing_applied = list(notes)
    qreg_note = unordered_qreg_note(parse_measurement_layout(qasm))
    if qreg_note:
        preprocessing_applied.append(qreg_note)
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)

    backend = _QulacsBackend()
    opt_level = min(payload.get("optimization_level", 0), 2)
    compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
    preprocessing_applied.append(_compilation_note(backend, opt_level))

    return CompileResult(
        circuit=(backend, compiled_circ, unit_pairs(tk_circ.bits), unit_pairs(tk_circ.qubits)),
        n_qubits=tk_circ.n_qubits,
        preprocessing_applied=preprocessing_applied)


def _compile_statevector(payload: dict) -> CompileResult:
    qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
    return _compile(payload, qasm, notes)


def _compile_measured(payload: dict) -> CompileResult:
    """Compile with the circuit's own measurements; the backend samples them at the end."""
    parse_measurement_layout(payload["circuit_data"]).require_terminal()
    compiled = _compile(payload, payload["circuit_data"])
    compiled.preprocessing_applied.append(_COUNTS_KEY_NOTE)
    return compiled


def _serialize(compiled: CompileResult) -> str:
    circ = compiled.circuit[1]
    return pytket.qasm.circuit_to_qasm_str(circ, maxwidth=max(32, len(circ.bits)))


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qulacs simulation.")

    def execute(compiled, _payload):
        backend, compiled_circ, _, _ = compiled.circuit
        return backend.get_result(backend.process_circuit(compiled_circ))

    def to_state(result, compiled, payload):
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
        backend, compiled_circ, _, _ = compiled.circuit
        handle = backend.process_circuit(
            compiled_circ, n_shots=payload.get("n_shots", 1024), seed=payload.get("seed"))
        return backend.get_result(handle)

    def shape_counts(result, compiled, payload):
        """Re-key the counts over the declared classical bits (msb)."""
        _, compiled_circ, bits, _ = compiled.circuit
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
