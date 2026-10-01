"""Request validation and job-status contracts of the benchmark, export, config and auth routes."""
import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from config import settings
from schemas import (
    AgreementThresholds, BatchPayload, GenerateCircuitPayload, MeasuredQasmPayload,
    PublicationRenderRequest, QasmPayload,
)

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


@pytest.fixture
def client(monkeypatch):
    from routers import benchmark, experiment, export, frontend
    from routers.errors import register_error_handlers
    from services.security import limiter
    import services.job_manager as job_manager

    monkeypatch.setattr(limiter, "enabled", False)
    started = []

    def fake_add_task(self, func, *args, **kwargs):
        started.append((func.__name__, args))
    monkeypatch.setattr("fastapi.BackgroundTasks.add_task", fake_add_task)

    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    for module in (benchmark, experiment, export, frontend):
        app.include_router(module.router)
    c = TestClient(app)
    c.started = started
    c.jobs = job_manager.ACTIVE_JOBS
    return c


@pytest.mark.parametrize("field,value", [
    ("optimization_level", -1),
    ("optimization_level", 4),
    ("runner_config", {"qiskit": -1}),
    ("runner_config", {"qiskit": [0, 7]}),
    ("timeout_seconds", 1),
    ("execution_target", "mars"),
])
def test_qasm_payload_rejects_out_of_range_values(field, value):
    with pytest.raises(ValidationError):
        QasmPayload(qasm_string=QASM, **{field: value})


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_thresholds_reject_nan_and_infinity(bad):
    with pytest.raises(ValidationError):
        AgreementThresholds(js_threshold=bad)


def test_shot_bounds():
    with pytest.raises(ValidationError):
        MeasuredQasmPayload(qasm_string=QASM, n_shots=settings.MAX_SHOTS + 1)
    with pytest.raises(ValidationError):
        BatchPayload(tasks=[], mode="measured", n_shots=0)
    assert MeasuredQasmPayload(qasm_string=QASM, n_shots=settings.MAX_SHOTS).n_shots == settings.MAX_SHOTS


def test_render_scale_is_bounded():
    base = {"results": {"x": 1}, "artifact_id": "a", "format": "png"}
    for scale in (0, 5, 1000):
        with pytest.raises(ValidationError):
            PublicationRenderRequest(**base, scale=scale)
    assert PublicationRenderRequest(**base, scale=4).scale == 4


def test_execution_target_defaults_to_server_mode():
    assert QasmPayload(qasm_string=QASM).execution_target == settings.EXECUTION_MODE


def test_generate_payload_requires_a_qubit():
    with pytest.raises(ValidationError):
        GenerateCircuitPayload(algorithm="ghz", qubits=0)


def test_compare_rejects_unknown_and_disabled_runners(client):
    r = client.post("/compare", json={"qasm_string": QASM, "target_simulators": ["projectq", "mars"]})
    assert r.status_code == 400
    assert "mars" in r.json()["detail"] and "projectq" in r.json()["detail"]
    r = client.post("/compare_measured", json={"qasm_string": QASM, "runner_config": {"nope": 1}})
    assert r.status_code == 400 and "nope" in r.json()["detail"]
    assert client.started == []


@pytest.mark.parametrize("body", [
    "qreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];\nx q[0];\n",
    "qreg q[1];\nreset q[0];\n",
    "qreg q[1];\ncreg c[1];\nif(c==1) x q[0];\n",
])
def test_statevector_rejects_non_unitary_circuits(client, body):
    qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n' + body
    r = client.post("/compare", json={"qasm_string": qasm})
    assert r.status_code == 400 and "measured mode" in r.json()["detail"]
    r = client.post("/run_batch_suite", json={
        "mode": "statevector", "tasks": [{"algorithm": "x", "qubits": 1, "qasm_string": qasm}]})
    assert r.status_code == 400
    r = client.post("/compare_measured", json={"qasm_string": qasm})
    assert r.status_code == 200


def test_compare_rejects_empty_circuit(client):
    assert client.post("/compare", json={"qasm_string": ""}).status_code == 400


def test_job_target_records_the_actual_mode(client):
    other = "kubernetes" if settings.EXECUTION_MODE == "local" else "local"
    r = client.post("/compare", json={"qasm_string": QASM, "execution_target": other})
    assert r.status_code == 200
    body = r.json()
    assert body["target"] == settings.EXECUTION_MODE
    assert body["requested_target"] == other


def test_compare_passes_effective_thresholds(client):
    client.post("/compare", json={"qasm_string": QASM})
    name, args = client.started[-1]
    assert name == "worker_compare"
    assert args[-3] == AgreementThresholds().model_dump()
    assert args[-2] is False
    assert args[-1] == 1


def test_failed_parse_job_is_failed_and_not_exportable(client, monkeypatch):
    import asyncio
    import services.job_manager as job_manager
    pytest.importorskip("pytket")

    async def fake_dispatch(*args, **kwargs):
        raise AssertionError("must not dispatch")
    monkeypatch.setattr(job_manager, "dispatch_to_runners", fake_dispatch)

    job_id = "failed-parse-job"
    job_manager.ACTIVE_JOBS[job_id] = job_manager.new_job()
    garbage = "OPENQASM 2.0;\nqreg q[2];\nfoo q[0];\n"
    asyncio.run(job_manager.worker_compare(job_id, garbage, 0, {}, 30, [], "local", {}, True, None))

    status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == "failed" and status["error"]
    assert status["results"]["error"] == status["error"]
    assert status["results"]["agreement_thresholds"] == AgreementThresholds().model_dump()
    assert client.post(f"/jobs/{job_id}/export", json={}).status_code == 409
    assert client.post("/export", json={"results": status["results"]}).status_code == 409
    del job_manager.ACTIVE_JOBS[job_id]


def test_config_exposes_mode_thresholds_and_limits(client):
    cfg = client.get("/config").json()
    assert cfg["execution_mode"] == settings.EXECUTION_MODE
    assert cfg["agreement_threshold_defaults"] == AgreementThresholds().model_dump()
    assert cfg["limits"] == {
        "max_qubits_statevector": settings.MAX_QUBITS_STATEVECTOR,
        "max_qubits_measured": settings.MAX_QUBITS_MEASURED,
        "timeout_min": settings.MIN_TIMEOUT_SEC,
        "timeout_max": settings.RUNNER_TIMEOUT_SEC,
        "timeout_default": settings.DEFAULT_TIMEOUT_SEC,
        "timing_repeats_max": settings.MAX_TIMING_REPEATS,
        "max_qasm_gate_statements": settings.MAX_QASM_GATES,
        "max_expanded_gates": settings.MAX_EXPANDED_GATES,
        "shots_min": settings.MIN_SHOTS,
        "shots_max": settings.MAX_SHOTS,
        "shots_default": settings.DEFAULT_SHOTS,
    }


H = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'


def _post_raw(client, path, text):
    return client.post(path, content=text, headers={"Content-Type": "application/json"})


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e400"])
def test_non_finite_threshold_is_422_without_echo(client, literal):
    body = '{"qasm_string": "%s", "thresholds": {"fidelity_tolerance": %s}}' % (
        QASM.replace("\n", "\\n").replace('"', '\\"'), literal)
    r = _post_raw(client, "/compare", body)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, list) and detail
    assert all(set(item) == {"loc", "msg", "type"} for item in detail)
    assert client.started == []


@pytest.mark.parametrize("path,body", [
    ("/compare", {"qasm_string": QASM, "bogus": 1}),
    ("/compare_measured", {"qasm_string": QASM, "nshots": 10}),
    ("/compare_measured", {"qasm_string": QASM, "seed": True}),
    ("/compare_measured", {"qasm_string": QASM, "seed": "5"}),
    ("/compare", {"qasm_string": QASM, "apply_preprocessing": "yes"}),
    ("/run_batch_suite", {"mode": "sv", "tasks": [{"algorithm": "ghz", "qubits": 2}]}),
    ("/run_batch_suite", {"mode": "measured", "tasks": [{"algorithm": "ghz", "qubits": True}]}),
    ("/experiments", {"circuits": [{"algorithm": "ghz", "qubits": 2}], "preprocessing": [True, False]}),
    ("/experiments", {"circuits": [{"algorithm": "ghz", "qubits": 2, "source": "web"}]}),
    ("/jobs/some-job/export", {"format": "zip-bomb"}),
])
def test_unknown_fields_and_wrong_types_are_rejected(client, path, body):
    r = client.post(path, json=body)
    assert r.status_code == 422, r.text
    assert all("input" not in item for item in r.json()["detail"])
    assert client.started == []


@pytest.mark.parametrize("qasm,expected", [
    ("OPENQASM 3;\nqubit[30] q;\n", "OpenQASM 3 is not supported"),
    ('OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nh q[0];\n', "OpenQASM 3 is not supported"),
    (H + "qreg q[2]\nh q[0];\n", "Syntax error on line 3"),
    (H + "qreg q[3];\ncreg c[2];\nh q;\nmeasure q -> c;\n", "measure operands differ in size"),
    (H + "qreg q[2];\ncreg c[2];\nmeasure q[0] -> c[7];\n", "outside the declared register"),
])
@pytest.mark.parametrize("path", ["/compare", "/compare_measured"])
def test_parse_errors_name_the_problem(client, path, qasm, expected):
    r = client.post(path, json={"qasm_string": qasm})
    assert r.status_code == 400, r.text
    assert expected in r.json()["detail"]


def test_batch_literal_task_is_validated_up_front(client):
    qasm = H + "qreg q[3];\ncreg c[2];\nmeasure q -> c;\n"
    r = client.post("/run_batch_suite", json={
        "mode": "measured", "tasks": [{"algorithm": "mine", "qubits": 3, "qasm_string": qasm}]})
    assert r.status_code == 400 and r.json()["detail"].startswith("Task 0 (mine): ")


def test_unknown_job_is_404_with_detail(client):
    from services.job_store import JOB_NOT_FOUND
    for r in (client.get("/jobs/nope"), client.get("/jobs/nope/report"),
              client.post("/jobs/nope/export", json={}), client.get("/experiments/nope/bundle")):
        assert r.status_code == 404 and r.json() == {"detail": JOB_NOT_FOUND}


def test_every_runner_failed_is_a_failed_job_with_results(client, monkeypatch):
    import asyncio
    import services.job_manager as job_manager

    async def fake_dispatch(runner_urls, runner_payload=None, timeout_seconds=None,
                            runner_statuses=None):
        return [{"simulator": name, "error": "boom"} for name in runner_urls]
    monkeypatch.setattr(job_manager, "dispatch_to_runners", fake_dispatch)

    job_id = "all-failed-job"
    job_manager.ACTIVE_JOBS[job_id] = job_manager.new_job()
    asyncio.run(job_manager.worker_compare(job_id, QASM, 0, {}, 30, ["qiskit", "cirq"],
                                           "local", {}, True, None))
    status = client.get(f"/jobs/{job_id}").json()
    assert status["status"] == "failed"
    assert status["error"] == "all 2 runners failed"
    assert len(status["results"]["raw_results"]) == 2
    assert client.get(f"/jobs/{job_id}/report").status_code == 200
    assert client.post(f"/jobs/{job_id}/export", json={}).status_code == 200
    del job_manager.ACTIVE_JOBS[job_id]


def test_bundle_and_report_routes_check_the_job_kind(client):
    import services.job_manager as job_manager
    job_manager.ACTIVE_JOBS["plain"] = job_manager._completed_job("local", {"raw_results": []}, {})
    job_manager.ACTIVE_JOBS["exp"] = {"status": "completed", "kind": "experiment", "target": "local",
                                      "bundle_files": {"a.txt": b"x"}, "results": {}}
    try:
        r = client.get("/experiments/plain/bundle")
        assert r.status_code == 404 and "not an experiment" in r.json()["detail"]
        for r in (client.get("/jobs/exp/report"), client.post("/jobs/exp/export", json={})):
            assert r.status_code == 409 and "/experiments/exp/bundle" in r.json()["detail"]
        assert client.get("/experiments/exp/bundle").status_code == 200
    finally:
        del job_manager.ACTIVE_JOBS["plain"], job_manager.ACTIVE_JOBS["exp"]


def test_openapi_declares_error_responses(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path, method, codes in [
        ("/compare", "post", {"400", "413", "422"}),
        ("/compare_measured", "post", {"400", "413", "422"}),
        ("/run_batch_suite", "post", {"400", "413", "422"}),
        ("/experiments", "post", {"400", "413", "422"}),
        ("/jobs/{job_id}", "get", {"404"}),
        ("/jobs/{job_id}/report", "get", {"404", "409"}),
        ("/jobs/{job_id}/export", "post", {"404", "409"}),
        ("/experiments/{job_id}/bundle", "get", {"404", "409"}),
    ]:
        assert codes <= set(paths[path][method]["responses"]), (path, method)


def test_seed_description_names_the_per_runner_derivation():
    text = MeasuredQasmPayload.model_fields["seed"].description
    assert "derived" in text and "shared by every runner" not in text
