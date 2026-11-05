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


def test_local_compose_gives_the_api_a_4_gib_job_storage_budget():
    compose = yaml.safe_load((_REPO / "docker-compose.yml").read_text())
    env = compose["services"]["api"]["environment"]
    assert "QROSETTA_JOB_SPILL_MAX_MIB=${QROSETTA_JOB_SPILL_MAX_MIB:-4096}" in env
    assert type(settings).model_fields["JOB_SPILL_MAX_MIB"].default == 10240


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


def test_max_kept_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv("QROSETTA_JOB_MAX_KEPT", raising=False)
    assert Settings().JOB_MAX_KEPT == 200
    monkeypatch.setenv("QROSETTA_JOB_MAX_KEPT", "5000")
    assert Settings().JOB_MAX_KEPT == 5000
    monkeypatch.setenv("QROSETTA_JOB_MAX_KEPT", "0")
    assert Settings().JOB_MAX_KEPT == 1


def test_config_publishes_the_kept_count():
    from fastapi.testclient import TestClient
    from main import app
    limits = TestClient(app).get("/config").json()["limits"]
    assert limits["job_max_kept"] == settings.JOB_MAX_KEPT == 200


def _many(now, finished_ages, unfinished=0):
    for i, age in enumerate(finished_ages):
        job_id = f"rt-f{i:03d}"
        job_manager.ACTIVE_JOBS[job_id] = {"status": "failed" if i % 3 == 0 else "completed",
                                           "target": "local", "finished_at": now - age}
    for i in range(unfinished):
        job_manager.ACTIVE_JOBS[f"rt-u{i:03d}"] = {"status": "processing", "target": "local",
                                                   "submitted_at": now - 99999}


def _ours():
    return {j for j in job_manager.ACTIVE_JOBS if str(j).startswith("rt-")}


def _spill(job_id):
    import os
    os.makedirs(job_store.job_dir(job_id), exist_ok=True)
    with open(job_store._path(job_id), "wb") as fh:
        fh.write(b"x")
    with open(os.path.join(job_store.job_dir(job_id), "task-00000.pickle"), "wb") as fh:
        fh.write(b"x")


def _foreign_finished():
    return sum(1 for j, job in job_manager.ACTIVE_JOBS.items() if not str(j).startswith("rt-")
               and isinstance(job, dict) and job.get("status") in ("completed", "failed"))


def test_over_the_bound_the_oldest_old_finished_jobs_go_with_their_files(monkeypatch):
    import os
    now = time.time()
    ages = [4000 + 10 * i for i in range(8)] + [60, 120, 1799]
    _many(now, ages, unfinished=4)
    for job_id in _ours():
        _spill(job_id)
    monkeypatch.setattr(settings, "JOB_MAX_KEPT", 5 + _foreign_finished())
    evicted = asyncio.run(job_manager.evict_over_count())
    assert evicted == 6
    gone = {f"rt-f{i:03d}" for i in range(2, 8)}
    assert not gone & _ours()
    kept = {"rt-f000", "rt-f001", "rt-f008", "rt-f009", "rt-f010"} | {f"rt-u{i:03d}" for i in range(4)}
    assert _ours() == kept
    for job_id in gone:
        assert not os.path.exists(job_store._path(job_id)) and not os.path.exists(job_store.job_dir(job_id))
    for job_id in kept:
        assert os.path.exists(job_store._path(job_id))


def test_jobs_younger_than_the_eviction_age_and_unfinished_jobs_stay(monkeypatch):
    now = time.time()
    _many(now, [3000, 1700, 900, 60, 10], unfinished=6)
    monkeypatch.setattr(settings, "JOB_MAX_KEPT", 1 + _foreign_finished())
    assert job_manager.over_count_job_ids(now) == ["rt-f000"]
    asyncio.run(job_manager.evict_over_count())
    assert _ours() == {"rt-f001", "rt-f002", "rt-f003", "rt-f004"} | {f"rt-u{i:03d}" for i in range(6)}


def test_within_the_bound_nothing_is_evicted(monkeypatch):
    now = time.time()
    _many(now, [90000, 50000, 7200])
    monkeypatch.setattr(settings, "JOB_MAX_KEPT", 3 + _foreign_finished())
    assert job_manager.over_count_job_ids(now) == []
    assert asyncio.run(job_manager.evict_over_count()) == 0
    assert {"rt-f000", "rt-f001", "rt-f002"} <= _ours()


def test_each_eviction_is_logged(monkeypatch, caplog):
    import logging
    now = time.time()
    _many(now, [9000, 8000, 7000])
    monkeypatch.setattr(settings, "JOB_MAX_KEPT", 1 + _foreign_finished())
    with caplog.at_level(logging.INFO):
        asyncio.run(job_manager.evict_over_count())
    lines = [r.getMessage() for r in caplog.records if "to keep at most" in r.getMessage()]
    assert lines == [f"Evicted finished job rt-f000 to keep at most {settings.JOB_MAX_KEPT} finished jobs",
                     f"Evicted finished job rt-f001 to keep at most {settings.JOB_MAX_KEPT} finished jobs"]


def test_the_periodic_sweep_applies_the_bound(monkeypatch):
    import main
    now = time.time()
    _many(now, [9000, 8000, 7000, 6000])
    monkeypatch.setattr(settings, "JOB_MAX_KEPT", 2 + _foreign_finished())
    monkeypatch.setattr(settings, "JOB_TTL_SEC", 86400)
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main._cleanup_old_jobs())
    assert sleeps == [600, 600]
    assert {"rt-f000", "rt-f001"}.isdisjoint(_ours()) and {"rt-f002", "rt-f003"} <= _ours()


def test_an_evicted_job_reads_as_not_found(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    now = time.time()
    _many(now, [9000, 8000])
    monkeypatch.setattr(settings, "JOB_MAX_KEPT", 1 + _foreign_finished())
    asyncio.run(job_manager.evict_over_count())
    client = TestClient(app)
    for path in ("/jobs/rt-f000", "/jobs/rt-f000/report"):
        r = client.get(path)
        assert r.status_code == 404 and r.json()["detail"] == job_store.JOB_NOT_FOUND
    assert client.get("/jobs/rt-f001").status_code == 200


def test_page_texts_give_the_retention_as_a_longest_time():
    retention = re.compile(r"(.{0,12})\$\{durationText\((?:getState\(\)\.jobTtlSec|ttl|seconds)\)\}")
    until = re.compile(r"until \$\{(?:clockText|_clock)\([^`]*?\)\}([^`]*)`")
    found = 0
    for path in sorted(_JS.glob("*.js")):
        src = path.read_text()
        for before in retention.findall(src):
            found += 1
            assert before.endswith("up to "), (path.name, before)
        for after in until.findall(src):
            found += 1
            assert after.startswith(" at the latest"), (path.name, after)
    assert found >= 13
    assert "for up to ${keptFor}" in (_JS / "job_link.js").read_text()
