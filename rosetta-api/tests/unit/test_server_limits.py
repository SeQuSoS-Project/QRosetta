"""Server limits: the playlist length cap and the job storage budget."""
import asyncio
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config import settings
from services import job_store

H = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
QASM = H + "qreg q[2];\nh q[0];\ncx q[0],q[1];\n"
GHZ = {"algorithm": "ghz", "qubits": 2}


@pytest.fixture
def client(monkeypatch):
    from routers import benchmark, experiment, frontend
    from routers.errors import register_error_handlers
    from services.security import limiter

    monkeypatch.setattr(limiter, "enabled", False)
    started = []

    def fake_add_task(self, func, *args, **kwargs):
        started.append((func.__name__, args))
    monkeypatch.setattr("fastapi.BackgroundTasks.add_task", fake_add_task)

    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    for module in (benchmark, experiment, frontend):
        app.include_router(module.router)
    c = TestClient(app)
    c.started = started
    return c


def test_playlist_over_the_task_limit_is_refused_unless_bypassed(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_BATCH_TASKS", 3)
    body = {"tasks": [GHZ] * 4, "mode": "measured"}
    r = client.post("/run_batch_suite", json=body)
    assert r.status_code == 400
    assert "Playlist too long: 4 circuits" in r.json()["detail"] and "max_batch_tasks" in r.json()["detail"]
    assert not client.started
    compile_only = {**body, "simulate": False, "compilers": {"pyzx": [1]}, "mode": "statevector"}
    assert client.post("/run_batch_suite", json=compile_only).status_code == 400
    assert client.post("/run_batch_suite", json={**body, "tasks": [GHZ] * 3}).status_code == 200
    assert client.post("/run_batch_suite", json={**body, "bypass_limits": True}).status_code == 200


def test_default_task_limit_holds_both_bundled_suites():
    from services import benchmark_library as bl
    bundled = sum(len(sizes) for sizes in bl.list_mqt().values()) + len(bl.list_qasmbench())
    assert settings.MAX_BATCH_TASKS >= bundled


@pytest.fixture
def spill_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path))
    return tmp_path


def test_storage_problem_names_the_budget(spill_dir, monkeypatch):
    monkeypatch.setattr(settings, "JOB_SPILL_MAX_MIB", 1)
    monkeypatch.setattr(settings, "JOB_SPILL_MIN_FREE_MIB", 0)
    assert job_store.storage_problem() is None
    (spill_dir / "job").mkdir()
    (spill_dir / "job" / "task-00000.pickle").write_bytes(b"x" * (1024 * 1024))
    problem = job_store.storage_problem()
    assert "1 MiB" in problem and "job_storage_max_mib" in problem


def test_storage_problem_names_the_free_space_floor(spill_dir, monkeypatch):
    monkeypatch.setattr(settings, "JOB_SPILL_MAX_MIB", 10**9)
    monkeypatch.setattr(settings, "JOB_SPILL_MIN_FREE_MIB", 10**12)
    problem = job_store.storage_problem()
    assert "low on disk space" in problem and "job_storage_min_free_mib" in problem


def test_a_full_store_refuses_new_runs_with_503(client, monkeypatch):
    import services.job_manager as job_manager
    monkeypatch.setattr(job_manager, "storage_problem", lambda: "The server's storage for job results is full.")
    for path, body in [("/compare", {"qasm_string": QASM}), ("/compare_measured", {"qasm_string": QASM}),
                       ("/run_batch_suite", {"tasks": [GHZ], "mode": "statevector"}),
                       ("/experiments", {"circuits": [GHZ]})]:
        r = client.post(path, json=body)
        assert r.status_code == 503, path
        assert r.json()["detail"] == "The server's storage for job results is full."
        assert int(r.headers["Retry-After"]) == job_manager.STORAGE_RETRY_AFTER_SEC
    assert not client.started


def test_task_report_is_not_written_over_the_budget(spill_dir, monkeypatch):
    monkeypatch.setattr(job_store, "storage_problem", lambda: "full")
    with pytest.raises(job_store.JobStorageFull, match="full"):
        job_store.spill_task_report("job-x", 0, {"a": 1})
    assert not os.path.exists(job_store.job_dir("job-x"))


def test_batch_stops_and_names_the_limit_when_the_store_fills(spill_dir, monkeypatch):
    import services.job_manager as job_manager
    from schemas import BatchPayload

    async def fake_run(qasm, *args, **kwargs):
        return {"input_qasm": qasm, "raw_results": [{"simulator": "qiskit", "dispatch_status": "ok"}]}
    monkeypatch.setattr(job_manager, "run_single_circuit_comparison", fake_run)
    writes = []

    def fake_storage_problem():
        writes.append(1)
        return "The server's storage for job results is full: limit 5 MiB." if len(writes) > 1 else None
    monkeypatch.setattr(job_store, "storage_problem", fake_storage_problem)

    payload = BatchPayload(tasks=[{"algorithm": "c", "qasm_string": QASM}] * 3, mode="statevector")
    job_id = "batch-storage-full"
    job_manager.ACTIVE_JOBS[job_id] = job_manager.new_job()
    try:
        asyncio.run(job_manager.worker_batch_suite(job_id, payload))
        job = job_manager.ACTIVE_JOBS[job_id]
        assert job["status"] == "failed"
        assert job["error"].startswith("The batch stopped at circuit 2 of 3")
        assert "limit 5 MiB" in job["error"]
        assert [t["status"] for t in job["progress"]["tasks"]] == ["done", "error", "queued"]
        assert not os.path.exists(job_store.job_dir(job_id))
    finally:
        job_manager.ACTIVE_JOBS.pop(job_id, None)
