# Execution script for the quantum simulator runner.

from fastapi import FastAPI
import pytket.qasm
from pytket.extensions.quest import QuESTBackend
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
from pytket.passes import RemoveBarriers
import time
import gc

app = FastAPI(title="QuEST Runner")
logger = get_logger("pytket-quest-runner")

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for QuEST simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        preprocessing_applied = []
        if payload.get("apply_preprocessing", True):
            RemoveBarriers().apply(tk_circ)
            preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the QuEST backend adapter.")

        backend = QuESTBackend()
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
        if opt_level > 0:
            preprocessing_applied.append(f"pytket QuESTBackend.get_compiled_circuit(level={opt_level}): pytket's native compilation pass for the QuEST backend, decomposing gates into the backend's supported gate set.")
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

        logger.info(f"QuEST simulation successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        return statevector_result(
            simulator="quest", statevector=statevector, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="msb",
            n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during QuEST simulation: {str(e)}")
        return runner_error("quest", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for QuEST (manual sampling).")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        preprocessing_applied = []
        if payload.get("apply_preprocessing", True):
            RemoveBarriers().apply(tk_circ)
            preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the QuEST backend adapter.")

        backend = QuESTBackend()
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
        if opt_level > 0:
            preprocessing_applied.append(f"pytket QuESTBackend.get_compiled_circuit(level={opt_level}): pytket's native compilation pass for the QuEST backend, decomposing gates into the backend's supported gate set.")
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

            counts_dict = _sample_from_statevector(statevector, payload.get("n_shots", 1024), n_qubits, payload.get("seed"))
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(f"QuEST manual sampling successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        # QuEST exposes the statevector but no native shot sampler here, so counts come from
        # sampling that statevector (see _sample_from_statevector above).
        return counts_result(
            simulator="quest", counts=counts_dict, sampling_method="sv_sample",
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="msb", n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during QuEST measurement simulation: {str(e)}")
        return runner_error("quest", e)

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "QuEST")
