"""ProjectQ runner: executes OpenQASM 2.0 circuits on pytket's ProjectQBackend.

ProjectQ has no shot sampler here, so the measured endpoint samples the computed statevector.
"""

from fastapi import FastAPI
import pytket.qasm
from pytket.extensions.projectq import ProjectQBackend
from pytket.passes import RemoveBarriers
from pytket.transform import Transform
from projectq.types._qubit import Qubit
from qrosetta_commons.counts import (
    parse_measurement_layout, prepare_final_state_sampling, prepare_statevector_qasm,
    statevector_in_declaration_order, unit_pairs, unordered_qreg_note,
)
from qrosetta_commons.helpers import (
    CompileResult, _draw_statevector_samples, get_logger,
    register_runner_endpoints, run_cli_main, run_measured_job, run_statevector_job,
    with_sdk_versions,
)

app = FastAPI(title="ProjectQ Runner")
logger = get_logger("pytket-projectq-runner")

_original_del = Qubit.__del__


def _quiet_del(self):
    """Suppress ProjectQ's error for qubits deallocated unmeasured after a statevector run."""
    try:
        _original_del(self)
    except RuntimeError as e:
        if "Qubit has not been measured / uncomputed" not in str(e):
            raise


Qubit.__del__ = _quiet_del

_REMOVE_BARRIERS_NOTE = (
    "pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to "
    "prevent parsing failures in the backend adapter.")
_REBASE_NOTE = (
    "pytket.transform.Transform.RebaseToTket(): rebases the circuit to pytket's CX + TK1 "
    "gate set before the backend's compilation pass, applied regardless of "
    "apply_preprocessing.")

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
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm)
    preprocessing_applied = list(notes)
    qreg_note = unordered_qreg_note(parse_measurement_layout(qasm))
    if qreg_note:
        preprocessing_applied.append(qreg_note)
    if payload.get("apply_preprocessing", True):
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append(_REMOVE_BARRIERS_NOTE)

    Transform.RebaseToTket().apply(tk_circ)
    preprocessing_applied.append(_REBASE_NOTE)

    backend = ProjectQBackend()
    opt_level = min(payload.get("optimization_level", 0), 2)
    compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
    preprocessing_applied.append(_compilation_note(backend, opt_level))

    return CompileResult(
        circuit=(backend, compiled_circ, unit_pairs(tk_circ.qubits)),
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


def _serialize(compiled: CompileResult) -> str:
    return pytket.qasm.circuit_to_qasm_str(compiled.circuit[1])


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for ProjectQ simulation.")

    def execute(compiled, _payload):
        backend, compiled_circ, _ = compiled.circuit
        return backend.get_result(backend.process_circuit(compiled_circ))

    def to_state(result, compiled, payload):
        return statevector_in_declaration_order(
            result.get_state(), payload["circuit_data"], compiled.circuit[2], "msb",
            compiled.preprocessing_applied)

    return run_statevector_job(
        simulator="projectq", payload=payload, logger=logger, compile_fn=_compile_statevector,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=to_state,
        qubit_ordering="msb", precision="complex128")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for ProjectQ (statevector sampling).")

    def execute(compiled, payload):
        backend, compiled_circ, _layout, _qubits = compiled.circuit
        handle = backend.process_circuit(compiled_circ)
        statevector = backend.get_result(handle).get_state()
        return _draw_statevector_samples(
            statevector, payload.get("n_shots", 1024), payload.get("seed"))

    def shape_counts(samples, compiled, _payload):
        _, _, layout, backend_qubits = compiled.circuit
        positions = layout.qubit_positions("msb", backend_qubits)
        return layout.counts_from_qubit_samples(samples, positions, "msb"), None

    return run_measured_job(
        simulator="projectq", payload=payload, logger=logger, compile_fn=_compile_sampled,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision="complex128")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "ProjectQ")
