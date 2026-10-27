"""GET /runners?fresh=true and GET /compilers?fresh=true: who may ask, the rate limit, the
5 s reuse, busy runners left alone, the run gate, and the error kinds."""
import asyncio
import socket

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import services.availability as availability
from config import settings
from routers import frontend
from routers.errors import register_error_handlers
from services import fresh_probes, run_registry
from services.run_registry import GATE, IN_FLIGHT

TOKEN = "lifecycle-secret-token"


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    availability.clear_cache()
    fresh_probes.reset()
    monkeypatch.setattr(settings, "EXECUTION_MODE", "local")
    monkeypatch.setattr(settings, "GPU_AVAILABLE", False)
    token_file = tmp_path / "lifecycle.token"
    token_file.write_text(TOKEN + "\n")
    monkeypatch.setenv("QROSETTA_LIFECYCLE_TOKEN_FILE", str(token_file))
    yield
    availability.clear_cache()
    fresh_probes.reset()


@pytest.fixture
def probes(monkeypatch):
    """Records the hosts probed; qulacs fails DNS, cirq times out, qiskit answers 500."""
    hosts = []
    real = httpx.AsyncClient

    def handler(request):
        host = request.url.host
        hosts.append(host)
        if host == "pytket-qulacs-runner":
            raise httpx.ConnectError("[Errno -2] Name or service not known", request=request)
        if host == "pytket-cirq-runner":
            raise httpx.ConnectTimeout("timed out", request=request)
        if host == "pytket-qiskit-runner":
            return httpx.Response(500)
        if host == "qibo-runner":
            raise httpx.ConnectError("[Errno 111] Connection refused", request=request)
        return httpx.Response(200, json={"available": True, "device": "CPU"})

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)
    monkeypatch.setattr(availability.httpx, "AsyncClient", factory)
    return hosts


def _client():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(frontend.router)
    return TestClient(app)


def _auth(token=TOKEN):
    return {"Authorization": f"Bearer {token}", "x-forwarded-for": "198.51.100.7"}


def test_fresh_needs_a_token_or_an_account(probes):
    client = _client()
    assert client.get("/runners?fresh=true").status_code == 401
    assert client.get("/runners?fresh=true", headers=_auth("wrong")).status_code == 401
    assert client.get("/compilers?fresh=true").status_code == 401
    assert probes == []
    assert client.get("/runners").status_code == 200


def test_a_signed_in_account_may_ask(monkeypatch, probes):
    monkeypatch.setattr(fresh_probes, "_account_for", lambda token: object())
    assert _client().get("/runners?fresh=true", headers=_auth("a-jwt")).status_code == 200


def test_fresh_rows_carry_probe_fields_and_error_kinds(probes):
    rows = {r["id"]: r for r in _client().get("/runners?fresh=true", headers=_auth()).json()}
    assert rows["qulacs"]["error_kind"] == "dns" and rows["qulacs"]["available"] is False
    assert rows["cirq"]["error_kind"] == "timeout"
    assert rows["qibo"]["error_kind"] == "connect"
    assert rows["qiskit"]["error_kind"] == "http"
    assert rows["quest"]["error_kind"] is None and rows["quest"]["device"] == "CPU"
    assert all(rows[r]["fresh"] for r in ("qulacs", "cirq", "quest"))
    assert rows["braket"]["fresh"] is False and rows["braket"]["reason"] == "disabled"
    assert rows["quest"]["probed_at"].endswith("Z")
    plain = {r["id"]: r for r in _client().get("/runners").json()}
    assert "fresh" not in plain["quest"]
    assert plain["qulacs"]["available"] is False


def test_fresh_probes_ignore_the_cache(probes):
    asyncio.run(availability.runner_availability(["quest"]))
    probes.clear()
    _client().get("/runners?fresh=true", headers=_auth())
    assert "pytket-quest-runner" in probes


def test_a_round_younger_than_five_seconds_is_reused(probes):
    client = _client()
    client.get("/runners?fresh=true", headers=_auth())
    first = len(probes)
    client.get("/runners?fresh=true", headers=_auth())
    assert len(probes) == first


def test_rate_limit_is_six_a_minute(probes):
    client = _client()
    codes = [client.get("/runners?fresh=true", headers=_auth()).status_code for _ in range(7)]
    assert codes == [200] * 6 + [429]
    last = client.get("/runners?fresh=true", headers=_auth())
    assert 1 <= int(last.headers["Retry-After"]) <= 61
    assert client.get("/runners").status_code == 200


def test_the_rate_limit_is_per_account_and_the_lifecycle_token_counts_as_one(monkeypatch, probes):
    from services.security import create_access_token
    monkeypatch.setattr(fresh_probes, "_account_for", lambda token: object())
    client = _client()
    first = create_access_token({"sub": "a@example.org", "uid": 1})
    second = create_access_token({"sub": "b@example.org", "uid": 2})
    for token in (first, second, TOKEN):
        codes = [client.get("/runners?fresh=true", headers=_auth(token)).status_code for _ in range(7)]
        assert codes == [200] * 6 + [429]


def test_busy_runners_are_not_probed(probes):
    ids = IN_FLIGHT.enter(["quest"])
    try:
        rows = {r["id"]: r for r in _client().get("/runners?fresh=true", headers=_auth()).json()}
    finally:
        IN_FLIGHT.leave(ids)
    assert "pytket-quest-runner" not in probes
    assert rows["quest"]["available"] is True and rows["quest"]["reason"] == "busy"
    assert rows["quest"]["fresh"] is False


def test_an_exclusive_run_gets_cached_values_and_no_probe(monkeypatch, probes):
    availability._cache["quest"] = (0.0, {"available": True, "reason": None, "device": "CPU"})
    monkeypatch.setattr(GATE, "_exclusive", True)
    rows = {r["id"]: r for r in _client().get("/runners?fresh=true", headers=_auth()).json()}
    assert probes == []
    assert rows["quest"]["fresh"] is False and rows["quest"]["reason"] == "exclusive_run"
    assert rows["quest"]["device"] == "CPU"
    assert rows["cirq"]["available"] is False


def test_the_round_holds_the_gate_as_a_shared_dispatch(monkeypatch, probes):
    seen = []
    real = availability.probe_now

    async def probe_now(names, services, timeout):
        seen.append(GATE.status()["shared_running"])
        return await real(names, services, timeout)
    monkeypatch.setattr(availability, "probe_now", probe_now)
    _client().get("/compilers?fresh=true", headers=_auth())
    assert seen == [1] and GATE.status()["shared_running"] == 0


def test_try_acquire_shared_never_waits():
    gate = run_registry.ExclusiveGate()
    assert gate.try_acquire_shared() is True
    asyncio.run(gate.release(False))
    gate._waiting_exclusive = 1
    assert gate.try_acquire_shared() is False


def test_dns_is_found_in_the_exception_chain():
    try:
        try:
            raise socket.gaierror(-3, "Temporary failure")
        except socket.gaierror as inner:
            raise httpx.ConnectError("connect failed") from inner
    except httpx.ConnectError as exc:
        assert availability.error_kind(exc) == "dns"
    assert availability.error_kind(httpx.ConnectError("refused")) == "connect"
    assert availability.error_kind(httpx.ReadTimeout("slow")) == "timeout"


def test_dispatch_marks_its_services_in_flight(monkeypatch):
    import services.dispatcher as dispatcher
    seen = []

    async def fake(runner_urls, payload, timeout, statuses):
        seen.append(IN_FLIGHT.busy())
        return []
    monkeypatch.setattr(dispatcher, "dispatch_http_local", fake)
    monkeypatch.setattr(dispatcher, "EXECUTION_MODE", "local")
    asyncio.run(dispatcher.dispatch_to_runners({"qiskit": "http://x", "cirq": "http://y"}, {}, 10))
    assert seen == [{"qiskit", "cirq"}] and IN_FLIGHT.busy() == set()
