"""V1-01: a runner or compiler response that is not a result becomes that backend's error;
the other backends of the job finish."""
import asyncio
import io
import json

import httpx
import pytest

import services.dispatcher_http as dh
import services.dispatcher_k8s as k8s
from services import result_contract
from services.result_contract import ResultContractError, check_result, parse_result


def _client_factory(monkeypatch, bodies: dict):
    real = httpx.AsyncClient

    def handler(request):
        body = bodies[request.url.host]
        return httpx.Response(200, content=body if isinstance(body, bytes) else json.dumps(body).encode())

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)
    monkeypatch.setattr(dh.httpx, "AsyncClient", factory)


def _dispatch(urls):
    payload = {"circuit_data": "x", "runner_config": {name: [0] for name in urls}}
    return {r["simulator"]: r for r in asyncio.run(dh.dispatch_http_local(urls, payload, 10))}


GOOD = {"simulator": "cirq", "statevector": "AAAAAAAA8D8AAAAAAAAAAA==", "execution_time_sec": 0.1}


@pytest.mark.parametrize("bad", [None, [1, 2], "text", 3, {"statevector": 5},
                                 {"error": {"nested": 1}}, {"execution_time_sec": "fast", "statevector": ""}])
def test_v1_01_a_response_that_is_not_a_result_is_that_backends_error(monkeypatch, bad):
    _client_factory(monkeypatch, {"bad-runner": bad, "good-runner": GOOD})
    results = _dispatch({"qiskit": "http://bad-runner:8000/run", "cirq": "http://good-runner:8000/run"})
    assert results["cirq"]["dispatch_status"] == "ok"
    assert results["cirq"]["statevector"] == GOOD["statevector"]
    assert results["qiskit"]["dispatch_status"] == "error"
    assert results["qiskit"]["error"].startswith("INVALID RESPONSE: the qiskit runner")
    assert results["qiskit"]["execution_time_sec"] is None


def test_v1_01_non_json_nan_and_deep_bodies_are_refused_with_fixed_text(monkeypatch):
    secret = "/home/appuser/app/secret-path"
    deep = b'{"a":' * 40 + b"1" + b"}" * 40
    very_deep = b"[" * 200_000 + b"]" * 200_000
    _client_factory(monkeypatch, {"html": f"<html>{secret}</html>".encode(),
                                  "nan": b'{"statevector": "", "execution_time_sec": NaN}',
                                  "deep": deep, "deeper": very_deep})
    results = _dispatch({"qiskit": "http://html:8000/run", "cirq": "http://nan:8000/run",
                         "qulacs": "http://deep:8000/run", "quest": "http://deeper:8000/run"})
    for key in results:
        assert results[key]["error"].startswith("INVALID RESPONSE"), key
        assert secret not in results[key]["error"]
    assert "not valid JSON" in results["qiskit"]["error"]
    assert "NaN" in results["cirq"]["error"]
    assert "levels deep" in results["qulacs"]["error"] and "levels deep" in results["quest"]["error"]


def test_v1_01_a_body_over_the_size_cap_is_refused_without_reading_it_all(monkeypatch):
    monkeypatch.setattr(dh, "MAX_RESULT_BYTES", 1024)
    _client_factory(monkeypatch, {"big": {"statevector": "A" * 4096}})
    result = _dispatch({"qiskit": "http://big:8000/run"})["qiskit"]
    assert result["dispatch_status"] == "error" and "larger than" in result["error"]


def test_v1_01_required_fields_follow_the_endpoint():
    assert check_result({"counts": {"01": 3}}, "run_measured")
    assert check_result({"error": "SDK said no"}, "run_measured")
    assert check_result({"transpiled_qasm": "OPENQASM 2.0;"}, "compile")
    for bad, endpoint in [({"statevector": ""}, "run_measured"), ({"counts": {"0": -1}}, "run_measured"),
                          ({"counts": {"0": True}}, "run_measured"), ({}, "compile"), ({}, "run")]:
        with pytest.raises(ResultContractError):
            check_result(bad, endpoint)
    with pytest.raises(ResultContractError, match="larger than"):
        parse_result(b" " * (result_contract.MAX_RESULT_BYTES + 1))


class _S3:
    def __init__(self, body):
        self.body, self.deleted, self.reads = body, [], 0

    def get_object(self, Bucket, Key):
        self.reads += 1
        return {"Body": io.BytesIO(self.body)}

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)


@pytest.mark.parametrize("body", [b"null", b"[1]", b"{not json", b'{"statevector": 1}'])
def test_v1_01_a_malformed_s3_result_is_the_runs_error_at_once(monkeypatch, body):
    monkeypatch.setattr(k8s.time, "sleep", lambda s: pytest.fail("a malformed result is not retried"))
    s3 = _S3(body)
    statuses = []
    result = k8s._fetch_s3_result(s3, "b", "jobs/completed/x.json", "qiskit", statuses.append, "run")
    assert result["error"].startswith("INVALID RESPONSE: the qiskit runner")
    assert result["dispatch_status"] == "error" and statuses == ["error"]
    assert s3.reads == 1 and s3.deleted == ["jobs/completed/x.json"]
