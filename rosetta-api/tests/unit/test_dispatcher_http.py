"""Unit tests for the HTTP dispatcher's failure classification and dispatch_status."""
import asyncio

import httpx

from services.dispatcher_http import safe_request


class _RaisingClient:
    def __init__(self, exc):
        self._exc = exc

    async def post(self, url, json, timeout=None):
        raise self._exc


class _StatusErrorClient:
    async def post(self, url, json, timeout=None):
        req = httpx.Request("POST", "http://runner/run")
        resp = httpx.Response(500, request=req)
        return resp  # raise_for_status() below turns 500 into HTTPStatusError


def _run(client, timeout_s=300):
    return asyncio.run(safe_request(client, "http://runner/run", {}, "qiskit", timeout_s))


def test_timeout_is_reported_as_timeout():
    r = _run(_RaisingClient(httpx.TimeoutException("slow")))
    assert r["simulator"] == "qiskit"
    assert "TIMEOUT" in r["error"] and "300" in r["error"]


def test_connect_error_is_unavailable():
    r = _run(_RaisingClient(httpx.ConnectError("refused")))
    assert "UNAVAILABLE" in r["error"]
    assert "OOM" not in r["error"] and "SIGABRT" not in r["error"]


def test_late_disconnect_reads_as_timeout_or_oom_not_a_definite_crash():
    # timeout budget 0 -> elapsed always >= 0.8*0 -> the "terminated near deadline" branch.
    r = _run(_RaisingClient(httpx.RemoteProtocolError("peer closed")), timeout_s=0)
    assert "RUNNER TERMINATED" in r["error"]
    assert "timeout / OOM" in r["error"]
    # never the old absolute "almost certainly SIGABRT/OOM" claim
    assert "almost certainly" not in r["error"]


def test_early_disconnect_is_connection_lost_not_crash():
    # huge timeout budget -> elapsed is a tiny fraction -> "connection lost", not "terminated".
    r = _run(_RaisingClient(httpx.ReadError("reset")), timeout_s=10**9)
    assert "CONNECTION LOST" in r["error"]
    assert "RUNNER TERMINATED" not in r["error"]


def test_http_status_error_is_classified():
    r = _run(_StatusErrorClient())
    assert "HTTP 500" in r["error"]


def test_error_shape_is_preserved():
    r = _run(_RaisingClient(httpx.ConnectError("x")))
    assert set(r) >= {"simulator", "error", "execution_time_sec", "memory_usage_mb",
                      "compilation_time_sec", "simulation_time_sec", "queue_wait_sec"}
    assert r["execution_time_sec"] is None and r["memory_usage_mb"] is None
    assert r["queue_wait_sec"] is None


def test_messages_do_not_point_users_at_container_logs():
    for exc in (httpx.ConnectError("x"), httpx.ReadError("reset")):
        assert "container logs" not in _run(_RaisingClient(exc), timeout_s=10**9)["error"]


def test_dispatch_status_classification():
    assert _run(_RaisingClient(httpx.TimeoutException("slow")))["dispatch_status"] == "timeout"
    assert _run(_RaisingClient(httpx.ConnectError("refused")))["dispatch_status"] == "offline"
    assert _run(_RaisingClient(httpx.ConnectTimeout("no route")))["dispatch_status"] == "offline"
    assert _run(_StatusErrorClient())["dispatch_status"] == "error"
