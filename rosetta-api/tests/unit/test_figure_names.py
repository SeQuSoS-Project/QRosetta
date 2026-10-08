"""Figures name the circuit as the app does (also when drawn from a job's server copy), name
backends by the app's long display names, and keep 16:9 at the slide size."""

import struct

import pytest

from services.publication import render_artifact
from services.publication.theme import BACKEND_DISPLAY_NAMES, backend_label
from tests.unit.frontend_harness import call_js, requires_node

COUNTS = {
    "n_shots": 100,
    "raw_results": [
        {"simulator": "qiskit", "counts": {"00": 50, "11": 50}, "qubit_ordering": "lsb"},
        {"simulator": "qsim-cirq", "counts": {"00": 48, "11": 52}, "qubit_ordering": "msb"},
        {"simulator": "pennylane-lightning~opt1~run2", "counts": {"00": 51, "11": 49},
         "qubit_ordering": "lsb"},
    ],
    "divergence_report": {"pairwise_agreement": []},
}


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_job_figures_use_the_circuit_name_the_browser_sends(client):
    from services.job_manager import ACTIVE_JOBS
    ACTIVE_JOBS["job-name"] = {"status": "completed", "full_results": COUNTS, "results": COUNTS}
    try:
        body = {"artifact_id": "counts_overview", "format": "svg"}
        unnamed = client.post("/jobs/job-name/publication/render", json=body)
        named = client.post("/jobs/job-name/publication/render",
                            json={**body, "circuit_name": "Bell State (Simple) (2q)"})
    finally:
        ACTIVE_JOBS.pop("job-name", None)
    assert unnamed.status_code == 200 and b"unnamed circuit" in unnamed.content
    assert named.status_code == 200 and b"Bell State (Simple) (2q)" in named.content
    assert b"unnamed circuit" not in named.content


def test_legends_use_display_names():
    svg, _, legend = render_artifact(COUNTS, "measured", "counts_overview", "svg", 1,
                                     {"colour": "highlight", "ref": "qsim-cirq"})
    assert b"Qiskit (IBM)" in svg and b"qsim (Google)" in svg
    assert "PL Lightning · L1 #2".encode() in svg
    assert b">qiskit<" not in svg
    assert "pair with qsim (Google)" in legend


@pytest.mark.parametrize("size,ratio", [("slide", 16 / 9)])
def test_slide_figures_keep_their_aspect_ratio(size, ratio):
    for artifact in ("counts_overview", "qubit_marginals", "js_divergence_heatmap"):
        report = {**COUNTS, "divergence_report": {
            "simulators": ["qiskit", "qsim-cirq"], "pairwise_agreement": [],
            "statistical_distance_matrix (js_divergence)": [[0.0, 0.001], [0.001, 0.0]],
            "hellinger_distance_matrix": [[0.0, 0.01], [0.01, 0.0]]}}
        png, _, _ = render_artifact(report, "measured", artifact, "png", 1, {"size": size})
        width, height = struct.unpack(">II", png[16:24])
        assert abs(width / height - ratio) < 0.01, (artifact, width, height)


def test_concurrent_renders_at_different_sizes_do_not_share_settings():
    from concurrent.futures import ThreadPoolExecutor

    def render(size):
        png, _, _ = render_artifact(COUNTS, "measured", "counts_overview", "png", 1, {"size": size})
        return struct.unpack(">II", png[16:24])

    alone = {size: render(size) for size in ("slide", "single")}
    with ThreadPoolExecutor(max_workers=2) as pool:
        mixed = list(pool.map(render, ["slide", "single"] * 6))
    assert mixed == [alone["slide"], alone["single"]] * 6


@requires_node
def test_display_names_match_the_browser_register():
    keys = list(BACKEND_DISPLAY_NAMES) + ["qiskit~opt2~run1", "unknown-sim", "qibo~opt0~run3"]
    assert call_js(["runner_key.js"], [("backendLabel", [k]) for k in keys]) == [
        backend_label(k) for k in keys]
