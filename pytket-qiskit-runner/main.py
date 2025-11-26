from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
import pytket.qasm
from pytket.extensions.qiskit import tk_to_qiskit
from qiskit_aer import AerSimulator
from qiskit.circuit import QuantumCircuit
import time
from qrosetta_commons.helpers import MemoryMonitor, calculate_theoretical_memory_mb, get_logger

logger = get_logger("pytket-qiskit-runner")

app = FastAPI(title="Qiskit Runner")

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info(f"Received circuit data for Qiskit simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        qiskit_circ = tk_to_qiskit(tk_circ)
        qiskit_circ.save_statevector()
        backend = AerSimulator(precision="double")
        
        with MemoryMonitor(interval=0.001) as monitor:
            start_time = time.perf_counter()
            
            job = backend.run(qiskit_circ, optimization_level=0)
            result = job.result()
            statevector = result.get_statevector()
            
            end_time = time.perf_counter()

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(tk_circ.n_qubits)
        execution_time = end_time - start_time
        
        statevector_str = [str(c) for c in statevector]
        logger.info(f"Qiskit simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "qiskit",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Qiskit simulation: {str(e)}")
        return { 
            "simulator": "qiskit", 
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "theoretical_memory_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info(f"Received measured circuit data for Qiskit simulation.")
    try:
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload.circuit_data)
        qiskit_circ = tk_to_qiskit(tk_circ)
        backend = AerSimulator(precision="double")

        with MemoryMonitor(interval=0.001) as monitor:
            start_time = time.perf_counter()
            
            job = backend.run(qiskit_circ, 
                              optimization_level=0, 
                              shots=payload.n_shots)
            result = job.result()
            counts = result.get_counts()
            
            end_time = time.perf_counter()

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        theoretical_mb = calculate_theoretical_memory_mb(tk_circ.n_qubits)
        execution_time = end_time - start_time
        
        num_clbits = qiskit_circ.num_clbits
        counts_dict = {}
        if num_clbits > 0:
            for k, v in counts.items():
                if k.startswith('0x'):
                    binary_key = format(int(k, 16), f'0{num_clbits}b')
                else:
                    binary_key = k.zfill(num_clbits)
                counts_dict[binary_key] = v
        else:
            counts_dict = counts

        logger.info(f"Qiskit measurement simulation successful in {execution_time:.4f}s.")
        
        return {
            "simulator": "qiskit",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "memory_usage_mb": memory_usage_mb,
            "theoretical_memory_mb": theoretical_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during Qiskit measurement simulation: {str(e)}")
        return {
            "simulator": "qiskit",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "theoretical_memory_mb": 0.0,
            "process_peak_mb": 0.0
        }