"""Regression test for POST /history/runs/{run_id}/export.

The history export assembled its own ExportContext rather than sharing the one in
routers/export.py, and its copy omitted publication_artifacts. A caller who asked for
figures and tables got a bundle without them and no error. This test pins the field
through the router so the two export paths cannot drift apart again.
"""
import uuid
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db.models as models
from db.database import Base, get_db
from routers import auth, history

_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
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


def _auth_headers(client, email):
    client.post("/auth/register", json={"email": email, "password": "testpass123"})
    r = client.post("/auth/token", data={"username": email, "password": "testpass123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_run(email):
    """Insert a run history row owned by the given user and return its id."""
    db = _TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).one()
        run_id = str(uuid.uuid4())
        run = models.RunHistory(
            id=run_id,
            user_id=user.id,
            run_name="pinned run",
            s3_object_key=f"runs/{run_id}.json",
        )
        db.add(run)
        db.commit()
        return run.id
    finally:
        db.close()


_REPORT = {"input_qasm": "OPENQASM 2.0;\nqreg q[2];\n", "raw_results": []}


def test_history_export_forwards_publication_artifacts(client):
    headers = _auth_headers(client, "export-artifacts@example.com")
    run_id = _seed_run("export-artifacts@example.com")

    selection = {
        "categories": ["agreement", "performance"],
        "figure_formats": ["svg", "png"],
        "table_formats": ["csv"],
    }

    with patch("routers.history.fetch_run_report", return_value=_REPORT), \
            patch("routers.history.build_ro_crate", return_value=b"ZIP") as mock_build:
        resp = client.post(
            f"/history/runs/{run_id}/export",
            json={"include_statevectors": False, "publication_artifacts": selection},
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    ctx = mock_build.call_args.args[0]
    assert ctx.publication_artifacts is not None, "publication_artifacts was dropped"
    assert ctx.publication_artifacts["categories"] == ["agreement", "performance"]
    assert ctx.publication_artifacts["figure_formats"] == ["svg", "png"]
    assert ctx.publication_artifacts["table_formats"] == ["csv"]


def test_history_export_without_artifacts_passes_none(client):
    headers = _auth_headers(client, "export-plain@example.com")
    run_id = _seed_run("export-plain@example.com")

    with patch("routers.history.fetch_run_report", return_value=_REPORT), \
            patch("routers.history.build_ro_crate", return_value=b"ZIP") as mock_build:
        resp = client.post(
            f"/history/runs/{run_id}/export",
            json={"include_statevectors": False},
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    assert mock_build.call_args.args[0].publication_artifacts is None
