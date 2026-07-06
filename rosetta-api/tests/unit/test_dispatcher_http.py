"""Unit tests for the HTTP dispatcher's honest failure classification (Phase-1 timeout fix).

A dropped connection must not be asserted to be a specific C++ crash; it is classified by how
long it took, so a timeout/OOM is not mislabelled. Driven with asyncio.run (no pytest-asyncio).
"""
import asyncio

import httpx

from services.dispatcher_http import safe_request


class _RaisingClient:
    def __init__(self, exc):
        self._exc = exc

    async def post(self, url, json):
        raise self._exc


class _StatusErrorClient:
    async def post(self, url, json):
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
    assert set(r) >= {"simulator", "error", "execution_time_sec", "memory_usage_mb"}
    assert r["execution_time_sec"] == 0.0
