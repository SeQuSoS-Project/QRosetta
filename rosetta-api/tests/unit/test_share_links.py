"""Read-only share links: owner-only creation, hashed tokens, expiry and revocation, one 404
for every failing token, and a response holding circuit texts only."""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db.models as models
import services.share_links as share_links
from db.database import Base, get_db
from routers import auth, history, share
from routers.errors import register_error_handlers
from services.security import limiter

REPORT = {
    "input_qasm": "OPENQASM 2.0;\nqreg q[1];\nh q[0];\n",
    "dispatched_circuits": [{"group": "statevector", "qasm": "OPENQASM 2.0;\nqreg q[1];\nh q[0];\n",
                             "api_preprocessing_applied": ["API: round trip"], "runners": ["qiskit"]}],
    "raw_results": [{
        "simulator": "qiskit", "transpiled_qasm": "h q[0];", "dispatch_group": "statevector",
        "gate_count": 1, "circuit_depth": 1, "gate_metrics_basis": "basis",
        "preprocessing_applied": ["API: round trip"], "sdk_versions": {"qiskit": "1.4.4"},
        "dispatch_status": "error", "error": "Traceback (most recent call last): secret path",
        "counts": {"0": 5}, "simulation_time_sec": 0.1, "cpu_environment": {"cpu_model": "x"},
    }],
    "runner_config": {"qiskit": 1},
    "job_id": "job-123",
}


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    import services.storage as storage
    monkeypatch.setattr(storage, "MOCK_S3_DIR", str(tmp_path))
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _get_db():
        db = session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    for router in (auth.router, history.router, share.router):
        app.include_router(router)
    app.dependency_overrides[get_db] = _get_db
    limiter.reset()
    return TestClient(app), session


def _login(client, email):
    client.post("/auth/register", json={"email": email, "password": "testpass123"})
    token = client.post("/auth/token", data={"username": email, "password": "testpass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _saved_run(client, headers, report=REPORT):
    r = client.post("/history/runs", json=report, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _read(client, token):
    return client.post("/shared/circuits", json={"token": token})


def test_owner_creates_a_link_that_serves_circuit_texts_only(app_client):
    client, session = app_client
    owner = _login(client, "owner@example.org")
    run_id = _saved_run(client, owner)
    created = client.post(f"/history/runs/{run_id}/share-links", json={"expires_in_days": 7}, headers=owner)
    assert created.status_code == 201, created.text
    link = created.json()
    assert link["active"] is True and link["run_id"] == run_id and len(link["token"]) == 43
    assert created.headers["cache-control"] == "no-store"

    shared = _read(client, link["token"])
    assert shared.status_code == 200
    body = shared.json()
    assert body["input_qasm"] == REPORT["input_qasm"]
    assert body["dispatched_circuits"] == REPORT["dispatched_circuits"]
    (result,) = body["raw_results"]
    assert result == {"simulator": "qiskit", "dispatch_group": "statevector", "transpiled_qasm": "h q[0];",
                      "gate_metrics_basis": "basis", "dispatch_status": "error", "gate_count": 1,
                      "circuit_depth": 1, "preprocessing_applied": ["API: round trip"],
                      "sdk_versions": {"qiskit": "1.4.4"}}
    assert set(body) == {"input_qasm", "dispatched_circuits", "raw_results", "run_name", "saved_at",
                         "link_expires_at"}
    assert "Traceback" not in shared.text and "job-123" not in shared.text and "owner@" not in shared.text
    assert shared.headers["referrer-policy"] == "no-referrer"


def test_only_the_token_hash_is_stored(app_client):
    client, session = app_client
    owner = _login(client, "hash@example.org")
    token = client.post(f"/history/runs/{_saved_run(client, owner)}/share-links", headers=owner).json()["token"]
    db = session()
    (row,) = db.query(models.ShareLink).all()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in {getattr(row, c.name) for c in models.ShareLink.__table__.columns}
    db.close()
    listed = client.get(f"/history/runs/{row.run_id}/share-links", headers=owner).json()
    assert "token" not in listed[0]


def test_another_account_cannot_create_list_or_revoke(app_client):
    client, _ = app_client
    owner = _login(client, "a@example.org")
    other = _login(client, "b@example.org")
    run_id = _saved_run(client, owner)
    link_id = client.post(f"/history/runs/{run_id}/share-links", headers=owner).json()["id"]
    assert client.post(f"/history/runs/{run_id}/share-links", headers=other).status_code == 404
    assert client.get(f"/history/runs/{run_id}/share-links", headers=other).status_code == 404
    assert client.delete(f"/history/share-links/{link_id}", headers=other).status_code == 404
    assert client.post(f"/history/runs/{run_id}/share-links").status_code == 401


@pytest.mark.parametrize("token", ["", "short", "x" * 43, "a" * 42 + "!", "A" * 64])
def test_malformed_and_unknown_tokens_get_the_same_404(app_client, token):
    client, _ = app_client
    r = _read(client, token)
    assert r.status_code == 404
    assert r.json() == {"detail": "This link does not exist, has expired or was revoked."}


def test_overlong_token_is_rejected_by_validation(app_client):
    client, _ = app_client
    assert _read(client, "a" * 65).status_code == 422


def test_revoked_expired_and_deleted_links_stop_resolving(app_client):
    client, session = app_client
    owner = _login(client, "life@example.org")
    run_id = _saved_run(client, owner)
    revoked = client.post(f"/history/runs/{run_id}/share-links", headers=owner).json()
    expired = client.post(f"/history/runs/{run_id}/share-links", headers=owner).json()
    deleted = client.post(f"/history/runs/{run_id}/share-links", headers=owner).json()

    r = client.delete(f"/history/share-links/{revoked['id']}", headers=owner)
    assert r.status_code == 200 and r.json()["active"] is False and r.json()["revoked_at"]
    assert _read(client, revoked["token"]).status_code == 404

    db = session()
    row = db.query(models.ShareLink).filter(models.ShareLink.id == expired["id"]).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    db.close()
    assert _read(client, expired["token"]).status_code == 404

    assert _read(client, deleted["token"]).status_code == 200
    assert client.request("DELETE", "/history/runs", json={"run_ids": [run_id]}, headers=owner).status_code == 200
    assert _read(client, deleted["token"]).status_code == 404
    db = session()
    assert db.query(models.ShareLink).count() == 0
    db.close()


def test_deactivated_owner_links_stop_resolving(app_client):
    client, session = app_client
    owner = _login(client, "gone@example.org")
    token = client.post(f"/history/runs/{_saved_run(client, owner)}/share-links", headers=owner).json()["token"]
    db = session()
    db.query(models.User).filter(models.User.email == "gone@example.org").one().is_active = False
    db.commit()
    db.close()
    assert _read(client, token).status_code == 404


def test_account_deletion_removes_links(app_client):
    client, session = app_client
    owner = _login(client, "delete@example.org")
    token = client.post(f"/history/runs/{_saved_run(client, owner)}/share-links", headers=owner).json()["token"]
    db = session()
    user = db.query(models.User).filter(models.User.email == "delete@example.org").one()
    from services.accounts import delete_account
    delete_account(db, user)
    assert db.query(models.ShareLink).count() == 0
    db.close()
    assert _read(client, token).status_code == 404


def test_expiry_is_bounded_and_active_links_are_capped(app_client, monkeypatch):
    client, _ = app_client
    owner = _login(client, "cap@example.org")
    run_id = _saved_run(client, owner)
    for days in (0, 91):
        assert client.post(f"/history/runs/{run_id}/share-links", json={"expires_in_days": days},
                           headers=owner).status_code == 422
    assert client.post(f"/history/runs/{run_id}/share-links", json={"token": "mine"},
                       headers=owner).status_code == 422
    monkeypatch.setattr(share_links, "MAX_ACTIVE_LINKS_PER_RUN", 2)
    ids = [client.post(f"/history/runs/{run_id}/share-links", headers=owner).json()["id"] for _ in range(2)]
    assert client.post(f"/history/runs/{run_id}/share-links", headers=owner).status_code == 409
    client.delete(f"/history/share-links/{ids[0]}", headers=owner)
    assert client.post(f"/history/runs/{run_id}/share-links", headers=owner).status_code == 201


def test_batch_report_shares_each_task(app_client):
    client, _ = app_client
    owner = _login(client, "batch@example.org")
    batch = {"mode": "statevector", "benchmark_summary": [
        {**REPORT, "task_name": "ghz (2q)"}, {"task_name": "failed", "error": "boom", "raw_results": []}]}
    token = client.post(f"/history/runs/{_saved_run(client, owner, batch)}/share-links", headers=owner).json()["token"]
    body = _read(client, token).json()
    assert [t["task_name"] for t in body["benchmark_summary"]] == ["ghz (2q)", "failed"]
    assert body["benchmark_summary"][0]["raw_results"][0]["transpiled_qasm"] == "h q[0];"
    assert "boom" not in str(body)


def test_reading_is_rate_limited(app_client):
    client, _ = app_client
    codes = [_read(client, "x").status_code for _ in range(31)]
    assert codes[:30] == [404] * 30 and codes[30] == 429
