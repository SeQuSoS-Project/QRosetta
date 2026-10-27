"""Shared state of the API process under concurrent threads and coroutines: the run registry,
the exclusive gate and claims, Kubernetes job slots, the pytket lock, figure rendering, the
distribution memo and the rate limiter."""
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import given, settings, strategies as st

from services.run_registry import ExclusiveGate, RunRegistry, claim_exclusive, release_exclusive


def _together(n, fn):
    """Run ``fn(i)`` in ``n`` threads released at once; return the results in order."""
    start = threading.Barrier(n)

    def call(i):
        start.wait(5)
        return fn(i)
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(call, range(n)))


def test_registry_counts_every_run_of_the_other_token_when_all_overlap():
    registry, tokens, per_token = RunRegistry(), (object(), object()), 6
    started = threading.Barrier(2 * per_token)

    def run(i):
        run_id = registry.start(tokens[i % 2])
        started.wait(5)
        return registry.finish(run_id)
    assert _together(2 * per_token, run) == [per_token] * (2 * per_token)
    assert registry.active() == 0


def test_one_exclusive_claim_per_client_under_simultaneous_requests():
    claims = _together(16, lambda i: claim_exclusive("10.0.0.9", f"claim-job-{i}"))
    holders = [i for i, held in enumerate(claims) if held is None]
    try:
        assert len(holders) == 1
        assert set(claims) - {None} == {f"claim-job-{holders[0]}"}
    finally:
        release_exclusive(f"claim-job-{holders[0]}")
    assert claim_exclusive("10.0.0.9", "claim-job-next") is None
    release_exclusive("claim-job-next")


ACTORS = st.lists(st.tuples(st.booleans(), st.integers(0, 4), st.integers(0, 3),
                            st.one_of(st.none(), st.integers(0, 8))),
                  min_size=1, max_size=8)


@settings(max_examples=60, deadline=None, derandomize=True)
@given(actors=ACTORS)
def test_gate_never_admits_an_exclusive_run_beside_another_and_ends_open(actors):
    """Each actor: (exclusive, steps before arriving, steps holding, step it is cancelled)."""
    async def scenario():
        gate, inside = ExclusiveGate(), {"exclusive": 0, "shared": 0}

        async def actor(exclusive, arrive, hold):
            for _ in range(arrive):
                await asyncio.sleep(0)
            await gate.acquire(exclusive)
            kind = "exclusive" if exclusive else "shared"
            inside[kind] += 1
            assert inside["exclusive"] <= 1
            assert not (inside["exclusive"] and inside["shared"])
            try:
                for _ in range(hold):
                    await asyncio.sleep(0)
            finally:
                inside[kind] -= 1
                await gate.release(exclusive)

        tasks = [asyncio.create_task(actor(x, a, h)) for x, a, h, _ in actors]
        for step in range(10):
            for task, (_, _, _, cancel_at) in zip(tasks, actors):
                if cancel_at == step:
                    task.cancel()
            await asyncio.sleep(0)
        done, pending = await asyncio.wait(tasks, timeout=2)
        assert not pending, "a dispatch never got through the gate"
        for task in done:
            if not task.cancelled():
                task.result()
        assert gate.status() == {"exclusive_running": False, "exclusive_waiting": 0,
                                 "shared_running": 0, "saves_running": 0,
                                 "host_load_running": 0}

    asyncio.run(scenario())


def test_k8s_job_slots_bound_concurrency_and_are_all_returned(monkeypatch):
    from config import settings as app_settings
    from services import dispatcher_k8s as k8s
    monkeypatch.setattr(k8s, "JOB_SLOTS", threading.BoundedSemaphore(2))
    lock, state = threading.Lock(), {"now": 0, "peak": 0}

    def inner(sim_name, url, payload, timeout_seconds, namespace, status_callback):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.01)
        with lock:
            state["now"] -= 1
        if sim_name.endswith("3"):
            raise RuntimeError("create refused")
        return {"simulator": sim_name, "dispatch_status": "ok"}
    monkeypatch.setattr(k8s, "_run_k8s_job_inner", inner)

    def spec(i):
        return {"key": f"sim{i}", "sim_name": f"sim{i}", "url": f"http://sim{i}-runner:8000/run",
                "opt_level": 0, "phase": 1}
    results = _together(10, lambda i: k8s._run_k8s_job_for_simulator(spec(i), {}, 5, "ns"))
    assert state["peak"] == 2
    assert [r["dispatch_status"] for r in results].count("offline") == 1
    assert k8s.JOB_SLOTS.acquire(blocking=False) and k8s.JOB_SLOTS.acquire(blocking=False)
    assert not k8s.JOB_SLOTS.acquire(blocking=False)

    monkeypatch.setattr(app_settings, "RUNNER_QUEUE_MAX_WAIT_SEC", 0.05)
    waited = k8s._run_k8s_job_for_simulator(spec(0), {}, 5, "ns")
    assert waited["never_started"] and waited["dispatch_status"] == "timeout"
    k8s.JOB_SLOTS.release()
    k8s.JOB_SLOTS.release()
    with pytest.raises(ValueError):
        k8s.JOB_SLOTS.release()


def _gate_circuit(i):
    return ('OPENQASM 2.0;\ninclude "qelib1.inc";\n'
            f"gate g{i} a, b {{ rx({0.1 * (i + 1)}) a; cx a, b; ry({0.05 * (i + 2)}) b; }}\n"
            f"qreg q[3];\ng{i} q[0], q[1];\ng{i} q[1], q[2];\nh q[{i % 3}];\n")


def test_simultaneous_pytket_round_trips_keep_each_circuits_gate_definitions():
    pytest.importorskip("pytket")
    from services.circuit_resolver import prepare_statevector_dispatch
    circuits = [_gate_circuit(i) for i in range(8)]
    serial = [prepare_statevector_dispatch(c, True)["qasm"] for c in circuits]
    for _ in range(3):
        assert _together(8, lambda i: prepare_statevector_dispatch(circuits[i], True)["qasm"]) == serial


def test_figures_rendered_at_once_in_different_sizes_match_serial_renders():
    from services.publication import render_artifact
    from tests.unit.test_publication import MEASURED
    sizes = ["auto", "single", "double", "slide"]

    def render(i):
        return render_artifact(MEASURED, "measured", "agreement_distribution", "svg",
                               params={"size": sizes[i % 4]})[0]
    serial = [render(i) for i in range(4)]
    assert _together(8, render) == serial * 2


def test_distribution_memo_returns_each_reports_own_data_under_load():
    from services.publication.distributions import count_probabilities

    def report(n):
        return {"n_shots": n, "raw_results": [
            {"simulator": "qiskit", "counts": {"0": n, "1": 1}, "qubit_ordering": "lsb"},
            {"simulator": "qibo", "counts": {"0": 1, "1": n}, "qubit_ordering": "lsb"}]}
    reports = [report(n) for n in range(2, 12)]

    def read(i):
        r = reports[i % len(reports)]
        return [count_probabilities(r)["totals"] for _ in range(20)]
    for i, totals in enumerate(_together(20, read)):
        n = reports[i % len(reports)]["n_shots"]
        assert all(t == {"qiskit": n + 1, "qibo": n + 1} for t in totals)


def test_rate_limit_admits_exactly_its_amount_to_simultaneous_requests():
    from limits import parse
    from services.security import limiter
    item, key = parse("30/minute"), "concurrency-test-client"
    limiter.reset()
    try:
        hits = _together(16, lambda i: sum(limiter.limiter.hit(item, key) for _ in range(5)))
        assert sum(hits) == 30
    finally:
        limiter.reset()
