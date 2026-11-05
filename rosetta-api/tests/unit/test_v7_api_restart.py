"""V7(e) Failure injection, the API restarting mid-job (WM#3).

Page: pollJobStatus (static/js/api.js) on a virtual clock against a scripted server keeps
polling through an outage with backoff (3, 6, 12, 24, then 30 s) for up to 5 minutes, shows that
it is waiting, never shows a proxy's HTML page, and ends on the server's 404 with a message
saying the restart lost the job. nginx answers a dead upstream with JSON. Server: a restarted
API answers 404 with JSON for the job and its report."""

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.unit.frontend_harness import NODE, call_js, requires_node

ROOT = Path(__file__).resolve().parents[3]
HARNESS = Path(__file__).with_name("poll_harness.mjs")
PATIENCE_MS = 5 * 60 * 1000
RUNNING = {"kind": "json", "status": 200, "body": {"job_id": "job-1", "status": "processing", "phase": "dispatching"}}
GONE = {"kind": "json", "status": 404, "body": {"detail": "Job not found. Finished jobs are kept for up to 30 "
                                                          "minutes and are lost if the server restarts; submit "
                                                          "the run again."}}
NGINX_502 = {"kind": "html", "status": 502}
NO_CONNECTION = {"kind": "network"}
DONE = {"kind": "json", "status": 200, "body": {"job_id": "job-1", "status": "completed", "phase": "done",
                                                "results": {"input_qasm": "x"}}}


def poll(phases):
    out = subprocess.run([NODE, str(HARNESS)], input=json.dumps({"phases": phases}), capture_output=True,
                         text=True, check=True, timeout=60)
    return json.loads(out.stdout)


def _gaps(result):
    times = [t for t, *_ in result["polls"]]
    return [b - a for a, b in zip(times, times[1:])]


def _no_html(result):
    for text in [result.get("message", "")] + result["kicker"]:
        assert "<" not in text and "nginx" not in text.lower(), text


@requires_node
@pytest.mark.parametrize("outage", [NGINX_502, NO_CONNECTION], ids=["nginx-502", "no-connection"])
def test_v7_02_the_page_waits_through_a_restart_and_says_the_job_was_lost(outage):
    result = poll([{"for_ms": 5000, "answer": RUNNING}, {"for_ms": 60000, "answer": outage},
                   {"answer": GONE}])
    assert result["outcome"] == "rejected" and result["terminal"] is True
    assert result["message"] == ("The server did not answer for a while and now has no record of this job: it "
                                 "restarted, and a restart loses every job in progress. Submit the run again.")
    assert 65000 <= result["elapsed_ms"] <= 65000 + 30000
    gaps = _gaps(result)
    failing = [g for (t, kind, *_), g in zip(result["polls"][1:], gaps) if t > 5000]
    assert gaps[0] == 3000
    assert any(g >= 12000 for g in failing), f"no backoff: {gaps}"
    assert max(gaps) <= 30000
    waiting = [k for k in result["kicker"] if k.startswith("Waiting for the server")]
    assert waiting and ("HTTP 502" in waiting[0] if outage is NGINX_502 else "no connection" in waiting[0])
    assert result["timers_left"] == 0
    _no_html(result)


@requires_node
def test_v7_02_the_page_stops_waiting_after_five_minutes_without_an_answer():
    result = poll([{"for_ms": 3000, "answer": RUNNING}, {"answer": NGINX_502}])
    assert result["outcome"] == "rejected" and result["terminal"] is False and result["stopped"] is False
    assert result["message"] == ("The server did not answer for 5 minutes (last: HTTP 502). The job may still be "
                                 "running there: reload this page when the server is back, and Earlier runs from "
                                 "this browser offers the job again.")
    first_failure = next(t for t, kind, *_ in result["polls"] if kind == "html")
    assert PATIENCE_MS <= result["elapsed_ms"] - first_failure <= PATIENCE_MS + 30000
    assert len(result["polls"]) <= 20, f"{len(result['polls'])} polls in five minutes"
    assert result["timers_left"] == 0
    _no_html(result)


@requires_node
def test_a_short_outage_ends_when_the_job_finishes():
    result = poll([{"for_ms": 4000, "answer": RUNNING}, {"for_ms": 20000, "answer": NGINX_502},
                   {"answer": DONE}])
    assert result["outcome"] == "resolved"
    assert result["value"] == {"input_qasm": "x"}
    assert result["kicker"][-1].startswith("Waiting for the server") or "Running on" in result["kicker"][-1]


@requires_node
def test_a_404_without_an_outage_keeps_the_expiry_wording():
    result = poll([{"for_ms": 4000, "answer": RUNNING}, {"answer": GONE}])
    assert result["terminal"] is True
    assert result["message"] == "The server has no record of this job. It may have expired or the server may have restarted."


@requires_node
def test_a_failed_poll_is_retried_with_the_api_error_detail():
    error = {"kind": "json", "status": 500, "body": {"detail": "Internal server error"}}
    result = poll([{"for_ms": 4000, "answer": RUNNING}, {"for_ms": 8000, "answer": error}, {"answer": DONE}])
    assert result["outcome"] == "resolved"
    assert any(k.startswith("Waiting for the server (HTTP 500: Internal server error)") for k in result["kicker"])


@requires_node
def test_v7_03_an_html_error_page_is_never_shown_as_source():
    page = "<html><head><title>502 Bad Gateway</title></head><body><h1>502 Bad Gateway</h1><hr>nginx</body></html>"
    got = call_js(["api.js"], [
        ("errorBodyText", [502, page, "text/html"]),
        ("errorBodyText", [504, page, ""]),
        ("errorBodyText", [500, page, "text/html; charset=utf-8"]),
        ("errorBodyText", [502, '{"detail": "The API is not answering."}', "application/json"]),
        ("errorBodyText", [400, "plain words", "text/plain"]),
        ("apiErrorText", [502, "The API did not answer, and the proxy in front of it returned an error page. "
                               "The server may be restarting; try again in a minute.", "Bad Gateway"]),
    ])
    assert got[0] == got[1] == ("The API did not answer, and the proxy in front of it returned an error page. "
                                "The server may be restarting; try again in a minute.")
    assert got[2] == ""
    assert got[3] == "The API is not answering."
    assert got[4] == "plain words"
    assert got[5].startswith("Request failed (HTTP 502): The API did not answer")


@requires_node
def test_poll_backoff_and_patience_constants():
    got = call_js(["api.js"], [("pollRetryDelay", [n]) for n in range(1, 8)] + [("POLL_OUTAGE_PATIENCE_MS", [])])
    assert got[:7] == [3000, 6000, 12000, 24000, 30000, 30000, 30000]
    assert got[7] == PATIENCE_MS


@pytest.mark.parametrize("conf", ["nginx/nginx.conf", "infra/nginx-frontend.conf"])
def test_v7_04_nginx_answers_a_dead_upstream_with_json(conf):
    text = (ROOT / conf).read_text()
    for status, location in ((502, "@api_unavailable"), (504, "@api_timeout")):
        assert re.search(rf"error_page\s+{status}\s+=\s+{location};", text), f"{conf}: no error_page {status}"
        block = re.search(rf"location {location} \{{(.*?';)\s*\}}", text, re.S).group(1)
        assert "default_type application/json;" in block
        body = re.search(rf"return {status} '(.*)';", block).group(1)
        assert isinstance(json.loads(body)["detail"], str)
    assert "proxy_intercept_errors on" not in text, "the API's own 502/504 bodies would be replaced"


def test_a_restarted_api_answers_404_with_json_for_the_job_and_its_report(tmp_path, monkeypatch):
    pytest.importorskip("pytket")
    from fastapi.testclient import TestClient

    import services.job_manager as job_manager
    from main import app
    from services import job_store, prep_worker
    from services.security import limiter
    from tests.unit._fault_runners import FaultRunner, wire_runners

    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    job_store.reset_spill_dir()
    monkeypatch.setattr(limiter, "enabled", False)
    monkeypatch.setattr(prep_worker, "IN_PROCESS", True)
    runners = {"qiskit": FaultRunner("qiskit"), "cirq": FaultRunner("cirq")}
    try:
        wire_runners(monkeypatch, runners)
        client = TestClient(app)
        r = client.post("/compare", json={"qasm_string": 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];\n',
                                          "target_simulators": ["qiskit", "cirq"], "timeout_seconds": 10})
        job_id = r.json()["job_id"]
        assert client.get(f"/jobs/{job_id}").json()["status"] == "completed"
        dict.pop(job_manager.ACTIVE_JOBS, job_id)
        job_store.reset_spill_dir()
        for path in (f"/jobs/{job_id}", f"/jobs/{job_id}/report", f"/jobs/{job_id}/summary"):
            r = client.get(path)
            assert r.status_code == 404 and r.headers["content-type"] == "application/json"
            assert r.json()["detail"] == job_store.JOB_NOT_FOUND
        assert "lost if the server restarts" in job_store.JOB_NOT_FOUND
    finally:
        for runner in runners.values():
            runner.close()
