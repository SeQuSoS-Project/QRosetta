# Shared common utilities for the Rosetta ecosystem.

import numpy as np
from collections import Counter
import time
import psutil
import threading
import os
import logging
import sys
import functools
import importlib.metadata

import base64

MAX_QUBITS_STATEVECTOR = int(os.getenv("MAX_QUBITS_STATEVECTOR", "18"))
MAX_QUBITS_MEASURED = int(os.getenv("MAX_QUBITS_MEASURED", "24"))

def get_logger(service_name: str) -> logging.Logger:
    """
    Configures a structured logger that outputs to stdout.
    Format: [Timestamp] [Level] [Service] Message
    """
    logger = logging.getLogger(service_name)

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

def encode_statevector(statevector: np.ndarray) -> str:
    """
    Serializes a NumPy array (complex128) to a Base64 string.
    """

    if statevector.dtype != np.complex128:
        statevector = statevector.astype(np.complex128)
    return base64.b64encode(statevector.tobytes()).decode('utf-8')

def decode_statevector(encoded_str: str) -> np.ndarray:
    """
    Deserializes a Base64 string back to a NumPy array (complex128).
    """
    try:
        bytes_data = base64.b64decode(encoded_str)
        return np.frombuffer(bytes_data, dtype=np.complex128)
    except Exception as e:

        raise ValueError(f"Failed to decode statevector: {e}")

def _sample_from_statevector(statevector, n_shots, n_qubits, seed=None):
    """
    Manually samples from a statevector's probability distribution.

    seed: optional int for reproducible sampling. None yields a fresh,
    non-deterministic generator (the prior behaviour).
    """

    probabilities = np.abs(statevector)**2

    rng = np.random.default_rng(seed)
    samples = rng.choice(
        len(statevector),
        size=n_shots,
        p=probabilities
    )

    sample_counts = Counter(samples)

    counts_dict = {
        format(k, f'0{n_qubits}b'): v
        for k, v in sample_counts.items()
    }
    return counts_dict

class MemoryMonitor:
    def __init__(self, interval=0.001):
        """
        interval: Sampling rate in seconds.
        0.001 (1ms) is fast enough to catch C++ spikes
        without slowing down the simulation significantly.
        """
        self.interval = interval
        self.process = psutil.Process(os.getpid())
        self.keep_measuring = True
        self.peak_memory = 0
        self.start_memory = 0
        self.baseline_memory = 0

    def _measure_loop(self):
        while self.keep_measuring:

            current_mem = self.process.memory_info().rss
            if current_mem > self.peak_memory:
                self.peak_memory = current_mem
            time.sleep(self.interval)

    def __enter__(self):

        self.baseline_memory = self.process.memory_info().rss
        self.peak_memory = self.baseline_memory

        self.keep_measuring = True
        self.thread = threading.Thread(target=self._measure_loop)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        self.keep_measuring = False
        self.thread.join()

    def get_peak_usage_mb(self):

        return (self.peak_memory - self.baseline_memory) / (1024 * 1024)

    def get_process_peak_mb(self):

        return self.peak_memory / (1024 * 1024)

def theoretical_statevector_mb(n_qubits: int) -> float:
    """
    Minimum memory to store a full statevector for n_qubits in complex128.
    = 2^N amplitudes × 16 bytes each.
    This is a lower-bound reference; actual runtime usage is always higher
    due to working buffers, compilation state, and intermediate tensors.
    Not meaningful for tensor-network simulators (report None for those).
    """
    return (2 ** n_qubits * 16) / (1024 ** 2)

def get_num_qubits_from_qasm(qasm_string: str) -> int:
    """
    Parses QASM string to find the size of the 'qreg'.
    Returns 0 if not found (or raises error if strict).
    """
    for line in qasm_string.split('\n'):
        if line.strip().startswith("qreg"):
            try:

                return int(line.split('[')[1].split(']')[0])
            except Exception:
                pass
    return 0

def strip_barriers_from_qasm(qasm_string: str) -> str:
    """Remove barrier instructions from QASM before simulation.
    Barriers are visual hints only — they don't affect the statevector.
    Some C++ backends (lightning.qubit) raise errors on qml.Barrier at larger wire counts."""
    return '\n'.join(
        line for line in qasm_string.split('\n')
        if not line.strip().startswith('barrier')
    )

def check_qubits_limit(qasm_string: str, max_qubits: int = 24):
    """
    Raises ValueError if the circuit has more qubits than allowed.
    24 qubits ~ 268 MB statevector (complex128).
    25 qubits ~ 536 MB statevector (OOM on 512 MiB local container,
    fits within 1 GiB K8s runner pod).
    """
    n_qubits = get_num_qubits_from_qasm(qasm_string)
    if n_qubits > max_qubits:
        raise ValueError(f"Circuit has {n_qubits} qubits, which exceeds the limit of {max_qubits} for this runner.")


# Distribution-name substrings that identify the quantum SDK packages worth recording
# for provenance. A runner's image is isolated and only contains its own stack, so
# scanning installed distributions for these yields exactly that runner's quantum
# dependencies (e.g. pytket + pytket-qiskit + qiskit + qiskit-aer for the qiskit runner).
_SDK_VERSION_KEYWORDS = (
    "qiskit", "cirq", "qulacs", "pennylane", "qibo", "pytket", "cuquantum",
    "custatevec", "torch", "quimb", "myqlm", "qat", "qrisp", "pyquil",
    "braket", "projectq",
)

_sdk_versions_cache = None

def get_sdk_versions() -> dict:
    """Return {distribution_name: version} for the quantum SDK packages installed in
    this process, read from importlib.metadata at runtime.

    These are the versions that executed the circuit, recorded in the report and the
    RO-Crate provenance. Versions are fixed for a process's lifetime, so the scan is
    cached after the first call.
    """
    global _sdk_versions_cache
    if _sdk_versions_cache is not None:
        return dict(_sdk_versions_cache)
    versions = {}
    try:
        for dist in importlib.metadata.distributions():
            try:
                name = dist.metadata["Name"]
            except Exception:
                name = None
            if name and any(k in name.lower() for k in _SDK_VERSION_KEYWORDS):
                versions[name] = dist.version
    except Exception:
        pass
    _sdk_versions_cache = versions
    return dict(versions)

def with_sdk_versions(func):
    """Decorator for a runner's process_run / process_run_measured.

    Attaches the executed SDK versions (get_sdk_versions) to the returned result dict
    under 'sdk_versions' on both the success and error paths.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, dict) and "sdk_versions" not in result:
            result["sdk_versions"] = get_sdk_versions()
        return result
    return wrapper


# --- isolated, hard-timeout execution -------------------------------------------------
# Runs a runner's process_run / process_run_measured in a spawned child process with a hard
# wall-clock kill, off the async event loop. A CPU-bound simulation cannot be interrupted in
# a thread, so a runaway or out-of-memory run is stopped by killing the process. spawn (not
# fork) is used so the GPU runners initialise cleanly in the child.

import asyncio as _asyncio
import importlib as _importlib
import multiprocessing as _multiprocessing
import queue as _queue
import re as _re
import resource as _resource
import statistics as _statistics

_SPAWN_CTX = _multiprocessing.get_context("spawn")

DEFAULT_HARD_TIMEOUT_SEC = int(os.getenv("RUNNER_HARD_TIMEOUT_SEC", "300"))

_QASM_NON_GATE_KEYWORDS = {
    "openqasm", "include", "qreg", "creg", "barrier", "measure", "reset", "if", "gate", "opaque",
}
_QASM_QUBIT_REF_RE = _re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\[\s*(\d+)\s*\]')


def count_qasm_gates_and_depth(qasm_str: str) -> tuple:
    """Count gate-application statements and their circuit depth from an OpenQASM 2.0
    string, with no quantum-SDK dependency (this module is imported by every runner).

    Depth uses the standard greedy-layering definition: a gate's layer is one more than
    the deepest layer already recorded on any qubit it touches. Qubits are identified by
    their literal ``register[index]`` token, so gates inside a custom ``gate ... { }``
    definition (which refer to bare formal parameters, no ``[index]``) are not counted,
    and neither are classically-conditioned (``if (...)``) statements.
    """
    depth_by_qubit = {}
    gate_count = 0
    # A gate/opaque definition's closing '}' has no preceding ';', so a naive split(';')
    # would glue it onto the next real statement's first word. Blanking braces avoids that
    # while still leaving 'gate'/'opaque' as each definition's own (skipped) first word.
    no_braces = _re.sub(r'//.*', '', qasm_str).replace('{', ' ').replace('}', ' ')
    for stmt in no_braces.split(';'):
        stmt = stmt.strip()
        if not stmt:
            continue
        words = stmt.split('(', 1)[0].split()
        if not words or words[0].lower() in _QASM_NON_GATE_KEYWORDS:
            continue
        qubits = _QASM_QUBIT_REF_RE.findall(stmt)
        if not qubits:
            continue
        gate_count += 1
        qubit_keys = [f"{reg}[{idx}]" for reg, idx in qubits]
        layer = max((depth_by_qubit.get(k, 0) for k in qubit_keys), default=0) + 1
        for k in qubit_keys:
            depth_by_qubit[k] = layer
    return gate_count, max(depth_by_qubit.values(), default=0)


def _call_once(module_name, func_name, payload):
    module = _importlib.import_module(module_name)
    return getattr(module, func_name)(payload)


def _isolated_target(result_q, module_name, func_name, payload):
    try:
        # Uniform disclosed warm-up: one full, discarded call (covering import/JIT/compile
        # caches) before every timed measurement, for all runners alike. Runners no longer
        # need their own ad-hoc warm-up call.
        _call_once(module_name, func_name, payload)

        repeats = max(1, int(payload.get("timing_repeats", 1) or 1))
        timed_results = [_call_once(module_name, func_name, payload) for _ in range(repeats)]
        result = timed_results[-1]

        if isinstance(result, dict):
            if repeats > 1:
                exec_times = [r.get("execution_time_sec") for r in timed_results
                              if isinstance(r.get("execution_time_sec"), (int, float))]
                if exec_times:
                    result["timing_repeats"] = repeats
                    result["execution_time_sec_mean"] = _statistics.mean(exec_times)
                    result["execution_time_sec_stdev"] = (
                        _statistics.stdev(exec_times) if len(exec_times) > 1 else 0.0)

            usage = _resource.getrusage(_resource.RUSAGE_SELF)
            result["process_peak_rss_mb"] = usage.ru_maxrss / 1024  # ru_maxrss is KB on Linux
            result["cpu_time_sec"] = usage.ru_utime + usage.ru_stime

            if "n_shots" in payload:
                result["n_shots"] = payload["n_shots"]

            transpiled_qasm = result.get("transpiled_qasm")
            if transpiled_qasm:
                gate_count, circuit_depth = count_qasm_gates_and_depth(transpiled_qasm)
                result["gate_count"] = gate_count
                result["circuit_depth"] = circuit_depth

        result_q.put(("ok", result))
    except Exception as e:
        result_q.put(("err", f"{type(e).__name__}: {e}"))


def _isolated_error(message):
    return {"error": message, "execution_time_sec": 0.0, "memory_usage_mb": 0.0}


def _run_isolated_blocking(module_name, func_name, payload, timeout_s):
    result_q = _SPAWN_CTX.Queue()
    proc = _SPAWN_CTX.Process(
        target=_isolated_target, args=(result_q, module_name, func_name, payload))
    proc.start()

    # Poll so a crashed child (e.g. OOM kill) is detected in ~0.2s rather than only at the
    # deadline, while still enforcing the hard timeout. get() drains the pipe as the child
    # writes, avoiding a large-result deadlock.
    deadline = time.monotonic() + timeout_s
    outcome = None
    while True:
        try:
            outcome = result_q.get(timeout=0.2)
            break
        except _queue.Empty:
            if not proc.is_alive() or time.monotonic() >= deadline:
                break
    result_q.close()

    if outcome is None:
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            if proc.is_alive():
                proc.kill()
                proc.join()
            return _isolated_error(
                f"TIMEOUT ({timeout_s}s): the simulation exceeded the time budget and was "
                f"terminated.")
        return _isolated_error(
            f"Runner subprocess exited (code {proc.exitcode}) without a result — most likely "
            f"an out-of-memory kill.")

    proc.join(5)
    if proc.is_alive():
        proc.terminate()
    status, value = outcome
    return value if status == "ok" else _isolated_error(value)


async def run_isolated(func, payload, default_timeout=None):
    """Await a runner function in a killable child process, without blocking the event loop.

    The wall-clock budget comes from ``payload['hard_timeout_seconds']`` (set by the
    dispatcher), falling back to ``default_timeout`` / RUNNER_HARD_TIMEOUT_SEC.
    """
    if default_timeout is None:
        default_timeout = DEFAULT_HARD_TIMEOUT_SEC
    timeout_s = payload.get("hard_timeout_seconds") or default_timeout
    loop = _asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _run_isolated_blocking, func.__module__, func.__name__, payload, int(timeout_s))


# --- shared runner scaffolding --------------------------------------------------------
# Every runner exposes the same HTTP surface, the same S3/local CLI, and the same result
# contract. These helpers hold that boilerplate once so each runner file is its imports plus
# the SDK-specific compile/execute logic.

_UNSET = object()


def _base_result(*, simulator, compilation_time, simulation_time, monitor, qubit_ordering,
                 n_qubits, theoretical_mb, preprocessing_applied, transpiled_qasm):
    # theoretical_mb defaults to (2^n * 16) computed from n_qubits; pass it explicitly
    # (e.g. None) for backends where a dense statevector size is not meaningful.
    if theoretical_mb is _UNSET:
        theoretical_mb = theoretical_statevector_mb(n_qubits)
    return {
        "simulator": simulator,
        "execution_time_sec": compilation_time + simulation_time,
        "compilation_time_sec": compilation_time,
        "simulation_time_sec": simulation_time,
        "memory_usage_mb": monitor.get_peak_usage_mb(),
        "process_peak_mb": monitor.get_process_peak_mb(),
        "qubit_ordering": qubit_ordering,
        "theoretical_statevector_mb": theoretical_mb,
        "preprocessing_applied": preprocessing_applied,
        "transpiled_qasm": transpiled_qasm,
    }


def statevector_result(*, simulator, statevector, compilation_time, simulation_time, monitor,
                       qubit_ordering, preprocessing_applied, transpiled_qasm,
                       n_qubits=None, theoretical_mb=_UNSET):
    """Assemble a runner's statevector result dict. ``statevector`` is the raw array-like
    output; it is encoded to the Base64 wire format here."""
    result = _base_result(
        simulator=simulator, compilation_time=compilation_time, simulation_time=simulation_time,
        monitor=monitor, qubit_ordering=qubit_ordering, n_qubits=n_qubits,
        theoretical_mb=theoretical_mb, preprocessing_applied=preprocessing_applied,
        transpiled_qasm=transpiled_qasm)
    result["statevector"] = encode_statevector(np.asarray(statevector))
    return result


def counts_result(*, simulator, counts, sampling_method, compilation_time, simulation_time,
                  monitor, qubit_ordering, preprocessing_applied, transpiled_qasm,
                  n_qubits=None, theoretical_mb=_UNSET):
    """Assemble a runner's measured (counts) result dict. ``sampling_method=None`` omits the
    key (a runner that does not label its sampling method)."""
    result = _base_result(
        simulator=simulator, compilation_time=compilation_time, simulation_time=simulation_time,
        monitor=monitor, qubit_ordering=qubit_ordering, n_qubits=n_qubits,
        theoretical_mb=theoretical_mb, preprocessing_applied=preprocessing_applied,
        transpiled_qasm=transpiled_qasm)
    result["counts"] = counts
    if sampling_method is not None:
        result["sampling_method"] = sampling_method
    return result


def runner_error(simulator: str, exc) -> dict:
    """Assemble a runner's error result dict from a caught exception."""
    return {
        "simulator": simulator,
        "error": str(exc),
        "execution_time_sec": 0.0,
        "memory_usage_mb": 0.0,
        "process_peak_mb": 0.0,
    }


def register_runner_endpoints(app, process_run, process_run_measured):
    """Register the standard /run and /run_measured endpoints on a runner's FastAPI app.

    Each runs the CPU-bound processor in a killable child process (run_isolated) so a runaway
    or OOM simulation cannot hang the worker.
    """
    from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload

    @app.post("/run")
    async def run_circuit(payload: CircuitPayload):
        return await run_isolated(process_run, payload.model_dump())

    @app.post("/run_measured")
    async def run_measured_circuit(payload: MeasuredCircuitPayload):
        return await run_isolated(process_run_measured, payload.model_dump())


def run_cli_main(app, process_run, process_run_measured, cli_name):
    """Runner entrypoint. With no CLI args, serves the FastAPI app; with ``--endpoint`` it
    runs one job from an inline ``--payload`` or an S3 job id (the Kubernetes dispatch path).
    Call under ``if __name__ == "__main__":``.
    """
    import sys
    if len(sys.argv) <= 1:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
        return

    import argparse
    import json
    import os
    parser = argparse.ArgumentParser(description=f"{cli_name} runner CLI")
    parser.add_argument("--endpoint", choices=["run", "run_measured"], required=True,
                        help="Which endpoint to invoke")
    parser.add_argument("--payload", default=None, help="JSON payload string")
    parser.add_argument("--s3-job-id", default=None,
                        help="S3 job ID: download payload from jobs/pending/<id>.json, "
                             "upload result to jobs/completed/<id>.json")
    args = parser.parse_args()

    def _process(payload_dict):
        return process_run(payload_dict) if args.endpoint == "run" else process_run_measured(payload_dict)

    if args.s3_job_id:
        import boto3
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

        result = _process(payload_dict)
        result_bytes = json.dumps(result).encode()
        s3.put_object(Bucket=bucket, Key=f"jobs/completed/{args.s3_job_id}.json",
                      Body=result_bytes, ContentLength=len(result_bytes))
        print(f"Job {args.s3_job_id} completed and uploaded to S3.")
    else:
        if args.payload is None:
            parser.error("--payload is required when --s3-job-id is not provided")
        print(json.dumps(_process(json.loads(args.payload))))