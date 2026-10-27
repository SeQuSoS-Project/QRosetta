"""GET /jobs/{job_id} phase: queued, dispatching, analysing, exporting, done."""
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("pytket")

import services.job_manager as job_manager  # noqa: E402
from services import job_store  # noqa: E402

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


@pytest.fixture(autouse=True)
def spill_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    yield
    for job_id in [j for j in job_manager.ACTIVE_JOBS if str(j).startswith("ph-")]:
        job_manager.ACTIVE_JOBS.pop(job_id, None)


@pytest.mark.parametrize("job,phase", [
    ({"status": "pending"}, "queued"),
    ({"status": "processing"}, "dispatching"),
    ({"status": "processing", "phase": "analysing"}, "analysing"),
    ({"status": "completed", "phase": "exporting"}, "done"),
    ({"status": "failed"}, "done"),
])
def test_job_phase_from_status(job, phase):
    assert job_manager.job_phase(job) == phase
    assert phase in job_manager.JOB_PHASES


def test_set_phase_outside_a_worker_does_nothing():
    job_manager.ACTIVE_JOBS["ph-idle"] = {"status": "processing", "target": "local"}
    job_manager.set_phase("analysing")
    assert "phase" not in job_manager.ACTIVE_JOBS["ph-idle"]


def test_a_single_run_reports_each_phase_in_order(monkeypatch):
    job_id = "ph-single"
    seen = []

    def note():
        seen.append(job_manager.job_phase(job_manager.ACTIVE_JOBS[job_id]))

    async def prepare(fn, *args):
        return fn(*args)

    async def dispatch(runner_urls, runner_payload=None, timeout_seconds=None, runner_statuses=None):
        note()
        return [{"simulator": n, "statevector": "AAAA", "dispatch_status": "ok"} for n in runner_urls]

    async def compile_circuit(*_a, **_k):
        note()
        return {}

    async def reports(results, thresholds):
        note()
        return {}, {}, {}

    original_store = job_manager.ACTIVE_JOBS.store

    async def store(jid, job):
        if jid == job_id:
            note()
        return await original_store(jid, job)

    monkeypatch.setattr(job_manager.prep_worker, "prepare", prepare)
    monkeypatch.setattr(job_manager, "dispatch_to_runners", dispatch)
    monkeypatch.setattr(job_manager, "compile_circuit", compile_circuit)
    monkeypatch.setattr(job_manager, "compile_comparison_reports", reports)
    monkeypatch.setattr(job_manager.ACTIVE_JOBS, "store", store)

    job_manager.ACTIVE_JOBS[job_id] = job_manager.new_job()
    note()
    asyncio.run(job_manager.worker_compare(job_id, QASM, 0, {}, 60, ["qiskit", "cirq"], "local"))
    note()
    assert seen == ["queued", "dispatching", "dispatching", "analysing", "exporting", "done"]


def test_job_envelope_carries_the_phase(monkeypatch):
    from routers import benchmark
    app = FastAPI()
    app.include_router(benchmark.router)
    job_manager.ACTIVE_JOBS["ph-route"] = {**job_manager.new_job(), "status": "processing",
                                           "phase": "analysing"}
    body = TestClient(app).get("/jobs/ph-route").json()
    assert body["phase"] == "analysing" and body["status"] == "processing"
