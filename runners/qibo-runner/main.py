# Execution script for the quantum simulator runner.

import argparse
import json
import os
import sys
import boto3
from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED
import numpy as np
import time
import gc

from qibo.models import Circuit
from qibo import gates, set_backend

set_backend("numpy")

logger = get_logger("qibo-runner")

app = FastAPI(title="Qibo Runner")

def _parse(qasm_str: str, optimization_level: int = 0) -> Circuit:
    """Parse QASM 2.0 into a Qibo Circuit and apply gate fusion.

    Level 0: no optimization
    Level 1: fuse single-qubit gate runs (max_qubits=1)
    Level 2: fuse up to 2-qubit blocks (max_qubits=2)
    """
    circuit = Circuit.from_qasm(qasm_str)
    if optimization_level >= 2:
        circuit = circuit.fuse(max_qubits=2)
    elif optimization_level == 1:
        circuit = circuit.fuse(max_qubits=1)
    return circuit

def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qibo simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        circuit = _parse(payload["circuit_data"], payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        circuit()

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            result = circuit()
            statevector = np.array(result.state())
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(statevector)
        logger.info(
            f"Qibo simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "qibo",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(circuit.nqubits)
        }
    except Exception as e:
        logger.error(f"Error during Qibo simulation: {str(e)}")
        return {
            "simulator": "qibo",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qibo simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        circuit = _parse(payload["circuit_data"], payload.get("optimization_level", 0))

        if not circuit.measurements:
            circuit.add(gates.M(*range(circuit.nqubits)))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        n_shots = payload.get("n_shots", 1024)

        circuit(nshots=n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            result = circuit(nshots=n_shots)
            counts_dict = dict(result.frequencies())
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        logger.info(
            f"Qibo measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "qibo",
            "counts": counts_dict,
            "sampling_method": "native",
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(circuit.nqubits)
        }
    except Exception as e:
        logger.error(f"Error during Qibo measurement simulation: {str(e)}")
        return {
            "simulator": "qibo",
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
        parser = argparse.ArgumentParser(description="Qibo runner CLI")
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
