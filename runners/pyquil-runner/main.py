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
import pytket.qasm
from pytket.passes import RemoveBarriers, PeepholeOptimise2Q, FullPeepholeOptimise
from pytket.transform import Transform
from pytket.extensions.pyquil import tk_to_pyquil
from pyquil import Program
from pyquil.quilbase import Gate
from pyquil.simulation import NumpyWavefunctionSimulator
import time
import gc

logger = get_logger("pyquil-runner")

app = FastAPI(title="PyQuil Runner")

def _to_quil_program(qasm_str: str, optimization_level: int = 0):
    """Parse QASM via pytket and convert to a Quil Program.

    Level 0: barrier removal only
    Level 1: + PeepholeOptimise2Q (cancel redundant 2Q gates, merge 1Q sequences)
    Level 2: + FullPeepholeOptimise (full 1Q merging + KAK-based 2Q reduction)
    """
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str)
    RemoveBarriers().apply(tk_circ)
    if optimization_level >= 2:
        FullPeepholeOptimise().apply(tk_circ)
    elif optimization_level == 1:
        PeepholeOptimise2Q().apply(tk_circ)

    Transform.RebaseToRzRx().apply(tk_circ)
    return tk_to_pyquil(tk_circ), tk_circ.n_qubits

def _gates_only(prog: Program) -> Program:
    """Return a Program with only Gate instructions — strips MEASURE, DECLARE, HALT, etc."""
    clean = Program()
    for inst in prog.instructions:
        if isinstance(inst, Gate):
            clean += inst
    return clean

def _simulate_statevector(gate_prog: Program, n_qubits: int) -> np.ndarray:
    """Apply gate instructions sequentially to |0> and return the statevector."""
    sim = NumpyWavefunctionSimulator(n_qubits=n_qubits)
    for inst in gate_prog.instructions:
        if isinstance(inst, Gate):
            sim.do_gate(inst)
    return np.array(sim.wf).flatten()

def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for PyQuil simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        prog, n_qubits = _to_quil_program(payload["circuit_data"], payload.get("optimization_level", 0))
        gate_prog = _gates_only(prog)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        _simulate_statevector(gate_prog, n_qubits)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = _simulate_statevector(gate_prog, n_qubits)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(statevector)
        logger.info(
            f"PyQuil simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "pyquil",
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
        logger.error(f"Error during PyQuil simulation: {str(e)}")
        return {
            "simulator": "pyquil",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for PyQuil simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        prog, n_qubits = _to_quil_program(payload["circuit_data"], payload.get("optimization_level", 0))
        gate_prog = _gates_only(prog)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        _simulate_statevector(gate_prog, n_qubits)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            statevector = _simulate_statevector(gate_prog, n_qubits)
            probs = np.abs(statevector) ** 2
            probs /= probs.sum()
            indices = np.random.choice(len(probs), size=payload.get("n_shots", 1024), p=probs)
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
            f"PyQuil measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        return {
            "simulator": "pyquil",
            "counts": counts_dict,
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
        logger.error(f"Error during PyQuil measurement simulation: {str(e)}")
        return {
            "simulator": "pyquil",
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
        parser = argparse.ArgumentParser(description="PyQuil runner CLI")
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
