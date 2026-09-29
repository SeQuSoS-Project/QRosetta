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

    r = client.post(f"/history/runs?circuit_id={circuit_id}", json={"result": "ok"}, headers=headers)
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
