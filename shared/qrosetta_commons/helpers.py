"""Shared runner utilities: QASM helpers, the timing/memory instrument, result contract,
isolated execution and the HTTP/CLI scaffolding."""

import asyncio as _asyncio
import base64
import functools
import gc
import importlib as _importlib
import importlib.metadata
import logging
import multiprocessing as _multiprocessing
import os
import queue as _queue
import re
import resource as _resource
import statistics as _statistics
import sys
import time
from collections import Counter

import numpy as np

from qrosetta_commons.memory import MemoryMonitor, lifetime_peak_rss

MAX_QUBITS_STATEVECTOR = int(os.getenv("MAX_QUBITS_STATEVECTOR", "18"))
MAX_QUBITS_MEASURED = int(os.getenv("MAX_QUBITS_MEASURED", "24"))

THREAD_ENV_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                   "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS")

UNMEASURED_METRICS = ("execution_time_sec", "compilation_time_sec", "simulation_time_sec",
                      "memory_usage_mb", "process_peak_mb")


def unmeasured_metrics() -> dict:
    """The per-run metrics of a failed run, each None because it was not measured."""
    return {name: None for name in UNMEASURED_METRICS}

METRIC_SCOPE = {
    "compilation_time_sec": "wall clock, t0..t1 of the last timed run",
    "simulation_time_sec": "wall clock, t2..t3 of the last timed run",
    "simulation_cpu_time_sec": "process CPU time (all threads), t2..t3 of the last timed run",
    "memory_usage_mb": "peak RSS minus RSS at monitor entry, pre_execute + t2..t3 of the "
                       "last timed run",
    "process_peak_mb": "peak RSS, pre_execute + t2..t3 of the last timed run",
    "cpu_time_sec": "process CPU time over the whole runner process: interpreter start, "
                    "imports, warm-up and all timed runs",
    "process_peak_rss_mb": "peak RSS over the whole runner process: interpreter start, "
                           "imports, warm-up and all timed runs",
    "queue_wait_sec": "wall clock the request waited for this runner's execution slot "
                      "before its process was spawned; 0 on the Kubernetes path",
}


def get_logger(service_name: str) -> logging.Logger:
    """Return a stdout logger formatted as ``timestamp | level | service | message``."""
    logger = logging.getLogger(service_name)
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(handler)
    return logger


def encode_statevector(statevector: np.ndarray) -> str:
    """Serialize a statevector to Base64 as complex128."""
    if statevector.dtype != np.complex128:
        statevector = statevector.astype(np.complex128)
    return base64.b64encode(statevector.tobytes()).decode('utf-8')


def decode_statevector(encoded_str: str) -> np.ndarray:
    """Deserialize a Base64 string into a complex128 array."""
    try:
        return np.frombuffer(base64.b64decode(encoded_str), dtype=np.complex128)
    except Exception as e:
        raise ValueError(f"Failed to decode statevector: {e}")


def _draw_statevector_samples(statevector, n_shots, seed=None):
    """Draw ``n_shots`` basis-state indices from a statevector's |amplitude|^2.

    Call from ``execute_fn``; pair with ``_counts_from_samples`` in ``postprocess_fn``.
    ``seed=None`` uses a fresh non-deterministic generator.
    """
    probabilities = np.abs(statevector)**2
    rng = np.random.default_rng(seed)
    return rng.choice(len(statevector), size=n_shots, p=probabilities)


def _counts_from_samples(samples, n_qubits):
    """Build a ``{bitstring: count}`` histogram from sampled indices. Call from
    ``postprocess_fn``."""
    return {
        format(k, f'0{n_qubits}b'): v
        for k, v in Counter(samples).items()
    }


def theoretical_statevector_mb(n_qubits: int) -> float:
    """Size of a dense complex128 statevector for ``n_qubits``: ``2^N * 16`` bytes, in MiB."""
    return (2 ** n_qubits * 16) / (1024 ** 2)


_QREG_DECL_RE = re.compile(r"\bqreg\s+\w+\s*\[\s*(\d+)\s*\]\s*;")
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_qasm_comments(qasm_string: str) -> str:
    """Remove // line comments and /* */ block comments from QASM source."""
    return _LINE_COMMENT_RE.sub("", _BLOCK_COMMENT_RE.sub("", qasm_string))


def get_num_qubits_from_qasm(qasm_string: str) -> int:
    """Total qubits declared by the circuit, summed over every ``qreg``; 0 if none."""
    sizes = _QREG_DECL_RE.findall(strip_qasm_comments(qasm_string))
    return sum(int(size) for size in sizes)


def strip_barriers_from_qasm(qasm_string: str) -> str:
    """Remove ``barrier`` lines from QASM source."""
    return '\n'.join(
        line for line in qasm_string.split('\n')
        if not line.strip().startswith('barrier')
    )


def check_qubits_limit(qasm_string: str, max_qubits: int = 24):
    """Raise ValueError if the circuit declares more than ``max_qubits`` qubits."""
    n_qubits = get_num_qubits_from_qasm(qasm_string)
    if n_qubits > max_qubits:
        raise ValueError(f"Circuit has {n_qubits} qubits, which exceeds the limit of {max_qubits} for this runner.")


_SDK_VERSION_KEYWORDS = (
    "qiskit", "cirq", "qulacs", "pennylane", "qibo", "pytket", "cuquantum",
    "custatevec", "torch", "quimb", "myqlm", "qat", "qrisp", "pyquil",
    "braket", "projectq",
)

_sdk_versions_cache = None


def get_sdk_versions() -> dict:
    """Return ``{distribution: version}`` for installed quantum-SDK packages (cached)."""
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
    """Decorator adding ``sdk_versions`` to a runner processor's result dict."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, dict) and "sdk_versions" not in result:
            result["sdk_versions"] = get_sdk_versions()
        return result
    return wrapper


def get_thread_env() -> dict:
    """Return the thread-count environment variables of this process (None if unset)."""
    return {name: os.environ.get(name) for name in THREAD_ENV_VARS}


_SPAWN_CTX = _multiprocessing.get_context("spawn")

DEFAULT_HARD_TIMEOUT_SEC = int(os.getenv("RUNNER_HARD_TIMEOUT_SEC", "300"))

_QASM_NON_GATE_KEYWORDS = {
    "openqasm", "include", "qreg", "creg", "barrier", "measure", "reset", "if", "gate", "opaque",
}
_QASM_QUBIT_REF_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\[\s*(\d+)\s*\]')


def count_qasm_gates_and_depth(qasm_str: str) -> tuple:
    """Return ``(gate_count, depth)`` for the top-level gate statements of OpenQASM 2.0.

    Depth is greedy layering over literal ``reg[i]`` operands. Statements inside
    ``gate``/``opaque`` definitions and ``if (...)`` statements are not counted.
    """
    depth_by_qubit = {}
    gate_count = 0
    no_braces = re.sub(r'//.*', '', qasm_str).replace('{', ' ').replace('}', ' ')
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


def run_with_uniform_measurement(func, payload):
    """Run a runner processor once as a discarded warm-up, then ``timing_repeats`` timed
    times, and attach process-level diagnostics to the last timed result.

    Used by both the isolated child (``run_isolated``) and the Kubernetes CLI path.
    ``cpu_time_sec`` and ``process_peak_rss_mb`` cover the whole runner process; see
    ``METRIC_SCOPE``, which is copied into the result as ``metric_scope``.
    """
    func(payload)

    repeats = max(1, int(payload.get("timing_repeats", 1) or 1))
    timed_results = [func(payload) for _ in range(repeats)]
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
        peak_mb, peak_method = lifetime_peak_rss()
        result["process_peak_rss_mb"] = peak_mb
        result["process_peak_rss_method"] = peak_method
        result["cpu_time_sec"] = usage.ru_utime + usage.ru_stime
        result["metric_scope"] = dict(METRIC_SCOPE)

        if "n_shots" in payload:
            result["n_shots"] = payload["n_shots"]

        transpiled_qasm = result.get("transpiled_qasm")
        if transpiled_qasm:
            gate_count, circuit_depth = count_qasm_gates_and_depth(transpiled_qasm)
            result["gate_count"] = gate_count
            result["circuit_depth"] = circuit_depth

    return result


def _isolated_target(result_q, module_name, func_name, payload):
    try:
        module = _importlib.import_module(module_name)
        func = getattr(module, func_name)
        result_q.put(("ok", run_with_uniform_measurement(func, payload)))
    except Exception as e:
        result_q.put(("err", f"{type(e).__name__}: {e}"))


def _isolated_error(message, timed_out=False):
    result = {"error": message, **unmeasured_metrics()}
    if timed_out:
        result["timed_out"] = True
    return result


def _run_isolated_blocking(module_name, func_name, payload, timeout_s):
    """Run the processor in a spawned child; poll every 0.2 s for a result, a dead child
    or the deadline."""
    result_q = _SPAWN_CTX.Queue()
    proc = _SPAWN_CTX.Process(
        target=_isolated_target, args=(result_q, module_name, func_name, payload))
    proc.start()

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
                f"TIMEOUT ({timeout_s}s): the runner process (spawn, SDK import, warm-up and "
                f"timed run) exceeded {timeout_s} s and was terminated.", timed_out=True)
        return _isolated_error(
            f"The runner process was terminated (exit code {proc.exitcode}) before returning "
            f"a result, most likely out of memory. Server operators can see details in the "
            f"runner logs.")

    proc.join(5)
    if proc.is_alive():
        proc.terminate()
    status, value = outcome
    return value if status == "ok" else _isolated_error(value)


async def run_isolated(func, payload, default_timeout=None):
    """Await a runner processor in a killable spawned child process.

    The wall-clock budget is ``payload['hard_timeout_seconds']``, else ``default_timeout``,
    else RUNNER_HARD_TIMEOUT_SEC.
    """
    if default_timeout is None:
        default_timeout = DEFAULT_HARD_TIMEOUT_SEC
    timeout_s = payload.get("hard_timeout_seconds") or default_timeout
    loop = _asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _run_isolated_blocking, func.__module__, func.__name__, payload, int(timeout_s))


_UNSET = object()


def _base_result(*, simulator, compilation_time, simulation_time, monitor, qubit_ordering,
                 n_qubits, theoretical_mb, preprocessing_applied, transpiled_qasm,
                 simulation_cpu_time=None, precision=None):
    """Fields common to statevector and counts results. ``theoretical_mb`` defaults to the
    dense size for ``n_qubits``; pass None where a dense statevector does not apply."""
    if theoretical_mb is _UNSET:
        theoretical_mb = theoretical_statevector_mb(n_qubits)
    return {
        "simulator": simulator,
        "execution_time_sec": compilation_time + simulation_time,
        "compilation_time_sec": compilation_time,
        "simulation_time_sec": simulation_time,
        "simulation_cpu_time_sec": simulation_cpu_time,
        "memory_usage_mb": monitor.get_peak_usage_mb(),
        "process_peak_mb": monitor.get_process_peak_mb(),
        "memory_method": getattr(monitor, "method", None),
        "qubit_ordering": qubit_ordering,
        "theoretical_statevector_mb": theoretical_mb,
        "preprocessing_applied": preprocessing_applied,
        "transpiled_qasm": transpiled_qasm,
        "precision": precision,
        "thread_env": get_thread_env(),
    }


def statevector_result(*, simulator, statevector, compilation_time, simulation_time, monitor,
                       qubit_ordering, preprocessing_applied, transpiled_qasm,
                       n_qubits=None, theoretical_mb=_UNSET, simulation_cpu_time=None,
                       precision=None):
    """Assemble a statevector result; ``statevector`` is encoded to Base64 here."""
    result = _base_result(
        simulator=simulator, compilation_time=compilation_time, simulation_time=simulation_time,
        monitor=monitor, qubit_ordering=qubit_ordering, n_qubits=n_qubits,
        theoretical_mb=theoretical_mb, preprocessing_applied=preprocessing_applied,
        transpiled_qasm=transpiled_qasm, simulation_cpu_time=simulation_cpu_time,
        precision=precision)
    result["statevector"] = encode_statevector(np.asarray(statevector))
    return result


def counts_result(*, simulator, counts, sampling_method, compilation_time, simulation_time,
                  monitor, qubit_ordering, preprocessing_applied, transpiled_qasm,
                  n_qubits=None, theoretical_mb=_UNSET, simulation_cpu_time=None,
                  precision=None):
    """Assemble a counts result; ``sampling_method=None`` omits that key."""
    result = _base_result(
        simulator=simulator, compilation_time=compilation_time, simulation_time=simulation_time,
        monitor=monitor, qubit_ordering=qubit_ordering, n_qubits=n_qubits,
        theoretical_mb=theoretical_mb, preprocessing_applied=preprocessing_applied,
        transpiled_qasm=transpiled_qasm, simulation_cpu_time=simulation_cpu_time,
        precision=precision)
    result["counts"] = counts
    if sampling_method is not None:
        result["sampling_method"] = sampling_method
    return result


def runner_error(simulator: str, exc) -> dict:
    """Assemble a runner error result from an exception."""
    return {"simulator": simulator, "error": str(exc), **unmeasured_metrics()}


class CompileResult:
    """Output of a runner's compile step, passed to its execute step.

    ``circuit`` is whatever the SDK executes; the scaffold does not inspect it.
    ``transpiled_qasm`` is set by runners that mutate the circuit during compilation;
    otherwise ``serialize_fn`` fills it after t1. ``precision`` (e.g. ``"complex64"``)
    overrides the ``precision`` passed to ``run_statevector_job`` / ``run_measured_job``.
    """

    __slots__ = ("circuit", "n_qubits", "preprocessing_applied", "transpiled_qasm", "precision")

    def __init__(self, circuit, n_qubits=None, preprocessing_applied=None, transpiled_qasm=None,
                 precision=None):
        self.circuit = circuit
        self.n_qubits = n_qubits
        self.preprocessing_applied = preprocessing_applied if preprocessing_applied is not None else []
        self.transpiled_qasm = transpiled_qasm
        self.precision = precision


def _timed_job(*, simulator, logger, payload, max_qubits, compile_fn, execute_fn,
               serialize_fn, monitor_interval, build_result, pre_execute_fn=None,
               postprocess_fn=None):
    """The shared measurement instrument for one runner call::

      check_qubits_limit -> t0 -> compile_fn -> t1                       (compilation_time)
      serialize_fn                                                       (outside both windows)
      MemoryMonitor + gc.collect() -> pre_execute_fn -> t2 -> execute_fn -> t3
                                                                         (simulation_time)
      postprocess_fn                                                     (outside both windows)

    Any failure becomes a ``runner_error``.
    """
    try:
        check_qubits_limit(payload["circuit_data"], max_qubits)
        declared_qubits = get_num_qubits_from_qasm(payload["circuit_data"])

        t0 = time.perf_counter()
        compiled = compile_fn(payload)
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        transpiled_qasm = compiled.transpiled_qasm
        if transpiled_qasm is None and serialize_fn is not None:
            transpiled_qasm = serialize_fn(compiled)

        with MemoryMonitor(interval=monitor_interval) as monitor:
            gc.collect()

            if pre_execute_fn is not None:
                pre_execute_fn(compiled, payload)

            c2 = time.process_time()
            t2 = time.perf_counter()
            executed = execute_fn(compiled, payload)
            t3 = time.perf_counter()
            c3 = time.process_time()
            simulation_time = t3 - t2

        if postprocess_fn is not None:
            executed = postprocess_fn(executed, compiled, payload)

        if logger is not None:
            logger.info(
                f"{simulator} simulation successful "
                f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
            )
        return build_result(
            executed=executed, compiled=compiled, monitor=monitor,
            compilation_time=compilation_time, simulation_time=simulation_time,
            transpiled_qasm=transpiled_qasm, simulation_cpu_time=c3 - c2,
            declared_qubits=declared_qubits,
        )
    except Exception as exc:
        if logger is not None:
            logger.error(f"Error during {simulator} simulation: {exc}", exc_info=True)
        return runner_error(simulator, exc)


def _resolve_theoretical_mb(theoretical_mb, declared_qubits):
    """Dense statevector size for the declared qubit count unless the runner overrode it."""
    if theoretical_mb is _UNSET:
        return theoretical_statevector_mb(declared_qubits)
    return theoretical_mb


def run_statevector_job(*, simulator, payload, compile_fn, execute_fn, qubit_ordering,
                        logger=None, serialize_fn=None, pre_execute_fn=None,
                        postprocess_fn=None, max_qubits=None,
                        monitor_interval=0.01, theoretical_mb=_UNSET, precision=None):
    """Run one statevector call through ``_timed_job``.

    ``execute_fn(compiled, payload)`` returns the raw statevector. ``precision`` names the
    backend's amplitude dtype (e.g. ``"complex128"``); None if unspecified.
    """
    def build_result(*, executed, compiled, monitor, compilation_time, simulation_time,
                     transpiled_qasm, simulation_cpu_time, declared_qubits):
        return statevector_result(
            simulator=simulator, statevector=executed, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering=qubit_ordering,
            n_qubits=compiled.n_qubits, preprocessing_applied=compiled.preprocessing_applied,
            transpiled_qasm=transpiled_qasm,
            theoretical_mb=_resolve_theoretical_mb(theoretical_mb, declared_qubits),
            simulation_cpu_time=simulation_cpu_time,
            precision=getattr(compiled, "precision", None) or precision)

    return _timed_job(
        simulator=simulator, logger=logger, payload=payload,
        max_qubits=MAX_QUBITS_STATEVECTOR if max_qubits is None else max_qubits,
        compile_fn=compile_fn, execute_fn=execute_fn, serialize_fn=serialize_fn,
        pre_execute_fn=pre_execute_fn, postprocess_fn=postprocess_fn,
        monitor_interval=monitor_interval, build_result=build_result)


def run_measured_job(*, simulator, payload, compile_fn, execute_fn, qubit_ordering,
                     logger=None, serialize_fn=None, pre_execute_fn=None,
                     postprocess_fn=None, max_qubits=None,
                     monitor_interval=0.01, theoretical_mb=_UNSET, precision=None):
    """Run one measured call through ``_timed_job``.

    ``execute_fn(compiled, payload)`` returns ``(counts, sampling_method)``, where
    sampling_method is ``'native'`` (backend sampled shots) or ``'statevector'`` (drawn
    from a computed statevector). ``precision`` as in ``run_statevector_job``.
    """
    def build_result(*, executed, compiled, monitor, compilation_time, simulation_time,
                     transpiled_qasm, simulation_cpu_time, declared_qubits):
        counts, sampling_method = executed
        return counts_result(
            simulator=simulator, counts=counts, sampling_method=sampling_method,
            compilation_time=compilation_time, simulation_time=simulation_time,
            monitor=monitor, qubit_ordering=qubit_ordering, n_qubits=compiled.n_qubits,
            preprocessing_applied=compiled.preprocessing_applied,
            transpiled_qasm=transpiled_qasm,
            theoretical_mb=_resolve_theoretical_mb(theoretical_mb, declared_qubits),
            simulation_cpu_time=simulation_cpu_time,
            precision=getattr(compiled, "precision", None) or precision)

    return _timed_job(
        simulator=simulator, logger=logger, payload=payload,
        max_qubits=MAX_QUBITS_MEASURED if max_qubits is None else max_qubits,
        compile_fn=compile_fn, execute_fn=execute_fn, serialize_fn=serialize_fn,
        pre_execute_fn=pre_execute_fn, postprocess_fn=postprocess_fn,
        monitor_interval=monitor_interval, build_result=build_result)


RUNNER_MAX_CONCURRENT = max(1, int(os.getenv("RUNNER_MAX_CONCURRENT", "1")))


class ExecutionSlots:
    """Admits at most ``limit`` isolated runs of one runner process at a time, first come
    first served.

    ``run`` waits for a slot (at most ``payload['max_queue_wait_seconds']`` when set), then
    calls ``run_isolated``, whose hard timeout therefore starts after the wait. Every result
    carries ``queue_wait_sec``. A run whose wait budget expires is not started and returns
    a ``timed_out`` / ``never_started`` error.
    """

    def __init__(self, limit=None):
        self.limit = RUNNER_MAX_CONCURRENT if limit is None else max(1, int(limit))
        self._semaphore = _asyncio.Semaphore(self.limit)
        self.waiting = 0
        self.running = 0

    async def run(self, func, payload):
        ahead = self.waiting + self.running
        budget = payload.get("max_queue_wait_seconds")
        t0 = time.monotonic()
        self.waiting += 1
        try:
            if budget is None:
                await self._semaphore.acquire()
            else:
                await _asyncio.wait_for(self._semaphore.acquire(), timeout=float(budget))
        except _asyncio.TimeoutError:
            waited = time.monotonic() - t0
            result = _isolated_error(
                f"TIMEOUT while queued behind {ahead} other run(s) on this runner: waited "
                f"{waited:.0f} s (queue budget {float(budget):.0f} s); the run never started.",
                timed_out=True)
            result["never_started"] = True
            result["queue_wait_sec"] = waited
            return result
        finally:
            self.waiting -= 1

        waited = time.monotonic() - t0
        self.running += 1
        try:
            result = await run_isolated(func, payload)
        finally:
            self.running -= 1
            self._semaphore.release()
        if isinstance(result, dict):
            result["queue_wait_sec"] = waited
        return result


def register_runner_endpoints(app, process_run, process_run_measured, max_concurrent=None):
    """Register ``/run`` and ``/run_measured`` on a runner app.

    Both endpoints share one ``ExecutionSlots`` (``RUNNER_MAX_CONCURRENT``, default 1), so
    concurrent requests to this runner queue instead of sharing its CPU and memory.
    """
    from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload

    slots = ExecutionSlots(max_concurrent)

    @app.post("/run")
    async def run_circuit(payload: CircuitPayload):
        return await slots.run(process_run, payload.model_dump())

    @app.post("/run_measured")
    async def run_measured_circuit(payload: MeasuredCircuitPayload):
        return await slots.run(process_run_measured, payload.model_dump())


def run_cli_main(app, process_run, process_run_measured, cli_name):
    """Runner entrypoint: with no args serve ``app``; with ``--endpoint`` run one job from
    ``--payload`` or ``--s3-job-id`` (the Kubernetes path)."""
    if len(sys.argv) <= 1:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
        return

    import argparse
    import json
    parser = argparse.ArgumentParser(description=f"{cli_name} runner CLI")
    parser.add_argument("--endpoint", choices=["run", "run_measured"], required=True,
                        help="Which endpoint to invoke")
    parser.add_argument("--payload", default=None, help="JSON payload string")
    parser.add_argument("--s3-job-id", default=None,
                        help="S3 job ID: download payload from jobs/pending/<id>.json, "
                             "upload result to jobs/completed/<id>.json")
    args = parser.parse_args()

    def _process(payload_dict):
        func = process_run if args.endpoint == "run" else process_run_measured
        result = run_with_uniform_measurement(func, payload_dict)
        if isinstance(result, dict):
            result["queue_wait_sec"] = 0.0
        return result

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
