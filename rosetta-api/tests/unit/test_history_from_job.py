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
