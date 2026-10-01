"""Tests for the CPU scheduling context: cgroup quota and throttling, window probes and
the per-run CPU fields the instrument records."""
import os

import pytest

from qrosetta_commons import cpu
from qrosetta_commons.helpers import run_statevector_job, run_with_uniform_measurement
from tests.unit import _instrument_fixture as fx


def _cgroup(tmp_path, monkeypatch, cpu_max=None, cpu_stat=None):
    if cpu_max is not None:
        (tmp_path / "cpu.max").write_text(cpu_max)
    if cpu_stat is not None:
        (tmp_path / "cpu.stat").write_text(cpu_stat)
    monkeypatch.setattr(cpu, "_CGROUP", str(tmp_path))


def test_quota_from_cgroup_v2(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch, cpu_max="100000 100000\n")
    assert cpu.cgroup_cpu_quota_cores() == 1.0


def test_unlimited_quota_is_none(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch, cpu_max="max 100000\n")
    assert cpu.cgroup_cpu_quota_cores() is None


def test_quota_from_cgroup_v1(tmp_path, monkeypatch):
    (tmp_path / "cpu").mkdir()
    (tmp_path / "cpu" / "cpu.cfs_quota_us").write_text("50000\n")
    (tmp_path / "cpu" / "cpu.cfs_period_us").write_text("100000\n")
    monkeypatch.setattr(cpu, "_CGROUP", str(tmp_path))
    assert cpu.cgroup_cpu_quota_cores() == 0.5


def test_throttled_usec_v2_and_v1(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch, cpu_stat="usage_usec 10\nnr_throttled 3\nthrottled_usec 4200\n")
    assert cpu.cgroup_throttled_usec() == 4200
    (tmp_path / "cpu.stat").unlink()
    (tmp_path / "cpu").mkdir()
    (tmp_path / "cpu" / "cpu.stat").write_text("nr_throttled 1\nthrottled_time 5000000\n")
    assert cpu.cgroup_throttled_usec() == 5000


def test_unreadable_cgroup_gives_none(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch)
    assert cpu.cgroup_throttled_usec() is None
    assert cpu.cgroup_cpu_quota_cores() is None


def test_window_probe_measures_throttle_delta(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch, cpu_stat="throttled_usec 1000\n")
    probe = cpu.WindowProbe().start()
    (tmp_path / "cpu.stat").write_text("throttled_usec 51000\n")
    probe.stop()
    assert probe.throttled_sec == pytest.approx(0.05)
    assert probe.involuntary_switches >= 0


def test_window_probe_measures_cgroup_cpu_usage(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch, cpu_stat="usage_usec 2000000\nthrottled_usec 0\n")
    probe = cpu.WindowProbe().start()
    (tmp_path / "cpu.stat").write_text("usage_usec 2500000\nthrottled_usec 0\n")
    probe.stop()
    assert probe.cgroup_cpu_sec == pytest.approx(0.5)


def test_cgroup_v1_cpuacct_usage(tmp_path, monkeypatch):
    (tmp_path / "cpuacct").mkdir()
    (tmp_path / "cpuacct" / "cpuacct.usage").write_text("3000000000\n")
    monkeypatch.setattr(cpu, "_CGROUP", str(tmp_path))
    assert cpu.cgroup_cpu_usage_usec() == 3000000


def test_window_probe_without_cgroup_reports_none(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch)
    probe = cpu.WindowProbe().start().stop()
    assert probe.throttled_sec is None and probe.cgroup_cpu_sec is None


@pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="needs procfs")
def test_current_cpu_is_in_affinity():
    assert cpu.current_cpu() in os.sched_getaffinity(0)


def test_timed_job_records_window_cpu_fields(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch, cpu_stat="throttled_usec 0\n")
    r = run_statevector_job(simulator="t", payload={"circuit_data": fx.QASM_2Q},
                            compile_fn=fx._compile, execute_fn=fx._execute_alloc,
                            qubit_ordering="msb")
    assert r.get("error") is None, r.get("error")
    assert r["simulation_throttled_sec"] == 0
    assert r["compilation_throttled_sec"] == 0
    assert isinstance(r["simulation_involuntary_switches"], int)
    assert isinstance(r["simulation_cpus"], list)


def test_repeats_summarise_throttling_and_cpu_environment(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch, cpu_max="100000 100000\n", cpu_stat="throttled_usec 0\n")

    def proc(payload):
        return run_statevector_job(simulator="t", payload=payload, compile_fn=fx._compile,
                                   execute_fn=fx._execute_alloc, qubit_ordering="msb")

    r = run_with_uniform_measurement(proc, {"circuit_data": fx.QASM_2Q, "timing_repeats": 3})
    assert r["simulation_throttled_samples"] == [0, 0, 0]
    assert r["simulation_throttled_sec"] == 0
    assert len(r["simulation_involuntary_switches_samples"]) == 3
    env = r["cpu_environment"]
    assert env["cpu_quota_cores"] == 1.0
    assert set(env["cpu_max_mhz"]) == {str(c) for c in r["simulation_cpus"]}
    assert "simulation_throttled_sec" in r["metric_scope"]


def test_parse_cpu_list():
    assert cpu.parse_cpu_list("0-3,8") == {0, 1, 2, 3, 8}
    for bad in ("", "3-1", "x", "-2"):
        with pytest.raises(ValueError):
            cpu.parse_cpu_list(bad)


def test_affinity_setting_restricts_the_process(monkeypatch):
    original = os.sched_getaffinity(0)
    target = min(original)
    monkeypatch.setenv(cpu.AFFINITY_ENV, str(target))
    try:
        cpu.apply_cpu_affinity()
        assert os.sched_getaffinity(0) == {target}
        assert cpu.cpu_environment()["cpu_affinity_setting"] == str(target)
    finally:
        os.sched_setaffinity(0, original)


def test_cpus_of_each_repeat_are_kept(tmp_path, monkeypatch):
    _cgroup(tmp_path, monkeypatch, cpu_stat="throttled_usec 0\n")

    def proc(payload):
        return run_statevector_job(simulator="t", payload=payload, compile_fn=fx._compile,
                                   execute_fn=fx._execute_alloc, qubit_ordering="msb")

    r = run_with_uniform_measurement(proc, {"circuit_data": fx.QASM_2Q, "timing_repeats": 2})
    assert len(r["simulation_cpus_samples"]) == 2
    assert set(r["simulation_cpus"]) == {c for s in r["simulation_cpus_samples"] for c in s}


def test_memory_limit_from_cgroup(tmp_path, monkeypatch):
    monkeypatch.setattr(cpu, "_CGROUP", str(tmp_path))
    (tmp_path / "memory.max").write_text("536870912\n")
    assert cpu.cgroup_memory_limit_mib() == 512
    (tmp_path / "memory.max").write_text("max\n")
    assert cpu.cgroup_memory_limit_mib() is None


def test_non_finite_amplitudes_are_an_error():
    import numpy as np

    def nan_state(compiled, payload):
        return np.array([np.nan, 0, 0, 0], dtype=complex)

    r = run_statevector_job(simulator="t", payload={"circuit_data": fx.QASM_2Q},
                            compile_fn=fx._compile, execute_fn=nan_state, qubit_ordering="msb")
    assert "non-finite amplitudes" in r["error"]
