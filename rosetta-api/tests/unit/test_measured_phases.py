"""Custom ordering in measured mode: one phase plan across the sampled and native groups."""

import asyncio

import pytest

import services.job_manager as job_manager
from services.dispatcher import effective_phases
from services.run_registry import EXCLUSIVE

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\nmeasure q -> c;\n'
PHASES = {"qiskit": 1, "pyquil": 1, "qulacs": 2, "quest": 3}


@pytest.fixture
def calls(monkeypatch):
    log = []

    async def dispatch(runner_urls, runner_payload=None, timeout_seconds=None, runner_statuses=None):
        phases = effective_phases(runner_urls, runner_payload.get("runner_phases"), bool(EXCLUSIVE.get()))
        entry = {"runners": sorted(runner_urls), "phases": set(phases.values())}
        log.append(entry)
        loop = asyncio.get_running_loop()
        entry["start"] = loop.time()
        await asyncio.sleep(0.02)
        entry["end"] = loop.time()
        return [{"simulator": n, "counts": {"00": 50, "01": 50}, "dispatch_status": "ok",
                 "dispatch_phase": phases[n]} for n in runner_urls]
    monkeypatch.setattr(job_manager, "dispatch_to_runners", dispatch)
    return log


def _run(exclusive=False):
    async def go():
        EXCLUSIVE.set(exclusive)
        return await job_manager.run_single_circuit_measurement(
            QASM, 100, target_simulators=list(PHASES), runner_phases=PHASES, seed=1)
    return asyncio.run(go())


def _assert_phase_order(log):
    for later in log:
        for earlier in log:
            if max(earlier["phases"]) < min(later["phases"]):
                assert earlier["end"] <= later["start"], (earlier, later)


def test_measured_phases_run_in_order_across_both_groups(calls):
    pytest.importorskip("pytket")
    report = _run()
    assert sorted(len(c["phases"]) for c in calls) == [1] * len(calls)
    _assert_phase_order(calls)
    assert report["effective_runner_phases"] == PHASES


def test_exclusive_measured_run_gives_each_backend_its_own_global_phase(calls):
    pytest.importorskip("pytket")
    report = _run(exclusive=True)
    assert all(len(c["runners"]) == 1 for c in calls)
    _assert_phase_order(calls)
    phases = report["effective_runner_phases"]
    assert sorted(phases.values()) == [1, 2, 3, 4]
    assert phases == {n: i + 1 for i, n in enumerate(sorted(PHASES))}


def test_effective_phases_keep_distinct_requested_phases_in_an_exclusive_run():
    assert effective_phases(["a", "b"], {"a": 2, "b": 1}, True) == {"a": 2, "b": 1}
    assert effective_phases(["a", "b"], {"a": 1, "b": 1}, True) == {"a": 1, "b": 2}
    assert effective_phases(["a", "b"], {"a": 3}, False) == {"a": 3, "b": 1}
