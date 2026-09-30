"""Shared runner utilities: QASM helpers, the timing/memory instrument, result contract,
isolated execution and the HTTP/CLI scaffolding."""

import asyncio as _asyncio
import base64
import functools
import gc
import hashlib
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
from pathlib import Path

import numpy as np

from qrosetta_commons.cpu import WindowProbe, cpu_environment
from qrosetta_commons.memory import MemoryMonitor, lifetime_peak_rss

MAX_QUBITS_STATEVECTOR = int(os.getenv("MAX_QUBITS_STATEVECTOR", "18"))
MAX_QUBITS_MEASURED = int(os.getenv("MAX_QUBITS_MEASURED", "24"))

THREAD_ENV_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                   "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS")

UNMEASURED_METRICS = ("execution_time_sec", "compilation_time_sec", "simulation_time_sec",
                      "simulation_cpu_time_sec", "memory_usage_mb", "process_peak_mb",
                      "process_peak_rss_mb", "cpu_time_sec", "compilation_throttled_sec",
                      "simulation_throttled_sec", "simulation_cgroup_cpu_time_sec")


def unmeasured_metrics() -> dict:
    """The per-run metrics of a failed run, each None because it was not measured."""
    return {name: None for name in UNMEASURED_METRICS}

METRIC_SCOPE = {
    "compilation_time_sec": "wall clock, t0..t1; median over the timed runs "
                            "(compilation_time_samples)",
    "simulation_time_sec": "wall clock, t2..t3; median over the timed runs "
                           "(simulation_time_samples)",
    "simulation_cpu_time_sec": "process CPU time (all threads), t2..t3; median over the timed "
                               "runs (simulation_cpu_time_samples)",
    "execution_time_sec": "compilation_time_sec + simulation_time_sec",
    "simulation_throttled_sec": "time the runner's cgroup was held by its CPU quota "
                                "(cpu.stat throttled_usec) between reads just before t2 and "
                                "just after t3; part of simulation_time_sec, not simulation; "
                                "median over the timed runs (simulation_throttled_samples); "
                                "None when the cgroup file is unreadable",
    "compilation_throttled_sec": "as simulation_throttled_sec, for t0..t1",
    "simulation_cgroup_cpu_time_sec": "CPU time of every process in the runner's cgroup "
                                      "(cpu.stat usage_usec) between reads just before t2 "
                                      "and just after t3; above simulation_cpu_time_sec when "
                                      "work ran outside the simulating process; median over "
                                      "the timed runs; None when the cgroup file is "
                                      "unreadable",
    "simulation_cpus": "logical CPUs the process was on at t2 and at t3, over every timed "
                       "run; cpu_environment.cpu_max_mhz gives each one's maximum frequency",
    "simulation_involuntary_switches_samples": "involuntary context switches of the process "
                                               "between t2 and t3, per timed run",
    "memory_usage_mb": "peak RSS minus RSS at monitor entry, pre_execute + t2..t3 of the "
                       "first timed run",
    "process_peak_mb": "peak RSS, pre_execute + t2..t3 of the first timed run",
    "cpu_time_sec": "process CPU time over the whole runner process: interpreter start, "
                    "imports, warm-up and all timed runs",
    "process_peak_rss_mb": "peak RSS over the whole runner process: interpreter start, "
                           "imports, warm-up and all timed runs",
    "cpu_environment": "host CPU model (/proc/cpuinfo), the runner cgroup's CPU quota in "
                       "cores (None = no quota), the process's CPU affinity and the maximum "
                       "frequency of each CPU in simulation_cpus",
    "queue_wait_sec": "wall clock the request waited for this runner's execution slot "
                      "before its process was spawned; 0 on the Kubernetes path",
    "theoretical_statevector_mb": "2^N x bytes per amplitude / 1024^2, N = qubits declared "
                                  "by the dispatched circuit; 8 bytes for complex64, 16 for "
                                  "complex128, and 16 when the backend reports no precision "
                                  "(see theoretical_statevector_basis)",
}

METRIC_SCOPE_ON_ERROR = ("every per-run and process metric is null: a failed run is not "
                         "measured")


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

    Call from ``execute_fn``. Build the counts in ``postprocess_fn`` with
    ``qrosetta_commons.counts.MeasurementLayout.counts_from_qubit_samples``, which keys them
    over the circuit's classical bits. ``seed=None`` uses a fresh non-deterministic generator.
    """
    probabilities = np.abs(statevector)**2
    rng = np.random.default_rng(seed)
    return rng.choice(len(statevector), size=n_shots, p=probabilities)


def _counts_from_samples(samples, n_qubits):
    """Build a ``{bitstring: count}`` histogram over qubit indices (width ``n_qubits``) from
    sampled indices. The keys are basis-state indices, not the classical-bit keys of the
    counts contract; runners use ``MeasurementLayout.counts_from_qubit_samples`` instead."""
    return {
        format(k, f'0{n_qubits}b'): v
        for k, v in Counter(samples).items()
    }


_BYTES_PER_AMPLITUDE = {"complex64": 8, "complex128": 16}


def bytes_per_amplitude(precision=None) -> int:
    """8 for complex64, 16 for complex128 and for an unknown or unreported precision."""
    return _BYTES_PER_AMPLITUDE.get(str(precision).lower() if precision else "", 16)


def theoretical_statevector_mb(n_qubits: int, precision=None) -> float:
    """Size of a dense statevector for ``n_qubits``: ``2^N * bytes_per_amplitude`` in MiB."""
    return (2 ** int(n_qubits or 0) * bytes_per_amplitude(precision)) / (1024 ** 2)


def theoretical_statevector_basis(n_qubits: int, precision=None) -> str:
    """The inputs of ``theoretical_statevector_mb`` in words, e.g. '2^5 x 16 B (complex128)'."""
    size = bytes_per_amplitude(precision)
    known = str(precision).lower() if precision else ""
    if known in _BYTES_PER_AMPLITUDE:
        return f"2^{int(n_qubits or 0)} x {size} B ({known})"
    return (f"2^{int(n_qubits or 0)} x {size} B (precision not reported; complex128 "
            f"assumed)")


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


_DECLARED_SDK_PACKAGES: list = []

NOT_INSTALLED = "not installed"


def declare_sdk_packages(*names: str) -> tuple:
    """Register the distributions whose versions every result reports as ``sdk_versions``.

    Call once at module level in the runner's ``main.py`` with the pip distribution names
    from its ``requirements.txt`` (e.g. ``"qiskit", "qiskit-aer"``). Repeated names are kept
    once. Returns the registered names.
    """
    for name in names:
        if name not in _DECLARED_SDK_PACKAGES:
            _DECLARED_SDK_PACKAGES.append(str(name))
    return tuple(_DECLARED_SDK_PACKAGES)


def declared_sdk_packages() -> tuple:
    return tuple(_DECLARED_SDK_PACKAGES)


def get_sdk_versions() -> dict:
    """``{name: version}`` for every declared package, read from the installed distribution
    metadata; ``"not installed"`` for a declared name with no installed distribution."""
    versions = {}
    for name in _DECLARED_SDK_PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = NOT_INSTALLED
    return versions


RUNNER_CODE_SHA256_BASIS = (
    "sha256 over the bytes of the runner's main.py followed by the bytes of every .py file "
    "of the installed qrosetta_commons package, in order of relative path")

_code_sha_cache: dict = {}


def _commons_sources() -> list:
    root = Path(__file__).resolve().parent
    return sorted(root.rglob("*.py"), key=lambda p: p.relative_to(root).as_posix())


def runner_code_sha256(main_path) -> str:
    """``RUNNER_CODE_SHA256_BASIS`` for ``main_path``; ``"unavailable: ..."`` when a file
    cannot be read."""
    key = str(main_path)
    if key not in _code_sha_cache:
        try:
            digest = hashlib.sha256(Path(main_path).read_bytes())
            for path in _commons_sources():
                digest.update(path.read_bytes())
            _code_sha_cache[key] = digest.hexdigest()
        except OSError as exc:
            _code_sha_cache[key] = f"unavailable: {type(exc).__name__}: {exc}"
    return _code_sha_cache[key]


def _module_code_sha256(func) -> str:
    module = sys.modules.get(getattr(func, "__module__", ""), None)
    path = getattr(module, "__file__", None)
    return runner_code_sha256(path) if path else "unavailable: processor module has no file"


DEFAULT_DEVICE = "CPU"


def with_sdk_versions(func):
    """Decorator for ``process_run`` / ``process_run_measured``.

    Adds ``sdk_versions`` (the ``declare_sdk_packages`` registry), ``runner_code_sha256``
    (computed when the runner module is imported) and ``device`` to every result dict.
    ``device`` keeps a value the runner set, else is ``"CPU"``, and is None on an error
    result the runner did not label.
    """
    code_sha = _module_code_sha256(func)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, dict):
            result.setdefault("sdk_versions", get_sdk_versions())
            result.setdefault("runner_code_sha256", code_sha)
            if result.get("device") is None:
                result["device"] = None if result.get("error") else DEFAULT_DEVICE
        return result
    wrapper.runner_code_sha256 = code_sha
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


MAX_TIMING_REPEATS = 10

TIMING_STATISTIC = "median"

_TIMED_SERIES = ("compilation_time", "simulation_time", "simulation_cpu_time",
                 "simulation_cgroup_cpu_time", "compilation_throttled", "simulation_throttled")


def timing_repeats_of(payload) -> int:
    """``payload['timing_repeats']`` bounded to [1, MAX_TIMING_REPEATS]; 1 when absent."""
    try:
        n = int(payload.get("timing_repeats") or 1)
    except (TypeError, ValueError):
        n = 1
    return max(1, min(n, MAX_TIMING_REPEATS))


def _summarise_timings(result: dict, timed_results: list) -> None:
    """Per-repeat samples and their mean/median/stdev; the reported compilation and
    simulation times become the medians and execution time their sum."""
    for series in _TIMED_SERIES:
        samples = [r.get(f"{series}_sec") for r in timed_results]
        if not all(isinstance(v, (int, float)) for v in samples):
            continue
        result[f"{series}_samples"] = samples
        result[f"{series}_sec_mean"] = _statistics.mean(samples)
        result[f"{series}_sec_median"] = _statistics.median(samples)
        result[f"{series}_sec_stdev"] = _statistics.stdev(samples) if len(samples) > 1 else None
        result[f"{series}_sec"] = result[f"{series}_sec_median"]
    comp, sim = result.get("compilation_time_sec"), result.get("simulation_time_sec")
    if isinstance(comp, (int, float)) and isinstance(sim, (int, float)):
        result["execution_time_sec"] = comp + sim
    result["simulation_involuntary_switches_samples"] = [
        r.get("simulation_involuntary_switches") for r in timed_results]
    result["simulation_cpus"] = sorted({c for r in timed_results
                                        for c in (r.get("simulation_cpus") or [])})
    result["timing_repeats"] = len(timed_results)
    result["timing_statistic"] = TIMING_STATISTIC


def run_with_uniform_measurement(func, payload):
    """Run a runner processor once as a discarded warm-up, then ``timing_repeats`` timed
    times (each a full compile + execute through the shared instrument, with the same
    payload and seed), and attach process-level diagnostics.

    The result, its output (statevector or counts) and its memory fields are those of the
    first timed run. ``compilation_time_sec``, ``simulation_time_sec`` and
    ``simulation_cpu_time_sec`` are the medians over the timed runs, with the per-run values
    in ``*_samples`` and ``*_sec_mean`` / ``*_sec_median`` / ``*_sec_stdev`` (stdev None
    for one run); ``execution_time_sec`` is compilation + simulation. A timed run that fails
    makes the result that failure (``failed_timing_repeat`` names which run).

    Used by both the isolated child (``run_isolated``) and the Kubernetes CLI path; the
    hard timeout covers the warm-up and every timed run. ``cpu_time_sec`` and
    ``process_peak_rss_mb`` cover the whole runner process; see ``METRIC_SCOPE``, which is
    copied into the result as ``metric_scope``.
    """
    func(payload)

    repeats = timing_repeats_of(payload)
    timed_results = []
    failed = None
    for i in range(repeats):
        timed = func(payload)
        timed_results.append(timed)
        if not isinstance(timed, dict) or timed.get("error"):
            failed = i
            break
    result = timed_results[0] if failed is None else timed_results[failed]

    if isinstance(result, dict) and result.get("error"):
        result.update(unmeasured_metrics())
        result["process_peak_rss_method"] = None
        result["metric_scope"] = {"on_error": METRIC_SCOPE_ON_ERROR}
        result["timing_repeats"] = repeats
        if failed:
            result["failed_timing_repeat"] = failed + 1
        return result

    if isinstance(result, dict):
        _summarise_timings(result, timed_results)

        usage = _resource.getrusage(_resource.RUSAGE_SELF)
        peak_mb, peak_method = lifetime_peak_rss()
        result["process_peak_rss_mb"] = peak_mb
        result["process_peak_rss_method"] = peak_method
        result["cpu_time_sec"] = usage.ru_utime + usage.ru_stime
        result["cpu_environment"] = cpu_environment(result.get("simulation_cpus") or [])
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
                f"every timed run) exceeded {timeout_s} s and was terminated.", timed_out=True)
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
                 simulation_cpu_time=None, precision=None, device=None):
    """Fields common to statevector and counts results. The theoretical statevector size is
    computed from ``n_qubits`` and ``precision`` for every backend; ``theoretical_mb`` is
    ignored. ``device`` None is filled in by ``with_sdk_versions``."""
    theoretical_mb = theoretical_statevector_mb(n_qubits or 0, precision)
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
        "theoretical_statevector_basis": theoretical_statevector_basis(n_qubits or 0, precision),
        "preprocessing_applied": preprocessing_applied,
        "transpiled_qasm": transpiled_qasm,
        "precision": precision,
        "device": device,
        "thread_env": get_thread_env(),
    }


def statevector_result(*, simulator, statevector, compilation_time, simulation_time, monitor,
                       qubit_ordering, preprocessing_applied, transpiled_qasm,
                       n_qubits=None, theoretical_mb=_UNSET, simulation_cpu_time=None,
                       precision=None, device=None):
    """Assemble a statevector result; ``statevector`` is encoded to Base64 here.

    Raises ValueError when the vector does not hold ``2**n_qubits`` amplitudes.
    """
    amplitudes = np.asarray(statevector).ravel()
    if n_qubits is not None and amplitudes.size != 2 ** int(n_qubits):
        raise ValueError(
            f"backend returned {amplitudes.size} amplitudes for {int(n_qubits)} qubits "
            f"(expected {2 ** int(n_qubits)})")
    result = _base_result(
        simulator=simulator, compilation_time=compilation_time, simulation_time=simulation_time,
        monitor=monitor, qubit_ordering=qubit_ordering, n_qubits=n_qubits,
        theoretical_mb=theoretical_mb, preprocessing_applied=preprocessing_applied,
        transpiled_qasm=transpiled_qasm, simulation_cpu_time=simulation_cpu_time,
        precision=precision, device=device)
    result["statevector"] = encode_statevector(amplitudes)
    return result


def counts_result(*, simulator, counts, sampling_method, compilation_time, simulation_time,
                  monitor, qubit_ordering, preprocessing_applied, transpiled_qasm,
                  n_qubits=None, theoretical_mb=_UNSET, simulation_cpu_time=None,
                  precision=None, device=None):
    """Assemble a counts result; ``sampling_method=None`` omits that key."""
    result = _base_result(
        simulator=simulator, compilation_time=compilation_time, simulation_time=simulation_time,
        monitor=monitor, qubit_ordering=qubit_ordering, n_qubits=n_qubits,
        theoretical_mb=theoretical_mb, preprocessing_applied=preprocessing_applied,
        transpiled_qasm=transpiled_qasm, simulation_cpu_time=simulation_cpu_time,
        precision=precision, device=device)
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


_MAXWIDTH_HINT = (
    " The compiled circuit has a classical register wider than the 32 bits pytket's QASM "
    "writer accepts by default (a backend pass such as FlattenRegisters merges every creg "
    "into one); the runner's serialize_fn must pass maxwidth to circuit_to_qasm_str.")


def _serialize(serialize_fn, compiled):
    """``serialize_fn(compiled)``; a failure is re-raised naming the step."""
    try:
        return serialize_fn(compiled)
    except Exception as exc:
        hint = _MAXWIDTH_HINT if "maxwidth" in str(exc) else ""
        raise RuntimeError(
            f"serialize_fn (recording transpiled_qasm after compilation) failed: "
            f"{type(exc).__name__}: {exc}{hint}") from exc


def _timed_job(*, simulator, logger, payload, max_qubits, compile_fn, execute_fn,
               serialize_fn, monitor_interval, build_result, pre_execute_fn=None,
               postprocess_fn=None):
    """The shared measurement instrument for one runner call::

      check_qubits_limit -> t0 -> compile_fn -> t1                       (compilation_time)
      serialize_fn                                                       (outside both windows)
      MemoryMonitor + gc.collect() -> pre_execute_fn -> t2 -> execute_fn -> t3
                                                                         (simulation_time)
      postprocess_fn                                                     (outside both windows)

    A ``WindowProbe`` read just outside each window records the cgroup CPU-quota throttling
    during it and, for the simulation window, involuntary context switches and the CPUs the
    process was on at t2 and t3. Any failure becomes a ``runner_error``.
    """
    try:
        check_qubits_limit(payload["circuit_data"], max_qubits)
        declared_qubits = get_num_qubits_from_qasm(payload["circuit_data"])

        compile_probe = WindowProbe().start()
        t0 = time.perf_counter()
        compiled = compile_fn(payload)
        t1 = time.perf_counter()
        compile_probe.stop()
        compilation_time = t1 - t0

        transpiled_qasm = compiled.transpiled_qasm
        if transpiled_qasm is None and serialize_fn is not None:
            transpiled_qasm = _serialize(serialize_fn, compiled)

        with MemoryMonitor(interval=monitor_interval) as monitor:
            gc.collect()

            if pre_execute_fn is not None:
                pre_execute_fn(compiled, payload)

            sim_probe = WindowProbe().start()
            c2 = time.process_time()
            t2 = time.perf_counter()
            executed = execute_fn(compiled, payload)
            t3 = time.perf_counter()
            c3 = time.process_time()
            sim_probe.stop()
            simulation_time = t3 - t2

        if postprocess_fn is not None:
            executed = postprocess_fn(executed, compiled, payload)

        if logger is not None:
            logger.info(
                f"{simulator} simulation successful "
                f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
            )
        result = build_result(
            executed=executed, compiled=compiled, monitor=monitor,
            compilation_time=compilation_time, simulation_time=simulation_time,
            transpiled_qasm=transpiled_qasm, simulation_cpu_time=c3 - c2,
            declared_qubits=declared_qubits,
        )
        result.update({
            "compilation_throttled_sec": compile_probe.throttled_sec,
            "simulation_throttled_sec": sim_probe.throttled_sec,
            "simulation_cgroup_cpu_time_sec": sim_probe.cgroup_cpu_sec,
            "simulation_involuntary_switches": sim_probe.involuntary_switches,
            "simulation_cpus": sim_probe.cpus,
        })
        return result
    except Exception as exc:
        if logger is not None:
            logger.error(f"Error during {simulator} simulation: {exc}", exc_info=True)
        return runner_error(simulator, exc)


def run_statevector_job(*, simulator, payload, compile_fn, execute_fn, qubit_ordering,
                        logger=None, serialize_fn=None, pre_execute_fn=None,
                        postprocess_fn=None, max_qubits=None,
                        monitor_interval=0.01, theoretical_mb=_UNSET, precision=None,
                        device=None):
    """Run one statevector call through ``_timed_job``.

    ``execute_fn(compiled, payload)`` returns the raw backend output; the statevector is
    ``postprocess_fn(raw, compiled, payload)`` when a ``postprocess_fn`` is given, else the
    raw output. ``precision`` names the backend's amplitude dtype (e.g. ``"complex128"``);
    None if unspecified. ``device`` (e.g. ``"GPU"``) defaults to ``"CPU"`` via
    ``with_sdk_versions``.
    """
    def build_result(*, executed, compiled, monitor, compilation_time, simulation_time,
                     transpiled_qasm, simulation_cpu_time, declared_qubits):
        return statevector_result(
            simulator=simulator, statevector=executed, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering=qubit_ordering,
            n_qubits=declared_qubits, preprocessing_applied=compiled.preprocessing_applied,
            transpiled_qasm=transpiled_qasm,
            simulation_cpu_time=simulation_cpu_time,
            precision=getattr(compiled, "precision", None) or precision, device=device)

    return _timed_job(
        simulator=simulator, logger=logger, payload=payload,
        max_qubits=MAX_QUBITS_STATEVECTOR if max_qubits is None else max_qubits,
        compile_fn=compile_fn, execute_fn=execute_fn, serialize_fn=serialize_fn,
        pre_execute_fn=pre_execute_fn, postprocess_fn=postprocess_fn,
        monitor_interval=monitor_interval, build_result=build_result)


def run_measured_job(*, simulator, payload, compile_fn, execute_fn, qubit_ordering,
                     logger=None, serialize_fn=None, pre_execute_fn=None,
                     postprocess_fn=None, max_qubits=None,
                     monitor_interval=0.01, theoretical_mb=_UNSET, precision=None,
                     device=None):
    """Run one measured call through ``_timed_job``.

    ``postprocess_fn(raw, compiled, payload)`` returns ``(counts, sampling_method)``; without
    a ``postprocess_fn``, ``execute_fn(compiled, payload)`` returns it. ``sampling_method``
    is ``'native'`` (the backend sampled the shots) or ``'sv_sample'`` (shots drawn from a
    computed statevector). ``precision`` and ``device`` as in ``run_statevector_job``.
    """
    def build_result(*, executed, compiled, monitor, compilation_time, simulation_time,
                     transpiled_qasm, simulation_cpu_time, declared_qubits):
        counts, sampling_method = executed
        return counts_result(
            simulator=simulator, counts=counts, sampling_method=sampling_method,
            compilation_time=compilation_time, simulation_time=simulation_time,
            monitor=monitor, qubit_ordering=qubit_ordering, n_qubits=declared_qubits,
            preprocessing_applied=compiled.preprocessing_applied,
            transpiled_qasm=transpiled_qasm,
            simulation_cpu_time=simulation_cpu_time,
            precision=getattr(compiled, "precision", None) or precision, device=device)

    return _timed_job(
        simulator=simulator, logger=logger, payload=payload,
        max_qubits=MAX_QUBITS_MEASURED if max_qubits is None else max_qubits,
        compile_fn=compile_fn, execute_fn=execute_fn, serialize_fn=serialize_fn,
        pre_execute_fn=pre_execute_fn, postprocess_fn=postprocess_fn,
        monitor_interval=monitor_interval, build_result=build_result)


RUNNER_MAX_CONCURRENT = max(1, int(os.getenv("RUNNER_MAX_CONCURRENT", "1")))


def _stamp_code_sha(result: dict, func) -> None:
    code_sha = getattr(func, "runner_code_sha256", None)
    if code_sha:
        result.setdefault("runner_code_sha256", code_sha)


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
            _stamp_code_sha(result, func)
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
            _stamp_code_sha(result, func)
        return result


def register_runner_endpoints(app, process_run, process_run_measured, max_concurrent=None,
                              capabilities=None):
    """Register ``/run`` and ``/run_measured`` on a runner app.

    Both endpoints share one ``ExecutionSlots`` (``RUNNER_MAX_CONCURRENT``, default 1), so
    concurrent requests to this runner queue instead of sharing its CPU and memory. With
    ``capabilities`` (a callable returning ``{"available": bool, "reason": str | None,
    "device": str | None}``), ``GET /capabilities`` returns its result; the API treats a
    runner without that endpoint as available.
    """
    from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload

    slots = ExecutionSlots(max_concurrent)

    if capabilities is not None:
        @app.get("/capabilities")
        async def runner_capabilities():
            try:
                info = dict(capabilities())
            except Exception as exc:
                return {"available": False, "reason": f"{type(exc).__name__}: {exc}", "device": None}
            return {"available": bool(info.get("available", False)),
                    "reason": info.get("reason"), "device": info.get("device")}

    @app.post("/run")
    async def run_circuit(payload: CircuitPayload):
        return await slots.run(process_run, payload.model_dump())

    @app.post("/run_measured")
    async def run_measured_circuit(payload: MeasuredCircuitPayload):
        return await slots.run(process_run_measured, payload.model_dump())


def _self_test_probes(process_run, process_run_measured, sv_order, counts_order):
    """``(name, thunk)`` for every probe; each thunk returns a list of failure messages."""
    from qrosetta_commons import contract_probes as cp

    def sv(qasm, pp=True):
        return process_run({"circuit_data": qasm, "optimization_level": 0,
                            "runner_config": {}, "apply_preprocessing": pp})

    def measured(qasm, n_shots, seed=cp.SEED_A):
        return process_run_measured({"circuit_data": qasm, "n_shots": n_shots, "seed": seed,
                                     "optimization_level": 0, "runner_config": {},
                                     "apply_preprocessing": True})

    probes = [
        ("statevector_one_hot",
         lambda: cp.check_one_hot_statevector(sv(cp.ONE_HOT_QASM), sv_order)),
        ("counts_one_hot",
         lambda: cp.check_one_hot_counts(measured(cp.ONE_HOT_MEASURED_QASM, cp.N_SHOTS),
                                         cp.N_SHOTS, counts_order)),
    ]
    for name, (body, pp, _n, _expected) in cp.STATEVECTOR_SHAPE_PROBES.items():
        probes.append((f"statevector_{name}", lambda name=name, body=body, pp=pp:
                       cp.check_statevector_shape(name, sv(cp.QASM_HEADER + body, pp), sv_order)))
    for name, (body, _expected) in cp.CLASSICAL_BIT_PROBES.items():
        probes.append((f"counts_{name}", lambda name=name, body=body: cp.check_classical_bits(
            name, measured(cp.QASM_HEADER + body, cp.CLASSICAL_N_SHOTS), cp.CLASSICAL_N_SHOTS,
            counts_order)))
    probes.append(("counts_measured_subset", lambda: cp.check_measured_subset(
        measured(cp.QASM_HEADER + cp.SUBSET_QASM, cp.CLASSICAL_N_SHOTS))))
    probes.append(("counts_mid_circuit", lambda: cp.check_mid_circuit(
        measured(cp.QASM_HEADER + cp.MID_CIRCUIT_QASM, cp.CLASSICAL_N_SHOTS))))
    probes.append(("seed_reproducibility", lambda: cp.check_seed_reproducibility(
        measured(cp.SEED_QASM, cp.SEED_N_SHOTS, cp.SEED_A),
        measured(cp.SEED_QASM, cp.SEED_N_SHOTS, cp.SEED_A),
        measured(cp.SEED_QASM, cp.SEED_N_SHOTS, cp.SEED_B))))
    return probes


def run_self_test(process_run, process_run_measured, qubit_ordering_statevector=None,
                  qubit_ordering_counts=None, out=None) -> int:
    """Run the contract probes of ``qrosetta_commons.contract_probes`` in-process.

    Each probe calls ``process_run`` / ``process_run_measured`` directly with the probe's
    circuit text and ``apply_preprocessing`` (the API's own dispatch rewrites are not
    applied), and prints ``PASS <probe>`` or ``FAIL <probe>: <reason>``. With a declared
    ordering, a result reporting a different ``qubit_ordering`` fails. Returns the number
    of failed probes.
    """
    out = out or sys.stdout
    failed = 0
    probes = _self_test_probes(process_run, process_run_measured,
                               qubit_ordering_statevector, qubit_ordering_counts)
    for name, probe in probes:
        try:
            failures = probe()
        except Exception as exc:
            failures = [f"{type(exc).__name__}: {exc}"]
        if failures:
            failed += 1
            print(f"FAIL {name}: {'; '.join(failures)}", file=out)
        else:
            print(f"PASS {name}", file=out)
    print(f"{failed} of {len(probes)} probe(s) failed", file=out)
    return failed


def run_cli_main(app, process_run, process_run_measured, cli_name,
                 qubit_ordering_statevector=None, qubit_ordering_counts=None):
    """Runner entrypoint: with no args serve ``app``; with ``--endpoint`` run one job from
    ``--payload`` or ``--s3-job-id`` (the Kubernetes path); with ``--self-test`` run
    ``run_self_test`` and exit non-zero when a probe fails."""
    if len(sys.argv) <= 1:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
        return

    import argparse
    import json
    parser = argparse.ArgumentParser(description=f"{cli_name} runner CLI")
    parser.add_argument("--endpoint", choices=["run", "run_measured"], default=None,
                        help="Which endpoint to invoke")
    parser.add_argument("--self-test", action="store_true",
                        help="Run the contract probes in-process and exit non-zero on failure")
    parser.add_argument("--payload", default=None, help="JSON payload string")
    parser.add_argument("--s3-job-id", default=None,
                        help="S3 job ID: download payload from jobs/pending/<id>.json, "
                             "upload result to jobs/completed/<id>.json")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(1 if run_self_test(process_run, process_run_measured,
                                    qubit_ordering_statevector, qubit_ordering_counts) else 0)
    if args.endpoint is None:
        parser.error("--endpoint is required unless --self-test is given")

    def _process(payload_dict):
        func = process_run if args.endpoint == "run" else process_run_measured
        result = run_with_uniform_measurement(func, payload_dict)
        if isinstance(result, dict):
            result["queue_wait_sec"] = 0.0
            _stamp_code_sha(result, func)
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
