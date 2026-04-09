from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq  
import cirq
from pytket.extensions.cirq.backends.cirq import CirqStateSampleBackend
from pytket.passes import RemoveBarriers
from pytket.transform import Transform
import time
import gc
import warnings
import logging

# Suppress FutureWarning from google.api_core about Python 3.10 EOL (not actionable here).
warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core")

# pytket's tk_to_cirq emits a root-level WARNING when a circuit has a symbolic
# global phase it cannot adjust. This is expected for our circuit inputs — suppress it.
logging.getLogger("root").setLevel(logging.ERROR)
# More targeted: silence only the specific message via a filter on the root logger.
class _SuppressGlobalPhaseWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "Global phase is dependent on a symbolic parameter" not in record.getMessage()

logging.getLogger().addFilter(_SuppressGlobalPhaseWarning())

logger = get_logger("pytket-cirq-runner")

app = FastAPI(title="Cirq Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info(f"Received circuit data for Cirq simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        RemoveBarriers().apply(tk_circ)

        # --- COMPATIBILITY LAYER ---
        # Convert generic gates (TK1, U3) into Rx and Rz rotations.
        # Cirq's converter natively understands these specific gates.
        Transform.RebaseToRzRx().apply(tk_circ)
        # ---------------------------

        cirq_circ = tk_to_cirq(tk_circ)
        simulator = cirq.Simulator(dtype=np.complex128)
        t1 = time.perf_counter()
        compilation_time = t1 - t0
        
        # --- WARM-UP ---
        _ = simulator.simulate(cirq_circ)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()
            
            # --- SIMULATION ---
            t2 = time.perf_counter()
            result = simulator.simulate(cirq_circ)
            statevector = result.final_state_vector
            t3 = time.perf_counter()
            simulation_time = t3 - t2
        
        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(np.array(statevector))
        logger.info(f"Cirq simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        
        return {
            "simulator": "cirq",
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
        logger.error(f"Error during Cirq simulation: {str(e)}")
        return { 
            "simulator": "cirq", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info(f"Received measured circuit data for Cirq simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        n_qubits = tk_circ.n_qubits
        RemoveBarriers().apply(tk_circ)

        # --- COMPATIBILITY LAYER ---
        Transform.RebaseToRzRx().apply(tk_circ)
        # ---------------------------

        backend = CirqStateSampleBackend()
        opt_level = min(payload.optimization_level, 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
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

        logger.info(f"Cirq measurement simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")
        
        return {
            "simulator": "cirq",
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
        logger.error(f"Error during Cirq measurement simulation: {str(e)}")
        return {
           "simulator": "cirq",
           "error": str(e),
           "execution_time_sec": 0.0,
           "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }