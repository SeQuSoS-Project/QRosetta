"""GET /jobs/{id}/circuit-texts: the Circuits view's panes, built in Python with the ids, order
and texts static/js/circuit_panes.js gives (checked on edge cases and the committed experiment
reports), carrying the share-link allowlist's fields only."""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import services.job_manager as job_manager
from routers import circuits
from routers.errors import register_error_handlers
from services.circuit_texts import circuit_panes
from tests.unit.frontend_harness import call_js, requires_node

REPO = Path(__file__).resolve().parents[3]
QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
FIELDS = ("id", "kind", "key", "group", "text")


def _report(**extra):
    return {
        "input_qasm": QASM,
        "dispatched_circuits": [{"group": "default", "qasm": QASM, "runners": ["qiskit", "cirq"],
                                 "api_preprocessing_applied": ["API: comments removed"]}],
        "raw_results": [
            {"simulator": "qiskit", "dispatch_group": "default", "transpiled_qasm": QASM, "gate_count": 2,
             "circuit_depth": 2, "preprocessing_applied": ["API: comments removed", "rebase"],
             "dispatch_status": "ok", "execution_time_sec": 0.5, "statevector": "AAAA"},
            {"simulator": "cirq", "dispatch_group": "default", "dispatch_status": "error",
             "error": "Traceback: /home/appuser/app/main.py line 3"},
        ],
        "compile_input": {"qasm": QASM, "api_preprocessing_applied": []},
        "compiled_circuits": [{"compiler": "staq~opt1~run1", "compiler_id": "staq", "transpiled_qasm": QASM,
                               "passes_applied": ["-O1"], "dispatch_status": "ok", "gate_count": 2},
                              {"compiler": "qmap~opt0~run1", "dispatch_status": "error",
                               "refusal": "idle qubit", "refusal_kind": "input", "error": "stderr text"}],
        **extra,
    }


EDGE_CASES = [
    _report(),
    {},
    {"input_qasm": 5, "raw_results": "x", "dispatched_circuits": {"group": "g"}},
    {"raw_results": [None, [], {"simulator": ""}, {"simulator": 7, "transpiled_qasm": 3}, 4, "s"]},
    {"dispatched_circuits": [None, {"group": "a"}, {"qasm": QASM}, {"group": "b", "qasm": QASM}]},
    {"compile_input": [QASM], "compiled_circuits": [None, [], {"compiler": ""}, {}]},
    {"compile_input": {"qasm": None}, "compiled_circuits": "x"},
]


def _experiment_reports():
    return [json.loads(p.read_text()) for p in sorted((REPO / "experiments").rglob("results/*/*.json"))]


@requires_node
def test_panes_match_the_circuits_view():
    reports = EDGE_CASES + _experiment_reports()
    assert len(reports) > len(EDGE_CASES)
    js = call_js(["circuit_panes.js"], [("circuitPanes", [r]) for r in reports])
    for report, panes in zip(reports, js):
        assert [{k: p.get(k) for k in FIELDS} for p in circuit_panes(report)] == \
            [{k: p.get(k) for k in FIELDS} for p in panes]


def test_panes_carry_the_allowlist_only():
    panes = {p["id"]: p for p in circuit_panes(_report())}
    assert list(panes) == ["input", "dispatched:default", "executed:qiskit", "executed:cirq", "compile-input",
                           "compiled:staq~opt1~run1", "compiled:qmap~opt0~run1"]
    assert panes["executed:qiskit"]["preprocessing_applied"] == ["API: comments removed", "rebase"]
    assert panes["executed:qiskit"]["gate_count"] == 2
    assert panes["dispatched:default"]["runners"] == ["qiskit", "cirq"]
    assert panes["compiled:qmap~opt0~run1"]["refusal"] == "idle qubit"
    text = json.dumps(panes)
    for leaked in ("Traceback", "stderr text", "execution_time_sec", "statevector", "AAAA"):
        assert leaked not in text


@pytest.fixture
def client():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(circuits.router)
    batch = {"benchmark_summary": [_report(task_name="bell"), {"task_name": "broken", "error": "bad"}]}
    job_manager.ACTIVE_JOBS["texts-single"] = job_manager._completed_job("local", _report(), {})
    job_manager.ACTIVE_JOBS["texts-batch"] = job_manager._completed_job("local", batch, {})
    job_manager.ACTIVE_JOBS["texts-running"] = {"status": "processing", "target": "local"}
    try:
        yield TestClient(app)
    finally:
        for job_id in ("texts-single", "texts-batch", "texts-running"):
            del job_manager.ACTIVE_JOBS[job_id]


def test_single_job(client):
    body = client.get("/jobs/texts-single/circuit-texts").json()
    assert body["job_id"] == "texts-single" and body["report_source"] == "server_job"
    assert len(body["circuits"]) == 1
    circuit = body["circuits"][0]
    assert circuit["task"] is None and circuit["task_name"] is None
    assert circuit["panes"] == circuit_panes(_report())


def test_playlist_job_and_one_task(client):
    body = client.get("/jobs/texts-batch/circuit-texts").json()
    assert [(c["task"], c["task_name"]) for c in body["circuits"]] == [(0, "bell"), (1, "broken")]
    assert body["circuits"][0]["panes"] == circuit_panes(_report(task_name="bell"))
    assert body["circuits"][1]["panes"] == []
    one = client.get("/jobs/texts-batch/circuit-texts", params={"task": 0}).json()
    assert one["circuits"] == body["circuits"][:1]


@pytest.mark.parametrize("path,params,status", [
    ("/jobs/texts-single/circuit-texts", {"task": 0}, 400),
    ("/jobs/texts-batch/circuit-texts", {"task": 5}, 404),
    ("/jobs/no-such-job/circuit-texts", {}, 404),
    ("/jobs/texts-running/circuit-texts", {}, 409),
    ("/jobs/texts-batch/circuit-texts", {"task": -1}, 422),
])
def test_errors(client, path, params, status):
    assert client.get(path, params=params).status_code == status
