"""DELETE /auth/me removes an account with saved circuits and run history without a
foreign-key violation. SQLite runs with PRAGMA foreign_keys=ON to enforce the constraint
as Postgres does.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from routers import auth, history

_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@event.listens_for(_engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def _override_get_db():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(history.router)
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def _register_and_login(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert r.status_code == 201, r.text
    r = client.post("/auth/token", data={"username": email, "password": "testpass123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_delete_account_with_saved_circuit_and_run_history_succeeds(client, tmp_path, monkeypatch):
    monkeypatch.setattr("services.storage.MOCK_S3_DIR", str(tmp_path))
    headers = _register_and_login(client, "delete-me-1@example.com")

    r = client.post("/history/circuits", json={"name": "c1", "qasm_string": "OPENQASM 2.0;"},
                     headers=headers)
    assert r.status_code == 201, r.text
    circuit_id = r.json()["id"]

    r = client.post(f"/history/runs?circuit_id={circuit_id}", json={"raw_results": []}, headers=headers)
    assert r.status_code == 201, r.text

    r = client.delete("/auth/me", headers=headers)
    assert r.status_code == 204, r.text

    r = client.post("/auth/token", data={"username": "delete-me-1@example.com", "password": "testpass123"})
    assert r.status_code == 401


def test_delete_account_with_only_a_saved_circuit_succeeds(client, monkeypatch, tmp_path):
    monkeypatch.setattr("services.storage.MOCK_S3_DIR", str(tmp_path))
    headers = _register_and_login(client, "delete-me-2@example.com")

    r = client.post("/history/circuits", json={"name": "c1", "qasm_string": "OPENQASM 2.0;"},
                     headers=headers)
    assert r.status_code == 201, r.text

    r = client.delete("/auth/me", headers=headers)
    assert r.status_code == 204, r.text


def test_delete_account_with_no_saved_data_succeeds(client):
    headers = _register_and_login(client, "delete-me-3@example.com")
    r = client.delete("/auth/me", headers=headers)
    assert r.status_code == 204, r.text


def _save_circuit(client, headers):
    r = client.post("/history/circuits", json={"name": "c1", "qasm_string": "OPENQASM 2.0;"},
                    headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _stored_reports(tmp_path):
    return sorted(p.name for p in tmp_path.rglob("*.json"))


def test_run_cannot_link_another_accounts_circuit(client, tmp_path, monkeypatch):
    monkeypatch.setattr("services.storage.MOCK_S3_DIR", str(tmp_path))
    owner = _register_and_login(client, "link-owner@example.com")
    other = _register_and_login(client, "link-other@example.com")
    circuit_id = _save_circuit(client, owner)

    r = client.post(f"/history/runs?circuit_id={circuit_id}", json={"raw_results": []}, headers=other)
    assert r.status_code == 404 and r.json()["detail"] == "Saved circuit not found"
    r = client.post("/history/runs?circuit_id=no-such-id", json={"raw_results": []}, headers=other)
    assert r.status_code == 404
    assert _stored_reports(tmp_path) == []
    assert client.get("/history/runs", headers=other).json() == []

    assert client.delete("/auth/me", headers=owner).status_code == 204


def test_owner_can_delete_account_when_another_run_names_its_circuit(client, tmp_path, monkeypatch):
    import db.models as models
    monkeypatch.setattr("services.storage.MOCK_S3_DIR", str(tmp_path))
    owner = _register_and_login(client, "legacy-owner@example.com")
    other = _register_and_login(client, "legacy-other@example.com")
    circuit_id = _save_circuit(client, owner)
    run_id = client.post("/history/runs", json={"raw_results": []}, headers=other).json()["id"]
    db = _TestingSessionLocal()
    db.query(models.RunHistory).filter(models.RunHistory.id == run_id).update(
        {models.RunHistory.circuit_id: circuit_id})
    db.commit()
    db.close()

    assert client.delete("/auth/me", headers=owner).status_code == 204
    runs = client.get("/history/runs", headers=other).json()
    assert [(r["id"], r["circuit_id"]) for r in runs] == [(run_id, None)]


def test_failed_report_deletion_leaves_the_account_intact(client, tmp_path, monkeypatch):
    monkeypatch.setattr("services.storage.MOCK_S3_DIR", str(tmp_path))
    headers = _register_and_login(client, "s3-fails@example.com")
    assert client.post("/history/runs", json={"raw_results": []}, headers=headers).status_code == 201

    def fail(keys):
        raise RuntimeError("storage down")
    monkeypatch.setattr("services.accounts.delete_run_reports", fail)
    r = client.delete("/auth/me", headers=headers)
    assert r.status_code == 500 and r.json()["detail"] == "Failed to delete stored run reports"
    assert len(client.get("/history/runs", headers=headers).json()) == 1
    assert len(_stored_reports(tmp_path)) == 1


def test_failed_database_step_keeps_the_stored_reports(client, tmp_path, monkeypatch):
    monkeypatch.setattr("services.storage.MOCK_S3_DIR", str(tmp_path))
    headers = _register_and_login(client, "db-fails@example.com")
    assert client.post("/history/runs", json={"raw_results": []}, headers=headers).status_code == 201

    def fail(db, run_ids):
        raise RuntimeError("database down")
    monkeypatch.setattr("services.accounts.delete_links", fail)
    assert client.delete("/auth/me", headers=headers).status_code == 500
    assert len(client.get("/history/runs", headers=headers).json()) == 1
    assert len(_stored_reports(tmp_path)) == 1


def test_failed_report_deletion_keeps_the_run_rows(client, tmp_path, monkeypatch):
    monkeypatch.setattr("services.storage.MOCK_S3_DIR", str(tmp_path))
    headers = _register_and_login(client, "batch-delete@example.com")
    run_id = client.post("/history/runs", json={"raw_results": []}, headers=headers).json()["id"]

    def fail(keys):
        raise RuntimeError("storage down")
    monkeypatch.setattr("services.history.delete_run_reports", fail)
    r = client.request("DELETE", "/history/runs", json={"run_ids": [run_id]}, headers=headers)
    assert r.status_code == 500
    assert [run["id"] for run in client.get("/history/runs", headers=headers).json()] == [run_id]


def test_failed_row_deletion_keeps_the_stored_reports(client, tmp_path, monkeypatch):
    monkeypatch.setattr("services.storage.MOCK_S3_DIR", str(tmp_path))
    headers = _register_and_login(client, "batch-delete-db@example.com")
    run_id = client.post("/history/runs", json={"raw_results": []}, headers=headers).json()["id"]

    def fail(db, run_ids):
        raise RuntimeError("database down")
    monkeypatch.setattr("services.history.delete_links", fail)
    r = client.request("DELETE", "/history/runs", json={"run_ids": [run_id]}, headers=headers)
    assert r.status_code == 500
    assert [run["id"] for run in client.get("/history/runs", headers=headers).json()] == [run_id]
    assert len(_stored_reports(tmp_path)) == 1
