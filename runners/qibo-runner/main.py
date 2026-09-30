"""Qibo runner: parses OpenQASM 2.0 with qibo.Circuit.from_qasm and simulates it on Qibo's numpy backend."""

import re

from fastapi import FastAPI
from qrosetta_commons.counts import (
    expand_register_broadcasts, prepare_final_state_sampling, prepare_statevector_qasm,
)
from qrosetta_commons.helpers import (
    CompileResult, declare_sdk_packages, get_logger, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, with_sdk_versions,
)
import numpy as np

from qibo.models import Circuit
from qibo import gates, set_backend

set_backend("numpy")

declare_sdk_packages("qibo")

logger = get_logger("qibo-runner")

app = FastAPI(title="Qibo Runner")

_PRECISION = "complex128"

_FROM_QASM_NOTE = (
    "qibo.models.Circuit.from_qasm(): Qibo's own OpenQASM 2.0 parser builds the circuit; "
    "qelib1 gates map to Qibo gates, and Qibo's U3 differs from qelib1 u3 by the global "
    "phase e^{-i(phi+lambda)/2}, which becomes a relative phase once the gate is controlled "
    "(cu3). Required by the adapter, applied regardless of apply_preprocessing.")
_REMOVE_BARRIERS_NOTE = (
    "Regex removal of barrier statements: Circuit.from_qasm rejects every barrier "
    "(\"Unsupported QuantumBarrier statement\").")
_BROADCAST_REASON = "qibo.models.Circuit.from_qasm accepts only indexed qubit operands"
_BARRIER_RE = re.compile(r"\bbarrier\b[^;]*;")
_FUSION_NOTE_SUFFIX = (
    " transpiled_qasm is the circuit before fusion, since fused blocks have no OpenQASM 2.0 "
    "form.")
_ADD_MEASUREMENTS_NOTE = (
    "qibo.gates.M(all qubits): one non-collapsing measurement of every qubit is appended to "
    "the measurement-free circuit, because Circuit.from_qasm marks a measurement followed by "
    "any later statement as collapsing. Required by the adapter, applied regardless of "
    "apply_preprocessing.")
_SAMPLING_NOTE = (
    "qibo CircuitResult.frequencies(): Qibo draws the shot frequencies and tallies them in "
    "one call, so the tally is inside simulation_time_sec.")


def _parse(qasm_str: str, optimization_level: int = 0) -> tuple[Circuit, list[str]]:
    """Parse QASM 2.0 into a Qibo Circuit and apply gate fusion.

    Level 0: no optimization
    Level 1: fuse single-qubit gate runs (max_qubits=1)
    Level 2+: fuse up to 2-qubit blocks (max_qubits=2)
    """
    circuit = Circuit.from_qasm(qasm_str)
    preprocessing_applied = [_FROM_QASM_NOTE]
    if optimization_level >= 2:
        circuit = circuit.fuse(max_qubits=2)
        preprocessing_applied.append(
            "qibo.Circuit.fuse(max_qubits=2): Fuses consecutive gate sequences acting on up "
            "to 2 qubits into single unitary blocks." + _FUSION_NOTE_SUFFIX)
    elif optimization_level == 1:
        circuit = circuit.fuse(max_qubits=1)
        preprocessing_applied.append(
            "qibo.Circuit.fuse(max_qubits=1): Fuses consecutive single-qubit gate runs into "
            "single unitary blocks." + _FUSION_NOTE_SUFFIX)
    return circuit, preprocessing_applied


def _compile(payload: dict, qasm: str, notes=()) -> CompileResult:
    notes = list(notes)
    qasm, broadcast_note = expand_register_broadcasts(qasm, _BROADCAST_REASON)
    if broadcast_note:
        notes.append(broadcast_note)
    if payload.get("apply_preprocessing", True) and _BARRIER_RE.search(qasm):
        qasm = _BARRIER_RE.sub("", qasm)
        notes.append(_REMOVE_BARRIERS_NOTE)
    circuit, preprocessing_applied = _parse(qasm, payload.get("optimization_level", 0))
    return CompileResult(
        circuit=circuit,
        n_qubits=circuit.nqubits,
        preprocessing_applied=notes + preprocessing_applied,
        transpiled_qasm=qasm,
        precision=_PRECISION)


def _compile_statevector(payload: dict) -> CompileResult:
    qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
    return _compile(payload, qasm, notes)


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qibo simulation.")

    def execute(compiled, _payload):
        return compiled.circuit().state()

    def shape_statevector(state, _compiled, _payload):
        return np.array(state)

    return run_statevector_job(
        simulator="qibo", payload=payload, logger=logger, compile_fn=_compile_statevector,
        execute_fn=execute, postprocess_fn=shape_statevector, qubit_ordering="msb",
        precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qibo simulation.")

    def compile_step(payload):
        qasm, layout, notes = prepare_final_state_sampling(payload["circuit_data"])
        compiled = _compile(payload, qasm, notes)
        compiled.circuit.add(gates.M(*range(compiled.circuit.nqubits)))
        compiled.preprocessing_applied += [_ADD_MEASUREMENTS_NOTE, _SAMPLING_NOTE]
        compiled.circuit = (compiled.circuit, layout)
        return compiled

    def seed_rng(_compiled, payload):
        """Qibo's numpy backend samples from numpy's global RNG."""
        if payload.get("seed") is not None:
            np.random.seed(payload["seed"])

    def execute(compiled, payload):
        circuit, _ = compiled.circuit
        return circuit(nshots=payload.get("n_shots", 1024)).frequencies(binary=False)

    def shape_counts(frequencies, compiled, _payload):
        """Map the all-qubit outcomes (qubit 0 most significant) to classical-bit keys."""
        _, layout = compiled.circuit
        positions = layout.qubit_positions("msb")
        return layout.counts_from_qubit_counts(frequencies, positions, "msb"), "native"

    return run_measured_job(
        simulator="qibo", payload=payload, logger=logger, compile_fn=compile_step,
        pre_execute_fn=seed_rng, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision=_PRECISION)


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qibo")
