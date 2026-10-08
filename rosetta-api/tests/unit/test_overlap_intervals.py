"""overlapping_runs counts runs whose runner processes overlapped, from the runner's own times."""

import asyncio
from datetime import datetime

import qrosetta_commons.helpers as helpers
from services.dispatcher import annotate_overlaps


def _iso(t):
    return datetime.fromtimestamp(1_800_000_000 + t).astimezone().isoformat()


def _run(dispatched, completed, wait, started, finished):
    return {"simulator": "x", "dispatched_at": _iso(dispatched), "completed_at": _iso(completed),
            "queue_wait_sec": wait, "process_started_at": _iso(started),
            "process_finished_at": _iso(finished)}


def test_sequential_runs_of_one_runner_do_not_overlap_despite_response_transfer():
    runs = [_run(0, 1.3, 0.0, 0.0, 1.0), _run(0, 2.3, 1.0, 1.0, 2.0), _run(0, 3.3, 2.0, 2.0, 3.0)]
    assert [r["overlapping_runs"] for r in annotate_overlaps(runs)] == [0, 0, 0]


def test_runs_that_did_overlap_are_counted():
    runs = [_run(0, 2, 0, 0.0, 2.0), _run(0, 2, 0, 1.0, 2.5)]
    assert [r["overlapping_runs"] for r in annotate_overlaps(runs)] == [1, 1]


def test_reports_without_runner_times_fall_back_to_dispatch_times():
    runs = [_run(0, 1.3, 0.0, 0, 0), _run(0, 2.3, 1.0, 0, 0)]
    for r in runs:
        del r["process_started_at"], r["process_finished_at"]
    assert [r["overlapping_runs"] for r in annotate_overlaps(runs)] == [1, 1]


def test_execution_slots_stamp_the_process_interval(monkeypatch):
    async def fake_isolated(func, payload, measured=True):
        await asyncio.sleep(0.01)
        return {"simulator": "x"}
    monkeypatch.setattr(helpers, "run_isolated", fake_isolated)
    result = asyncio.run(helpers.ExecutionSlots(1).run(lambda p: None, {}))
    start = datetime.fromisoformat(result["process_started_at"])
    end = datetime.fromisoformat(result["process_finished_at"])
    assert 0.005 < (end - start).total_seconds() < 5
