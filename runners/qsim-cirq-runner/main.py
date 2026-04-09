from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq
from pytket.passes import RemoveBarriers
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


def _to_cirq_circuit(qasm_str: str, optimization_level: int = 0) -> cirq.Circuit:
    """Parse QASM string via pytket, convert to Cirq, then apply Cirq-native optimizations.

    Level 0: no optimization
    Level 1: basic cleanup (drop empty moments, align)
    Level 2: full reduction (eject Z/phased-Paulis, merge single-qubit gates)
    """
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str)
    RemoveBarriers().apply(tk_circ)
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

    return circ


def _strip_measurements(circ: cirq.Circuit) -> cirq.Circuit:
    """Return a copy of the circuit with all measurement gates removed."""
    return cirq.Circuit(
        op for op in circ.all_operations()
        if not isinstance(op.gate, cirq.MeasurementGate)
    )


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    if not QSIM_AVAILABLE:
        return {
            "simulator": "qsim-cirq",
            "error": "qsimcirq package not installed",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

    logger.info("Received circuit data for qsim-Cirq simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        cirq_circ = _to_cirq_circuit(payload.circuit_data, payload.optimization_level)
        cirq_circ_no_meas = _strip_measurements(cirq_circ)
        simulator = qsimcirq.QSimSimulator()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = simulator.simulate(cirq_circ_no_meas)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            result = simulator.simulate(cirq_circ_no_meas)
            statevector = result.final_state_vector
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(np.array(statevector))
        logger.info(
            f"qsim-Cirq simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        n_qubits = len(cirq_circ_no_meas.all_qubits())
        return {
            "simulator": "qsim-cirq",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
        }
    except Exception as e:
        logger.error(f"Error during qsim-Cirq simulation: {str(e)}")
        return {
            "simulator": "qsim-cirq",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    if not QSIM_AVAILABLE:
        return {
            "simulator": "qsim-cirq",
            "error": "qsimcirq package not installed",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

    logger.info("Received measured circuit data for qsim-Cirq simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        cirq_circ = _to_cirq_circuit(payload.circuit_data, payload.optimization_level)
        # Strip any existing measurements and add a clean terminal measurement
        # on all qubits so qsim's run() interface can sample deterministically.
        all_qubits = sorted(cirq_circ.all_qubits())
        circ_with_meas = _strip_measurements(cirq_circ) + cirq.measure(
            *all_qubits, key="result"
        )
        simulator = qsimcirq.QSimSimulator()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = simulator.run(circ_with_meas, repetitions=payload.n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            run_result = simulator.run(circ_with_meas, repetitions=payload.n_shots)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        # Convert measurement array (n_shots × n_qubits) → {bitstring: count}
        measurements = run_result.measurements["result"]
        counts_dict: dict = {}
        for shot in measurements:
            bitstring = "".join(str(int(b)) for b in shot)
            counts_dict[bitstring] = counts_dict.get(bitstring, 0) + 1

        logger.info(
            f"qsim-Cirq measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        n_qubits = len(all_qubits)
        return {
            "simulator": "qsim-cirq",
            "counts": counts_dict,
            "sampling_method": "native",
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
        }
    except Exception as e:
        logger.error(f"Error during qsim-Cirq measurement simulation: {str(e)}")
        return {
            "simulator": "qsim-cirq",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }
