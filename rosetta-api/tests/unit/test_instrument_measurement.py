"""Tests for the shared measurement instrument: memory, CPU time, thread env, precision,
theoretical size and per-runner seed derivation."""
import asyncio
import resource
import time

import numpy as np
import pytest

from qrosetta_commons import derive_runner_seed, memory
from qrosetta_commons.helpers import (
    CompileResult, MemoryMonitor, THREAD_ENV_VARS, run_measured_job, run_statevector_job,
    run_isolated, theoretical_statevector_mb)
from tests.unit import _instrument_fixture as fx

MIB = 1024 * 1024
vmhwm_only = pytest.mark.skipif(not memory._reset_hwm(), reason="needs /proc/self/clear_refs")


def _sv_job(execute_fn, qasm=fx.QASM_2Q, compile_fn=fx._compile, **kw):
    return run_statevector_job(
        simulator="t", payload={"circuit_data": qasm}, compile_fn=compile_fn,
        execute_fn=execute_fn, qubit_ordering="msb", **kw)


@vmhwm_only
def test_short_allocation_is_captured_by_vmhwm():
    """In-process, the allocator may reuse already-resident heap pages, so the bound is
    loose here; the isolated-child test checks the deployment path tightly."""
    r = _sv_job(fx._execute_alloc)
    assert r["memory_method"] == "vmhwm"
    assert fx.ALLOC_MIB * 0.75 < r["memory_usage_mb"] < fx.ALLOC_MIB + 3, r["memory_usage_mb"]
    assert r["process_peak_mb"] >= r["memory_usage_mb"]


def test_sampling_fallback_when_clear_refs_unwritable(monkeypatch):
    monkeypatch.setattr(memory, "_CLEAR_REFS_PATH", "/nonexistent/clear_refs")
    with MemoryMonitor(interval=0.01) as monitor:
        buf = np.ones(fx.ALLOC_MIB * MIB // 8)
    assert monitor.method == "sampled_10ms"
    assert abs(monitor.get_peak_usage_mb() - fx.ALLOC_MIB) < 3
    del buf


@vmhwm_only
def test_isolated_child_reports_its_own_peak_not_the_parents():
    parent_buf = np.ones(200 * MIB // 8)
    parent_buf[:] = 2.0
    parent_maxrss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    del parent_buf

    r = asyncio.run(run_isolated(fx.alloc_32mib, {"circuit_data": fx.QASM_2Q}))
    assert r["memory_method"] == "vmhwm"
    assert r["process_peak_rss_method"] == "vmhwm"
    assert abs(r["memory_usage_mb"] - fx.ALLOC_MIB) < 3, r["memory_usage_mb"]
    assert r["process_peak_rss_mb"] < parent_maxrss_mb
    assert r["process_peak_rss_mb"] >= r["process_peak_mb"]
    assert r["cpu_time_sec"] > 0
    assert set(r["metric_scope"]) >= {"cpu_time_sec", "process_peak_rss_mb",
                                      "simulation_cpu_time_sec"}


@vmhwm_only
def test_lifetime_peak_survives_the_monitor_reset():
    before = memory.lifetime_peak_rss()[0]
    buf = np.ones(64 * MIB // 8)
    buf[:] = 1.0
    del buf
    with MemoryMonitor():
        pass
    assert memory.lifetime_peak_rss()[0] >= before


def test_simulation_cpu_time_covers_only_execute():
    def compile_busy(payload):
        end = time.process_time() + 0.1
        while time.process_time() < end:
            pass
        return CompileResult(circuit=None, n_qubits=2)

    def execute_busy(compiled, payload):
        end = time.process_time() + 0.05
        while time.process_time() < end:
            pass
        return np.array([1, 0, 0, 0], dtype=np.complex128)

    r = _sv_job(execute_busy, compile_fn=compile_busy)
    assert 0.05 <= r["simulation_cpu_time_sec"] < 0.09


def test_thread_env_recorded(monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    monkeypatch.delenv("NUMEXPR_NUM_THREADS", raising=False)
    r = _sv_job(lambda c, p: np.array([1, 0, 0, 0]))
    assert set(r["thread_env"]) == set(THREAD_ENV_VARS)
    assert r["thread_env"]["OMP_NUM_THREADS"] == "1"
    assert r["thread_env"]["NUMEXPR_NUM_THREADS"] is None


def test_precision_default_kwarg_and_compile_override():
    sv = lambda c, p: np.array([1, 0, 0, 0])
    assert _sv_job(sv)["precision"] is None
    assert _sv_job(sv, precision="complex64")["precision"] == "complex64"
    override = lambda p: CompileResult(circuit=None, n_qubits=2, precision="complex128")
    assert _sv_job(sv, compile_fn=override, precision="complex64")["precision"] == "complex128"

    r = run_measured_job(
        simulator="t", payload={"circuit_data": fx.QASM_2Q, "n_shots": 4},
        compile_fn=fx._compile, execute_fn=lambda c, p: ({"00": 4}, "native"),
        qubit_ordering="msb", precision="complex64")
    assert r["precision"] == "complex64" and r["counts"] == {"00": 4}


def test_theoretical_size_uses_declared_qubits_not_backend_count():
    qasm = 'OPENQASM 2.0;\nqreg a[2];\nqreg b[3];\nh a[0];\n'
    reduced = lambda p: CompileResult(circuit=None, n_qubits=1)
    r = _sv_job(lambda c, p: np.array([1, 0]), qasm=qasm, compile_fn=reduced)
    assert r["theoretical_statevector_mb"] == theoretical_statevector_mb(5)
    r_none = _sv_job(lambda c, p: np.array([1, 0]), qasm=qasm, compile_fn=reduced,
                     theoretical_mb=None)
    assert r_none["theoretical_statevector_mb"] is None


def test_derive_runner_seed_is_deterministic_and_bounded():
    assert derive_runner_seed(42, "qiskit") == 2037181181
    seeds = {derive_runner_seed(42, k) for k in ("qiskit", "cirq", "qulacs", "quest")}
    assert len(seeds) == 4
    assert derive_runner_seed(43, "qiskit") != derive_runner_seed(42, "qiskit")
    assert all(0 <= derive_runner_seed(s, "cirq") < 2**31 for s in range(200))


def test_derive_runner_seed_rejects_bad_input():
    with pytest.raises(TypeError):
        derive_runner_seed(True, "qiskit")
    with pytest.raises(TypeError):
        derive_runner_seed("42", "qiskit")
    with pytest.raises(ValueError):
        derive_runner_seed(42, "")
