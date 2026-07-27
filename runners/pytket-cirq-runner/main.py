# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq
import cirq
from pytket.extensions.cirq.backends.cirq import CirqStateSampleBackend
from pytket.passes import RemoveBarriers, auto_rebase_pass
from pytket.circuit import OpType
from pytket.transform import Transform
import time
import gc
import warnings
import logging

warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core")

logging.getLogger("root").setLevel(logging.ERROR)

class _SuppressGlobalPhaseWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "Global phase is dependent on a symbolic parameter" not in record.getMessage()

logging.getLogger().addFilter(_SuppressGlobalPhaseWarning())

logger = get_logger("pytket-cirq-runner")

app = FastAPI(title="Cirq Runner")

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Cirq simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        preprocessing_applied = []
        if payload.get("apply_preprocessing", True):
            RemoveBarriers().apply(tk_circ)
            preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the backend adapter.")
            auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
            preprocessing_applied.append("pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Universally decomposes complex multi-qubit and single-qubit gates (like CU3, CRX) into a standard CX/Rz/Rx basis to prevent parsing failures in the backend.")
        else:
            Transform.RebaseToRzRx().apply(tk_circ)
            
        cirq_circ = tk_to_cirq(tk_circ)
        simulator = cirq.Simulator(dtype=np.complex128)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # Provenance only — serialized after t1 so it does not inflate compilation_time.
        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_circ)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            result = simulator.simulate(cirq_circ)
            statevector = result.final_state_vector
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(f"Cirq simulation successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        return statevector_result(
            simulator="cirq", statevector=statevector, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="lsb",
            n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Cirq simulation: {str(e)}")
        return runner_error("cirq", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Cirq simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        preprocessing_applied = []
        if payload.get("apply_preprocessing", True):
            RemoveBarriers().apply(tk_circ)
            preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the backend adapter.")
            auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
            preprocessing_applied.append("pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Universally decomposes complex multi-qubit and single-qubit gates (like CU3, CRX) into a standard CX/Rz/Rx basis to prevent parsing failures in the backend.")
        else:
            Transform.RebaseToRzRx().apply(tk_circ)

        backend = CirqStateSampleBackend()
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # Provenance only — serialized after t1 so it does not inflate compilation_time.
        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_circ)

        n_shots = payload.get("n_shots", 1024)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # pytket's CirqBackend ignores a seed kwarg but samples via numpy's global
            # RNG, so reproducibility is achieved by seeding numpy directly (verified).
            # seed=None leaves it non-deterministic (prior behaviour).
            if payload.get("seed") is not None:
                np.random.seed(payload["seed"])
            t2 = time.perf_counter()
            handle = backend.process_circuit(compiled_circ, n_shots=n_shots)
            counts = backend.get_result(handle).get_counts()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        counts_dict = {"".join(map(str, k)): int(v) for k, v in counts.items()}

        logger.info(f"Cirq measurement simulation successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        return counts_result(
            simulator="cirq", counts=counts_dict, sampling_method="native",
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="msb", n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Cirq measurement simulation: {str(e)}")
        return runner_error("cirq", e)

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Cirq")
