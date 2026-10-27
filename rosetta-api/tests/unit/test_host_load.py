"""Host-load notices (spec S24): POST /local/host-load behind the lifecycle token, the registry
interval runs count as server_overlapping_host_load, the gate an exclusive run waits for, expiry
after the last heartbeat, and the stop marks that make a lost run read stopped_by_user."""

import asyncio
from pathlib import Path

import pytest

from services import host_load, timing_caveats
from services.run_registry import GATE, REGISTRY, ExclusiveGate

TOKEN = "t" * 43


@pytest.fixture(autouse=True)
def clean():
    asyncio.run(host_load.reset())
    yield
    asyncio.run(host_load.reset())
    assert GATE.status()["host_load_running"] == 0


@pytest.fixture
def client(tmp_path, monkeypatch):
    pytest.importorskip("pytket")
    from fastapi.testclient import TestClient
    from main import app
    path = tmp_path / "lifecycle.token"
    path.write_text(TOKEN + "\n")
    monkeypatch.setenv("QROSETTA_LIFECYCLE_TOKEN_FILE", str(path))
    monkeypatch.setattr(host_load, "_ensure_expiry", lambda: None)
    return TestClient(app)


def _post(client, body, token=TOKEN):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/local/host-load", json=body, headers=headers)


def test_the_route_is_hidden_without_the_lifecycle_token(client):
    for token in (None, "wrong", ""):
        assert _post(client, {"action": "begin", "kind": "build"}, token).status_code == 404
        assert _post(client, {"no": "body"}, token).status_code == 404
    assert "/local/host-load" not in client.get("/openapi.json").json()["paths"]
    assert GATE.status()["host_load_running"] == 0


def test_begin_heartbeat_end(client):
    begun = _post(client, {"action": "begin", "kind": "build", "services": ["qiskit", "api"]})
    assert begun.status_code == 200
    notice = begun.json()
    assert notice["gate_held"] is True and notice["services"] == ["qiskit", "api"]
    assert notice["ttl_sec"] == host_load.NOTICE_TTL_SEC and notice["heartbeat_every_sec"] == host_load.HEARTBEAT_SEC
    assert GATE.status()["host_load_running"] == 1
    assert client.get("/config").json()["exclusive"]["host_load_running"] == 1
    assert _post(client, {"action": "heartbeat", "notice_id": notice["notice_id"]}).status_code == 200
    ended = _post(client, {"action": "end", "notice_id": notice["notice_id"]})
    assert ended.status_code == 200 and ended.json()["ended"] is True
    assert GATE.status()["host_load_running"] == 0
    assert _post(client, {"action": "end", "notice_id": notice["notice_id"]}).status_code == 404
    assert _post(client, {"action": "begin"}).status_code == 400
    assert _post(client, {"action": "heartbeat"}).status_code == 400
    assert _post(client, {"action": "begin", "kind": "rm -rf"}).status_code == 422
    assert _post(client, {"action": "begin", "kind": "build", "services": ["Bad Name"]}).status_code == 422


def test_runs_overlapping_a_notice_count_it_and_runs_of_other_jobs_separately():
    async def scenario():
        run = REGISTRY.start(object())
        other = REGISTRY.start(object())
        notice = await host_load.begin("pull")
        await host_load.end(notice["notice_id"])
        REGISTRY.finish(other)
        return REGISTRY.finish_counts(run)

    assert asyncio.run(scenario()) == {"runs": 1, "host_load": 1}


def test_a_run_after_the_notice_ended_does_not_count_it():
    async def scenario():
        notice = await host_load.begin("build")
        await host_load.end(notice["notice_id"])
        await asyncio.sleep(0.01)
        return REGISTRY.finish_counts(REGISTRY.start(object()))

    assert asyncio.run(scenario()) == {"runs": 0, "host_load": 0}


def test_a_notice_expires_after_its_last_heartbeat(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(host_load, "_clock", lambda: now["t"])

    async def scenario():
        notice = await host_load.begin("probe")
        now["t"] += host_load.NOTICE_TTL_SEC - 1
        await host_load.heartbeat(notice["notice_id"])
        now["t"] += host_load.NOTICE_TTL_SEC - 1
        assert await host_load.expire_due() == []
        now["t"] += 2
        assert await host_load.expire_due() == [notice["notice_id"]]
        with pytest.raises(host_load.NoticeNotFound):
            await host_load.heartbeat(notice["notice_id"])

    asyncio.run(scenario())
    assert GATE.status()["host_load_running"] == 0


def test_an_exclusive_dispatch_waits_for_host_load_and_a_shared_one_does_not():
    async def scenario():
        gate = ExclusiveGate()
        assert gate.hold_host_load()
        await asyncio.wait_for(gate.acquire(False), 1)
        await gate.release(False)
        exclusive = asyncio.create_task(gate.acquire(True, max_wait=5))
        await asyncio.sleep(0.05)
        assert not exclusive.done()
        await gate.release_host_load()
        assert await asyncio.wait_for(exclusive, 1) >= 0.05
        assert not gate.hold_host_load(), "an exclusive run in progress is not held back"
        await gate.release(True)

    asyncio.run(scenario())


def test_a_notice_during_an_exclusive_run_is_recorded_without_holding_the_gate(monkeypatch):
    async def scenario():
        await GATE.acquire(True)
        try:
            run = REGISTRY.start(object())
            notice = await host_load.begin("build")
            assert notice["gate_held"] is False
            await host_load.end(notice["notice_id"])
            return REGISTRY.finish_counts(run)
        finally:
            await GATE.release(True)

    assert asyncio.run(scenario())["host_load"] == 1


def test_stop_notices_mark_their_services(monkeypatch):
    now = {"t": 5000.0}
    monkeypatch.setattr(host_load, "_clock", lambda: now["t"])

    async def scenario():
        whole = await host_load.begin("stop")
        assert host_load.stopped_by_user("cirq~opt1~run2")
        await host_load.end(whole["notice_id"])
        now["t"] += host_load.STOP_GRACE_SEC + 1
        assert not host_load.stopped_by_user("cirq")
        some = await host_load.begin("remove", ["qulacs"])
        assert host_load.stopped_by_user("qulacs") and not host_load.stopped_by_user("qiskit")
        await host_load.end(some["notice_id"])
        build = await host_load.begin("build", ["qiskit"])
        assert not host_load.stopped_by_user("qiskit")
        await host_load.end(build["notice_id"])

    asyncio.run(scenario())


def test_host_load_is_a_timing_caveat():
    result = {"simulator": "qiskit", "server_overlapping_host_load": 2, "timing_samples": 3, "exclusive": True}
    codes = [c["code"] for c in timing_caveats.result_caveats(result)]
    assert "host_load" in codes
    report = timing_caveats.summarize([("qiskit", result)])
    assert [c["code"] for c in report if c["code"] == "host_load"] == ["host_load"]
    assert "host_load" not in [c["code"] for c in timing_caveats.result_caveats(
        {**result, "server_overlapping_host_load": 0})]


def test_the_compose_file_mounts_the_token_into_the_api_only():
    import yaml
    repo = Path(__file__).resolve().parents[3]
    doc = yaml.safe_load((repo / "docker-compose.yml").read_text())
    assert (repo / "infra" / "lifecycle-token.none").stat().st_size == 0
    token_mounts = {name: [v for v in svc.get("volumes", []) if isinstance(v, dict)
                           and v.get("target") == "/run/secrets/lifecycle_token"]
                    for name, svc in doc["services"].items()}
    assert [name for name, mounts in token_mounts.items() if mounts] == ["api"]
    (mount,) = token_mounts["api"]
    assert mount == {"type": "bind", "source": "${QROSETTA_LIFECYCLE_TOKEN_PATH:-./infra/lifecycle-token.none}",
                     "target": "/run/secrets/lifecycle_token", "read_only": True, "bind": {"selinux": "Z"}}
    assert "secrets" not in doc and not any(svc.get("secrets") for svc in doc["services"].values())
    assert "QROSETTA_LIFECYCLE_TOKEN_FILE=/run/secrets/lifecycle_token" in doc["services"]["api"]["environment"]
