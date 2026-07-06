# Execution script for the quantum simulator runner.

import argparse
import json
import os
import sys
import boto3
from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
import pytket.qasm
import numpy as np
from pytket.extensions.qiskit import tk_to_qiskit
from qiskit_aer import AerSimulator
from qiskit.circuit import QuantumCircuit
from qiskit import transpile as qiskit_transpile
from qiskit import qasm2
import time
import gc
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions

logger = get_logger("pytket-qiskit-runner")

app = FastAPI(title="Qiskit Runner")

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qiskit simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        qiskit_circ = tk_to_qiskit(tk_circ)
        
        preprocessing_applied = []
        opt_level = payload.get("optimization_level", 0)
        if opt_level > 0:
            qiskit_circ = qiskit_transpile(qiskit_circ, optimization_level=min(opt_level, 3))
            preprocessing_applied.append(f"qiskit.compiler.transpile(level={min(opt_level, 3)}): Native Qiskit transpilation pass applied to optimize the circuit structure for the Aer backend.")
        
        transpiled_qasm = qasm2.dumps(qiskit_circ)
        qiskit_circ.save_statevector()
        backend = AerSimulator(precision="double")
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        _ = backend.run(qiskit_circ, optimization_level=0)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            job = backend.run(qiskit_circ, optimization_level=0)
            result = job.result()
            statevector = result.get_statevector()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(np.array(statevector))
        logger.info(f"Qiskit simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "qiskit",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits),
            "preprocessing_applied": preprocessing_applied,
            "transpiled_qasm": transpiled_qasm
        }
    except Exception as e:
        logger.error(f"Error during Qiskit simulation: {str(e)}")
        return {
            "simulator": "qiskit",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qiskit simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        qiskit_circ = tk_to_qiskit(tk_circ)
        
        preprocessing_applied = []
        opt_level = payload.get("optimization_level", 0)
        if opt_level > 0:
            qiskit_circ = qiskit_transpile(qiskit_circ, optimization_level=min(opt_level, 3))
            preprocessing_applied.append(f"qiskit.compiler.transpile(level={min(opt_level, 3)}): Native Qiskit transpilation pass applied to optimize the circuit structure for the Aer backend.")
            
        transpiled_qasm = qasm2.dumps(qiskit_circ)
        backend = AerSimulator(precision="double")
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        n_shots = payload.get("n_shots", 1024)

        _ = backend.run(qiskit_circ, optimization_level=0, shots=n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            # seed_simulator=None keeps Aer's default non-deterministic sampling.
            job = backend.run(qiskit_circ, optimization_level=0, shots=n_shots, seed_simulator=payload.get("seed"))
            result = job.result()
            counts = result.get_counts()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

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

        logger.info(f"Qiskit measurement simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "qiskit",
            "counts": counts_dict,
            "sampling_method": "native",
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits),
            "preprocessing_applied": preprocessing_applied,
            "transpiled_qasm": transpiled_qasm
        }
    except Exception as e:
        logger.error(f"Error during Qiskit measurement simulation: {str(e)}")
        return {
            "simulator": "qiskit",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qiskit")
