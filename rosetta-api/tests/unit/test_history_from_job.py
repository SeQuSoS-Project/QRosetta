"""POST /history/runs/from_job/{job_id} and the timestamps of saved runs."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import services.job_manager as job_manager
from db.database import Base, get_db
from routers import auth, history
from routers.errors import register_error_handlers

_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def _get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    import services.storage as storage
    monkeypatch.setattr(storage, "MOCK_S3_DIR", str(tmp_path))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(history.router)
    app.dependency_overrides[get_db] = _get_db
    c = TestClient(app)
    c.post("/auth/register", json={"email": "hist@example.org", "password": "testpass123"})
    token = c.post("/auth/token", data={"username": "hist@example.org",
                                        "password": "testpass123"}).json()["access_token"]
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


def _job(job_id, report, status="completed"):
    job = job_manager._completed_job("local", report, {})
    job["status"] = status
    job_manager.ACTIVE_JOBS[job_id] = job
    return job


def test_saves_batch_from_the_server_copy_without_statevectors(client):
    report = {"mode": "statevector", "benchmark_summary": [
        {"task_name": f"ghz ({n}q)", "raw_results": [{"simulator": "qiskit", "statevector": "A" * 5000}]}
        for n in range(4)]}
    _job("batch-job-1234", report)
    try:
        r = client.post("/history/runs/from_job/batch-job-1234", json={"name": "my batch"})
        assert r.status_code == 201, r.text
        run = r.json()
        assert run["run_name"] == "my batch" and run["created_at"].endswith("Z")
        saved = client.get(f"/history/runs/{run['id']}").json()
        assert saved["run_id"] == run["id"] and saved["created_at"] == run["created_at"]
        assert saved["statevector_storage"] == "removed_before_storage"
        assert saved["job_id"] == "batch-job-1234"
        assert "statevector" not in saved["benchmark_summary"][0]["raw_results"][0]
        listed = client.get("/history/runs").json()
        assert listed[0]["created_at"].endswith("Z")
    finally:
        del job_manager.ACTIVE_JOBS["batch-job-1234"]


def test_default_name_and_empty_body(client):
    _job("measured-job-5678", {"n_shots": 10, "raw_results": []})
    try:
        r = client.post("/history/runs/from_job/measured-job-5678")
        assert r.status_code == 201 and r.json()["run_name"] == "measured run measured"
    finally:
        del job_manager.ACTIVE_JOBS["measured-job-5678"]


def test_rejects_unknown_unfinished_and_experiment_jobs(client):
    assert client.post("/history/runs/from_job/nope", json={}).status_code == 404
    job_manager.ACTIVE_JOBS["running"] = job_manager.new_job()
    job_manager.ACTIVE_JOBS["exp"] = {"status": "completed", "kind": "experiment", "bundle_files": {}}
    try:
        assert client.post("/history/runs/from_job/running", json={}).status_code == 409
        r = client.post("/history/runs/from_job/exp", json={})
        assert r.status_code == 409 and "bundle" in r.json()["detail"]
        assert client.post("/history/runs/from_job/running", json={"nam": "x"}).status_code == 422
    finally:
        del job_manager.ACTIVE_JOBS["running"], job_manager.ACTIVE_JOBS["exp"]


def test_requires_authentication(client):
    client.headers.pop("Authorization")
    assert client.post("/history/runs/from_job/anything", json={}).status_code == 401


def test_saving_the_same_job_twice_returns_the_first_run(client):
    _job("dup-job-0001", {"n_shots": 10, "raw_results": []})
    try:
        first = client.post("/history/runs/from_job/dup-job-0001")
        second = client.post("/history/runs/from_job/dup-job-0001", json={"name": "again"})
        assert first.status_code == 201 and second.status_code == 200
        assert second.json()["id"] == first.json()["id"]
        assert len(client.get("/history/runs").json()) == len(
            {r["id"] for r in client.get("/history/runs").json()})
        assert sum(r["id"] == first.json()["id"] for r in client.get("/history/runs").json()) == 1
        client.request("DELETE", "/history/runs", json={"run_ids": [first.json()["id"]]})
        third = client.post("/history/runs/from_job/dup-job-0001")
        assert third.status_code == 201 and third.json()["id"] != first.json()["id"]
    finally:
        del job_manager.ACTIVE_JOBS["dup-job-0001"]


def test_run_name_is_accepted_and_name_is_an_alias(client):
    _job("named-job-0001", {"n_shots": 10, "raw_results": []})
    _job("named-job-0002", {"n_shots": 10, "raw_results": []})
    try:
        r = client.post("/history/runs/from_job/named-job-0001", json={"run_name": "via run_name"})
        assert r.status_code == 201 and r.json()["run_name"] == "via run_name"
        assert r.json()["job_id"] == "named-job-0001"
        r = client.post("/history/runs/from_job/named-job-0002", json={"name": "via name"})
        assert r.status_code == 201 and r.json()["run_name"] == "via name"
        again = client.post("/history/runs/from_job/named-job-0002")
        assert again.status_code == 200 and again.json()["job_id"] == "named-job-0002"
    finally:
        del job_manager.ACTIVE_JOBS["named-job-0001"], job_manager.ACTIVE_JOBS["named-job-0002"]


def test_concurrent_saves_of_one_job_store_one_run(monkeypatch):
    import threading
    import time
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from fastapi import Response
    import routers.history as history_router
    import services.history as history_service

    stored = {}

    def slow_save(db, user_id, payload, circuit_id=None, saved_from=None):
        time.sleep(0.2)
        run = SimpleNamespace(id=f"run-{len(stored)}", user_id=user_id, run_name=payload["run_name"], job_id=payload.get("job_id"),
                              created_at=datetime.now(timezone.utc))
        stored[run.id] = run
        return run
    monkeypatch.setattr(history_service, "save_run", slow_save)
    monkeypatch.setattr(history_service, "find_run_for_job",
                        lambda db, uid, jid: next((r for r in stored.values() if r.job_id == jid), None))
    user = SimpleNamespace(id=1)
    _job("race-job-0001", {"n_shots": 10, "raw_results": []})
    codes, ids = [], []

    def save():
        response = Response(status_code=201)
        run = history_router.save_run_from_job("race-job-0001", response, None, None, user)
        codes.append(response.status_code)
        ids.append(run.id)
    try:
        threads = [threading.Thread(target=save) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(stored) == 1 and len(set(ids)) == 1
        assert sorted(codes) == [200] * 5 + [201]
    finally:
        del job_manager.ACTIVE_JOBS["race-job-0001"]


@pytest.mark.parametrize("body", [
    {"result": "ok"},
    {"raw_results": "notalist"},
    {"raw_results": [1, 2]},
    {"raw_results": [], "divergence_report": "x"},
    {"benchmark_summary": "x"},
    {"benchmark_summary": [{"raw_results": "x"}]},
])
def test_client_supplied_report_is_validated(client, body):
    r = client.post("/history/runs", json=body)
    assert r.status_code == 422, r.text
    assert isinstance(r.json()["detail"], list) and r.json()["detail"][0]["msg"]


@pytest.mark.parametrize("body", [
    {"raw_results": [{"simulator": "qiskit"}], "divergence_report": {}},
    {"benchmark_summary": [{"task_name": "t", "error": "failed"}, {"raw_results": []}]},
])
def test_valid_client_reports_are_stored(client, body):
    assert client.post("/history/runs", json=body).status_code == 201


def test_owner_survives_completion_and_only_the_owner_can_save(client):
    other = TestClient(client.app)
    other.post("/auth/register", json={"email": "thief@example.org", "password": "testpass123"})
    token = other.post("/auth/token", data={"username": "thief@example.org", "password": "testpass123"}).json()["access_token"]
    other.headers.update({"Authorization": f"Bearer {token}"})
    owner_id = client.get("/auth/me").json()["id"]
    job_manager.ACTIVE_JOBS["owned-job-1"] = job_manager.new_job("local", owner_id)
    job_manager.ACTIVE_JOBS["owned-job-1"] = job_manager._completed_job("local", {"raw_results": []}, {})
    try:
        assert job_manager.ACTIVE_JOBS["owned-job-1"]["owner_user_id"] == owner_id
        r = other.post("/history/runs/from_job/owned-job-1")
        assert r.status_code == 403 and "another signed-in account" in r.json()["detail"]
        assert client.post("/history/runs/from_job/owned-job-1").status_code == 201
    finally:
        del job_manager.ACTIVE_JOBS["owned-job-1"]


def test_an_anonymous_job_can_be_saved_by_any_account(client):
    job_manager.ACTIVE_JOBS["anon-job-1"] = job_manager.new_job("local", None)
    job_manager.ACTIVE_JOBS["anon-job-1"] = job_manager._completed_job("local", {"raw_results": []}, {})
    try:
        assert client.post("/history/runs/from_job/anon-job-1").status_code == 201
    finally:
        del job_manager.ACTIVE_JOBS["anon-job-1"]


def test_a_job_whose_report_files_are_gone_is_404(client):
    import os
    _job("expired-job-1", {"raw_results": []})
    os.remove(job_manager.ACTIVE_JOBS["expired-job-1"]["full_results"].path)
    try:
        r = client.post("/history/runs/from_job/expired-job-1")
        assert r.status_code == 404 and r.json()["detail"] == job_manager.JOB_NOT_FOUND
    finally:
        del job_manager.ACTIVE_JOBS["expired-job-1"]


def test_a_job_evicted_after_its_report_is_read_is_still_saved(client, monkeypatch):
    _job("evicted-job-1", {"raw_results": [{"simulator": "qiskit", "statevector": "A" * 64}]})
    real = job_manager.full_report

    def read_then_evict(job, each_task=None):
        report = real(job, each_task)
        job_manager.ACTIVE_JOBS.pop("evicted-job-1")
        return report
    monkeypatch.setattr(job_manager, "full_report", read_then_evict)
    r = client.post("/history/runs/from_job/evicted-job-1")
    assert r.status_code == 201, r.text
    assert "evicted-job-1" not in job_manager.ACTIVE_JOBS
