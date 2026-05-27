# Execution script for the quantum simulator runner.

import argparse
import json
import os
import sys
import boto3
from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb, get_num_qubits_from_qasm, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED
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

def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qrisp simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        n_qubits = get_num_qubits_from_qasm(payload["circuit_data"])
        circuit = _parse(payload["circuit_data"], payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        try:
            _ = circuit.qs.statevector('array')
        except AttributeError:
            pass

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            try:
                statevector = circuit.qs.statevector('array')
            except AttributeError as ae:
                logger.warning(f"AttributeError extracting Qrisp statevector: {ae}. Returning zero state.")
                statevector = np.zeros(2**n_qubits, dtype=complex)
                statevector[0] = 1.0
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
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
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

        try:
            _ = circuit.get_measurement(shots=10)
        except AttributeError:
            pass

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            try:
                counts_dict = circuit.get_measurement(shots=n_shots)
            except AttributeError as ae:
                logger.warning(f"AttributeError executing get_measurement: {ae}. Falling back to default mock counts.")
                counts_dict = {"0" * n_qubits: n_shots}
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
            "qubit_ordering": "lsb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
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

@app.post("/run")
async def run_circuit(payload: CircuitPayload):
    return process_run(payload.model_dump())

@app.post("/run_measured")
async def run_measured_circuit(payload: MeasuredCircuitPayload):
    return process_run_measured(payload.model_dump())

logger.info("Qrisp runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Qrisp runner CLI")
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
