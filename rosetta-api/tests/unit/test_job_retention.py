"""Job retention: QROSETTA_JOB_TTL_SEC (limits.job_ttl_sec), 24 hours in the local compose
file, and oldest-first eviction of finished jobs when the job storage crosses a limit."""
import asyncio
import re
import time
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

pytest.importorskip("pytket")

import services.job_manager as job_manager  # noqa: E402
from config import Settings, settings  # noqa: E402
from services import job_store  # noqa: E402
from services.job_store import retention_text  # noqa: E402
from tests.unit.frontend_harness import call_js, requires_node  # noqa: E402

_REPO = Path(__file__).resolve().parents[3]
_JS = Path(__file__).resolve().parents[2] / "static" / "js"


@pytest.fixture(autouse=True)
def spill_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    yield
    for job_id in [j for j in job_manager.ACTIVE_JOBS if str(j).startswith("rt-")]:
        job_manager.ACTIVE_JOBS.pop(job_id, None)


def test_ttl_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("QROSETTA_JOB_TTL_SEC", "86400")
    assert Settings().JOB_TTL_SEC == 86400
    monkeypatch.delenv("QROSETTA_JOB_TTL_SEC")
    assert Settings().JOB_TTL_SEC == 1800
    monkeypatch.setenv("QROSETTA_JOB_TTL_SEC", "5")
    assert Settings().JOB_TTL_SEC == 60


def test_local_compose_keeps_jobs_for_a_day():
    compose = yaml.safe_load((_REPO / "docker-compose.yml").read_text())
    env = compose["services"]["api"]["environment"]
    assert "QROSETTA_JOB_TTL_SEC=${QROSETTA_JOB_TTL_SEC:-86400}" in env


def test_config_publishes_the_retention():
    from fastapi.testclient import TestClient
    from main import app
    limits = TestClient(app).get("/config").json()["limits"]
    assert limits["job_ttl_sec"] == settings.JOB_TTL_SEC
    assert limits["job_evictable_after_sec"] == settings.JOB_EVICTABLE_AFTER_SEC


def test_expiry_follows_the_setting(monkeypatch):
    now = time.time()
    job_manager.ACTIVE_JOBS["rt-old"] = {"status": "completed", "target": "local",
                                         "finished_at": now - 7200}
    monkeypatch.setattr(settings, "JOB_TTL_SEC", 86400)
    assert "rt-old" not in job_manager.expired_job_ids(now)
    monkeypatch.setattr(settings, "JOB_TTL_SEC", 1800)
    assert "rt-old" in job_manager.expired_job_ids(now)


def _jobs(now):
    job_manager.ACTIVE_JOBS["rt-a"] = {"status": "completed", "target": "local", "finished_at": now - 5000}
    job_manager.ACTIVE_JOBS["rt-b"] = {"status": "failed", "target": "local", "finished_at": now - 9000}
    job_manager.ACTIVE_JOBS["rt-recent"] = {"status": "completed", "target": "local", "finished_at": now - 60}
    job_manager.ACTIVE_JOBS["rt-running"] = {"status": "processing", "target": "local", "submitted_at": now - 9999}


def test_full_storage_evicts_finished_jobs_oldest_first(monkeypatch):
    _jobs(time.time())
    evicted = []
    real_pop = dict.pop

    def problem():
        return None if len(evicted) >= 2 else "full"

    def remove(job_id):
        evicted.append(job_id)
    monkeypatch.setattr(job_manager, "storage_problem", problem)
    monkeypatch.setattr(job_manager, "remove_job_files", remove)
    assert asyncio.run(job_manager.make_room_for_results()) is None
    assert evicted == ["rt-b", "rt-a"]
    assert "rt-recent" in job_manager.ACTIVE_JOBS and "rt-running" in job_manager.ACTIVE_JOBS
    assert real_pop is dict.pop


def test_storage_still_full_after_eviction_is_a_503(monkeypatch):
    _jobs(time.time())
    monkeypatch.setattr(job_manager, "storage_problem", lambda: "full")
    monkeypatch.setattr(job_manager, "remove_job_files", lambda job_id: None)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(job_manager.require_job_storage())
    assert caught.value.status_code == 503
    assert "rt-recent" in job_manager.ACTIVE_JOBS and "rt-running" in job_manager.ACTIVE_JOBS
    assert "rt-a" not in job_manager.ACTIVE_JOBS and "rt-b" not in job_manager.ACTIVE_JOBS


def test_no_problem_evicts_nothing(monkeypatch):
    _jobs(time.time())
    monkeypatch.setattr(job_manager, "storage_problem", lambda: None)
    asyncio.run(job_manager.require_job_storage())
    assert {"rt-a", "rt-b"} <= set(job_manager.ACTIVE_JOBS)


DURATIONS = [1800, 86400, 3600, 60, 90, 7200, 5400, 1, 59, 120]


def test_retention_text():
    assert [retention_text(s) for s in (1800, 86400, 3600, 90)] == [
        "30 minutes", "24 hours", "1 hour", "90 seconds"]


@requires_node
def test_page_and_server_write_durations_alike():
    got = call_js(["request_limits.js"], [("durationText", [s]) for s in DURATIONS])
    assert got == [retention_text(s) for s in DURATIONS]


def test_page_texts_read_the_retention():
    for name in ("workspace.js", "share_links.js", "history.js", "artifacts_renderer.js",
                 "export_panel.js", "experiment.js"):
        src = (_JS / name).read_text()
        assert not re.search(r"\b30 minutes\b", src), name
    assert "FINISHED_KEEP_MS" not in (_JS / "workspace.js").read_text()
    assert "setFinishedKeepMs(seconds * 1000)" in (_JS / "app.js").read_text()
