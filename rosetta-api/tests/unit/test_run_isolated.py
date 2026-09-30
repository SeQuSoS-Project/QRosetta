"""Tests for helpers.run_isolated, the spawned-subprocess hard-kill.

Verifies a normal run returns, a runaway is killed promptly at the budget, a crash (OOM)
fails fast, and an in-sim exception is surfaced. Driven with asyncio.run.
"""
import asyncio
import time

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


def test_repeat_with_variance():
    # fx.with_qasm reports a constant execution_time_sec, so the stdev is exactly 0.
    r = _call(fx.with_qasm, {"timing_repeats": 3})
    assert r["timing_repeats"] == 3
    assert r["execution_time_sec_mean"] == 0.01
    assert r["execution_time_sec_stdev"] == 0.0


def test_default_repeats_is_one_and_omits_variance_fields():
    r = _call(fx.with_qasm, {})
    assert "timing_repeats" not in r
    assert "execution_time_sec_mean" not in r


def test_failed_run_reports_no_process_metrics():
    r = _call(fx.returns_error, {"seed": 1})
    assert r["error"]
    assert r["cpu_time_sec"] is None and r["process_peak_rss_mb"] is None
