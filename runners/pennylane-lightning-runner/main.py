# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, get_num_qubits_from_qasm, strip_barriers_from_qasm, with_sdk_versions, statevector_result, counts_result, runner_error
import pennylane as qml
import functools
import time
import gc

app = FastAPI(title="Pennylane Lightning Runner")
logger = get_logger("pennylane-lightning-runner")

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received statevector circuit data for Pennylane-Lightning simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        circuit_data = strip_barriers_from_qasm(payload["circuit_data"])
        transpiled_qasm = circuit_data
        qasm_op = qml.from_qasm(circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload["circuit_data"])
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

        level = payload.get("optimization_level", 0)
        passes = []
        preprocessing_applied = ["qrosetta_commons.helpers.strip_barriers_from_qasm(): Strips barrier instructions from the QASM string, as PennyLane's QASM parser does not support them."]
        if level == 1:
            passes = [qml.transforms.cancel_inverses]
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
        elif level == 2:
            passes = [qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
            preprocessing_applied.append("qml.transforms.merge_rotations: Merges consecutive rotation gates on the same qubit/axis into a single rotation.")
        elif level >= 3:
            passes = [qml.transforms.commute_controlled, qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
            preprocessing_applied.append("qml.transforms.commute_controlled: Pushes single-qubit gates through controlled gates to enable further cancellations.")
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
            preprocessing_applied.append("qml.transforms.merge_rotations: Merges consecutive rotation gates on the same qubit/axis into a single rotation.")

        @functools.partial(qml.compile, pipeline=passes)
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state()

        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = statevector_circuit()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(f"Pennylane-Lightning statevector simulation successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        return statevector_result(
            simulator="pennylane-lightning", statevector=statevector, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="msb",
            n_qubits=num_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Pennylane-Lightning statevector simulation: {str(e)}")
        return runner_error("pennylane-lightning", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Pennylane-Lightning (manual sampling).")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        circuit_data = strip_barriers_from_qasm(payload["circuit_data"])
        transpiled_qasm = circuit_data
        qasm_op = qml.from_qasm(circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload["circuit_data"])
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

        level = payload.get("optimization_level", 0)
        passes = []
        preprocessing_applied = ["qrosetta_commons.helpers.strip_barriers_from_qasm(): Strips barrier instructions from the QASM string, as PennyLane's QASM parser does not support them."]
        if level == 1:
            passes = [qml.transforms.cancel_inverses]
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
        elif level == 2:
            passes = [qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
            preprocessing_applied.append("qml.transforms.merge_rotations: Merges consecutive rotation gates on the same qubit/axis into a single rotation.")
        elif level >= 3:
            passes = [qml.transforms.commute_controlled, qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
            preprocessing_applied.append("qml.transforms.commute_controlled: Pushes single-qubit gates through controlled gates to enable further cancellations.")
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
            preprocessing_applied.append("qml.transforms.merge_rotations: Merges consecutive rotation gates on the same qubit/axis into a single rotation.")

        @functools.partial(qml.compile, pipeline=passes)
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state()

        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = statevector_circuit()
            counts_dict = _sample_from_statevector(statevector, payload.get("n_shots", 1024), num_qubits, payload.get("seed"))
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(f"Pennylane-Lightning manual sampling successful (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        return counts_result(
            simulator="pennylane-lightning", counts=counts_dict, sampling_method="sv_sample",
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="msb", n_qubits=num_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during Pennylane-Lightning measurement simulation: {str(e)}")
        return runner_error("pennylane-lightning", e)

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Pennylane-Lightning")
