"""Runner availability: /capabilities probing, requires_gpu, request rejection and skipping."""
import asyncio

import httpx
import pytest
from fastapi import HTTPException

import services.availability as availability
from config import settings


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    availability.clear_cache()
    monkeypatch.setattr(settings, "EXECUTION_MODE", "local")
    monkeypatch.setattr(settings, "GPU_AVAILABLE", False)
    yield
    availability.clear_cache()


def _mock_transport(monkeypatch, handler):
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)
    monkeypatch.setattr(availability.httpx, "AsyncClient", factory)


def _handler(request):
    host = request.url.host
    if host == "pytket-qiskit-runner":
        return httpx.Response(404)
    if host == "cuquantum-runner":
        return httpx.Response(200, json={"available": False, "reason": "no CUDA device", "device": None})
    if host == "qibo-runner":
        return httpx.Response(200, json={"available": True, "reason": None, "device": "CPU"})
    raise httpx.ConnectError("refused", request=request)


def test_probe_results(monkeypatch):
    _mock_transport(monkeypatch, _handler)
    got = asyncio.run(availability.runner_availability(["qiskit", "cuquantum", "qibo", "cirq"]))
    assert got["qiskit"] == {"available": True, "reason": None, "device": None}
    assert got["cuquantum"] == {"available": False, "reason": "no CUDA device", "device": None}
    assert got["qibo"]["device"] == "CPU"
    assert got["cirq"] == {"available": False, "reason": "unreachable", "device": None}


def test_runner_without_endpoint_that_requires_a_gpu_is_unavailable(monkeypatch):
    _mock_transport(monkeypatch, lambda request: httpx.Response(404))
    got = asyncio.run(availability.runner_availability(["cuquantum"]))
    assert got["cuquantum"]["available"] is False and "GPU" in got["cuquantum"]["reason"]


def test_kubernetes_uses_the_registry_flag(monkeypatch):
    monkeypatch.setattr(settings, "EXECUTION_MODE", "kubernetes")
    got = asyncio.run(availability.runner_availability(["cuquantum", "qiskit"]))
    assert got["cuquantum"]["available"] is False and got["qiskit"]["available"] is True
    monkeypatch.setattr(settings, "GPU_AVAILABLE", True)
    got = asyncio.run(availability.runner_availability(["cuquantum"]))
    assert got["cuquantum"]["available"] is True


def test_explicit_unavailable_target_is_rejected(monkeypatch):
    _mock_transport(monkeypatch, _handler)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(availability.require_available(["qiskit", "cuquantum"]))
    assert exc.value.status_code == 400
    assert "cuquantum: no CUDA device" in exc.value.detail
    asyncio.run(availability.require_available(["qiskit"]))


def test_all_enabled_skips_unavailable_and_records_why(monkeypatch):
    _mock_transport(monkeypatch, _handler)
    urls = {"qiskit": "q", "cuquantum": "c"}
    kept, skipped = asyncio.run(availability.filter_available(urls, []))
    assert kept == {"qiskit": "q"}
    assert skipped == [{"id": "cuquantum", "reason": "no CUDA device"}]
    kept, skipped = asyncio.run(availability.filter_available(urls, ["cuquantum"]))
    assert kept == urls and skipped == []


def test_cuquantum_requires_a_gpu_in_the_registry():
    assert settings.get_runner_services()["cuquantum"]["requires_gpu"] is True


def test_runner_scaffold_serves_capabilities():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from qrosetta_commons.helpers import register_runner_endpoints
    app = FastAPI()
    register_runner_endpoints(app, lambda p: {}, lambda p: {},
                              capabilities=lambda: {"available": False, "reason": "no GPU", "gpu_name": None})
    body = TestClient(app).get("/capabilities").json()
    assert {k: body[k] for k in ("available", "reason", "device")} == {"available": False, "reason": "no GPU",
                                                                       "device": None}
    assert "gpu_name" not in body and "image_git_sha" in body
    assert set(body["image_identity"]) == {"source", "release", "git_sha"}


def test_every_runner_serves_capabilities_with_its_image_identity(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from qrosetta_commons import helpers, image_identity
    monkeypatch.setattr(helpers, "IMAGE_GIT_SHA", "abc1234")
    monkeypatch.setattr(image_identity, "_identity", lambda: {
        "source": "built_locally", "release": None, "git_sha": "abc1234", "container": {}, "emulation": {}})
    monkeypatch.setattr(image_identity, "build_file_hashes", lambda: {"Dockerfile": "ab" * 32})
    app = FastAPI()
    helpers.register_runner_endpoints(app, lambda p: {}, lambda p: {})
    body = TestClient(app).get("/capabilities").json()
    assert body == {"available": True, "reason": None, "device": None, "image_git_sha": "abc1234",
                    "image_identity": {"source": "built_locally", "release": None, "git_sha": "abc1234"},
                    "build_files": {"Dockerfile": "ab" * 32}}


def test_runner_rows_carry_what_the_image_reports(monkeypatch):
    from services import service_listing
    body = {"available": True, "reason": None, "device": None, "image_git_sha": "abc1234",
            "image_identity": {"source": "release", "release": "2.0.0", "git_sha": "abc1234", "extra": "x"},
            "build_files": {"Dockerfile": "ab" * 32}}
    _mock_transport(monkeypatch, lambda request: httpx.Response(200, json=body))
    info = asyncio.run(availability.runner_availability(["qiskit"]))["qiskit"]
    row = service_listing.runner_row("qiskit", settings.get_runner_services()["qiskit"], info)
    assert row["versions"] == {"image_git_sha": "abc1234", "build_files": {"Dockerfile": "ab" * 32},
                               "image_identity": {"source": "release", "release": "2.0.0", "git_sha": "abc1234"}}


@pytest.mark.parametrize("mode", ["local", "kubernetes"])
def test_undeployed_services_are_unavailable_with_a_reason(monkeypatch, mode):
    monkeypatch.setattr(settings, "EXECUTION_MODE", mode)
    monkeypatch.setattr(settings, "NOT_DEPLOYED", frozenset({"qsynth"}))
    _mock_transport(monkeypatch, lambda request: httpx.Response(404))
    status = asyncio.run(availability.runner_availability(
        ["qsynth", "pyzx"], services=settings.get_compiler_services()))
    assert status["qsynth"] == {"available": False, "reason": availability.NOT_DEPLOYED, "device": None}
    assert status["pyzx"]["available"] is True
