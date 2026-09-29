"""Qrisp runner: imports OpenQASM 2.0 into a low-level qrisp.QuantumCircuit and runs Qrisp's built-in simulator."""

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, get_num_qubits_from_qasm, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, with_sdk_versions,
)
import numpy as np

logger = get_logger("qrisp-runner")

app = FastAPI(title="Qrisp Runner")

_PRECISION = "complex64"

_IMPORT_NOTE = (
    "qrisp.QuantumCircuit.from_qasm_str(): Qrisp parses the QASM with "
    "qiskit.QuantumCircuit.from_qasm_str and converts it with QuantumCircuit.from_qiskit. "
    "Qrisp's simulator uses complex64 (qrisp.simulator.unitary_management.np_dtype). "
    "Required by the adapter, applied regardless of apply_preprocessing.")
_SAMPLING_NOTE = (
    "qrisp.QuantumCircuit.run(): Qrisp samples the shots and tallies them in one call, so "
    "the tally is inside simulation_time_sec. Counts keys are ordered by classical bit, "
    "c[0] right-most.")


def _parse(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 into a Qrisp QuantumCircuit.

    Qrisp's optimisations target high-level Qrisp programs, so optimization_level is not
    applied to an imported circuit.
    """
    from qrisp import QuantumCircuit
    if optimization_level > 0:
        logger.info(
            f"Qrisp: optimization_level={optimization_level} requested "
            "but not applicable at the QASM circuit level; running at level 0.")
    return QuantumCircuit.from_qasm_str(qasm_str)


def _compile(payload: dict, extra_notes=()) -> CompileResult:
    circuit = _parse(payload["circuit_data"], payload.get("optimization_level", 0))
    return CompileResult(
        circuit=circuit,
        n_qubits=get_num_qubits_from_qasm(payload["circuit_data"]),
        preprocessing_applied=[_IMPORT_NOTE, *extra_notes],
        transpiled_qasm=payload["circuit_data"],
        precision=_PRECISION)


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qrisp simulation.")

    def execute(compiled, _payload):
        return compiled.circuit.statevector_array()

    def shape_statevector(statevector, _compiled, _payload):
        return np.asarray(statevector, dtype=complex)

    # statevector_array() is big-endian: qubit 0 is the most significant index bit.
    return run_statevector_job(
        simulator="qrisp", payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, postprocess_fn=shape_statevector, qubit_ordering="msb",
        precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qrisp simulation.")

    def compile_step(payload):
        return _compile(payload, extra_notes=(_SAMPLING_NOTE,))

    def seed_rng(_compiled, payload):
        """Qrisp's simulator samples from numpy's global RNG; run() takes no seed."""
        if payload.get("seed") is not None:
            np.random.seed(payload["seed"])

    def execute(compiled, payload):
        return compiled.circuit.run(shots=payload.get("n_shots", 1024))

    def shape_counts(counts, _compiled, _payload):
        return counts, "native"

    # run() keys are little-endian: c[0] is the right-most character.
    return run_measured_job(
        simulator="qrisp", payload=payload, logger=logger, compile_fn=compile_step,
        pre_execute_fn=seed_rng, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="lsb", precision=_PRECISION)


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("Qrisp runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qrisp")
