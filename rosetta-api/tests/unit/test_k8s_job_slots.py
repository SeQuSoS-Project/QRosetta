"""Kubernetes job slots: at most K8S_MAX_CONCURRENT_JOBS Jobs at once, the wait recorded,
a run that never gets a slot or whose pod the quota refuses reported as never started."""

import threading
import time
from types import SimpleNamespace

import pytest

from services import dispatcher_k8s as k8s


SPEC = {"key": "qiskit", "sim_name": "qiskit", "url": "http://pytket-qiskit-runner:8000/run",
        "opt_level": 0, "phase": 1}


def _run(monkeypatch, inner, slots=2, budget=5):
    monkeypatch.setattr(k8s, "JOB_SLOTS", threading.BoundedSemaphore(slots))
    monkeypatch.setattr(k8s.settings, "K8S_MAX_CONCURRENT_JOBS", slots)
    monkeypatch.setattr(k8s.settings, "RUNNER_QUEUE_MAX_WAIT_SEC", budget)
    monkeypatch.setattr(k8s, "_run_k8s_job_inner", inner)
    return lambda spec=SPEC: k8s._run_k8s_job_for_simulator(spec, {}, 10, "ns")


def test_no_more_jobs_than_slots_and_wait_recorded(monkeypatch):
    lock = threading.Lock()
    state = {"now": 0, "peak": 0}

    def inner(*_a, **_k):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.2)
        with lock:
            state["now"] -= 1
        return {"statevector": "x"}

    run = _run(monkeypatch, inner, slots=2)
    results = [None] * 5
    threads = [threading.Thread(target=lambda i=i: results.__setitem__(i, run())) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert state["peak"] == 2
    waits = sorted(r["queue_wait_sec"] for r in results)
    assert waits[0] < 0.1 and waits[-1] >= 0.35
    assert all(r["dispatch_status"] == "ok" for r in results)


def test_slot_released_when_job_creation_raises(monkeypatch):
    def inner(*_a, **_k):
        raise RuntimeError("api down")

    run = _run(monkeypatch, inner, slots=1)
    assert run()["dispatch_status"] == "offline"
    assert run()["dispatch_status"] == "offline"


def test_no_slot_within_budget_is_never_started(monkeypatch):
    run = _run(monkeypatch, lambda *_a, **_k: {}, slots=1, budget=0.2)
    k8s.JOB_SLOTS.acquire()
    result = run()
    assert result["dispatch_status"] == "timeout"
    assert result["timeout_kind"] == "queue"
    assert result["never_started"] is True
    assert result["queue_wait_sec"] >= 0.2
    assert "job slots" in result["error"]


def _event(reason, message):
    return SimpleNamespace(reason=reason, message=message)


@pytest.mark.parametrize("events, expected", [
    ([_event("FailedCreate", 'pods "p" is forbidden: exceeded quota: q, requested: limits.cpu=1, used: limits.cpu=3500m, limited: limits.cpu=4')], "limits.cpu"),
    ([_event("SuccessfulCreate", "Created pod: p")], None),
    ([], None),
])
def test_quota_refusal_resource(events, expected):
    core = SimpleNamespace(list_namespaced_event=lambda **_k: SimpleNamespace(items=events))
    assert k8s._pod_refusal_resource(core, "ns", "job") == expected
