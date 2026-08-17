# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, with_sdk_versions,
)
import numpy as np

from qibo.models import Circuit
from qibo import gates, set_backend

set_backend("numpy")

logger = get_logger("qibo-runner")

app = FastAPI(title="Qibo Runner")

def _parse(qasm_str: str, optimization_level: int = 0) -> tuple[Circuit, list[str]]:
    """Parse QASM 2.0 into a Qibo Circuit and apply gate fusion.

    Level 0: no optimization
    Level 1: fuse single-qubit gate runs (max_qubits=1)
    Level 2: fuse up to 2-qubit blocks (max_qubits=2)
    """
    circuit = Circuit.from_qasm(qasm_str)
    preprocessing_applied = []
    if optimization_level >= 2:
        circuit = circuit.fuse(max_qubits=2)
        preprocessing_applied.append("qibo.Circuit.fuse(max_qubits=2): Fuses consecutive gate sequences acting on up to 2 qubits into single unitary blocks, reducing gate count at the cost of larger per-block matrices.")
    elif optimization_level == 1:
        circuit = circuit.fuse(max_qubits=1)
        preprocessing_applied.append("qibo.Circuit.fuse(max_qubits=1): Fuses consecutive single-qubit gate runs into single unitary blocks, reducing sequential gate overhead.")
    return circuit, preprocessing_applied


def _compile(payload: dict) -> CompileResult:
    circuit, preprocessing_applied = _parse(
        payload["circuit_data"], payload.get("optimization_level", 0))
    return CompileResult(
        circuit=circuit,
        n_qubits=circuit.nqubits,
        preprocessing_applied=preprocessing_applied,
        transpiled_qasm=payload["circuit_data"])


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qibo simulation.")

    def execute(compiled, _payload):
        return np.array(compiled.circuit().state())

    return run_statevector_job(
        simulator="qibo", payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, qubit_ordering="msb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qibo simulation.")

    def compile_step(payload):
        compiled = _compile(payload)
        if not compiled.circuit.measurements:
            compiled.circuit.add(gates.M(*range(compiled.circuit.nqubits)))
        return compiled

    def seed_rng(_compiled, payload):
        # Qibo's numpy backend samples via numpy's global RNG; seeding it makes
        # the run reproducible. seed=None leaves it non-deterministic (prior behaviour).
        if payload.get("seed") is not None:
            np.random.seed(payload["seed"])

    def execute(compiled, payload):
        result = compiled.circuit(nshots=payload.get("n_shots", 1024))
        return dict(result.frequencies()), "native"

    return run_measured_job(
        simulator="qibo", payload=payload, logger=logger, compile_fn=compile_step,
        pre_execute_fn=seed_rng, execute_fn=execute, qubit_ordering="msb")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qibo")
