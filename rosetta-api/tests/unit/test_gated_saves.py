"""Gated saves (spec S23): ?gated=true on GET /jobs/{id}/report and POST /jobs/{id}/export is
admitted only while no dispatch is in flight, holds new dispatches back until it has been sent,
and is recorded on the job; qrosetta run saves through it and wait finishes a deferred crate."""

import asyncio
import json
import os
import time
import zipfile

import pytest

from tests.unit._qrosetta_app import BELL, app_server  # noqa: F401

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import results, waiting  # noqa: E402
from services import gated_saves  # noqa: E402
from services.run_registry import GATE, ExclusiveGate  # noqa: E402


@pytest.fixture(autouse=True)
def clean_gate():
    before = GATE.status()
    yield
    assert GATE.status() == before, "a test left the gate held"


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}


@pytest.fixture
def bell(tmp_path):
    path = tmp_path / "bell.qasm"
    path.write_text(BELL)
    return str(path)


def test_a_save_is_admitted_only_while_no_dispatch_runs_or_waits():
    async def scenario():
        gate = ExclusiveGate()
        assert gate.try_acquire_save()
        await gate.release_save()
        await gate.acquire(False)
        assert not gate.try_acquire_save()
        exclusive = asyncio.create_task(gate.acquire(True))
        await asyncio.sleep(0.01)
        await gate.release(False)
        await asyncio.wait_for(exclusive, 1)
        assert not gate.try_acquire_save()
        await gate.release(True)
        assert gate.try_acquire_save() and gate.try_acquire_save()
        assert gate.status()["saves_running"] == 2
        await gate.release_save()
        await gate.release_save()

    asyncio.run(scenario())


def test_dispatches_wait_behind_a_save_and_record_the_wait():
    async def scenario():
        gate = ExclusiveGate()
        assert gate.try_acquire_save()
        assert gate.try_acquire_shared(), "a fresh-probe round is not held back by a save"
        await gate.release(False)
        shared = asyncio.create_task(gate.acquire(False))
        exclusive = asyncio.create_task(gate.acquire(True, max_wait=5))
        await asyncio.sleep(0.05)
        assert not shared.done() and not exclusive.done()
        await gate.release_save()
        assert await asyncio.wait_for(exclusive, 1) >= 0.05
        await gate.release(True)
        assert await asyncio.wait_for(shared, 1) >= 0.05
        await gate.release(False)

    asyncio.run(scenario())


def _finished_job(client):
    job_id = client.post("/compare", json={"qasm_string": BELL, "target_simulators": ["qiskit", "cirq"]}).json()["job_id"]
    deadline = time.monotonic() + 30
    while client.get(f"/jobs/{job_id}").json()["status"] not in ("completed", "failed"):
        assert time.monotonic() < deadline
        time.sleep(0.05)
    return job_id


def test_gated_report_and_crate_routes(app_server):
    transport, _fleet = app_server
    client = transport.client
    job_id = _finished_job(client)
    assert client.get(f"/jobs/{job_id}").json()["saves"] is None
    assert GATE.try_acquire_shared()
    try:
        busy = client.get(f"/jobs/{job_id}/report", params={"gated": "true"})
        busy_crate = client.post(f"/jobs/{job_id}/export", params={"gated": "true"}, json={})
        assert client.get(f"/jobs/{job_id}/report").status_code == 200
    finally:
        asyncio.run(GATE.release(False))
    assert busy.status_code == busy_crate.status_code == 409
    assert busy.json()["detail"].startswith("gate_busy: 1 dispatch(es) in flight")
    assert busy.headers["retry-after"] == str(gated_saves.RETRY_AFTER_SEC)

    report = client.get(f"/jobs/{job_id}/report", params={"gated": "true"})
    assert report.status_code == 200 and report.content == client.get(f"/jobs/{job_id}/report").content
    crate = client.post(f"/jobs/{job_id}/export", params={"gated": "true"}, json={})
    assert crate.status_code == 200 and crate.headers["content-type"] == "application/zip"
    assert GATE.status()["saves_running"] == 0

    saves = client.get(f"/jobs/{job_id}").json()["saves"]
    assert saves["report"]["gate_busy_refusals"] == 1 and saves["report"]["gated_admitted_at"]
    assert saves["report"]["deferred_sec"] >= 0 and saves["report"]["first_refused_at"]
    assert saves["report"]["ungated_requests"] == 2 and saves["report"]["ungated_with_dispatches_in_flight"] == 1
    assert saves["crate"]["gate_busy_refusals"] == 1 and saves["crate"]["ungated_requests"] == 0
    assert not any(k.startswith("_") for entry in saves.values() for k in entry)


def test_a_gated_request_for_an_unfinished_or_unknown_job_keeps_its_own_status(app_server):
    transport, _fleet = app_server
    assert transport.client.get("/jobs/nope/report", params={"gated": "true"}).status_code == 404
    assert GATE.status()["saves_running"] == 0


def test_run_saves_through_the_gate_and_wait_finishes_a_deferred_crate(app_server, env, bell, capsys, monkeypatch):
    transport, _fleet = app_server
    monkeypatch.setattr(waiting, "pause", lambda seconds: None)
    assert main(["run", bell, "--json"], env=env, transport_factory=transport) == 0
    job = json.loads(capsys.readouterr().out)["data"]["jobs"][0]
    assert results.read_status(job["dir"]) == "complete"
    with zipfile.ZipFile(os.path.join(job["dir"], "ro-crate.zip")) as z:
        assert any(n.endswith("ro-crate-metadata.json") for n in z.namelist())
    gated = [(m, p) for m, p, q, _b in transport.requests if q == {"gated": "true"}]
    assert ("GET", f"/jobs/{job['job_id']}/report") in gated and ("POST", f"/jobs/{job['job_id']}/export") in gated
    assert transport.client.get(f"/jobs/{job['job_id']}").json()["saves"]["crate"]["gated_admitted_at"]

    ticks = iter(range(0, 1_000_000, 10))
    monkeypatch.setattr(waiting, "clock", lambda: next(ticks))
    assert GATE.try_acquire_shared()
    try:
        assert main(["run", bell, "--json"], env=env, transport_factory=transport) == 0
    finally:
        asyncio.run(GATE.release(False))
    deferred = json.loads(capsys.readouterr().out)["data"]["jobs"][0]
    assert results.read_status(deferred["dir"]) == "crate-deferred"
    assert os.path.isfile(os.path.join(deferred["dir"], "report.json"))
    assert not os.path.exists(os.path.join(deferred["dir"], "ro-crate.zip"))
    saves = transport.client.get(f"/jobs/{deferred['job_id']}").json()["saves"]
    assert saves["crate"]["gate_busy_refusals"] >= 1 and saves["crate"]["gated_admitted_at"] is None

    assert main(["wait"], env=env, transport_factory=transport) == 0
    assert results.read_status(deferred["dir"]) == "complete"
    record = json.load(open(os.path.join(deferred["dir"], "job.json")))
    assert record["crate_deferred_since"] and record["crate_deferred_sec"] is not None
    assert record["concurrent_with_other_jobs"] is True, "the report fell back to an ungated save beside a run"
    saves = transport.client.get(f"/jobs/{deferred['job_id']}").json()["saves"]
    assert saves["report"]["ungated_with_dispatches_in_flight"] == 1
    assert saves["crate"]["gated_admitted_at"] and saves["crate"]["deferred_sec"] >= 0
    assert saves["crate"]["ungated_requests"] == 0
