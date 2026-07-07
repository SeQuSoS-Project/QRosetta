# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq
from pytket.passes import RemoveBarriers, auto_rebase_pass
from pytket.circuit import OpType
from pytket.transform import Transform
import cirq
import time
import gc

try:
    import qsimcirq
    QSIM_AVAILABLE = True
except ImportError:
    QSIM_AVAILABLE = False

logger = get_logger("qsim-cirq-runner")

app = FastAPI(title="qsim-Cirq Runner")

def _to_cirq_circuit(qasm_str: str, optimization_level: int = 0, apply_preprocessing: bool = True) -> tuple[cirq.Circuit, list[str], "pytket.circuit.Circuit"]:
    """Parse QASM string via pytket, convert to Cirq, then apply Cirq-native optimizations.

    Returns the pytket Circuit (not its QASM string) so the caller can serialize it
    for provenance outside the timed compilation window.
    """
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str)

    preprocessing_applied = []
    if apply_preprocessing:
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the backend adapter.")
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        preprocessing_applied.append("pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Universally decomposes complex multi-qubit and single-qubit gates (like CU3, CRX) into a standard CX/Rz/Rx basis to prevent parsing failures in the backend.")
    else:
        Transform.RebaseToRzRx().apply(tk_circ)

    circ = tk_to_cirq(tk_circ)

    if optimization_level >= 1:
        circ = cirq.drop_empty_moments(circ)
        circ = cirq.align_left(circ)

    if optimization_level >= 2:
        circ = cirq.eject_z(circ)
        circ = cirq.eject_phased_paulis(circ)
        circ = cirq.merge_single_qubit_gates_to_phxz(circ)
        circ = cirq.drop_empty_moments(circ)

    return circ, preprocessing_applied, tk_circ

def _strip_measurements(circ: cirq.Circuit) -> cirq.Circuit:
    """Return a copy of the circuit with all measurement gates removed."""
    return cirq.Circuit(
        op for op in circ.all_operations()
        if not isinstance(op.gate, cirq.MeasurementGate)
    )

@with_sdk_versions
def process_run(payload: dict) -> dict:
    if not QSIM_AVAILABLE:
        return runner_error("qsim-cirq", "qsimcirq package not installed")

    circuit_data = payload["circuit_data"]
    optimization_level = payload.get("optimization_level", 0)

    logger.info("Received circuit data for qsim-Cirq simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        cirq_circ, preprocessing_applied, tk_export = _to_cirq_circuit(circuit_data, optimization_level, payload.get("apply_preprocessing", True))
        cirq_circ_no_meas = _strip_measurements(cirq_circ)
        simulator = qsimcirq.QSimSimulator()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # Provenance only — serialized after t1 so it does not inflate compilation_time.
        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_export)

        _ = simulator.simulate(cirq_circ_no_meas)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            result = simulator.simulate(cirq_circ_no_meas)
            statevector = result.final_state_vector
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(
            f"qsim-Cirq simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        n_qubits = len(cirq_circ_no_meas.all_qubits())
        return statevector_result(
            simulator="qsim-cirq", statevector=statevector, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="lsb",
            n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during qsim-Cirq simulation: {str(e)}")
        return runner_error("qsim-cirq", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    if not QSIM_AVAILABLE:
        return runner_error("qsim-cirq", "qsimcirq package not installed")

    circuit_data = payload["circuit_data"]
    optimization_level = payload.get("optimization_level", 0)
    n_shots = payload.get("n_shots", 1024)

    logger.info("Received measured circuit data for qsim-Cirq simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        cirq_circ, preprocessing_applied, tk_export = _to_cirq_circuit(circuit_data, optimization_level, payload.get("apply_preprocessing", True))

        all_qubits = sorted(cirq_circ.all_qubits())
        circ_with_meas = _strip_measurements(cirq_circ) + cirq.measure(
            *all_qubits, key="result"
        )
        # seed=None keeps qsim's default non-deterministic sampling.
        simulator = qsimcirq.QSimSimulator(seed=payload.get("seed"))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # Provenance only — serialized after t1 so it does not inflate compilation_time.
        transpiled_qasm = pytket.qasm.circuit_to_qasm_str(tk_export)

        _ = simulator.run(circ_with_meas, repetitions=n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            run_result = simulator.run(circ_with_meas, repetitions=n_shots)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        measurements = run_result.measurements["result"]
        counts_dict: dict = {}
        for shot in measurements:
            bitstring = "".join(str(int(b)) for b in shot)
            counts_dict[bitstring] = counts_dict.get(bitstring, 0) + 1

        logger.info(
            f"qsim-Cirq measurement simulation successful "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        n_qubits = len(all_qubits)
        return counts_result(
            simulator="qsim-cirq", counts=counts_dict, sampling_method="native",
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="msb", n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during qsim-Cirq measurement simulation: {str(e)}")
        return runner_error("qsim-cirq", e)

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "qsim-Cirq")
