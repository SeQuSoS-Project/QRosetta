import argparse
import json
import os
import sys
import boto3
from fastapi import FastAPI
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload
from qrosetta_commons.helpers import MemoryMonitor, get_logger, encode_statevector, theoretical_statevector_mb, check_qubits_limit
import numpy as np
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq
from pytket.passes import RemoveBarriers
from pytket.transform import Transform
import cirq
import time
import gc

try:
    import qsimcirq
    QSIM_AVAILABLE = True
except ImportError:
    QSIM_AVAILABLE = False

logger = get_logger("qsim-cirq-runner")

app = FastAPI(title="qsim-Cirq Runner")


def _to_cirq_circuit(qasm_str: str, optimization_level: int = 0) -> cirq.Circuit:
    """Parse QASM string via pytket, convert to Cirq, then apply Cirq-native optimizations.

    Level 0: no optimization
    Level 1: basic cleanup (drop empty moments, align)
    Level 2: full reduction (eject Z/phased-Paulis, merge single-qubit gates)
    """
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str)
    RemoveBarriers().apply(tk_circ)
    Transform.RebaseToRzRx().apply(tk_circ)
    circ = tk_to_cirq(tk_circ)

    if optimization_level >= 1:
        circ = cirq.drop_empty_moments(circ)
        circ = cirq.align_left(circ)

    if optimization_level >= 2:
        circ = cirq.eject_z(circ)
        circ = cirq.eject_phased_paulis(circ)
        circ = cirq.merge_single_qubit_gates_to_phxz(circ)
        circ = cirq.drop_empty_moments(circ)

    return circ


def _strip_measurements(circ: cirq.Circuit) -> cirq.Circuit:
    """Return a copy of the circuit with all measurement gates removed."""
    return cirq.Circuit(
        op for op in circ.all_operations()
        if not isinstance(op.gate, cirq.MeasurementGate)
    )


def process_run(payload: dict) -> dict:
    if not QSIM_AVAILABLE:
        return {
            "simulator": "qsim-cirq",
            "error": "qsimcirq package not installed",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

    circuit_data = payload["circuit_data"]
    optimization_level = payload.get("optimization_level", 0)

    logger.info("Received circuit data for qsim-Cirq simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], 24)
        # --- COMPILATION ---
        t0 = time.perf_counter()
        cirq_circ = _to_cirq_circuit(circuit_data, optimization_level)
        cirq_circ_no_meas = _strip_measurements(cirq_circ)
        simulator = qsimcirq.QSimSimulator()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = simulator.simulate(cirq_circ_no_meas)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            result = simulator.simulate(cirq_circ_no_meas)
            statevector = result.final_state_vector
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        statevector_str = encode_statevector(np.array(statevector))
        logger.info(
            f"qsim-Cirq simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        n_qubits = len(cirq_circ_no_meas.all_qubits())
        return {
            "simulator": "qsim-cirq",
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
        logger.error(f"Error during qsim-Cirq simulation: {str(e)}")
        return {
            "simulator": "qsim-cirq",
            "error": str(e),
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }


def process_run_measured(payload: dict) -> dict:
    if not QSIM_AVAILABLE:
        return {
            "simulator": "qsim-cirq",
            "error": "qsimcirq package not installed",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
            "process_peak_mb": 0.0
        }

    circuit_data = payload["circuit_data"]
    optimization_level = payload.get("optimization_level", 0)
    n_shots = payload.get("n_shots", 1024)

    logger.info("Received measured circuit data for qsim-Cirq simulation.")
    try:
        check_qubits_limit(payload["circuit_data"], 24)
        # --- COMPILATION ---
        t0 = time.perf_counter()
        cirq_circ = _to_cirq_circuit(circuit_data, optimization_level)
        # Strip any existing measurements and add a clean terminal measurement
        # on all qubits so qsim's run() interface can sample deterministically.
        all_qubits = sorted(cirq_circ.all_qubits())
        circ_with_meas = _strip_measurements(cirq_circ) + cirq.measure(
            *all_qubits, key="result"
        )
        simulator = qsimcirq.QSimSimulator()
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        # --- WARM-UP ---
        _ = simulator.run(circ_with_meas, repetitions=n_shots)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            # --- SIMULATION ---
            t2 = time.perf_counter()
            run_result = simulator.run(circ_with_meas, repetitions=n_shots)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        memory_usage_mb = monitor.get_peak_usage_mb()
        process_peak_mb = monitor.get_process_peak_mb()
        execution_time = compilation_time + simulation_time

        # Convert measurement array (n_shots × n_qubits) → {bitstring: count}
        measurements = run_result.measurements["result"]
        counts_dict: dict = {}
        for shot in measurements:
            bitstring = "".join(str(int(b)) for b in shot)
            counts_dict[bitstring] = counts_dict.get(bitstring, 0) + 1

        logger.info(
            f"qsim-Cirq measurement simulation successful in {execution_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )

        n_qubits = len(all_qubits)
        return {
            "simulator": "qsim-cirq",
            "counts": counts_dict,
            "sampling_method": "native",
            "execution_time_sec": execution_time,
            "compilation_time_sec": compilation_time,
            "simulation_time_sec": simulation_time,
            "memory_usage_mb": memory_usage_mb,
            "process_peak_mb": process_peak_mb,
            "qubit_ordering": "msb",
            "theoretical_statevector_mb": theoretical_statevector_mb(n_qubits)
        }
    except Exception as e:
        logger.error(f"Error during qsim-Cirq measurement simulation: {str(e)}")
        return {
            "simulator": "qsim-cirq",
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
        parser = argparse.ArgumentParser(description="qsim-Cirq runner CLI")
        parser.add_argument(
            "--endpoint",
            choices=["run", "run_measured"],
            required=True,
            help="Which endpoint to invoke"
        )
        parser.add_argument(
            "--payload",
            default=None,
            help="JSON payload string"
        )
        parser.add_argument(
            "--s3-job-id",
            default=None,
            help="S3 job ID: download payload from jobs/pending/<id>.json, upload result to jobs/completed/<id>.json"
        )
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

            if args.endpoint == "run":
                result = process_run(payload_dict)
            else:
                result = process_run_measured(payload_dict)

            result_bytes = json.dumps(result).encode()
            s3.put_object(
                Bucket=bucket,
                Key=f"jobs/completed/{args.s3_job_id}.json",
                Body=result_bytes,
                ContentLength=len(result_bytes),
            )
            print(f"Job {args.s3_job_id} completed and uploaded to S3.")
        else:
            if args.payload is None:
                parser.error("--payload is required when --s3-job-id is not provided")
            payload_dict = json.loads(args.payload)

            if args.endpoint == "run":
                result = process_run(payload_dict)
            else:
                result = process_run_measured(payload_dict)

            print(json.dumps(result))
    else:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
