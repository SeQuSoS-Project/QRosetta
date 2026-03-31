from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector
import numpy as np
import time
import gc

from qat.interop.openqasm import OqasmParser
from qat.qpus import PyLinalg

logger = get_logger("myqlm-runner")

app = FastAPI(title="myQLM Runner")

_parser = OqasmParser()
_qpu = PyLinalg()


def _compile_circuit(qasm_str: str):
    """Parse QASM 2.0 into a myQLM Circuit via OqasmParser.compile()."""
    return _parser.compile(qasm_str)


def _get_statevector(circuit) -> np.ndarray:
    """Run PyLinalg with nbshots=0 and return the statevector."""
    n_qubits = circuit.nbqbits
    job = circuit.to_job(job_type="SAMPLE", nbshots=0)
    result = _qpu.submit(job)
    sv = np.zeros(2 ** n_qubits, dtype=complex)
    for sample in result:
        if sample.amplitude is not None:
            sv[sample.state.int] = sample.amplitude
    return sv


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    logger.info("Received circuit data for myQLM simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circuit = _compile_circuit(payload.circuit_data)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _get_statevector(circuit)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            statevector = _get_statevector(circuit)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(statevector)
        logger.info(
            f"myQLM simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "myqlm",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during myQLM simulation: {str(e)}")
        return {
            "simulator": "myqlm",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    logger.info("Received measured circuit data for myQLM simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circuit = _compile_circuit(payload.circuit_data)
        n_qubits = circuit.nbqbits
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _get_statevector(circuit)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            statevector = _get_statevector(circuit)
            probs = np.abs(statevector) ** 2
            probs /= probs.sum()
            indices = np.random.choice(len(probs), size=payload.n_shots, p=probs)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        counts_dict = {}
        for idx in indices:
            bitstring = format(idx, f"0{n_qubits}b")
            counts_dict[bitstring] = counts_dict.get(bitstring, 0) + 1

        logger.info(
            f"myQLM measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "myqlm",
            "counts": counts_dict,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb
        }
    except Exception as e:
        logger.error(f"Error during myQLM measurement simulation: {str(e)}")
        return {
            "simulator": "myqlm",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }
