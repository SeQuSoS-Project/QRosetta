# Execution script for the quantum simulator runner.

from fastapi import FastAPI
import numpy as np
import pytket.qasm
from pytket.extensions.projectq import ProjectQBackend
from pytket.passes import RemoveBarriers
from pytket.transform import Transform
from collections import Counter
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
import time
import gc

app = FastAPI(title="ProjectQ Runner")
logger = get_logger("pytket-projectq-runner")

import projectq.types._qubit
from projectq.types._qubit import Qubit

_original_del = Qubit.__del__

def _quiet_del(self):
    try:
        _original_del(self)
    except RuntimeError as e:
        if "Qubit has not been measured / uncomputed" in str(e):

            pass
        else:
            raise e

Qubit.__del__ = _quiet_del

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for ProjectQ simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        preprocessing_applied = []
        if payload.get("apply_preprocessing", True):
            RemoveBarriers().apply(tk_circ)
            preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the backend adapter.")

        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_circ)

        Transform.RebaseToTket().apply(tk_circ)

        backend = ProjectQBackend()
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        h_warm = backend.process_circuit(compiled_circ)
        _ = backend.get_result(h_warm).get_state()

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            handle = backend.process_circuit(compiled_circ)
            statevector = backend.get_result(handle).get_state()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(f"ProjectQ simulation successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        return statevector_result(
            simulator="projectq", statevector=statevector, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="lsb",
            n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during ProjectQ simulation: {str(e)}")
        return runner_error("projectq", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for ProjectQ (manual sampling).")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits

        preprocessing_applied = []
        if payload.get("apply_preprocessing", True):
            RemoveBarriers().apply(tk_circ)
            preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the backend adapter.")

        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_circ)

        Transform.RebaseToTket().apply(tk_circ)

        backend = ProjectQBackend()
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        h_warm = backend.process_circuit(compiled_circ)
        _ = backend.get_result(h_warm).get_state()

        with MemoryMonitor(interval=0.001) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            handle = backend.process_circuit(compiled_circ)
            statevector = backend.get_result(handle).get_state()

            counts_dict = _sample_from_statevector(statevector, payload.get("n_shots", 1024), n_qubits, payload.get("seed"))
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(f"ProjectQ manual sampling successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        # This runner does not label a sampling_method (sampling_method=None omits the key).
        return counts_result(
            simulator="projectq", counts=counts_dict, sampling_method=None,
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="lsb", n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during ProjectQ measurement simulation: {str(e)}")
        return runner_error("projectq", e)

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "ProjectQ")
