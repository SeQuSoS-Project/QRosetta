"""API contract fixes of play-test round 3: token lifetime, saved runs and circuits by job
id, delete status codes, optional export bodies, request-time task limits, compile status
keys, publication artifact discovery and the OpenAPI schema keywords."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

pytest.importorskip("pytket")

import services.job_manager as job_manager  # noqa: E402
from config import settings  # noqa: E402
from db.database import Base, get_db  # noqa: E402
from routers import auth, benchmark, export, generation, history, publication  # noqa: E402
from routers.errors import register_error_handlers  # noqa: E402
from services.security import limiter  # noqa: E402

H = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
BELL = H + "qreg q[2];\nh q[0];\ncx q[0],q[1];\n"

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def _get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


def _login(c, email):
    c.post("/auth/register", json={"email": email, "password": "testpass123"})
    r = c.post("/auth/token", data={"username": email, "password": "testpass123"})
    return r


@pytest.fixture
def client(tmp_path, monkeypatch):
    import services.storage as storage
    monkeypatch.setattr(storage, "MOCK_S3_DIR", str(tmp_path))
    monkeypatch.setattr(limiter, "enabled", False)
    started = []
    monkeypatch.setattr("fastapi.BackgroundTasks.add_task",
                        lambda self, func, *a, **k: started.append(func.__name__))
    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    for module in (auth, history, export, benchmark, publication, generation):
        app.include_router(module.router)
    app.dependency_overrides[get_db] = _get_db
    c = TestClient(app)
    c.started = started
    return c


@pytest.fixture
def user(client, request):
    token = _login(client, f"r3-{request.node.name[:40].lower()}@example.org").json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture
def job():
    ids = []

    def make(job_id, report):
        job_manager.ACTIVE_JOBS[job_id] = job_manager._completed_job("local", report, {})
        ids.append(job_id)
    yield make
    for job_id in ids:
        job_manager.ACTIVE_JOBS.pop(job_id, None)


def test_token_reports_its_lifetime(client):
    r = _login(client, "lifetime@example.org")
    assert r.status_code == 200
    assert r.json()["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_saved_job_is_returned_after_the_job_expires_and_listed_with_its_job_id(user, job):
    job("expiring-job-0001", {"raw_results": [{"simulator": "qiskit", "counts": {"0": 1}}], "n_shots": 1})
    first = user.post("/history/runs/from_job/expiring-job-0001")
    assert first.status_code == 201
    job_manager.ACTIVE_JOBS.pop("expiring-job-0001")
    again = user.post("/history/runs/from_job/expiring-job-0001", json={"run_name": "renamed"})
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"] and again.json()["run_name"] == "renamed"
    listed = {r["id"]: r for r in user.get("/history/runs").json()}
    assert listed[first.json()["id"]]["job_id"] == "expiring-job-0001"
    assert user.post("/history/runs/from_job/never-saved-0002").status_code == 404


def test_uploaded_run_has_no_job_id_in_the_list(user):
    r = user.post("/history/runs", json={"raw_results": [], "job_id": "client-said"})
    assert r.status_code == 201 and r.json()["job_id"] is None


def test_patch_accepts_name_like_from_job(user, job):
    job("rename-job-0003", {"raw_results": []})
    run_id = user.post("/history/runs/from_job/rename-job-0003", json={"name": "a"}).json()["id"]
    r = user.patch(f"/history/runs/{run_id}", json={"name": "b"})
    assert r.status_code == 200 and r.json()["run_name"] == "b"


def test_delete_runs_reports_what_it_did(user):
    run_id = user.post("/history/runs", json={"raw_results": []}).json()["id"]
    assert user.request("DELETE", "/history/runs", json={"run_ids": ["nope"]}).status_code == 404
    r = user.request("DELETE", "/history/runs", json={"run_ids": [run_id, "nope"]})
    assert r.status_code == 200
    assert r.json()["deleted"] == [run_id] and r.json()["not_found"] == ["nope"]


def test_run_links_to_a_circuit_given_in_the_body(user):
    circuit = user.post("/history/circuits", json={"name": "bell", "qasm_string": BELL}).json()
    r = user.post("/history/runs", json={"raw_results": [], "circuit_id": circuit["id"]})
    assert r.status_code == 201 and r.json()["circuit_id"] == circuit["id"]
    assert user.post("/history/runs", json={"raw_results": [], "circuit_id": "other"}).status_code == 404
    clash = user.post(f"/history/runs?circuit_id={circuit['id']}", json={"raw_results": [], "circuit_id": "x"})
    assert clash.status_code == 422


def test_saved_circuits_are_validated_renamed_and_deleted(user):
    assert user.post("/history/circuits", json={"name": "x", "qasm_string": "not qasm at all"}).status_code == 400
    circuit = user.post("/history/circuits", json={"name": "bell", "qasm_string": BELL}).json()
    run = user.post(f"/history/runs?circuit_id={circuit['id']}", json={"raw_results": []}).json()
    r = user.patch(f"/history/circuits/{circuit['id']}", json={"name": "bell pair"})
    assert r.status_code == 200 and r.json()["name"] == "bell pair"
    assert user.delete(f"/history/circuits/{circuit['id']}").status_code == 204
    assert user.delete(f"/history/circuits/{circuit['id']}").status_code == 404
    assert user.get("/history/circuits").json() == []
    assert {r["id"]: r for r in user.get("/history/runs").json()}[run["id"]]["circuit_id"] is None


def test_job_export_body_is_optional(client):
    r = client.post("/jobs/no-such-job/export")
    assert r.status_code == 404


def test_preset_task_over_the_limit_is_rejected_up_front(client):
    r = client.post("/run_batch_suite", json={
        "mode": "statevector",
        "tasks": [{"algorithm": "ghz", "qubits": 3},
                  {"algorithm": "ghz", "qubits": settings.MAX_QUBITS_STATEVECTOR + 1}]})
    assert r.status_code == 400
    assert r.json()["detail"].startswith("tasks[1] (ghz): ")
    assert not client.started
    ok = client.post("/run_batch_suite", json={
        "mode": "measured", "tasks": [{"algorithm": "ghz", "qubits": settings.MAX_QUBITS_STATEVECTOR + 1}]})
    assert ok.status_code == 200


def test_compile_only_run_takes_a_circuit_with_measurements(client):
    qasm = BELL + "creg c[2];\nmeasure q -> c;\n"
    r = client.post("/compare", json={"qasm_string": qasm, "simulate": False,
                                      "compilers": {"pyzx": [1]}, "target_simulators": []})
    assert r.status_code == 200, r.text


def test_algorithms_report_per_mode_caps(client):
    for algo in client.get("/algorithms").json():
        assert algo["max_qubits_statevector"] <= settings.MAX_QUBITS_STATEVECTOR
        assert algo["max_qubits_measured"] <= settings.MAX_QUBITS_MEASURED
        assert algo["max_qubits_statevector"] <= algo["max_qubits"]


def test_single_level_compile_status_key_is_the_record_key():
    from services.compilation import _compile_status_keys, _CompileStatuses, compile_key
    assert _compile_status_keys({"qmap": [0], "bqskit": [1, 2]}) == [
        "qmap~opt0~run1", "bqskit~opt1~run1", "bqskit~opt2~run1"]
    statuses = {}
    view = _CompileStatuses(statuses, {"qmap": [0], "bqskit": [1, 2]})
    view["qmap"] = "running"
    view.setdefault("bqskit~opt2~run1", "queued")
    assert statuses == {compile_key("qmap", 0): "running", "bqskit~opt2~run1": "queued"}


def _measured_report():
    return {"n_shots": 100, "raw_results": [
        {"simulator": "qiskit", "counts": {"00": 50, "11": 50}, "qubit_ordering": "lsb"},
        {"simulator": "cirq", "counts": {"00": 48, "11": 52}, "qubit_ordering": "msb"}],
        "divergence_report": {}, "performance_report": {}, "resource_report": {}}


def test_unknown_artifact_lists_the_ids_the_report_offers(client, job):
    report = _measured_report()
    listed = client.post("/publication/artifacts", json={"results": report})
    assert listed.status_code == 200, listed.text
    ids = [a["id"] for a in listed.json()]
    assert ids and all(a["formats"] for a in listed.json())
    r = client.post("/publication/render", json={"results": report, "artifact_id": "nosuch", "format": "svg"})
    assert r.status_code == 404 and ids[0] in r.json()["detail"]
    job("artifact-job-0004", report)
    by_job = client.get("/jobs/artifact-job-0004/publication/artifacts")
    assert by_job.status_code == 200 and [a["id"] for a in by_job.json()] == ids
    assert client.get("/jobs/missing-job/publication/artifacts").status_code == 404


def test_api_reference_pages_load_pinned_assets():
    import re
    from main import app
    c = TestClient(app)
    for path in ("/docs", "/redoc"):
        html = c.get(path).text
        urls = re.findall(r"https://cdn\.jsdelivr\.net/npm/[^\"']+", html)
        assert urls, path
        assert all(re.search(r"@\d+\.\d+\.\d+/", u) for u in urls), urls
        assert "fonts.googleapis" not in html and "tiangolo" not in html


def _walk(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key
            yield from _walk(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _walk(value, f"{path}/{i}")


def test_openapi_uses_json_schema_keywords_and_documents_reports():
    from main import app
    app.openapi_schema = None
    spec = TestClient(app).get("/openapi.json").json()
    bad = [(p, k) for p, k in _walk(spec["components"]) if k in ("ge", "le", "gt", "lt")
           and "/properties/" in p and not p.endswith("/properties")]
    assert not bad, bad
    task = spec["components"]["schemas"]["BenchmarkTask"]["properties"]["qubits"]
    assert {"type": "integer", "minimum": 0} in task["anyOf"]
    job_200 = spec["paths"]["/jobs/{job_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert job_200["$ref"].endswith("/JobStatus")
    for name in ("SingleCircuitReport", "BatchReport", "ExperimentResults", "RunnerResult",
                 "PairwiseAgreement", "JobReport", "SavedRunReport"):
        assert name in spec["components"]["schemas"], name
    assert "expires_in" in spec["components"]["schemas"]["Token"]["required"]
    pair = spec["components"]["schemas"]["PairwiseAgreement"]["properties"]
    assert "verdict" in pair["measured_assessment"]["description"]
