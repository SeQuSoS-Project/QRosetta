"""GET /health and GET /ready: no sign-in or rate limit, /health touches nothing, /ready
checks the database and the job spill directory without leaving files or naming
infrastructure, bounds a database that hangs, and reuses a result for a second."""
import logging
import os
import threading

import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from db import database  # noqa: E402
from main import app, _SuppressAlgorithmsFilter  # noqa: E402
from services import job_store, readiness  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, tmp_path):
    spill = tmp_path / "spill"
    spill.mkdir()
    monkeypatch.setattr(job_store, "SPILL_DIR", str(spill))
    readiness.reset()
    yield spill
    readiness.reset()


@pytest.fixture
def client():
    return TestClient(app)


class _BrokenEngine:
    def connect(self):
        raise RuntimeError("could not connect to server at db.internal.example:5432 (10.0.0.7)")


def test_health_answers_without_touching_the_database(client, monkeypatch):
    monkeypatch.setattr(database, "engine", _BrokenEngine())
    resp = client.get("/health", headers={"x-forwarded-for": "203.0.113.9"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.headers["cache-control"] == "no-store"
    assert "x-ratelimit-limit" not in resp.headers


def test_ready_when_the_database_answers_and_the_spill_directory_takes_files(client, _fresh):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "checks": {"database": "ok", "job_storage": "ok"}}
    assert resp.headers["cache-control"] == "no-store"
    assert "x-ratelimit-limit" not in resp.headers
    assert os.listdir(_fresh) == []


def test_not_ready_names_the_check_and_no_infrastructure(client, monkeypatch):
    monkeypatch.setattr(database, "engine", _BrokenEngine())
    resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body == {"detail": "Not ready: the database does not answer.", "status": "not_ready",
                    "checks": {"database": "failed", "job_storage": "ok"}}
    assert "example" not in resp.text and "10.0.0.7" not in resp.text and "5432" not in resp.text


def test_missing_spill_directory_is_not_ready(client, monkeypatch, tmp_path):
    missing = tmp_path / "gone"
    monkeypatch.setattr(job_store, "SPILL_DIR", str(missing))
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["checks"] == {"database": "ok", "job_storage": "failed"}
    assert str(tmp_path) not in resp.text
    assert not missing.exists()


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores directory modes")
def test_read_only_spill_directory_is_not_ready(client, _fresh):
    os.chmod(_fresh, 0o500)
    try:
        resp = client.get("/ready")
    finally:
        os.chmod(_fresh, 0o700)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Not ready: the job storage directory does not accept new files."


def test_a_hanging_database_check_times_out_and_is_not_started_twice(client, monkeypatch):
    release = threading.Event()
    calls = []

    def hang():
        calls.append(1)
        release.wait(10)

    monkeypatch.setitem(readiness.CHECKS, "database", hang)
    monkeypatch.setattr(readiness, "CHECK_TIMEOUT_SEC", 0.1)
    monkeypatch.setattr(readiness, "REUSE_SEC", 0.0)
    try:
        for _ in range(3):
            resp = client.get("/ready")
            assert resp.status_code == 503
            assert resp.json()["checks"] == {"database": "timeout", "job_storage": "ok"}
        assert len(calls) == 1
    finally:
        release.set()


def test_a_result_is_reused_for_a_second(client, monkeypatch):
    calls = []
    monkeypatch.setitem(readiness.CHECKS, "database", lambda: calls.append(1))
    assert client.get("/ready").status_code == 200
    assert client.get("/ready").status_code == 200
    assert len(calls) == 1
    readiness.reset()
    assert client.get("/ready").status_code == 200
    assert len(calls) == 2


def test_probe_access_lines_are_dropped_from_the_log():
    quiet = _SuppressAlgorithmsFilter()

    def kept(line):
        return quiet.filter(logging.LogRecord("uvicorn.access", logging.INFO, "", 0, line, None, None))

    assert not kept('127.0.0.1:5 - "GET /health HTTP/1.1" 200')
    assert not kept('127.0.0.1:5 - "GET /ready HTTP/1.1" 200')
    assert kept('127.0.0.1:5 - "GET /ready HTTP/1.1" 503')
    assert kept('127.0.0.1:5 - "GET /healthz HTTP/1.1" 200')



def test_compose_and_rahti_probe_the_health_routes():
    import yaml
    from pathlib import Path
    repo = Path(__file__).resolve().parents[3]
    compose = yaml.safe_load((repo / "docker-compose.yml").read_text())
    assert "http://localhost:8000/health'" in " ".join(compose["services"]["api"]["healthcheck"]["test"])
    rahti = yaml.safe_load((repo / "infra" / "rahti" / "api.yaml").read_text())
    container = rahti["items"][0]["spec"]["template"]["spec"]["containers"][0]
    assert container["startupProbe"]["httpGet"]["path"] == "/health"
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["readinessProbe"]["httpGet"]["path"] == "/ready"
    liveness = container["livenessProbe"]
    assert liveness["periodSeconds"] * liveness["failureThreshold"] > 330
