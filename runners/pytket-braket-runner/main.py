from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb
import numpy as np
import pytket.qasm
from pytket.extensions.braket import BraketBackend
from pytket.passes import RemoveBarriers
import time
import gc

logger = get_logger("pytket-braket-runner")

app = FastAPI(title="Braket Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info(f"Received circuit data for Braket simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        RemoveBarriers().apply(tk_circ)

        backend = BraketBackend(local=True)
        opt_level = min(payload.optimization_level, 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)

        # CRITICAL FIX: Strip Global Phase
        # Braket attempts to apply global phase as a unitary, causing 16TiB OOM on 20 qubits.
        compiled_circ.add_phase(-compiled_circ.phase)

        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = backend.process_circuit(compiled_circ)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            handle = backend.process_circuit(compiled_circ)
            statevector = backend.get_result(handle).get_state()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(np.array(statevector))

        logger.info(f"Braket simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "braket",
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
        logger.error(f"Error during Braket simulation: {str(e)}")
        return { 
            "simulator": "braket", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info(f"Received measured circuit data for Braket simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        RemoveBarriers().apply(tk_circ)

        backend = BraketBackend(local=True)
        opt_level = min(payload.optimization_level, 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)

        # CRITICAL FIX: Strip Global Phase
        compiled_circ.add_phase(-compiled_circ.phase)

        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = backend.process_circuit(compiled_circ, n_shots=payload.n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            handle = backend.process_circuit(compiled_circ, n_shots=payload.n_shots)
            counts = backend.get_result(handle).get_counts()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

        counts_dict = { "".join(map(str, k)): int(v) for k, v in counts.items() }

        logger.info(f"Braket measurement simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "braket",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
        }
    except Exception as e:
        logger.error(f"Error during Braket measurement simulation: {str(e)}")
        return {
            "simulator": "braket",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }