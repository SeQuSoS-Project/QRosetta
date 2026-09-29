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
    from routers import benchmark, export, frontend
    from services.security import limiter
    import services.job_manager as job_manager

    monkeypatch.setattr(limiter, "enabled", False)
    started = []

    def fake_add_task(self, func, *args, **kwargs):
        started.append((func.__name__, args))
    monkeypatch.setattr("fastapi.BackgroundTasks.add_task", fake_add_task)

    app = FastAPI()
    app.state.limiter = limiter
    for module in (benchmark, export, frontend):
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
    assert args[-1] == AgreementThresholds().model_dump()


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
        "shots_min": settings.MIN_SHOTS,
        "shots_max": settings.MAX_SHOTS,
    }
