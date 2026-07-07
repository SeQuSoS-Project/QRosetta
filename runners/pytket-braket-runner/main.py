# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
import pytket.qasm
from pytket.extensions.braket import BraketBackend
from pytket.passes import RemoveBarriers
import time
import gc

logger = get_logger("pytket-braket-runner")

app = FastAPI(title="Braket Runner")

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Braket simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        preprocessing_applied = []
        if payload.get("apply_preprocessing", True):
            RemoveBarriers().apply(tk_circ)
            preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the backend adapter.")

        backend = BraketBackend(local=True)
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)

        compiled_circ.add_phase(-compiled_circ.phase)

        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # Provenance only — serialized after t1 so it does not inflate compilation_time.
        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_circ)

        _ = backend.process_circuit(compiled_circ)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            handle = backend.process_circuit(compiled_circ)
            statevector = backend.get_result(handle).get_state()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(f"Braket simulation successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        return statevector_result(
            simulator="braket", statevector=statevector, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="lsb",
            n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Braket simulation: {str(e)}")
        return runner_error("braket", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Braket simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        preprocessing_applied = []
        if payload.get("apply_preprocessing", True):
            RemoveBarriers().apply(tk_circ)
            preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the backend adapter.")

        backend = BraketBackend(local=True)
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)

        compiled_circ.add_phase(-compiled_circ.phase)

        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # Provenance only — serialized after t1 so it does not inflate compilation_time.
        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_circ)

        n_shots = payload.get("n_shots", 1024)

        _ = backend.process_circuit(compiled_circ, n_shots=n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            # seed=None keeps the backend's default non-deterministic sampling.
            handle = backend.process_circuit(compiled_circ, n_shots=n_shots, seed=payload.get("seed"))
            counts = backend.get_result(handle).get_counts()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        counts_dict = {"".join(map(str, k)): int(v) for k, v in counts.items()}

        logger.info(f"Braket measurement simulation successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        # This runner does not label a sampling_method (sampling_method=None omits the key).
        return counts_result(
            simulator="braket", counts=counts_dict, sampling_method=None,
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="lsb", n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Braket measurement simulation: {str(e)}")
        return runner_error("braket", e)

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Braket")
