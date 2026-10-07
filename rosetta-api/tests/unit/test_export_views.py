"""Export views: parameter validation, file-name slugs, the measured-distribution data,
crate items and POST /publication/render with parameters."""
import json

import pytest

from services.publication import (
    ParameterError, build_publication_items, item_paths, list_artifacts, normalize_params,
    render_artifact, view_defaults, view_slug,
)
from services.publication.distributions import count_selection, hamming, marginals, spread
from services.publication.subset import subset_results
from tests.unit.test_publication import MEASURED, STATEVECTOR


def _report():
    """Three backends on 3 classical bits; b declares lsb, so its keys are reversed."""
    return {
        "n_shots": 100, "task_name": "toy (3q)",
        "divergence_report": {"simulators": ["a", "b", "c"], "pairwise_agreement": [
            {"simulators": ["a", "b"], "mode": "measured", "measured_assessment": "distinguishable"},
            {"simulators": ["a", "c"], "mode": "measured",
             "measured_assessment": "consistent_within_shot_noise"},
            {"simulators": ["b", "c"], "mode": "measured",
             "measured_assessment": "consistent_within_shot_noise",
             "marginal_assessment": "marginal_distinguishable"}]},
        "raw_results": [
            {"simulator": "a", "qubit_ordering": "msb", "counts": {"000": 50, "110": 30, "001": 20}},
            {"simulator": "b", "qubit_ordering": "lsb", "counts": {"000": 40, "011": 40, "100": 20}},
            {"simulator": "c", "qubit_ordering": "msb", "counts": {"111": 100}},
            {"simulator": "d", "error": "boom"},
        ],
    }


def test_defaults_fill_in_and_backends_collapse_to_none():
    rep = _report()
    p = normalize_params("counts", {}, rep)
    assert p["backends"] is None and p["ref"] == "a" and p["bits"] == [0, 1, 2]
    assert normalize_params("counts", {"backends": ["c", "a", "b", "d"]}, rep)["backends"] is None
    p = normalize_params("counts", {"backends": ["c", "a"]}, rep)
    assert p["backends"] == ["a", "c"] and p["ref"] == "a"


@pytest.mark.parametrize("params,msg", [
    ({"nope": 1}, "unknown parameter"),
    ({"layout": "pie"}, "layout must be one of"),
    ({"top": 0}, "top must be an integer from 1 to 64"),
    ({"top": True}, "top must be an integer"),
    ({"threshold": float("nan")}, "threshold must be a number"),
    ({"backends": ["zz"]}, "backends not in this report"),
    ({"backends": []}, "select at least one backend"),
    ({"backends": ["a"], "ref": "b"}, "ref must be one of the selected backends"),
    ({"bits": [0, 0]}, "distinct"),
    ({"bits": [3]}, "between 0 and 2"),
    ({"bits": list(range(7))}, "1 to 6"),
    ({"size": "poster"}, "size must be one of"),
])
def test_bad_parameters_are_rejected(params, msg):
    with pytest.raises(ValueError, match=msg):
        normalize_params("counts", params, _report())


def test_tables_and_text_take_no_figure_parameters():
    with pytest.raises(ValueError, match="unknown parameter"):
        normalize_params("agreement", {"size": "single"}, _report())
    assert set(view_defaults("glossary")) == {"backends"}


def test_slug_names_non_default_parameters_only():
    rep = _report()
    assert view_slug("counts", normalize_params("counts", {}, rep), rep) == "counts"
    p = normalize_params("counts", {"layout": "diff", "ref": "b", "threshold": 1e-05,
                                    "other": False, "bits": [2, 0], "backends": ["a", "b"]}, rep)
    assert view_slug("counts", p, rep) == (
        "counts_2-backends_layout-diff_ref-b_threshold-1e-05_bits-2-0_no-other")
    p = normalize_params("counts", {"backends": ["b", "c"]}, rep)
    assert view_slug("counts", p, rep) == "counts_2-backends"


def test_count_selection_aligns_lsb_keys_and_folds_the_rest():
    rep = _report()
    sel = count_selection(rep, normalize_params("counts", {"top": 2}, rep))
    assert sel["cp"]["sims"] == ["a", "b", "c"] and sel["cp"]["missing"] == ["d"]
    assert [r["label"] for r in sel["rows"]] == ["111", "000", "other (+2)"]
    assert sel["rows"][1]["vals"] == [0.5, 0.4, 0.0]
    assert sel["rows"][2]["vals"] == pytest.approx([0.5, 0.6, 0.0])
    assert sel["other"]["share"] == "36.7"
    assert "the other 2 (36.7% of shots on average) are summed into 'other'" in sel["note"]
    lsb = count_selection(rep, normalize_params("counts", {"keyorder": "lsb", "sort": "bitstring"}, rep))
    assert [r["label"] for r in lsb["rows"]] == ["000", "011", "100", "111"]


def test_marginal_over_chosen_bits_sums_out_the_rest():
    rep = _report()
    sel = count_selection(rep, normalize_params(
        "counts", {"outcomes": "bits", "bits": [2, 0], "sort": "bitstring"}, rep))
    assert [r["label"] for r in sel["rows"]] == ["00", "01", "10", "11"]
    b = {r["label"]: r["vals"][1] for r in sel["rows"]}
    assert b == pytest.approx({"00": 0.4, "01": 0.4, "10": 0.2, "11": 0.0})
    assert sel["key_note"] == "keys read c[2] c[0] from left to right"


def test_single_bit_marginals_hamming_and_spread():
    rep = _report()
    m = marginals(rep)
    assert m["m"]["a"] == pytest.approx([0.3, 0.3, 0.2])
    assert m["m"]["b"] == pytest.approx([0.4, 0.4, 0.2])
    h = hamming(rep)
    assert h["h"]["a"] == pytest.approx([0.5, 0.2, 0.3, 0.0])
    assert h["h"]["c"] == pytest.approx([0, 0, 0, 1.0])
    s = spread(rep)["rows"]
    assert (s["a"]["observed"], s["a"]["half"], s["a"]["ninety"]) == (3, 1, 3)
    assert (s["b"]["half"], s["b"]["ninety"]) == (2, 3)


def test_subset_slices_matrices_and_filters_pairs():
    rep = {**_report()}
    rep["divergence_report"] = {**rep["divergence_report"],
                                "m": [[0, 1, 2], [1, 0, 3], [2, 3, 0]]}
    sub = subset_results(rep, ["a", "c"])
    assert sub["divergence_report"]["simulators"] == ["a", "c"]
    assert sub["divergence_report"]["m"] == [[0, 2], [2, 0]]
    assert [r["simulators"] for r in sub["divergence_report"]["pairwise_agreement"]] == [["a", "c"]]
    assert [r["simulator"] for r in sub["raw_results"]] == ["a", "c"]
    assert rep["divergence_report"]["simulators"] == ["a", "b", "c"]


def test_render_uses_the_backend_subset_and_size():
    rep = _report()
    _, _, legend = render_artifact(rep, "measured", "counts_overview", "svg",
                                   params={"backends": ["a", "b"]})
    assert "for 2 backend(s)" in legend
    small = render_artifact(rep, "measured", "counts_overview", "svg", params={"size": "single"})[0]
    assert b'width="2' in small[:600] or b"width='2" in small[:600]
    with pytest.raises(ValueError, match="takes no parameters"):
        render_artifact(rep, "measured", "circuit_a", "text", params={"x": 1})


def test_highlight_names_the_rule_in_the_caption():
    rep = _report()
    legend = list_artifacts(rep, "measured", {"counts": {"colour": "highlight", "ref": "b"}})
    cap = next(a["legend"] for a in legend if a["id"] == "counts_overview")
    assert "Coloured: backends whose pair with b is a disagreement" in cap


def test_items_write_figures_specs_and_tables_with_unique_names():
    rep = _report()
    files, desc = build_publication_items(rep, "measured", [
        {"view": "counts", "params": {"layout": "diff"}, "formats": ["svg", "csv", "latex"]},
        {"view": "counts", "params": {"layout": "diff"}, "formats": ["png"]},
        {"view": "glossary", "params": {}, "formats": ["markdown"]},
        {"view": "metadata", "params": {"backends": ["a"]}, "formats": ["csv"]},
    ])
    assert sorted(files) == sorted(
        item_paths("counts", "counts_layout-diff", ["svg", "csv", "latex"])
        + item_paths("counts", "counts_layout-diff-2", ["png"])
        + item_paths("glossary", "glossary", ["markdown"])
        + item_paths("metadata", "metadata_1-backends", ["csv"]))
    spec = json.loads(files["figures/counts_layout-diff.spec.json"])
    assert spec["view"] == "counts" and spec["parameters"]["layout"] == "diff"
    assert spec["caption"] == desc["figures/counts_layout-diff.svg"]
    assert files["tables/metadata_1-backends.csv"].decode().count("\n") == 2
    assert "reference/glossary.md" in files


def test_items_skip_views_the_report_lacks_and_reject_bad_input():
    files, _ = build_publication_items(STATEVECTOR, "statevector",
                                       [{"view": "counts", "params": {}, "formats": ["svg"]}])
    assert files == {}
    with pytest.raises(ParameterError, match="not offered"):
        build_publication_items(MEASURED, "measured",
                                [{"view": "agreement", "params": {}, "formats": ["svg"]}])
    with pytest.raises(ParameterError, match="layout must be one of"):
        build_publication_items(MEASURED, "measured",
                                [{"view": "counts", "params": {"layout": "x"}, "formats": ["svg"]}])


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_render_endpoint_takes_params_and_rejects_bad_ones(client):
    body = {"results": _report(), "artifact_id": "hamming_weight", "format": "svg",
            "params": {"layout": "diff", "ref": "b"}}
    r = client.post("/publication/render", json=body)
    assert r.status_code == 200 and r.content.startswith(b"<?xml")
    r = client.post("/publication/render", json={**body, "params": {"layout": "pie"}})
    assert r.status_code == 400 and "layout must be one of" in r.json()["detail"]


def test_export_with_bad_item_is_a_400(client):
    body = {"results": {**MEASURED, "input_qasm": "OPENQASM 2.0;\nqreg q[3];\n"},
            "publication_artifacts": {"items": [
                {"view": "counts", "params": {"top": 500}, "formats": ["svg"]}]}}
    r = client.post("/export", json=body)
    assert r.status_code == 400 and "top must be an integer" in r.json()["detail"]


def test_job_render_reads_the_server_copy(client):
    from services.job_manager import ACTIVE_JOBS
    ACTIVE_JOBS["job-x"] = {"status": "completed", "full_results": _report(), "results": _report()}
    ACTIVE_JOBS["job-b"] = {"status": "completed",
                            "full_results": {"benchmark_summary": [_report()]},
                            "results": {"benchmark_summary": [_report()]}}
    try:
        r = client.post("/jobs/job-x/publication/render",
                        json={"artifact_id": "qubit_marginals", "format": "svg", "params": {"layout": "diff"}})
        assert r.status_code == 200 and r.content.startswith(b"<?xml")
        assert client.post("/jobs/nope/publication/render",
                           json={"artifact_id": "x", "format": "svg"}).status_code == 404
        r = client.post("/jobs/job-b/publication/render", json={"artifact_id": "hamming_weight", "format": "svg"})
        assert r.status_code == 400 and "task" in r.json()["detail"]
        r = client.post("/jobs/job-b/publication/render",
                        json={"artifact_id": "hamming_weight", "format": "svg", "task": 0})
        assert r.status_code == 200
        assert client.post("/jobs/job-b/publication/render",
                           json={"artifact_id": "hamming_weight", "format": "svg", "task": 3}).status_code == 404
    finally:
        ACTIVE_JOBS.pop("job-x", None)
        ACTIVE_JOBS.pop("job-b", None)


def test_export_view_literal_matches_the_views():
    from typing import get_args
    from schemas.benchmark import ExportView
    from services.publication.views import VIEW_BY_ID
    assert set(get_args(ExportView)) == set(VIEW_BY_ID)


def test_ref_defaults_to_a_backend_with_counts_and_rejects_one_without():
    rep = _report()
    rep["divergence_report"]["simulators"] = ["d", "a", "b", "c"]
    assert normalize_params("counts", {}, rep)["ref"] == "a"
    with pytest.raises(ParameterError, match="ref must be a backend with counts; d has none"):
        normalize_params("counts", {"ref": "d", "layout": "diff"}, rep)
    assert normalize_params("counts", {"backends": ["d"]}, rep)["ref"] is None


def test_title_off_keeps_panel_labels():
    rep = _report()
    with_t = render_artifact(rep, "measured", "counts_overview", "svg", params={"layout": "panels"})[0]
    no_t = render_artifact(rep, "measured", "counts_overview", "svg",
                           params={"layout": "panels", "title": False})[0]
    assert b"Measured outcome probabilities" in with_t and b"Measured outcome probabilities" not in no_t
    for sim in (b">a<", b">b<", b">c<"):
        assert sim in no_t


def test_render_errors_that_are_not_parameter_errors_are_500(client, monkeypatch):
    import routers.publication as pub
    def boom(*a, **k):
        raise ValueError("internal numpy detail")
    monkeypatch.setattr(pub, "render_artifact", boom)
    r = client.post("/publication/render", json={"results": _report(), "artifact_id": "hamming_weight", "format": "svg"})
    assert r.status_code == 500 and "numpy" not in r.text


def test_playlist_crate_names_the_circuit_on_a_bad_item():
    from services.exporter import _generate_publication_artifacts, build_export_context
    import schemas
    task = {**_report(), "task_name": "toy (3q)", "input_qasm": "OPENQASM 2.0;\nqreg q[3];\n"}
    payload = schemas.ExportPayload(publication_artifacts={"items": [
        {"view": "counts", "params": {"backends": ["zz"]}, "formats": ["svg"]}]})
    ctx = build_export_context({"benchmark_summary": [task]}, payload)
    with pytest.raises(ParameterError, match="circuit toy \\(3q\\): counts: backends not in this report"):
        _generate_publication_artifacts(ctx)
