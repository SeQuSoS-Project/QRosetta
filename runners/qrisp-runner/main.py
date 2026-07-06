# Execution script for the quantum simulator runner.

import argparse
import json
import os
import sys
import boto3
from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb, get_num_qubits_from_qasm, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions
import numpy as np
import time
import gc

import traceback

logger = get_logger("qrisp-runner")

app = FastAPI(title="Qrisp Runner")

def _parse(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 into a Qrisp QuantumCircuit.

    Qrisp's QuantumCircuit is a QASM-level wrapper; its optimization model is
    designed for high-level Qrisp programs, not post-QASM gate passes. All
    optimization levels run identically.
    """
    from qrisp import QuantumCircuit
    if optimization_level > 0:
        logger.info(
            f"Qrisp: optimization_level={optimization_level} requested "
            "but not applicable at the QASM circuit level; running at level 0."
        )
    return QuantumCircuit.from_qasm_str(qasm_str)

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qrisp simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        n_qubits = get_num_qubits_from_qasm(payload["circuit_data"])
        circuit = _parse(payload["circuit_data"], payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # The statevector lives on the low-level QuantumCircuit itself via
        # statevector_array(); Qrisp's QASM-imported QuantumCircuit has no `.qs`
        # (QuantumSession) attribute, so the high-level qs.statevector() API is
        # not available here. A warm-up call excludes JIT/import overhead from
        # the timed run, matching the other native runners. Any failure is
        # allowed to propagate to the outer handler and surface as an honest
        # error rather than a fabricated fallback state.
        _ = circuit.statevector_array()

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = np.asarray(circuit.statevector_array(), dtype=complex)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(statevector)
        logger.info(
            f"Qrisp simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "qrisp",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            # Qrisp's statevector_array() is big-endian: qubit 0 is the most
            # significant bit of the amplitude index (verified: X on qubit 0
            # populates index 2^(n-1)). This differs from the counts convention
            # of run() below, which is little-endian; both are labelled to match
            # their actual native output rather than forced to a single value.
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits),
            "preprocessing_applied": [],
            "transpiled_qasm": payload["circuit_data"]
        }
    except Exception as e:
        logger.error(f"Error during Qrisp simulation: {str(e)}\n{traceback.format_exc()}")
        return {
            "simulator": "qrisp",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qrisp simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        n_qubits = get_num_qubits_from_qasm(payload["circuit_data"])
        circuit = _parse(payload["circuit_data"], payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        n_shots = payload.get("n_shots", 1024)

        # Native shot-based sampling runs through the low-level circuit's run()
        # method (the high-level get_measurement() API belongs to QuantumVariable
        # and is not available on a QASM-imported QuantumCircuit). This requires
        # the circuit to carry measurement instructions, which measured-mode QASM
        # does. A warm-up call excludes JIT/import overhead from the timed run;
        # any failure propagates to the outer handler as an honest error rather
        # than fabricated all-zero counts.
        _ = circuit.run(shots=min(n_shots, 10))

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # Qrisp's simulator samples via numpy's global RNG (run() exposes no seed
            # argument); seeding it makes the run reproducible. seed=None leaves it
            # non-deterministic (prior behaviour).
            if payload.get("seed") is not None:
                np.random.seed(payload["seed"])
            t2 = time.perf_counter()
            counts_dict = circuit.run(shots=n_shots)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        logger.info(
            f"Qrisp measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "qrisp",
            "counts": counts_dict,
            "sampling_method": "native",
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            # Qrisp's run() counts keys are little-endian: qubit 0 is the
            # right-most character of the bitstring (verified: X on qubit 0
            # yields '0...01'), matching the qiskit/Aer counts convention. Note
            # this differs from the statevector endpoint's big-endian ordering
            # above; each is labelled to reflect Qrisp's actual native output.
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits),
            "preprocessing_applied": [],
            "transpiled_qasm": payload["circuit_data"]
        }
    except Exception as e:
        logger.error(f"Error during Qrisp measurement simulation: {str(e)}\n{traceback.format_exc()}")
        return {
            "simulator": "qrisp",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

register_runner_endpoints(app, process_run, process_run_measured)

logger.info("Qrisp runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qrisp")
