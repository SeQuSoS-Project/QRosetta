"""Tests for helpers.run_isolated — the in-runner spawned-subprocess hard-kill (Phase 2).

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
    assert _call(fx.fast, {"x": 21}) == {"result": 42}


def test_runaway_is_killed_at_the_budget():
    t0 = time.monotonic()
    r = _call(fx.slow, {"sleep": 60, "hard_timeout_seconds": 1})
    elapsed = time.monotonic() - t0
    assert "TIMEOUT" in r["error"] and "1s" in r["error"]
    assert elapsed < 10, f"kill took too long: {elapsed:.1f}s"  # not the full 60s
    assert r["execution_time_sec"] == 0.0


def test_crash_fails_fast_not_at_deadline():
    t0 = time.monotonic()
    r = _call(fx.boom, {"hard_timeout_seconds": 30})
    elapsed = time.monotonic() - t0
    assert "without a result" in r["error"]  # OOM-style message
    assert elapsed < 10, f"crash detection waited for the deadline: {elapsed:.1f}s"


def test_in_sim_exception_is_surfaced():
    r = _call(fx.raiser, {})
    assert "ValueError" in r["error"] and "bad gate" in r["error"]


def test_default_timeout_used_when_absent():
    # No hard_timeout_seconds -> falls back to the default; fast func still returns.
    assert _call(fx.fast, {"x": 5}) == {"result": 10}
