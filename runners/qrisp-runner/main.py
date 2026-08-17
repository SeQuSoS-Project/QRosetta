# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, get_num_qubits_from_qasm, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, with_sdk_versions,
)
import numpy as np

logger = get_logger("qrisp-runner")

app = FastAPI(title="Qrisp Runner")

def _parse(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 into a Qrisp QuantumCircuit.

    Qrisp's QuantumCircuit is a QASM-level wrapper; its optimization model is
    designed for high-level Qrisp programs, not post-QASM gate passes. All
    optimization levels run identically.
    """
    from qrisp import QuantumCircuit
    if optimization_level > 0:
        logger.info(
            f"Qrisp: optimization_level={optimization_level} requested "
            "but not applicable at the QASM circuit level; running at level 0."
        )
    return QuantumCircuit.from_qasm_str(qasm_str)


def _compile(payload: dict) -> CompileResult:
    circuit = _parse(payload["circuit_data"], payload.get("optimization_level", 0))
    return CompileResult(
        circuit=circuit,
        n_qubits=get_num_qubits_from_qasm(payload["circuit_data"]),
        preprocessing_applied=[],
        transpiled_qasm=payload["circuit_data"])


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qrisp simulation.")

    def execute(compiled, _payload):
        # The statevector lives on the low-level QuantumCircuit itself via
        # statevector_array(); Qrisp's QASM-imported QuantumCircuit has no `.qs`
        # (QuantumSession) attribute, so the high-level qs.statevector() API is
        # not available here.
        return np.asarray(compiled.circuit.statevector_array(), dtype=complex)

    # Qrisp's statevector_array() is big-endian: qubit 0 is the most significant bit of
    # the amplitude index (verified: X on qubit 0 populates index 2^(n-1)). This differs
    # from the counts convention of run() below, which is little-endian; both are labelled
    # to match their actual native output rather than forced to a single value.
    return run_statevector_job(
        simulator="qrisp", payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, qubit_ordering="msb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qrisp simulation.")

    def seed_rng(_compiled, payload):
        # Qrisp's simulator samples via numpy's global RNG (run() exposes no seed
        # argument); seeding it makes the run reproducible. seed=None leaves it
        # non-deterministic (prior behaviour).
        if payload.get("seed") is not None:
            np.random.seed(payload["seed"])

    def execute(compiled, payload):
        # Native shot-based sampling runs through the low-level circuit's run()
        # method (the high-level get_measurement() API belongs to QuantumVariable
        # and is not available on a QASM-imported QuantumCircuit). This requires
        # the circuit to carry measurement instructions, which measured-mode QASM does.
        return compiled.circuit.run(shots=payload.get("n_shots", 1024)), "native"

    # Qrisp's run() counts keys are little-endian: qubit 0 is the right-most character of
    # the bitstring (verified: X on qubit 0 yields '0...01'), matching the qiskit/Aer
    # counts convention. Note this differs from the statevector endpoint's big-endian
    # ordering above; each is labelled to reflect Qrisp's actual native output.
    return run_measured_job(
        simulator="qrisp", payload=payload, logger=logger, compile_fn=_compile,
        pre_execute_fn=seed_rng, execute_fn=execute, qubit_ordering="lsb")


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("Qrisp runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qrisp")
