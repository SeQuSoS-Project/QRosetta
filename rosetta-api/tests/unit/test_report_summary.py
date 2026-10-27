"""Verdicts recorded by the aggregator, the summary routes (GET /jobs/{id}/summary,
GET /history/runs/{id}/summary, POST /summary), and the page's reading of either: a report
without recorded verdicts shows, once the server's summary is attached, what the same report
shows with them recorded."""
import asyncio
import copy

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import services.job_manager as job_manager
from db.database import Base, get_db
from qrosetta_commons.helpers import encode_statevector
from routers import auth, history, summary
from routers.errors import register_error_handlers
from services.aggregator import compile_comparison_reports, compile_measurement_reports
from services.analysis.divergence import ANALYSIS_VERSION
from services.analysis.divergence.verdicts import backend_verdicts, pair_verdict
from services.publication.distributions import disagrees
from services.report_summary import report_summary
from tests.unit.frontend_harness import call_js, requires_node
from tests.unit.server_verdicts import with_server_verdicts
from tests.unit.verdict_corpus import corpus

HARNESS = ["../../tests/unit/verdict_attach_harness.mjs"]

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def _get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    import services.storage as storage
    monkeypatch.setattr(storage, "MOCK_S3_DIR", str(tmp_path))
    app = FastAPI()
    register_error_handlers(app)
    for router in (auth.router, history.router, summary.router):
        app.include_router(router)
    app.dependency_overrides[get_db] = _get_db
    c = TestClient(app)
    c.post("/auth/register", json={"email": "summary@example.org", "password": "testpass123"})
    token = c.post("/auth/token", data={"username": "summary@example.org",
                                        "password": "testpass123"}).json()["access_token"]
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


def _strip_verdicts(report: dict) -> dict:
    """A copy of a report as an older analysis version wrote it: no pair_verdict, no backend_verdicts."""
    out = copy.deepcopy(report)
    for task in out["benchmark_summary"] if isinstance(out.get("benchmark_summary"), list) else [out]:
        div = task.get("divergence_report") if isinstance(task, dict) else None
        if isinstance(div, dict):
            div.pop("backend_verdicts", None)
            for p in div.get("pairwise_agreement") or []:
                p.pop("pair_verdict", None)
    return out


def _statevector_results():
    rng = np.random.default_rng(7)
    sv = rng.normal(size=8) + 1j * rng.normal(size=8)
    sv /= np.linalg.norm(sv)
    other = rng.normal(size=8) + 1j * rng.normal(size=8)
    other /= np.linalg.norm(other)
    results = [{"simulator": name, "statevector": encode_statevector(sv), "qubit_ordering": "msb",
                "dispatch_status": "ok"} for name in ("qiskit", "cirq", "qulacs")]
    results.append({"simulator": "qrisp", "statevector": encode_statevector(other), "qubit_ordering": "msb",
                    "dispatch_status": "ok"})
    results.append({"simulator": "quest", "dispatch_status": "timeout", "error": "TIMEOUT"})
    return results


def _counts_results():
    rng = np.random.default_rng(11)
    out = []
    for i, name in enumerate(("qiskit", "cirq", "qulacs", "qrisp")):
        p = [0.5, 0.0, 0.0, 0.5] if name != "qrisp" else [0.25, 0.25, 0.25, 0.25]
        counts = {format(k, "02b"): int(v) for k, v in enumerate(rng.multinomial(4000, p)) if v}
        out.append({"simulator": name, "counts": counts, "qubit_ordering": "msb", "runner_seed": i,
                    "dispatch_status": "ok"})
    return out


@pytest.fixture(scope="module")
def new_reports():
    sv_results = _statevector_results()
    div, _, _ = asyncio.run(compile_comparison_reports(sv_results))
    counts_results = _counts_results()
    mdiv, _, _ = asyncio.run(compile_measurement_reports(counts_results, 4000))
    return [{"raw_results": sv_results, "divergence_report": div},
            {"n_shots": 4000, "raw_results": counts_results, "divergence_report": mdiv}]


def test_the_aggregator_records_the_rule_on_every_pair(new_reports):
    for report in new_reports:
        div = report["divergence_report"]
        assert div["analysis_version"] == ANALYSIS_VERSION
        assert all(p["pair_verdict"] == pair_verdict(p) for p in div["pairwise_agreement"])
        assert div["backend_verdicts"] == backend_verdicts(_strip_verdicts(report))
    sv, measured = (r["divergence_report"]["backend_verdicts"] for r in new_reports)
    assert sv["headline_model"]["flagged"] == ["qrisp"]
    assert {b["key"]: b["status"] for b in sv["backends"]}["quest"] == "timeout"
    assert measured["mode"] == "measured" and measured["headline_model"]["flagged"] == ["qrisp"]


def test_summary_of_a_new_report_equals_what_it_records(new_reports):
    for report in new_reports:
        out = report_summary(report, "server_job")
        assert out["analysis_version"] == ANALYSIS_VERSION and out["report_source"] == "server_job"
        assert out["backend_verdicts"] == report["divergence_report"]["backend_verdicts"]
        assert [{k: v for k, v in e.items() if k != "simulators"} for e in out["pair_verdicts"]] == [
            p["pair_verdict"] for p in report["divergence_report"]["pairwise_agreement"]]


def test_job_summary_route_reads_the_server_copy(client, new_reports):
    batch = {"mode": "statevector", "benchmark_summary": [new_reports[0], {"task_name": "x", "error": "bad"}]}
    job_manager.ACTIVE_JOBS["summary-single"] = job_manager._completed_job("local", new_reports[1], {})
    job_manager.ACTIVE_JOBS["summary-batch"] = job_manager._completed_job("local", batch, {})
    try:
        single = client.get("/jobs/summary-single/summary")
        assert single.status_code == 200, single.text
        body = single.json()
        assert body["report_source"] == "server_job" and body["benchmark_summary"] is None
        assert body["backend_verdicts"] == new_reports[1]["divergence_report"]["backend_verdicts"]
        tasks = client.get("/jobs/summary-batch/summary").json()["benchmark_summary"]
        assert tasks[0]["backend_verdicts"] == new_reports[0]["divergence_report"]["backend_verdicts"]
        assert tasks[1]["pair_verdicts"] == [] and tasks[1]["backend_verdicts"]["backends"] == []
        assert client.get("/jobs/no-such-job/summary").status_code == 404
    finally:
        del job_manager.ACTIVE_JOBS["summary-single"]
        del job_manager.ACTIVE_JOBS["summary-batch"]


def test_post_summary_gives_an_older_report_the_recorded_verdicts(client, new_reports):
    for report in new_reports:
        old = _strip_verdicts(report)
        for r in old["raw_results"]:
            r.pop("statevector", None)
        r = client.post("/summary", json={"results": old})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["report_source"] == "client_supplied" and body["analysis_version"] == ANALYSIS_VERSION
        assert body["report_analysis_version"] == ANALYSIS_VERSION
        assert body["backend_verdicts"] == report["divergence_report"]["backend_verdicts"]


@pytest.mark.parametrize("bad, problem", [
    ({"divergence_report": {"pairwise_agreement": [1]}}, "pair objects"),
    ({"divergence_report": {"pairwise_agreement": [{"simulators": ["Qiskit", "cirq"]}]}}, "runner ids"),
    ({"divergence_report": {"simulators": "qiskit"}}, "runner ids"),
    ({"divergence_report": {"pairwise_agreement": [{"simulators": [1, "cirq"]}]}}, "runner ids"),
])
def test_post_summary_refuses_pairs_it_cannot_key(client, bad, problem):
    r = client.post("/summary", json={"results": bad})
    assert r.status_code == 400 and problem in r.json()["detail"]


def test_saved_run_summary_reads_the_stored_report(client, new_reports):
    old = _strip_verdicts(new_reports[1])
    saved = client.post("/history/runs", json=old)
    assert saved.status_code == 201, saved.text
    body = client.get(f"/history/runs/{saved.json()['id']}/summary").json()
    assert body["report_source"] == "saved_run" and body["saved_from"] == "upload"
    assert body["backend_verdicts"] == new_reports[1]["divergence_report"]["backend_verdicts"]
    assert client.get("/history/runs/not-a-run/summary").status_code == 404


def test_figure_colours_follow_the_pair_verdict():
    pair = {"simulators": ["a", "b"], "mode": "measured", "agreement": "distance_within_threshold",
            "metrics": {"measured_assessment": "distinguishable"}}
    report = {"divergence_report": {"pairwise_agreement": [pair]}}
    assert disagrees(report, "a", "b") is True
    pair["pair_verdict"] = {**pair_verdict(pair), "differs": False}
    assert disagrees(report, "a", "b") is False


@requires_node
def test_page_reads_the_summary_input_it_sends():
    reports = [r for _, r in corpus(n_synthetic=150, n_headline=60)]
    bodies = call_js(["run_status.js"], [("summaryInput", [r]) for r in reports])
    for report, body in zip(reports, bodies):
        assert report_summary(body["results"], "client_supplied") == report_summary(report, "client_supplied")


@requires_node
def test_attached_summary_shows_what_recorded_verdicts_show():
    reports = [r for name, r in corpus(n_synthetic=0, n_headline=80)]
    reports.append({"mode": "measured", "benchmark_summary": reports[-3:]})
    calls = []
    for report in reports:
        recorded = with_server_verdicts(report)
        old = _strip_verdicts(recorded)
        calls += [("shownVerdicts", [recorded]), ("shownVerdicts", [old, report_summary(old, "client_supplied")])]
    out = call_js(HARNESS, calls)
    for i in range(0, len(out), 2):
        recorded, attached = out[i], out[i + 1]
        assert recorded["lacked"] is False and attached["lacked"] is True and attached["lacks"] is False
        assert attached["tasks"] == recorded["tasks"]


@requires_node
def test_page_refuses_to_read_a_report_without_verdicts():
    report = {"raw_results": [{"simulator": "a", "dispatch_status": "ok"}],
              "divergence_report": {"pairwise_agreement": []}}
    assert "no per-backend verdicts" in call_js(HARNESS, [("readWithoutVerdicts", [report])])[0]
    assert call_js(HARNESS, [("readWithoutVerdicts", [with_server_verdicts(report)])])[0] is None
