# Execution script for the quantum simulator runner.

import argparse
import json
import os
import sys
import boto3
from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb, check_qubits_limit
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

_TQ_BASIS_GATES = [
    'h', 'x', 'y', 'z', 's', 't', 'sdg',
    'cx', 'cz', 'swap', 'ccx',
    'rx', 'ry', 'rz', 'u2', 'u3',
]

def _compile(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 with Qiskit and convert to a TorchQuantum module.

    Level 0: no optimization (but still decomposes to safe basis gates)
    Level 1: Qiskit transpiler level 1 (single-qubit gate consolidation, basic cancellation)
    Level 2: Qiskit transpiler level 2 (unitary synthesis + gate cancellation)

    We always transpile with _TQ_BASIS_GATES regardless of opt level to ensure
    gates like cu1/u1 are decomposed into gates TorchQuantum can handle.

    Returns (tq_module, n_qubits).
    """
    qc = QiskitCircuit.from_qasm_str(qasm_str)

    qc = qiskit_transpile(
        qc,
        optimization_level=min(max(optimization_level, 0), 2),
        basis_gates=_TQ_BASIS_GATES,
    )

    qc.remove_final_measurements(inplace=True)
    n_qubits = qc.num_qubits
    tq_module = qiskit2tq(qc)
    return tq_module, n_qubits

def _run_sv(tq_module, n_qubits: int) -> np.ndarray:
    """Execute the TorchQuantum module and return a numpy complex statevector."""
    qdev = tq.QuantumDevice(n_wires=n_qubits, bsz=1, device="cpu")
    with torch.no_grad():
        tq_module(qdev)

    sv = qdev.get_states_1d().detach().cpu().numpy()[0]
    return sv

def process_run(payload: dict) -> dict:
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
        check_qubits_limit(payload["circuit_data"], 24)

        t0 = time.perf_counter()
        tq_module, n_qubits = _compile(payload["circuit_data"], payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        _run_sv(tq_module, n_qubits)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

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

def process_run_measured(payload: dict) -> dict:
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
        check_qubits_limit(payload["circuit_data"], 24)

        t0 = time.perf_counter()
        tq_module, n_qubits = _compile(payload["circuit_data"], payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        n_shots = payload.get("n_shots", 1024)

        _run_sv(tq_module, n_qubits)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            sv = _run_sv(tq_module, n_qubits)

            probs = torch.tensor(np.abs(sv) ** 2, dtype=torch.float64)

            probs = torch.clamp(probs, min=0.0)
            probs = probs / probs.sum()

            sample_indices = torch.multinomial(
                probs.float(), num_samples=n_shots, replacement=True
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
            "sampling_method": "sv_sample",
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

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    return process_run(payload.model_dump())

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    return process_run_measured(payload.model_dump())

logger.info("TorchQuantum runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="TorchQuantum runner CLI")
        parser.add_argument("--endpoint", choices=["run", "run_measured"], required=True,
                            help="Which endpoint to invoke")
        parser.add_argument("--payload", default=None, help="JSON payload string")
        parser.add_argument("--s3-job-id", default=None,
                            help="S3 job ID: download payload from jobs/pending/<id>.json, upload result to jobs/completed/<id>.json")
        args = parser.parse_args()

        if args.s3_job_id:
            s3 = boto3.client(
                "s3",
                endpoint_url=os.getenv("S3_ENDPOINT_URL"),
                aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
                region_name=os.getenv("S3_REGION", "us-east-1"),
            )
            bucket = os.getenv("S3_BUCKET_NAME")
            payload_env = os.getenv("QROSETTA_PAYLOAD")
            if payload_env:
                payload_dict = json.loads(payload_env)
            else:
                obj = s3.get_object(Bucket=bucket, Key=f"jobs/pending/{args.s3_job_id}.json")
                payload_dict = json.loads(obj["Body"].read())

            result = process_run(payload_dict) if args.endpoint == "run" else process_run_measured(payload_dict)

            result_bytes = json.dumps(result).encode()
            s3.put_object(Bucket=bucket, Key=f"jobs/completed/{args.s3_job_id}.json",
                          Body=result_bytes, ContentLength=len(result_bytes))
            print(f"Job {args.s3_job_id} completed and uploaded to S3.")
        else:
            if args.payload is None:
                parser.error("--payload is required when --s3-job-id is not provided")
            payload_dict = json.loads(args.payload)
            result = process_run(payload_dict) if args.endpoint == "run" else process_run_measured(payload_dict)
            print(json.dumps(result))
    else:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
