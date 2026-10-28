"""V7(c) Failure injection, the circuit preparation worker killed mid-preparation: the job
fails with a message that names how the worker ended and does not claim one cause, no runner is
dispatched, and the next job starts a new worker and runs."""

import os
import signal
import threading
import time

import pytest

from tests.unit._fault_runners import api_with_runners, assert_no_raw_exception_text  # noqa: F401

pytest.importorskip("pytket")

import services.job_manager as job_manager  # noqa: E402
from services import prep_worker  # noqa: E402
from tests.unit import prep_probes  # noqa: E402

BELL = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


@pytest.fixture
def real_worker(monkeypatch, tmp_path):
    """The real preparation worker, started fresh with QROSETTA_TEST_PREP_MARKER set."""
    marker = tmp_path / "prep.pid"
    monkeypatch.setenv("QROSETTA_TEST_PREP_MARKER", str(marker))
    prep_worker.stop()
    yield marker
    prep_worker.stop()


def _kill_marked_worker(marker, sig=signal.SIGKILL, seconds=120.0):
    record = {}

    def watch():
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if marker.exists() and marker.read_text():
                record["pid"] = int(marker.read_text())
                os.kill(record["pid"], sig)
                return
            time.sleep(0.05)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    return thread, record


@pytest.mark.parametrize("sig, how", [
    (signal.SIGKILL, "killed by SIGKILL, which the kernel sends when memory runs out and a forced stop "
                     "also sends; this server did not record which"),
    (signal.SIGTERM, "killed by SIGTERM"),
])
def test_v7_01_a_killed_preparation_worker_fails_the_job_naming_how_it_ended(
        api_with_runners, real_worker, monkeypatch, sig, how):
    api = api_with_runners({"qiskit": None, "cirq": None})
    monkeypatch.setattr(prep_worker, "IN_PROCESS", False)
    real = job_manager.prepare_statevector_dispatch
    monkeypatch.setattr(job_manager, "prepare_statevector_dispatch",
                        prep_probes.marked_slow_statevector_preparation)
    thread, killed = _kill_marked_worker(real_worker, sig)
    t0 = time.monotonic()
    env = api.finished(api.compare(BELL))
    thread.join(5)
    assert killed.get("pid"), "the preparation never started"
    assert time.monotonic() - t0 < 25, "the job waited for the killed worker's sleep"
    assert env["status"] == "failed"
    assert env["error"].startswith(
        f"The circuit preparation process ended while preparing this circuit ({how}).")
    assert env["error"].endswith(prep_worker.DISPATCH_HINT)
    assert not any(r.requests for r in api.runners.values()), "a runner was dispatched"
    assert_no_raw_exception_text(env)
    assert prep_worker.worker_pid() is None

    monkeypatch.setattr(job_manager, "prepare_statevector_dispatch", real)
    next_env = api.finished(api.compare(BELL))
    assert next_env["status"] == "completed"
    assert {r["dispatch_status"] for r in next_env["results"]["raw_results"]} == {"ok"}
    assert prep_worker.worker_pid() not in (None, killed["pid"])


def test_a_killed_worker_fails_one_playlist_circuit_and_the_rest_run(api_with_runners, real_worker,
                                                                    monkeypatch):
    api = api_with_runners({"qiskit": None, "cirq": None})
    monkeypatch.setattr(prep_worker, "IN_PROCESS", False)
    calls = {"n": 0}
    real = job_manager.prepare_statevector_dispatch

    def first_slow(qasm, apply_preprocessing):
        calls["n"] += 1
        return prep_probes.marked_slow_statevector_preparation if calls["n"] == 1 else real

    original_prepare = prep_worker.prepare

    async def prepare(func, qasm, apply_preprocessing):
        if func is real:
            func = first_slow(qasm, apply_preprocessing)
        return await original_prepare(func, qasm, apply_preprocessing)

    monkeypatch.setattr(prep_worker, "prepare", prepare)
    thread, killed = _kill_marked_worker(real_worker)
    tasks = [{"qasm_string": BELL, "name": f"bell{i}"} for i in range(3)]
    env = api.finished(api.batch(tasks))
    thread.join(5)
    assert killed.get("pid")
    assert env["status"] == "completed"
    assert [t["status"] for t in env["progress"]["tasks"]] == ["error", "done", "done"]
    first = env["results"]["benchmark_summary"][0]
    assert first["error"].startswith("The circuit preparation process ended while preparing this circuit")
    assert_no_raw_exception_text(env)
