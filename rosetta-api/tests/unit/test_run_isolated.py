"""Tests for helpers.run_isolated, the spawned-subprocess hard-kill.

Verifies a normal run returns, a runaway is killed promptly at the budget, a crash (OOM)
fails fast, and an in-sim exception is surfaced. Driven with asyncio.run.
"""
import asyncio
import time

import pytest

from qrosetta_commons.helpers import run_isolated
from tests.unit import _isolated_fixture as fx


def _call(func, payload):
    return asyncio.run(run_isolated(func, payload))


def test_normal_run_returns_result():
    r = _call(fx.fast, {"x": 21})
    assert r["result"] == 42
    assert isinstance(r["cpu_time_sec"], float) and r["cpu_time_sec"] >= 0
    assert isinstance(r["process_peak_rss_mb"], float) and r["process_peak_rss_mb"] > 0


def test_runaway_is_killed_at_the_budget():
    t0 = time.monotonic()
    r = _call(fx.slow, {"sleep": 60, "hard_timeout_seconds": 1})
    elapsed = time.monotonic() - t0
    assert r["error"].startswith("TIMEOUT (1s)") and r["timed_out"] is True
    assert "SDK import" in r["error"]
    assert elapsed < 10, f"kill took too long: {elapsed:.1f}s"  # not the full 60s
    assert r["execution_time_sec"] is None and r["memory_usage_mb"] is None


def _wait_until_gone(pid, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with open(f"/proc/{pid}/stat") as fh:
                if fh.read().split(") ", 1)[1].startswith("Z"):
                    return True
        except FileNotFoundError:
            return True
        time.sleep(0.05)
    return False


@pytest.mark.parametrize("return_early", [False, True])
def test_a_subprocess_of_the_child_does_not_outlive_it(tmp_path, return_early):
    pid_file = tmp_path / "pid"
    r = _call(fx.starts_subprocess, {"pid_file": str(pid_file), "hard_timeout_seconds": 2,
                                     "return_early": return_early})
    assert ("error" in r) is not return_early
    assert _wait_until_gone(int(pid_file.read_text())), "subprocess still running"


def test_crash_fails_fast_not_at_deadline():
    t0 = time.monotonic()
    r = _call(fx.boom, {"hard_timeout_seconds": 30})
    elapsed = time.monotonic() - t0
    assert "before returning a result" in r["error"]  # OOM-style message
    assert "container logs" not in r["error"] and "timed_out" not in r
    assert elapsed < 10, f"crash detection waited for the deadline: {elapsed:.1f}s"


def test_in_sim_exception_is_surfaced():
    r = _call(fx.raiser, {})
    assert "ValueError" in r["error"] and "bad gate" in r["error"]


def test_default_timeout_used_when_absent():
    assert _call(fx.fast, {"x": 5})["result"] == 10


def test_n_shots_is_echoed_when_present_in_payload():
    r = _call(fx.fast, {"x": 1, "n_shots": 512})
    assert r["n_shots"] == 512


def test_n_shots_absent_when_not_in_payload():
    r = _call(fx.fast, {"x": 1})
    assert "n_shots" not in r


def test_gate_count_and_depth_derived_from_transpiled_qasm():
    r = _call(fx.with_qasm, {})
    assert r["gate_count"] == 2
    assert r["circuit_depth"] == 2


def test_repeats_report_samples_and_medians():
    r = _call(fx.with_qasm, {"timing_repeats": 3})
    assert r["timing_repeats"] == 3
    assert r["timing_statistic"] == "median"


def test_default_repeats_is_one():
    r = _call(fx.with_qasm, {})
    assert r["timing_repeats"] == 1
    assert r["timing_statistic"] == "median"


def test_failed_run_reports_no_process_metrics():
    r = _call(fx.returns_error, {"seed": 1})
    assert r["error"]
    assert r["cpu_time_sec"] is None and r["process_peak_rss_mb"] is None
