# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
import numpy as np
import time
import gc

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

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qibo simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        circuit, preprocessing_applied = _parse(payload["circuit_data"], payload.get("optimization_level", 0))
        transpiled_qasm = payload["circuit_data"]
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            result = circuit()
            statevector = np.array(result.state())
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(
            f"Qibo simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return statevector_result(
            simulator="qibo", statevector=statevector, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="msb",
            n_qubits=circuit.nqubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Qibo simulation: {str(e)}")
        return runner_error("qibo", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qibo simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        circuit, preprocessing_applied = _parse(payload["circuit_data"], payload.get("optimization_level", 0))
        transpiled_qasm = payload["circuit_data"]

        if not circuit.measurements:
            circuit.add(gates.M(*range(circuit.nqubits)))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        n_shots = payload.get("n_shots", 1024)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # Qibo's numpy backend samples via numpy's global RNG; seeding it makes
            # the run reproducible. seed=None leaves it non-deterministic (prior behaviour).
            if payload.get("seed") is not None:
                np.random.seed(payload["seed"])
            t2 = time.perf_counter()
            result = circuit(nshots=n_shots)
            counts_dict = dict(result.frequencies())
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(
            f"Qibo measurement simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return counts_result(
            simulator="qibo", counts=counts_dict, sampling_method="native",
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="msb", n_qubits=circuit.nqubits,
            preprocessing_applied=preprocessing_applied, transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Qibo measurement simulation: {str(e)}")
        return runner_error("qibo", e)

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qibo")
