import argparse
import json
import os
import sys
import boto3
from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb
import numpy as np
import time
import gc

from qat.interop.openqasm import OqasmParser
from qat.qpus import PyLinalg

logger = get_logger("myqlm-runner")

app = FastAPI(title="myQLM Runner")

_qpu = PyLinalg()


def _compile_circuit(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 into a myQLM Circuit. Fresh parser per call — OqasmParser is stateful.

    myQLM's PyLinalg QPU does not expose configurable circuit-level optimization
    passes through its standard API. All optimization levels run identically.
    """
    if optimization_level > 0:
        logger.info(
            f"myQLM: optimization_level={optimization_level} requested "
            "but not supported by PyLinalg; running at level 0."
        )
    return OqasmParser().compile(qasm_str)


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


def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for myQLM simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circuit = _compile_circuit(payload["circuit_data"], payload.get("optimization_level", 0))
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

        n_qubits = circuit.nbqbits
        return {
            "simulator": "myqlm",
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
        logger.error(f"Error during myQLM simulation: {str(e)}")
        return {
            "simulator": "myqlm",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }


def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for myQLM simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        circuit = _compile_circuit(payload["circuit_data"], payload.get("optimization_level", 0))
        n_qubits = circuit.nbqbits
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        n_shots = payload.get("n_shots", 1024)

        # nbshots=0 rejects circuits with measurement gates, so sample natively.
        job = circuit.to_job(job_type="SAMPLE", nbshots=n_shots)

        # --- WARM-UP ---
        _qpu.submit(job)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            result = _qpu.submit(job)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        # PyLinalg returns probabilities, not raw counts — reconstruct and normalise.
        counts_dict = {
            format(sample.state.int, f"0{n_qubits}b"): round(sample.probability * n_shots)
            for sample in result
            if round(sample.probability * n_shots) > 0
        }
        # Correct rounding drift so total equals exactly n_shots.
        diff = n_shots - sum(counts_dict.values())
        if diff != 0 and counts_dict:
            top = max(counts_dict, key=counts_dict.get)
            counts_dict[top] += diff

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
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits),
            "sampling_method": "probability_rounding"
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


@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    return process_run(payload.model_dump())


@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    return process_run_measured(payload.model_dump())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="myQLM runner CLI")
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
