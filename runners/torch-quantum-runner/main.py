from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb
import numpy as np
import time
import gc
import traceback

logger = get_logger("torchquantum-runner")

app = FastAPI(title="TorchQuantum Runner")

try:
    import torch
    import torchquantum as tq
    from torchquantum.plugin import qiskit2tq
    from qiskit import QuantumCircuit as QiskitCircuit, transpile as qiskit_transpile
    TORCHQUANTUM_AVAILABLE = True
    logger.info("TorchQuantum and Qiskit loaded successfully.")
except ImportError as e:
    TORCHQUANTUM_AVAILABLE = False
    logger.warning(f"TorchQuantum import failed: {e}. Runner will return errors for all requests.")


# Gates that qiskit2tq can reliably convert to TorchQuantum ops.
_TQ_BASIS_GATES = [
    'h', 'x', 'y', 'z', 's', 't', 'sdg', 'tdg',
    'cx', 'cz', 'swap', 'ccx',
    'rx', 'ry', 'rz', 'u1', 'u2', 'u3',
]


def _compile(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 with Qiskit and convert to a TorchQuantum module.

    Level 0: no optimization
    Level 1: Qiskit transpiler level 1 (single-qubit gate consolidation, basic cancellation)
    Level 2: Qiskit transpiler level 2 (unitary synthesis + gate cancellation)

    Returns (tq_module, n_qubits).
    """
    qc = QiskitCircuit.from_qasm_str(qasm_str)
    if optimization_level > 0:
        qc = qiskit_transpile(
            qc,
            optimization_level=min(optimization_level, 2),
            basis_gates=_TQ_BASIS_GATES,
        )
    # Strip measurements so we can run statevector simulation
    qc.remove_final_measurements(inplace=True)
    n_qubits = qc.num_qubits
    tq_module = qiskit2tq(qc)
    return tq_module, n_qubits


def _run_sv(tq_module, n_qubits: int) -> np.ndarray:
    """Execute the TorchQuantum module and return a numpy complex statevector."""
    qdev = tq.QuantumDevice(n_wires=n_qubits, bsz=1, device="cpu")
    with torch.no_grad():
        tq_module(qdev)
    # get_states_1d() → shape (bsz, 2^n)
    sv = qdev.get_states_1d().detach().cpu().numpy()[0]
    return sv


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info("Received circuit data for TorchQuantum statevector simulation.")
    if not TORCHQUANTUM_AVAILABLE:
        return {
            "simulator": "torchquantum",
            "error": "TorchQuantum is not installed in this environment.",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0,
        }
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tq_module, n_qubits = _compile(payload.circuit_data, payload.optimization_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP (excluded from reported timing) ---
        _run_sv(tq_module, n_qubits)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            # --- SIMULATION ---
            t2 = time.perf_counter()
            sv = _run_sv(tq_module, n_qubits)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(sv)
        logger.info(
            f"TorchQuantum simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "torchquantum",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
        }
    except Exception as e:
        logger.error(f"Error during TorchQuantum simulation: {str(e)}\n{traceback.format_exc()}")
        return {
            "simulator": "torchquantum",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0,
        }


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info("Received circuit data for TorchQuantum measurement simulation.")
    if not TORCHQUANTUM_AVAILABLE:
        return {
            "simulator": "torchquantum",
            "error": "TorchQuantum is not installed in this environment.",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0,
        }
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tq_module, n_qubits = _compile(payload.circuit_data, payload.optimization_level)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP (excluded from reported timing) ---
        _run_sv(tq_module, n_qubits)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            # --- SIMULATION + SAMPLING ---
            t2 = time.perf_counter()
            sv = _run_sv(tq_module, n_qubits)

            # Derive counts by sampling from the probability distribution
            probs = torch.tensor(np.abs(sv) ** 2, dtype=torch.float64)
            # Guard against tiny negative rounding errors
            probs = torch.clamp(probs, min=0.0)
            probs = probs / probs.sum()

            sample_indices = torch.multinomial(
                probs.float(), num_samples=payload.n_shots, replacement=True
            ).numpy()

            fmt = f"{{:0{n_qubits}b}}"
            counts: dict[str, int] = {}
            for idx in sample_indices:
                bitstring = fmt.format(int(idx))
                counts[bitstring] = counts.get(bitstring, 0) + 1

            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        logger.info(
            f"TorchQuantum measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "torchquantum",
            "counts": counts,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
        }
    except Exception as e:
        logger.error(f"Error during TorchQuantum measurement simulation: {str(e)}\n{traceback.format_exc()}")
        return {
            "simulator": "torchquantum",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0,
        }


logger.info("TorchQuantum runner API instantiated and ready to receive traffic.")
