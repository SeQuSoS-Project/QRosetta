"""V1-05: a client-supplied report cannot ask for an n x n render or summary beyond what a server
job produces, and a render that cannot get the figure renderer is a 503 with Retry-After."""
import threading
import time

import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from config import settings  # noqa: E402
from main import app  # noqa: E402
from services.publication import theme  # noqa: E402
from services.report_validation import report_caps, report_problems  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    from services.security import limiter
    monkeypatch.setattr(limiter, "enabled", False)
    return TestClient(app)


def _report(n_backends: int) -> dict:
    sims = [f"qiskit~opt0~run{i}" for i in range(n_backends)]
    return {"raw_results": [{"simulator": s, "statevector": ""} for s in sims],
            "divergence_report": {"simulators": sims,
                                  "fidelity_matrix": [[1.0] * n_backends for _ in sims],
                                  "all_outcomes_observed": ["0"] * 5000}}


def test_v1_05_reports_up_to_the_caps_pass_and_beyond_them_are_refused():
    keys = report_caps()["max_report_runner_keys"]
    assert report_problems(_report(keys)) == []
    assert "raw_results holds" in report_problems(_report(keys + 1))[0]
    wide = _report(2)
    wide["divergence_report"]["fidelity_matrix"] = [[1.0] * (keys + 1)] * 2
    assert "fidelity_matrix" in report_problems(wide)[0]
    pairs = _report(2)
    pairs["divergence_report"]["pairwise_agreement"] = [{}] * (report_caps()["max_report_pairs"] + 1)
    assert "pairwise_agreement" in report_problems(pairs)[0]
    batch = {"benchmark_summary": [{"raw_results": []}] * (settings.MAX_REPORT_TASKS + 1)}
    assert "circuits" in report_problems(batch)[0]


def test_v1_05_the_caps_are_published_and_enforced_on_the_routes(client):
    limits = client.get("/config").json()["limits"]
    assert {k: limits[k] for k in report_caps()} == report_caps()
    big = _report(report_caps()["max_report_runner_keys"] + 1)
    for path, body in (("/summary", {"results": big}),
                       ("/publication/render", {"results": big, "artifact_id": "fidelity_heatmap", "format": "svg"}),
                       ("/publication/artifacts", {"results": big})):
        response = client.post(path, json=body)
        assert response.status_code == 400, path
        assert "at most" in response.json()["detail"]


def test_v1_05_a_render_waits_a_bounded_time_for_the_renderer(client, monkeypatch):
    monkeypatch.setattr(settings, "RENDER_LOCK_WAIT_SEC", 0.2)
    from tests.unit.test_publication import MEASURED as report
    artifacts = client.post("/publication/artifacts", json={"results": report}).json()
    figure = next(a["id"] for a in artifacts if "svg" in a["formats"])
    held, release = threading.Event(), threading.Event()

    def hold():
        with theme.mpl_lock():
            held.set()
            release.wait(10)
    holder = threading.Thread(target=hold)
    holder.start()
    held.wait(5)
    try:
        started = time.monotonic()
        response = client.post("/publication/render", json={"results": report, "artifact_id": figure, "format": "svg"})
        assert time.monotonic() - started < 5
    finally:
        release.set()
        holder.join()
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "10"
    assert client.post("/publication/render", json={"results": report, "artifact_id": figure,
                                                    "format": "svg"}).status_code == 200


def test_v1_05_without_a_wait_set_the_lock_waits_without_limit():
    with theme.render_lock_wait(None):
        with theme.mpl_lock():
            pass
    with theme.render_lock_wait(0.01), theme.mpl_lock():
        with pytest.raises(theme.RendererBusy):
            with theme.render_lock_wait(0.01), theme.mpl_lock():
                pass
