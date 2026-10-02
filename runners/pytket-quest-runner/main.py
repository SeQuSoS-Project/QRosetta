"""QuEST runner: executes OpenQASM 2.0 circuits on pytket's QuESTBackend.

QuEST has no shot sampler here, so the measured endpoint samples the computed statevector.
"""

from fastapi import FastAPI
import numpy as np
import pytket.qasm
from pytket.backends.backendresult import BackendResult
from pytket.extensions.quest import QuESTBackend, tk_to_quest
from qrosetta_commons.counts import (
    PYTKET_BROADCAST_REASON, PYTKET_QASM_MAXWIDTH, expand_register_broadcasts,
    parse_measurement_layout, prepare_final_state_sampling, prepare_statevector_qasm,
    statevector_in_declaration_order, unit_pairs, unordered_qreg_note,
)
from qrosetta_commons.helpers import (
    CompileResult, declare_sdk_packages, _draw_statevector_samples, get_logger,
    register_runner_endpoints, require_distribution_version, run_cli_main, run_measured_job,
    run_statevector_job, with_sdk_versions,
)
from pytket.passes import RemoveBarriers

declare_sdk_packages("pytket", "pytket-quest", "pyquest")
require_distribution_version("pytket-quest", "0.1.0", "QuESTBackend.process_circuits")

app = FastAPI(title="QuEST Runner")
logger = get_logger("pytket-quest-runner")

_REMOVE_BARRIERS_NOTE = (
    "pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to "
    "prevent parsing failures in the QuEST backend adapter.")

_CONVERT_NOTE = (
    "pytket QuESTBackend's circuit checks and tk_to_quest(reverse_index=True, "
    "replace_implicit_swaps=True) run after the default compilation pass, inside "
    "compilation_time; the timed run applies the converted circuit to a fresh QuEST "
    "register, as QuESTBackend.process_circuits does, and reads the amplitudes. In statevector "
    "mode the global phase of the pytket circuit is restored after the timed run; in measured "
    "mode the phase is applied, the state read as BackendResult.get_state() and the shots "
    "drawn inside the timed run.")

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
    key = (type(backend).__name__, level)
    if key not in _PASS_NOTES:
        names = ", ".join(_pass_names(backend.default_compilation_pass(level).to_dict()))
        _PASS_NOTES[key] = (
            f"pytket {key[0]}.get_compiled_circuit(optimisation_level={level}): the "
            f"backend's default compilation pass [{names}], applied at every optimisation "
            "level including 0; rewrites the circuit into the backend's supported gate set.")
    return _PASS_NOTES[key]


def _compile(payload: dict, qasm: str, notes) -> CompileResult:
    qasm, broadcast_note = expand_register_broadcasts(qasm, PYTKET_BROADCAST_REASON)
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm, maxwidth=PYTKET_QASM_MAXWIDTH)
    preprocessing_applied = list(notes) + ([broadcast_note] if broadcast_note else [])
    qreg_note = unordered_qreg_note(parse_measurement_layout(qasm))
    if qreg_note:
        preprocessing_applied.append(qreg_note)
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)

    backend = QuESTBackend()
    opt_level = min(payload.get("optimization_level", 0), 2)
    compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
    preprocessing_applied.append(_compilation_note(backend, opt_level))
    backend._check_all_circuits([compiled_circ], nomeasure_warn=False)
    quest_circ = tk_to_quest(compiled_circ, reverse_index=True, replace_implicit_swaps=True)
    preprocessing_applied.append(_CONVERT_NOTE)

    return CompileResult(
        circuit=(backend, (compiled_circ, quest_circ), unit_pairs(tk_circ.qubits)),
        n_qubits=tk_circ.n_qubits,
        preprocessing_applied=preprocessing_applied)


def _compile_statevector(payload: dict) -> CompileResult:
    qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
    return _compile(payload, qasm, notes)


def _compile_sampled(payload: dict) -> CompileResult:
    """Compile the measurement-free circuit; the layout maps sampled qubits to clbits."""
    qasm, layout, notes = prepare_final_state_sampling(payload["circuit_data"])
    compiled = _compile(payload, qasm, notes)
    backend, compiled_circ, backend_qubits = compiled.circuit
    compiled.circuit = (backend, compiled_circ, layout, backend_qubits)
    return compiled


def _final_amplitudes(compiled):
    """Apply the converted circuit to a fresh register (QuESTBackend.process_circuits)."""
    backend, (compiled_circ, quest_circ) = compiled.circuit[:2]
    register = backend._sim(compiled_circ.n_qubits, backend._density_matrix)
    register.apply_circuit(quest_circ)
    return register[:]


def _state(amplitudes, compiled_circ):
    """The statevector with the pytket circuit's global phase, as BackendResult.get_state()."""
    amplitudes = amplitudes * np.exp(float(compiled_circ.phase) * np.pi * 1j)
    return BackendResult(state=amplitudes, q_bits=sorted(compiled_circ.qubits, reverse=False)).get_state()


def _serialize(compiled: CompileResult) -> str:
    circ = compiled.circuit[1][0]
    return pytket.qasm.circuit_to_qasm_str(circ, maxwidth=max(32, len(circ.bits)))


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for QuEST simulation.")

    def execute(compiled, _payload):
        return _final_amplitudes(compiled)

    def to_state(amplitudes, compiled, payload):
        return statevector_in_declaration_order(
            _state(amplitudes, compiled.circuit[1][0]), payload["circuit_data"],
            compiled.circuit[2], "msb", compiled.preprocessing_applied)

    return run_statevector_job(
        simulator="quest", payload=payload, logger=logger, compile_fn=_compile_statevector,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=to_state,
        qubit_ordering="msb", precision="complex128")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for QuEST (statevector sampling).")

    def execute(compiled, payload):
        statevector = _state(_final_amplitudes(compiled), compiled.circuit[1][0])
        return _draw_statevector_samples(
            statevector, payload.get("n_shots", 1024), payload.get("seed"))

    def shape_counts(samples, compiled, _payload):
        _, _, layout, backend_qubits = compiled.circuit
        positions = layout.qubit_positions("msb", backend_qubits)
        return layout.counts_from_qubit_samples(samples, positions, "msb"), "sv_sample"

    return run_measured_job(
        simulator="quest", payload=payload, logger=logger, compile_fn=_compile_sampled,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision="complex128")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "QuEST")
