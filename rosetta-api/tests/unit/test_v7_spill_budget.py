"""V7(d) Failure injection, the job store over its budget: real reports in a real spill
directory with a 1 MiB budget, written by the real dispatcher from fake runners. New runs get
503 with Retry-After; finished jobs past JOB_EVICTABLE_AFTER_SEC are evicted first; a playlist
that fills the store stops, names the limit and leaves no files; a disk below the free-space
floor (shutil.disk_usage faked) is refused the same way."""

import os
import time
from collections import namedtuple

import pytest

from config import settings
from services import job_store
from tests.unit._fault_runners import assert_no_raw_exception_text, fault_api

pytest.importorskip("pytket")

import services.job_manager as job_manager  # noqa: E402

BELL = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
WIDE = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[12];\n'
        + "".join(f"h q[{i}];\n" for i in range(12)))
RUN_ROUTES = [
    ("/compare", {"qasm_string": BELL}),
    ("/compare_measured", {"qasm_string": BELL, "n_shots": 100}),
    ("/run_batch_suite", {"tasks": [{"qasm_string": BELL}], "mode": "statevector"}),
    ("/experiments", {"circuits": [{"qasm_string": BELL}], "mode": "statevector",
                      "preprocessing_modes": [True, False]}),
]

@pytest.fixture
def api_with_runners(tmp_path, monkeypatch):
    yield from fault_api(tmp_path, monkeypatch)


def _usage_mib():
    return job_store.spill_usage_bytes() / (1024 * 1024)


def _job_files(job_id):
    return [p for p in (job_store._path(job_id), job_store.job_dir(job_id)) if os.path.exists(p)]


def _fill_with_a_finished_job(api, finished_ago):
    """A real finished job whose report holds the budget; its finished_at set ``finished_ago``
    seconds back."""
    job_id = api.compare(WIDE)
    env = api.finished(job_id)
    assert env["status"] == "completed"
    job = dict.__getitem__(job_manager.ACTIVE_JOBS, job_id)
    job["finished_at"] = time.time() - finished_ago
    return job_id


@pytest.fixture
def budget(monkeypatch):
    monkeypatch.setattr(settings, "JOB_SPILL_MAX_MIB", 1)
    return 1


@pytest.mark.parametrize("path, body", RUN_ROUTES)
def test_a_full_store_refuses_every_run_route_with_503_and_retry_after(api_with_runners, budget,
                                                                      monkeypatch, path, body):
    api = api_with_runners({"qiskit": None, "cirq": None, "qulacs": None})
    monkeypatch.setattr(settings, "JOB_SPILL_MAX_MIB", 10)
    holder = _fill_with_a_finished_job(api, finished_ago=0)
    monkeypatch.setattr(settings, "JOB_SPILL_MAX_MIB", 0.2)
    assert _usage_mib() >= 0.2
    jobs_before = set(job_manager.ACTIVE_JOBS)
    r = api.client.post(path, json={**body, "target_simulators": ["qiskit", "cirq"], "timeout_seconds": 10})
    assert r.status_code == 503
    assert r.headers["retry-after"] == str(job_manager.STORAGE_RETRY_AFTER_SEC)
    detail = r.json()["detail"]
    assert detail.startswith("The server's storage for job results is full: it holds ")
    assert "and its limit is 0.2 MiB (limits.job_storage_max_mib in GET /config)" in detail
    assert set(job_manager.ACTIVE_JOBS) == jobs_before
    assert _job_files(holder), "a job that finished just now was evicted"
    assert_no_raw_exception_text(r.json())


def test_an_old_finished_job_is_evicted_to_make_room(api_with_runners, budget, monkeypatch):
    api = api_with_runners({"qiskit": None, "cirq": None, "qulacs": None})
    monkeypatch.setattr(settings, "JOB_SPILL_MAX_MIB", 10)
    old = _fill_with_a_finished_job(api, finished_ago=settings.JOB_EVICTABLE_AFTER_SEC + 60)
    monkeypatch.setattr(settings, "JOB_SPILL_MAX_MIB", 0.2)
    new = api.compare(BELL)
    assert api.finished(new)["status"] == "completed"
    assert api.client.get(f"/jobs/{old}").status_code == 404
    assert not _job_files(old)


def test_a_playlist_that_fills_the_store_stops_names_the_limit_and_keeps_no_files(
        api_with_runners, budget):
    api = api_with_runners({"qiskit": None, "cirq": None, "qulacs": None})
    tasks = [{"qasm_string": WIDE, "name": f"wide{i}"} for i in range(8)]
    job_id = api.batch(tasks)
    env = api.finished(job_id)
    assert env["status"] == "failed"
    stopped = env["progress"]["completed"] + 1
    assert 1 < stopped < 8, f"stopped at circuit {stopped}"
    assert env["error"].startswith(
        f"The batch stopped at circuit {stopped} of 8, and the results of the batch were not kept. "
        "The server's storage for job results is full: it holds ")
    assert "limits.job_storage_max_mib in GET /config" in env["error"]
    statuses = [t["status"] for t in env["progress"]["tasks"]]
    assert statuses == ["done"] * (stopped - 1) + ["error"] + ["queued"] * (8 - stopped)
    assert env["progress"]["current_index"] is None
    assert not _job_files(job_id)
    assert _usage_mib() < 0.05
    r = api.client.get(f"/jobs/{job_id}/report")
    assert r.status_code == 409 and r.json()["detail"].startswith("This job failed before any runner ran")
    assert_no_raw_exception_text(env)
    after = api.compare(BELL)
    assert api.finished(after)["status"] == "completed"


def test_a_disk_below_the_free_space_floor_refuses_runs_and_stops_a_playlist(api_with_runners,
                                                                            monkeypatch):
    api = api_with_runners({"qiskit": None, "cirq": None})
    usage = namedtuple("usage", "total used free")
    free = {"mib": 4096}
    monkeypatch.setattr(job_store.shutil, "disk_usage",
                        lambda path: usage(10 << 30, 0, free["mib"] << 20))
    monkeypatch.setattr(settings, "JOB_SPILL_MIN_FREE_MIB", 1024)
    tasks = [{"qasm_string": BELL, "name": f"b{i}"} for i in range(4)]

    real_spill = job_store.spill_task_report

    def spill_and_shrink(job_id, index, report):
        ref = real_spill(job_id, index, report)
        if index == 1:
            free["mib"] = 100
        return ref
    monkeypatch.setattr(job_manager, "spill_task_report", spill_and_shrink)
    job_id = api.batch(tasks)
    env = api.finished(job_id)
    assert env["status"] == "failed"
    assert env["error"].startswith(
        "The batch stopped at circuit 3 of 4, and the results of the batch were not kept. The server is "
        "low on disk space for job results: 100 MiB free, and it keeps at least 1,024 MiB free")
    assert not _job_files(job_id)

    r = api.client.post("/compare", json={"qasm_string": BELL, "target_simulators": ["qiskit"],
                                          "timeout_seconds": 10})
    assert r.status_code == 503 and r.headers["retry-after"]
    assert r.json()["detail"].startswith("The server is low on disk space for job results: 100 MiB free")
