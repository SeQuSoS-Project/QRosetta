"""Tests for helpers.ExecutionSlots: per-runner serialisation and queue-wait reporting."""
import asyncio
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from qrosetta_commons.helpers import ExecutionSlots, register_runner_endpoints
from tests.unit import _isolated_fixture as fx


def test_runs_are_serialised_and_report_queue_wait():
    async def main():
        slots = ExecutionSlots(1)
        t0 = time.monotonic()
        results = await asyncio.gather(
            slots.run(fx.slow, {"sleep": 1.0}), slots.run(fx.slow, {"sleep": 1.0}))
        return results, time.monotonic() - t0

    (first, second), elapsed = asyncio.run(main())
    assert first["queue_wait_sec"] < 0.5
    assert second["queue_wait_sec"] >= 0.9
    assert elapsed >= 2.0


def test_queue_budget_expiry_never_starts_the_run():
    async def main():
        slots = ExecutionSlots(1)
        return await asyncio.gather(
            slots.run(fx.slow, {"sleep": 3.0}),
            slots.run(fx.fast, {"x": 1, "max_queue_wait_seconds": 0.5}))

    running, queued = asyncio.run(main())
    assert queued["timed_out"] is True and queued["never_started"] is True
    assert queued["error"].startswith("TIMEOUT while queued behind 1 other run(s)")
    assert queued["execution_time_sec"] is None and queued["queue_wait_sec"] >= 0.5
    assert "result" not in queued


def test_queue_wait_is_in_endpoint_results():
    app = FastAPI()
    register_runner_endpoints(app, fx.fast, fx.fast)
    r = TestClient(app).post("/run", json={"circuit_data": "x", "max_queue_wait_seconds": 30})
    assert r.status_code == 200 and r.json()["queue_wait_sec"] >= 0
