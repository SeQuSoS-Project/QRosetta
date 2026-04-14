import argparse
import json
import os
import sys
import boto3
from fastapi import FastAPI
import numpy as np
import pytket.qasm
from pytket.extensions.quest import QuESTBackend
from collections import Counter
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb
import time
import gc

app = FastAPI(title="QuEST Runner")
logger = get_logger("pytket-quest-runner")


def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for QuEST simulation.")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits
        backend = QuESTBackend()
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
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
        logger.info(f"QuEST simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "quest",
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
        logger.error(f"Error during QuEST simulation: {str(e)}")
        return {
            "simulator": "quest",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }


def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for QuEST (manual sampling).")
    try:
        # --- COMPILATION ---
        t0 = time.perf_counter()
        tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
        n_qubits = tk_circ.n_qubits

        backend = QuESTBackend()
        opt_level = min(payload.get("optimization_level", 0), 2)
        compiled_circ = backend.get_compiled_circuit(tk_circ, optimisation_level=opt_level)
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

            # --- BENCHMARKING FIX: Sampling is now timed ---
            counts_dict = _sample_from_statevector(statevector, payload.get("n_shots", 1024), n_qubits)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

        logger.info(f"QuEST manual sampling successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "quest",
            "counts": counts_dict,
            "sampling_method": "native",
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
        }
    except Exception as e:
        logger.error(f"Error during QuEST measurement simulation: {str(e)}")
        return {
            "simulator": "quest",
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
        parser = argparse.ArgumentParser(description="QuEST runner CLI")
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
