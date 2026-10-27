"""Outcome counts and roles of the verdict summary (``outcomes``, ``outcome_roles``, ``runs``)
and GET /config ``summary_outcomes``, which qrosetta's --fail-on reads."""
import asyncio

import numpy as np
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("pytket")

from qrosetta_commons.helpers import encode_statevector  # noqa: E402
from services.aggregator import compile_comparison_reports  # noqa: E402
from services.analysis.divergence import ANALYSIS_VERSION  # noqa: E402
from services.report_summary import OUTCOME_ROLES, outcome_catalog, report_summary  # noqa: E402


def _report(vectors, extra=()):
    results = [{"simulator": name, "statevector": encode_statevector(sv), "qubit_ordering": "msb",
                "dispatch_status": "ok"} for name, sv in vectors]
    results += list(extra)
    div, _, _ = asyncio.run(compile_comparison_reports(results, None))
    return {"raw_results": results, "divergence_report": div}


def _vec(seed):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=4) + 1j * rng.normal(size=4)
    return v / np.linalg.norm(v)


def test_outcomes_count_each_pair_under_its_verdict_and_runs_without_output():
    a, b = _vec(1), _vec(2)
    report = _report([("qiskit", a), ("cirq", a), ("qulacs", b)],
                     [{"simulator": "quest", "dispatch_status": "timeout", "error": "TIMEOUT"}])
    out = report_summary(report, "server_job")
    verdicts = [v["verdict"] for v in out["pair_verdicts"]]
    for name in ("differs", "agrees", "not_comparable", "inconclusive", "differs_by_only", "bit_order", "unassessed"):
        assert out["outcomes"][name] == verdicts.count(name)
    assert out["outcomes"]["differs"] == 2 and out["outcomes"]["agrees"] == 1
    assert out["outcomes"]["runs_without_output"] == 1 and out["outcomes"]["no_comparison"] == 0
    assert out["runs"] == {"total": 4, "returned": 3, "without_output": 1, "circuit_failed": False}
    assert out["outcome_roles"] == OUTCOME_ROLES


def test_no_comparison_and_a_failed_circuit():
    failed = {"error": "does not parse"}
    out = report_summary(failed, "client_supplied")
    assert out["outcomes"]["no_comparison"] == 1 and out["outcomes"]["runs_without_output"] == 1
    single = report_summary(_report([("qiskit", _vec(1))]), "server_job")
    assert single["outcomes"]["no_comparison"] == 1 and single["outcomes"]["runs_without_output"] == 0


def test_playlist_outcomes_are_sums_over_tasks():
    a = _vec(3)
    task = _report([("qiskit", a), ("cirq", a)])
    out = report_summary({"benchmark_summary": [task, task, {"error": "bad"}]}, "server_job")
    assert out["outcomes"]["agrees"] == 2 and out["outcomes"]["runs_without_output"] == 1
    assert out["runs"] == {"total": 4, "returned": 4, "without_output": 0, "circuits_failed": 1}
    assert [t["outcomes"]["agrees"] for t in out["benchmark_summary"]] == [1, 1, 0]


def test_every_role_is_one_the_cli_maps_and_every_verdict_has_a_role():
    from schemas.reports import PairVerdict
    verdicts = PairVerdict.model_fields["verdict"].annotation.__args__
    assert set(verdicts) <= set(OUTCOME_ROLES)
    assert set(OUTCOME_ROLES.values()) == {"difference", "not_established", "runs_without_output", "agreement"}


def test_config_publishes_the_outcome_catalog():
    from main import app
    body = TestClient(app).get("/config").json()
    assert body["summary_outcomes"] == outcome_catalog()
    assert body["summary_outcomes"]["analysis_version"] == ANALYSIS_VERSION
    assert body["server"]["features"]["summary"] == 1
