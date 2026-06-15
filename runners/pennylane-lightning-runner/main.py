# Execution script for the quantum simulator runner.

import argparse
import json
import os
import sys
import boto3
from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import _sample_from_statevector, MemoryMonitor, get_logger, encode_statevector, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, get_num_qubits_from_qasm, theoretical_statevector_mb, strip_barriers_from_qasm, with_sdk_versions
import pennylane as qml
import numpy as np
import functools
import time
import gc

app = FastAPI(title="Pennylane Lightning Runner")
logger = get_logger("pennylane-lightning-runner")

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received statevector circuit data for Pennylane-Lightning simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        circuit_data = strip_barriers_from_qasm(payload["circuit_data"])
        transpiled_qasm = circuit_data
        qasm_op = qml.from_qasm(circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload["circuit_data"])
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

        level = payload.get("optimization_level", 0)
        passes = []
        preprocessing_applied = ["qrosetta_commons.helpers.strip_barriers_from_qasm(): Strips barrier instructions from the QASM string, as PennyLane's QASM parser does not support them."]
        if level == 1:
            passes = [qml.transforms.cancel_inverses]
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
        elif level == 2:
            passes = [qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
            preprocessing_applied.append("qml.transforms.merge_rotations: Merges consecutive rotation gates on the same qubit/axis into a single rotation.")
        elif level >= 3:
            passes = [qml.transforms.commute_controlled, qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
            preprocessing_applied.append("qml.transforms.commute_controlled: Pushes single-qubit gates through controlled gates to enable further cancellations.")
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
            preprocessing_applied.append("qml.transforms.merge_rotations: Merges consecutive rotation gates on the same qubit/axis into a single rotation.")

        @functools.partial(qml.compile, pipeline=passes)
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state()

        _ = statevector_circuit()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = statevector_circuit()
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(np.array(statevector))

        logger.info(f"Pennylane-Lightning statevector simulation successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "pennylane-lightning",
            "statevector": statevector_str,
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(num_qubits),
            "preprocessing_applied": preprocessing_applied,
            "transpiled_qasm": transpiled_qasm
        }
    except Exception as e:
        logger.error(f"Error during Pennylane-Lightning statevector simulation: {str(e)}")
        return {
            "simulator": "pennylane-lightning",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Pennylane-Lightning (manual sampling).")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        circuit_data = strip_barriers_from_qasm(payload["circuit_data"])
        transpiled_qasm = circuit_data
        qasm_op = qml.from_qasm(circuit_data)
        num_qubits = get_num_qubits_from_qasm(payload["circuit_data"])
        dev = qml.device("lightning.qubit", wires=num_qubits, shots=None)

        level = payload.get("optimization_level", 0)
        passes = []
        preprocessing_applied = ["qrosetta_commons.helpers.strip_barriers_from_qasm(): Strips barrier instructions from the QASM string, as PennyLane's QASM parser does not support them."]
        if level == 1:
            passes = [qml.transforms.cancel_inverses]
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
        elif level == 2:
            passes = [qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
            preprocessing_applied.append("qml.transforms.merge_rotations: Merges consecutive rotation gates on the same qubit/axis into a single rotation.")
        elif level >= 3:
            passes = [qml.transforms.commute_controlled, qml.transforms.cancel_inverses, qml.transforms.merge_rotations]
            preprocessing_applied.append("qml.transforms.commute_controlled: Pushes single-qubit gates through controlled gates to enable further cancellations.")
            preprocessing_applied.append("qml.transforms.cancel_inverses: Cancels adjacent inverse gate pairs (e.g. H·H, X·X) to reduce gate count.")
            preprocessing_applied.append("qml.transforms.merge_rotations: Merges consecutive rotation gates on the same qubit/axis into a single rotation.")

        @functools.partial(qml.compile, pipeline=passes)
        @qml.qnode(dev)
        def statevector_circuit():
            qasm_op()
            return qml.state()

        _ = statevector_circuit()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = statevector_circuit()
            counts_dict = _sample_from_statevector(statevector, payload.get("n_shots", 1024), num_qubits)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()

        execution_time = compilation_time + simulation_time

        logger.info(f"Pennylane-Lightning manual sampling successful in {execution_time:.4f}s (Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s).")

        return {
            "simulator": "pennylane-lightning",
            "counts": counts_dict,
            "sampling_method": "sv_sample",
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(num_qubits),
            "preprocessing_applied": preprocessing_applied,
            "transpiled_qasm": transpiled_qasm
        }
    except Exception as e:
        logger.error(f"Error during Pennylane-Lightning measurement simulation: {str(e)}")
        return {
            "simulator": "pennylane-lightning",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

@app.post("/run")
def run_circuit(payload: CircuitPayload):
    return process_run(payload.model_dump())

@app.post("/run_measured")
def run_measured_circuit(payload: MeasuredCircuitPayload):
    return process_run_measured(payload.model_dump())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Pennylane-Lightning runner CLI")
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
