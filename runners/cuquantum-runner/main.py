from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb
import numpy as np
import time
import gc
import traceback

logger = get_logger("cuquantum-runner")

app = FastAPI(title="cuQuantum Runner")

try:
    from qiskit import QuantumCircuit, transpile as qiskit_transpile
    from qiskit_aer import AerSimulator, AerError
    AERSIM_AVAILABLE = True
    logger.info("qiskit-aer loaded successfully.")
except ImportError as e:
    AERSIM_AVAILABLE = False
    logger.warning(f"qiskit-aer import failed: {e}. Runner will return errors.")

# Detect GPU once at startup by actually running a tiny circuit
_GPU_AVAILABLE = False
if AERSIM_AVAILABLE:
    try:
        from qiskit import QuantumCircuit as _QC
        _probe_qc = _QC(1)
        _probe_qc.h(0)
        _probe_qc.save_statevector()
        _probe_sim = AerSimulator(method='statevector', device='GPU')
        _probe_sim.run(_probe_qc).result()
        _GPU_AVAILABLE = True
    except Exception:
        _GPU_AVAILABLE = False
    logger.info(f"GPU/cuQuantum available: {_GPU_AVAILABLE}")


def _run_safe(sim, qc, **kwargs):
    """Run a circuit, falling back to CPU if GPU execution fails."""
    try:
        return sim.run(qc, **kwargs).result()
    except AerError as e:
        if _GPU_AVAILABLE:
            logger.warning(f"GPU run failed ({e}), retrying on CPU.")
            cpu_sim = AerSimulator(method='statevector')
            return cpu_sim.run(qc, **kwargs).result()
        raise


def _compile(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 into a Qiskit QuantumCircuit and apply Qiskit transpiler passes.

    Level 0: no optimization
    Level 1: basic gate cancellation and 1Q consolidation
    Level 2: unitary synthesis + gate cancellation
    Level 3: heavy optimization (slowest compile, fewest gates)
    """
    qc = QuantumCircuit.from_qasm_str(qasm_str)
    if optimization_level > 0:
        qc = qiskit_transpile(qc, optimization_level=min(optimization_level, 3))
    return qc


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info(f"Received statevector request (GPU={_GPU_AVAILABLE}).")
    if not AERSIM_AVAILABLE:
        return {"simulator": "cuquantum", "error": "qiskit-aer not installed.",
                "execution_time_sec": 0.0, "memory_usage_mb": 0.0, "process_peak_mb": 0.0}
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        qc = _compile(payload.circuit_data, payload.optimization_level)
        qc.remove_final_measurements(inplace=True)
        qc.save_statevector()
        sim = AerSimulator(method='statevector', device='GPU') if _GPU_AVAILABLE else AerSimulator(method='statevector')
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _run_safe(sim, qc)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            # --- SIMULATION ---
            t2 = time.perf_counter()
            result = _run_safe(sim, qc)
            sv = np.asarray(result.get_statevector())
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        logger.info(
            f"cuQuantum simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return {
            "simulator": "cuquantum",
            "statevector": encode_statevector(sv),
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(qc.num_qubits)
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}\n{traceback.format_exc()}")
        return {"simulator": "cuquantum", "error": str(e),
                "execution_time_sec": 0.0, "memory_usage_mb": 0.0, "process_peak_mb": 0.0}


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info(f"Received measurement request (GPU={_GPU_AVAILABLE}).")
    if not AERSIM_AVAILABLE:
        return {"simulator": "cuquantum", "error": "qiskit-aer not installed.",
                "execution_time_sec": 0.0, "memory_usage_mb": 0.0, "process_peak_mb": 0.0}
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        qc = _compile(payload.circuit_data, payload.optimization_level)
        sim = AerSimulator(method='statevector', device='GPU') if _GPU_AVAILABLE else AerSimulator(method='statevector')
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _run_safe(sim, qc, shots=10)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            # --- SIMULATION ---
            t2 = time.perf_counter()
            result = _run_safe(sim, qc, shots=payload.n_shots)
            counts = dict(result.get_counts())
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        logger.info(
            f"cuQuantum measurement successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return {
            "simulator": "cuquantum",
            "counts": counts,
            "sampling_method": "native",
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(qc.num_qubits)
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}\n{traceback.format_exc()}")
        return {"simulator": "cuquantum", "error": str(e),
                "execution_time_sec": 0.0, "memory_usage_mb": 0.0, "process_peak_mb": 0.0}


logger.info("cuQuantum runner API instantiated and ready to receive traffic.")
