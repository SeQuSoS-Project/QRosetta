"""V7(a) Failure injection, runner faults: the real app dispatches over HTTP to fake runners on
loopback sockets. A runner that is slow past the timeout, resets or closes the connection,
sends a truncated, malformed, non-object or oversized body, or answers HTTP 500 becomes that
backend's error with its dispatch status; the others finish, the job reaches a terminal state
and no exception text reaches the client."""

import pytest

from services import dispatcher_http
from tests.unit._fault_runners import (  # noqa: F401
    FAULTS, api_with_runners, assert_no_raw_exception_text,
)

BELL = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'

EXPECTED = {
    "slow": ("timeout", "TIMEOUT (1s): the qiskit runner did not respond"),
    "reset": ("error", "CONNECTION LOST after ~0s to the qiskit runner"),
    "close": ("error", "CONNECTION LOST after ~0s to the qiskit runner"),
    "truncated": ("error", "CONNECTION LOST after ~0s to the qiskit runner"),
    "truncated_json": ("error", "INVALID RESPONSE: the qiskit runner returned a response the API cannot use (it is not valid JSON)"),
    "not_json": ("error", "(it is not valid JSON)"),
    "html_200": ("error", "(it is not valid JSON)"),
    "list": ("error", "(it is not a JSON object)"),
    "null": ("error", "(it is not a JSON object)"),
    "nan": ("error", "(it holds NaN, which JSON does not allow)"),
    "no_statevector": ("error", "(it has neither an error nor a valid statevector field)"),
    "http_500": ("error", "HTTP 500 from the qiskit runner."),
    "oversized_declared": ("error", "(it is larger than 0 MiB)"),
    "oversized_chunked": ("error", "(it is larger than 0 MiB)"),
}


@pytest.fixture(autouse=True)
def small_result_cap(monkeypatch):
    monkeypatch.setattr(dispatcher_http, "MAX_RESULT_BYTES", 64 * 1024)


def _results(env):
    return {r["simulator"]: r for r in env["results"]["raw_results"]}


def test_every_fault_is_listed():
    assert set(EXPECTED) == set(FAULTS)


@pytest.mark.parametrize("fault", FAULTS)
def test_one_faulty_runner_fails_alone_and_the_job_completes(api_with_runners, fault):
    api = api_with_runners({"qiskit": fault, "cirq": None, "qulacs": None}, delay=5.0)
    env = api.finished(api.compare(BELL))
    assert env["status"] == "completed"
    results = _results(env)
    status, text = EXPECTED[fault]
    assert results["qiskit"]["dispatch_status"] == status
    assert text in results["qiskit"]["error"]
    for name in ("cirq", "qulacs"):
        assert results[name]["dispatch_status"] == "ok" and not results[name].get("error")
    assert env["runner_statuses"] == {"qiskit": {"timeout": "timeout"}.get(status, "error"),
                                      "cirq": "done", "qulacs": "done"}
    assert env["results"]["run_completeness"]["job_status"] == "completed"
    assert_no_raw_exception_text(env)


def test_a_runner_that_stops_after_its_probe_is_offline(api_with_runners):
    import services.availability as availability
    api = api_with_runners({"qiskit": None, "cirq": None, "qulacs": None})
    availability._cache["qiskit"] = (availability.time.monotonic(),
                                      {"available": True, "reason": None, "device": None})
    api.runners["qiskit"].close()
    env = api.finished(api.compare(BELL))
    results = _results(env)
    assert results["qiskit"]["dispatch_status"] == "offline"
    assert results["qiskit"]["error"].startswith("UNAVAILABLE: the qiskit runner could not be reached.")
    assert env["status"] == "completed" and env["runner_statuses"]["qiskit"] == "offline"
    assert_no_raw_exception_text(env)


def test_a_closed_runner_is_refused_before_the_run_when_named(api_with_runners):
    api = api_with_runners({"qiskit": None, "cirq": None})
    api.runners["qiskit"].close()
    r = api.client.post("/compare", json={"qasm_string": BELL, "target_simulators": ["qiskit", "cirq"],
                                          "timeout_seconds": 10})
    assert r.status_code == 400
    assert r.json()["detail"] == "Unavailable runner(s) requested: qiskit: unreachable."


def test_every_runner_faulty_fails_the_job_with_its_results(api_with_runners):
    api = api_with_runners({"qiskit": "reset", "cirq": "list", "qulacs": "http_500"})
    env = api.finished(api.compare(BELL))
    assert env["status"] == "failed"
    assert env["error"] == "all 3 runners failed"
    assert {r["dispatch_status"] for r in env["results"]["raw_results"]} == {"error"}
    assert env["results"]["run_completeness"]["job_status"] == "failed"
    assert_no_raw_exception_text(env)


def test_a_playlist_with_a_faulty_runner_finishes_every_circuit(api_with_runners):
    api = api_with_runners({"qiskit": "truncated", "cirq": None, "qulacs": None})
    tasks = [{"qasm_string": BELL, "name": f"bell{i}"} for i in range(3)]
    env = api.finished(api.batch(tasks))
    assert env["status"] == "completed"
    assert env["progress"]["completed"] == 3
    assert [t["status"] for t in env["progress"]["tasks"]] == ["done"] * 3
    for task in env["results"]["benchmark_summary"]:
        by_name = {r["simulator"]: r for r in task["raw_results"]}
        assert by_name["qiskit"]["dispatch_status"] == "error"
        assert by_name["cirq"]["dispatch_status"] == by_name["qulacs"]["dispatch_status"] == "ok"
    assert_no_raw_exception_text(env)


def test_the_report_download_of_a_job_with_faults_is_json(api_with_runners):
    api = api_with_runners({"qiskit": "nan", "cirq": None})
    job_id = api.compare(BELL)
    api.finished(job_id)
    r = api.client.get(f"/jobs/{job_id}/report")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    report = r.json()
    assert {x["simulator"]: x["dispatch_status"] for x in report["raw_results"]} == {"qiskit": "error", "cirq": "ok"}
    assert_no_raw_exception_text(report)
