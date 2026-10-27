"""A cancelled run releases its execution slot only after its child process group is dead."""
import asyncio
import os
import signal
import time

import pytest

from qrosetta_commons.helpers import ExecutionSlots
from tests.unit import _isolated_fixture as fx


async def _wait_for_file(path, seconds=20.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists() and path.read_text():
            return int(path.read_text())
        await asyncio.sleep(0.05)
    raise AssertionError(f"{path} was not written")


def _kill_leftover(pid):
    if pid and fx.process_alive(pid):
        os.kill(pid, signal.SIGKILL)


@pytest.mark.parametrize("measured", [True, False])
def test_cancelled_run_holds_the_slot_until_its_child_is_dead(tmp_path, measured):
    pid_file = tmp_path / "pid"
    child_pid = None

    async def main():
        nonlocal child_pid
        slots = ExecutionSlots(1)
        first = asyncio.create_task(slots.run(
            fx.slow_records_pid, {"pid_file": str(pid_file), "sleep": 30,
                                  "hard_timeout_seconds": 60}, measured=measured))
        child_pid = await _wait_for_file(pid_file)
        second = asyncio.create_task(slots.run(
            fx.reports_watched_pid, {"watch_pid": child_pid}, measured=measured))
        await asyncio.sleep(0.2)
        t0 = time.monotonic()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        cancel_sec = time.monotonic() - t0
        alive_after_cancel = fx.process_alive(child_pid)
        return alive_after_cancel, cancel_sec, await second

    try:
        alive_after_cancel, cancel_sec, second = asyncio.run(main())
    finally:
        _kill_leftover(child_pid)
    assert second["watched_alive"] is False, "the next run started beside the cancelled child"
    assert not alive_after_cancel, "the cancelled run's child kept running"
    assert cancel_sec < 5, f"cancellation took {cancel_sec:.1f} s"


def test_cancelled_run_kills_subprocesses_of_the_child(tmp_path):
    pid_file = tmp_path / "pid"
    grandchild_pid = None

    async def main():
        nonlocal grandchild_pid
        slots = ExecutionSlots(1)
        task = asyncio.create_task(slots.run(
            fx.starts_subprocess, {"pid_file": str(pid_file), "hard_timeout_seconds": 60}))
        grandchild_pid = await _wait_for_file(pid_file)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        deadline = time.monotonic() + 2
        while fx.process_alive(grandchild_pid) and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        return fx.process_alive(grandchild_pid)

    try:
        alive = asyncio.run(main())
    finally:
        _kill_leftover(grandchild_pid)
    assert not alive, "the child's subprocess kept running"


def test_a_second_cancel_does_not_release_the_slot_early(tmp_path):
    pid_file = tmp_path / "pid"
    child_pid = None

    async def main():
        nonlocal child_pid
        slots = ExecutionSlots(1)
        task = asyncio.create_task(slots.run(
            fx.slow_records_pid, {"pid_file": str(pid_file), "sleep": 30,
                                  "hard_timeout_seconds": 60}))
        child_pid = await _wait_for_file(pid_file)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return fx.process_alive(child_pid), slots.running

    try:
        alive, running = asyncio.run(main())
    finally:
        _kill_leftover(child_pid)
    assert not alive and running == 0


def test_uncancelled_runs_return_the_same_fields():
    async def main():
        slots = ExecutionSlots(1)
        return (await slots.run(fx.with_qasm, {"timing_repeats": 2}),
                await slots.run(fx.fast, {"x": 3}, measured=False),
                await slots.run(fx.raiser, {}))

    measured, compiled, failed = asyncio.run(main())
    assert sorted(measured) == [
        "circuit_depth", "cpu_environment", "cpu_time_sec", "execution_time_sec", "gate_count",
        "gate_metrics_basis", "metric_scope", "process_finished_at", "process_peak_rss_mb",
        "process_peak_rss_method", "process_started_at", "queue_wait_sec", "result",
        "simulation_cpus", "simulation_cpus_samples", "simulation_involuntary_switches_samples",
        "timing_repeats", "timing_statistic", "transpiled_qasm"]
    assert measured["result"] == "ok" and measured["gate_count"] == 2
    assert sorted(compiled) == ["process_finished_at", "process_started_at", "queue_wait_sec",
                                "result"]
    assert compiled["result"] == 6
    assert sorted(failed) == [
        "compilation_throttled_sec", "compilation_time_sec", "cpu_time_sec", "error",
        "execution_time_sec", "memory_usage_mb", "process_finished_at", "process_peak_mb",
        "process_peak_rss_mb", "process_started_at", "queue_wait_sec",
        "simulation_cgroup_cpu_time_sec", "simulation_cpu_time_sec", "simulation_throttled_sec",
        "simulation_time_sec"]
    assert failed["error"] == "ValueError: bad gate"
