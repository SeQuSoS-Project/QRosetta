"""V7(b) Failure injection, runner processes killed mid-run: the real Qibo runner
(runners/qibo-runner/main.py, served by uvicorn) beside two fake runners, with the API
dispatching over HTTP. Killing the run's child process fails only that backend, names the
signal, and frees the runner's execution slot for the next run; killing the runner's server
process (as `podman kill` does) fails only that backend, takes the child with it, and the next
job without it runs. A run whose caller went away keeps the runner's slot (V7-08, open)."""

import http.client
import json
import os
import signal
import threading
import time

import psutil
import pytest

from tests.unit._fault_runners import (
    FaultRunner, Api, assert_no_raw_exception_text, wire_runners,
)

pytest.importorskip("qibo")
pytest.importorskip("pytket")

from tests.unit._real_runner import RealRunner  # noqa: E402

N_QUBITS = 12


def _slow_circuit(layers=20, n=N_QUBITS):
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";', f'qreg q[{n}];']
    for _ in range(layers):
        lines += [f"rx(0.3) q[{i}];" for i in range(n)]
        lines += [f"cx q[{i}],q[{i + 1}];" for i in range(n - 1)]
    return "\n".join(lines) + "\n"


PLUS = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\nh q[1];\n'


@pytest.fixture
def fleet(tmp_path, monkeypatch):
    """(Api, real qibo runner): the app dispatching to the real Qibo runner and fake qiskit and
    cirq runners, 60 s per run, 30 s of queue budget."""
    import services.availability as availability
    import services.job_manager as job_manager
    from fastapi.testclient import TestClient
    from main import app
    from services import job_store, prep_worker
    from services.security import limiter

    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    job_store.reset_spill_dir()
    monkeypatch.setattr(limiter, "enabled", False)
    monkeypatch.setattr(prep_worker, "IN_PROCESS", True)
    qibo = RealRunner("qibo-runner")
    fakes = {name: FaultRunner(name) for name in ("qiskit", "cirq")}
    runners = {"qibo": qibo, **fakes}
    wire_runners(monkeypatch, runners, run_timeout=60, queue_budget=30)
    before = set(job_manager.ACTIVE_JOBS)
    try:
        yield Api(TestClient(app), runners), qibo
    finally:
        qibo.close()
        for fake in fakes.values():
            fake.close()
        availability.clear_cache()
        for job_id in [j for j in job_manager.ACTIVE_JOBS if j not in before]:
            job_manager.ACTIVE_JOBS.pop(job_id, None)


def _kill_when_running(runner, target, seconds=60.0, after=0.3):
    """In a thread: once ``target(runner)`` names a process that has lived ``after`` seconds,
    SIGKILL it; the thread records the pid and the time of the kill."""
    record = {}

    def watch():
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            proc = target(runner)
            if proc is not None:
                try:
                    alive_for = time.time() - proc.create_time()
                except psutil.Error:
                    alive_for = 0
                if alive_for >= after:
                    record["pid"] = proc.pid
                    record["children"] = [c.pid for c in runner.run_children()]
                    os.kill(proc.pid, signal.SIGKILL)
                    record["at"] = time.monotonic()
                    return
            time.sleep(0.02)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    return thread, record


def _the_run_child(runner):
    children = runner.run_children()
    return children[0] if children else None


def _the_server(runner):
    return psutil.Process(runner.pid) if runner.run_children() else None


def _results(env):
    return {r["simulator"]: r for r in env["results"]["raw_results"]}


def test_a_killed_run_child_fails_only_its_backend_and_frees_the_slot(fleet):
    api, qibo = fleet
    thread, killed = _kill_when_running(qibo, _the_run_child)
    env = api.finished(api.compare(_slow_circuit(), timing_repeats=10))
    thread.join(5)
    assert killed.get("pid"), "the run's child was never seen"
    assert env["status"] == "completed"
    results = _results(env)
    assert results["qibo"]["dispatch_status"] == "error"
    assert results["qibo"]["process_exit_signal"] == "SIGKILL"
    assert ("it was killed by signal 9 (SIGKILL). The kernel sends SIGKILL when memory runs out, and a "
            "forced stop sends it too; this server did not record what sent it.") in results["qibo"]["error"]
    assert results["qiskit"]["dispatch_status"] == results["cirq"]["dispatch_status"] == "ok"
    assert_no_raw_exception_text(env)
    assert not psutil.pid_exists(killed["pid"]) or psutil.Process(killed["pid"]).status() == psutil.STATUS_ZOMBIE

    t0 = time.monotonic()
    after = api.finished(api.compare(PLUS))
    results = _results(after)
    assert results["qibo"]["dispatch_status"] == "ok", results["qibo"].get("error")
    assert results["qibo"]["queue_wait_sec"] < 1.0
    assert time.monotonic() - t0 < 30
    assert after["status"] == "completed"
    assert not after["results"]["divergence_report"].get("error")


def test_a_killed_runner_server_fails_only_its_backend_and_takes_its_child(fleet):
    api, qibo = fleet
    thread, killed = _kill_when_running(qibo, _the_server)
    env = api.finished(api.compare(_slow_circuit(), timing_repeats=10))
    thread.join(5)
    assert killed.get("pid") == qibo.pid
    assert env["status"] == "completed"
    results = _results(env)
    assert results["qibo"]["dispatch_status"] == "error"
    assert results["qibo"]["error"].startswith("CONNECTION LOST after ~")
    assert "The runner process or its container ended, or the network connection failed" in results["qibo"]["error"]
    assert results["qiskit"]["dispatch_status"] == results["cirq"]["dispatch_status"] == "ok"
    assert_no_raw_exception_text(env)

    deadline = time.monotonic() + 5
    while any(psutil.pid_exists(p) and psutil.Process(p).status() != psutil.STATUS_ZOMBIE
              for p in killed["children"]) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not [p for p in killed["children"]
                if psutil.pid_exists(p) and psutil.Process(p).status() != psutil.STATUS_ZOMBIE], \
        "the run's child outlived its killed server"

    r = api.client.post("/compare", json={"qasm_string": PLUS, "target_simulators": ["qibo", "qiskit"],
                                          "timeout_seconds": 10})
    if r.status_code == 400:
        assert "qibo: unreachable" in r.json()["detail"]
    else:
        later = api.finished(r.json()["job_id"])
        assert _results(later)["qibo"]["dispatch_status"] == "offline"
    rest = api.finished(api.compare(PLUS, targets=["qiskit", "cirq"]))
    assert rest["status"] == "completed"


def _post(port, body, timeout):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    conn.request("POST", "/run", body=json.dumps(body), headers={"Content-Type": "application/json"})
    try:
        return json.loads(conn.getresponse().read())
    finally:
        conn.close()


@pytest.mark.xfail(strict=True, reason="V7-08: a runner keeps running, and holding its slot for, a run whose "
                                       "caller went away (the API restarted); proposed fix in defects-V7.md")
def test_v7_08_a_run_whose_caller_went_away_does_not_hold_the_runner_slot():
    qibo = RealRunner("qibo-runner")
    try:
        with pytest.raises(OSError):
            _post(qibo.port, {"circuit_data": _slow_circuit(60, n=14), "timing_repeats": 10,
                              "hard_timeout_seconds": 120, "max_queue_wait_seconds": 60}, timeout=1.0)
        result = _post(qibo.port, {"circuit_data": PLUS, "hard_timeout_seconds": 60,
                                   "max_queue_wait_seconds": 60}, timeout=120)
        assert not result.get("error"), result.get("error")
        assert result["queue_wait_sec"] < 1.0, f"waited {result['queue_wait_sec']:.1f} s behind an abandoned run"
    finally:
        qibo.close()
