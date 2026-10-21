"""A client-supplied report whose fields hold values of the wrong type is a 400 on the
publication, export and saved-run export routes; the server's own copy of a job keeps
its 500. A report holding NaN or Infinity is refused before it is stored or read."""
import copy
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

pytest.importorskip("pytket")

import services.job_manager as job_manager  # noqa: E402
from db.database import Base, get_db  # noqa: E402
from routers import auth, export, history, publication  # noqa: E402
from routers.errors import register_error_handlers  # noqa: E402
from services.security import limiter  # noqa: E402
from tests.unit.test_publication import MEASURED  # noqa: E402

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
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
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    for module in (auth, history, export, publication):
        app.include_router(module.router)
    app.dependency_overrides[get_db] = _get_db
    return TestClient(app, raise_server_exceptions=False)


def _string_in_matrix():
    report = copy.deepcopy(MEASURED)
    report["divergence_report"]["statistical_distance_matrix (js_divergence)"][0][1] = "N"
    return report


def _string_count():
    report = copy.deepcopy(MEASURED)
    report["raw_results"][0].update(counts={"001": "many"}, qubit_ordering="lsb")
    return report


def _registry_entry_null():
    return {**copy.deepcopy(MEASURED), "runner_registry": {"qiskit": None}}


HEATMAP = "js_divergence_heatmap"


def _is_unreadable(response):
    return (response.status_code == 400
            and response.json()["detail"].startswith("Invalid report: a field holds a value of the wrong type"))


def test_render_of_a_supplied_report_with_a_string_in_a_matrix_is_400(client):
    ok = client.post("/publication/render", json={"results": MEASURED, "artifact_id": HEATMAP, "format": "svg"})
    assert ok.status_code == 200
    bad = client.post("/publication/render",
                      json={"results": _string_in_matrix(), "artifact_id": HEATMAP, "format": "svg"})
    assert _is_unreadable(bad), bad.text


def test_artifact_list_of_a_supplied_report_with_a_string_count_is_400(client):
    assert _is_unreadable(client.post("/publication/artifacts", json={"results": _string_count()}))


def test_unknown_artifact_is_still_404(client):
    r = client.post("/publication/render", json={"results": MEASURED, "artifact_id": "nope", "format": "svg"})
    assert r.status_code == 404 and "Unknown artifact" in r.json()["detail"]


def test_export_of_a_supplied_report_with_a_null_registry_entry_is_400(client):
    assert client.post("/export", json={"results": MEASURED}).status_code == 200
    assert _is_unreadable(client.post("/export", json={"results": _registry_entry_null()}))


def test_export_of_an_uploaded_run_with_a_null_registry_entry_is_400(client):
    client.post("/auth/register", json={"email": "shapes@example.org", "password": "testpass123"})
    token = client.post("/auth/token", data={"username": "shapes@example.org",
                                             "password": "testpass123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    run = client.post("/history/runs", json=_registry_entry_null(), headers=headers)
    assert run.status_code == 201, run.text
    assert _is_unreadable(client.post(f"/history/runs/{run.json()['id']}/export", headers=headers))


def test_server_copy_of_a_job_keeps_its_500(client):
    job_id = "shape-job-0001"
    job_manager.ACTIVE_JOBS[job_id] = job_manager._completed_job("local", _string_in_matrix(), {})
    try:
        r = client.post(f"/jobs/{job_id}/publication/render",
                        json={"artifact_id": HEATMAP, "format": "svg"})
        assert r.status_code == 500
    finally:
        job_manager.ACTIVE_JOBS.pop(job_id, None)


def _post_raw(client, path, body, headers=None):
    return client.post(path, content=json.dumps(body, allow_nan=True).encode(),
                       headers={"Content-Type": "application/json", **(headers or {})})


def _nan_time():
    report = copy.deepcopy(MEASURED)
    report["performance_report"]["ranking"][1]["simulation_time_sec"] = float("nan")
    return report


@pytest.mark.parametrize("path", ["/export", "/publication/artifacts"])
def test_non_finite_numbers_in_a_supplied_report_are_400(client, path):
    r = _post_raw(client, path, {"results": _nan_time()})
    assert r.status_code == 400
    assert "performance_report.ranking[1].simulation_time_sec is NaN or infinite" in r.json()["detail"]
    inf = {**copy.deepcopy(MEASURED), "n_shots": float("inf")}
    assert "n_shots is NaN or infinite" in _post_raw(client, path, {"results": inf}).json()["detail"]


def test_a_report_with_nan_is_not_saved(client):
    client.post("/auth/register", json={"email": "nan@example.org", "password": "testpass123"})
    token = client.post("/auth/token", data={"username": "nan@example.org",
                                             "password": "testpass123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = _post_raw(client, "/history/runs", _nan_time(), headers)
    assert r.status_code == 400 and "NaN or infinite" in r.json()["detail"]
    listed = client.get("/history/runs", headers=headers)
    assert listed.status_code == 200 and listed.json() == []
