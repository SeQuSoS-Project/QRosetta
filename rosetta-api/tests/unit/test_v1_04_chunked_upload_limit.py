"""V1-04: the upload limit holds for bodies sent without Content-Length (chunked), with no
nginx in front."""
import asyncio
import json

import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from config import settings  # noqa: E402
from main import LimitUploadSize, app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    from services.security import limiter
    monkeypatch.setattr(limiter, "enabled", False)
    return TestClient(app)


def _chunks(body: bytes, size: int = 64 * 1024):
    for i in range(0, len(body), size):
        yield body[i:i + size]


def _json_body(n_bytes: int) -> bytes:
    return json.dumps({"qasm_string": "x" * n_bytes}).encode()


def test_v1_04_a_chunked_body_over_the_limit_is_413(client):
    response = client.post("/compare", content=_chunks(_json_body(settings.MAX_UPLOAD_BYTES + 10)),
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert "upload limit" in response.json()["detail"]


def test_v1_04_the_plan_path_keeps_its_larger_limit_when_chunked(client):
    body = json.dumps({"source": "single", "modes": ["statevector"], "preprocessing": "on",
                       "circuits": [{"qasm_string": "x" * (settings.MAX_UPLOAD_BYTES + 10), "name": "big"}]}).encode()
    assert client.post("/plan", content=_chunks(body), headers={"Content-Type": "application/json"}).status_code == 200
    huge = _json_body(settings.MAX_PLAN_REQUEST_BYTES + 10)
    assert client.post("/plan", content=_chunks(huge), headers={"Content-Type": "application/json"}).status_code == 413


def test_v1_04_an_invalid_content_length_is_400(client):
    response = client.post("/compare", content=b"{}", headers={"Content-Length": "abc", "Content-Type": "application/json"})
    assert response.status_code == 400


def test_v1_04_reading_stops_at_the_first_chunk_over_the_limit():
    pulled = []
    chunks = [b"a" * 600, b"b" * 600, b"c" * 600, b""]

    async def receive():
        body = chunks[len(pulled)]
        pulled.append(body)
        return {"type": "http.request", "body": body, "more_body": bool(body)}

    async def inner(scope, receive, send):
        while (await receive()).get("more_body"):
            pass
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    sent = []

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/compare", "headers": []}
    asyncio.run(LimitUploadSize(inner, max_upload_size=1000)(scope, receive, send))
    assert len(pulled) == 2
    assert sent[0]["status"] == 413
