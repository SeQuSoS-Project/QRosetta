# Unit tests for the publication-artifact engine (services/publication.py).

import pytest

from services.publication import (
    build_publication_artifacts,
    list_artifacts,
    render_artifact,
    PUBLICATION_CATEGORIES,
    SUPPORTED_FIGURE_FORMATS,
    SUPPORTED_TABLE_FORMATS,
)

MEASURED = {
    "n_shots": 128,
    "seed": 12345,
    "divergence_report": {
        "simulators": ["qiskit", "qibo"],
        "statistical_distance_matrix (js_divergence)": [[-1.0, 0.69], [0.69, -1.0]],
        "hellinger_distance_matrix": [[-1.0, 1.0], [1.0, -1.0]],
        "pairwise_agreement": [
            {
                "simulators": ["qiskit", "qibo"],
                "mode": "measured",
                "agreement": "agree_after_bit_reversal",
                "registered_transform": "bit_reversal",
                "metrics": {
                    "js_divergence": 0.6931,
                    "statistical_test": {
                        "basis": "bit_reversal", "verdict": "consistent",
                        "effect_size": {"total_variation": 0.0, "cramers_v": 0.0},
                        "power": {"power_to_detect_delta_at_observed_shots": 0.126,
                                  "shots_per_backend_for_target_power": 1570},
                        "chi2": {"p_value": 1.0, "p_value_bh": 1.0},
                        "g_test": {"p_value": 1.0, "p_value_bh": 1.0},
                    },
                },
            }
        ],
        "statistical_test_summary": {"family_size": 1, "verdict_counts": {"consistent": 1}},
    },
    "performance_report": {"ranking": [
        {"simulator": "qiskit", "status": "success", "compilation_time_sec": 0.01,
         "simulation_time_sec": 0.08, "execution_time_sec": 0.09, "cpu_time_sec": 0.085,
         "gate_count": 3, "circuit_depth": 3},
        {"simulator": "qibo", "status": "success", "compilation_time_sec": 0.02,
         "simulation_time_sec": 0.03, "execution_time_sec": 0.05, "cpu_time_sec": 0.048,
         "gate_count": 3, "circuit_depth": 3},
    ]},
    "resource_report": {"ranking": [
        {"simulator": "qibo", "status": "success", "memory_usage_mb": 10.0, "process_peak_mb": 100.0,
         "process_peak_rss_mb": 95.5},
        {"simulator": "qiskit", "status": "success", "memory_usage_mb": 12.5, "process_peak_mb": 120.0,
         "process_peak_rss_mb": 110.3},
    ]},
    "raw_results": [
        {"simulator": "qiskit", "counts": {"001": 128}},
        {"simulator": "qibo", "counts": {"100": 128}},
    ],
}

STATEVECTOR = {
    "divergence_report": {
        "simulators": ["qiskit", "cirq"],
        "fidelity_matrix": [[-1.0, 0.0], [0.0, -1.0]],
        "pairwise_agreement": [
            {"simulators": ["qiskit", "cirq"], "mode": "statevector",
             "agreement": "agree_after_bit_reversal", "registered_transform": "bit_reversal",
             "metrics": {"direct_fidelity": 0.0, "bit_reversed_fidelity": 1.0}},
        ],
    },
    "performance_report": {"ranking": [
        {"simulator": "qiskit", "status": "success", "compilation_time_sec": 0.01,
         "simulation_time_sec": 0.04, "execution_time_sec": 0.05},
    ]},
    "resource_report": {"ranking": []},
}

_MAGIC = {
    "svg": lambda b: b"<svg" in b[:400],
    "png": lambda b: b[:8] == b"\x89PNG\r\n\x1a\n",
    "pdf": lambda b: b[:5] == b"%PDF-",
    "xlsx": lambda b: b[:2] == b"PK",
}


def _all_measured():
    return build_publication_artifacts(
        MEASURED, "measured", PUBLICATION_CATEGORIES,
        figure_formats=SUPPORTED_FIGURE_FORMATS, table_formats=SUPPORTED_TABLE_FORMATS)


def test_all_figure_formats_have_valid_magic_bytes():
    arts = _all_measured()
    figs = {p: b for p, b in arts.items() if p.startswith("figures/")}
    assert figs
    for path, data in figs.items():
        ext = path.rsplit(".", 1)[1]
        assert _MAGIC[ext](data), f"{path} failed magic check"


def test_all_tables_present_in_all_formats():
    arts = _all_measured()
    for base in ("agreement", "performance", "resources", "statistical_test"):
        for ext in ("csv", "latex", "html", "xlsx"):
            assert f"tables/{base}.{ext}" in arts, f"missing tables/{base}.{ext}"
    assert _MAGIC["xlsx"](arts["tables/agreement.xlsx"])


def test_artifacts_are_byte_deterministic():
    # SVG/PNG/PDF figures and CSV/LaTeX/HTML tables are byte-reproducible. XLSX is a ZIP
    # container whose member timestamps vary; it is asserted structurally below instead.
    a1 = _all_measured()
    a2 = _all_measured()
    assert a1.keys() == a2.keys()
    for path in a1:
        if path.endswith(".xlsx"):
            continue
        assert a1[path] == a2[path], f"{path} not reproducible"


def test_xlsx_tables_are_valid_and_reopenable():
    import io
    from openpyxl import load_workbook
    arts = _all_measured()
    xlsx = [b for p, b in arts.items() if p.endswith(".xlsx")]
    assert xlsx
    for data in xlsx:
        assert data[:2] == b"PK"
        wb = load_workbook(io.BytesIO(data))  # must reopen without error
        assert wb.active.max_row >= 3  # title + caption + header at minimum


def test_latex_uses_booktabs_and_escapes_underscores():
    arts = build_publication_artifacts(MEASURED, "measured", ("agreement",),
                                       (), ("latex",))
    tex = arts["tables/agreement.latex"].decode()
    assert "\\toprule" in tex and "\\bottomrule" in tex and "booktabs" in tex
    assert "agree\\_after\\_bit\\_reversal" in tex  # underscore escaped
    assert "registered-transform lattice" in tex  # caption present


def test_agreement_table_content():
    arts = build_publication_artifacts(MEASURED, "measured", ("agreement",), (), ("csv",))
    csv = arts["tables/agreement.csv"].decode()
    assert "qiskit × qibo" in csv
    assert "agree_after_bit_reversal" in csv
    assert "consistent" in csv  # statistical verdict column present for measured


def test_statistical_test_table_measured_only():
    measured = build_publication_artifacts(MEASURED, "measured", ("statistical",), (), ("csv",))
    assert "tables/statistical_test.csv" in measured
    csv = measured["tables/statistical_test.csv"].decode()
    assert "1570" in csv and "consistent" in csv  # shots-for-power + verdict
    # statevector has no statistical test -> no table, no histograms
    sv = build_publication_artifacts(STATEVECTOR, "statevector", ("statistical",),
                                     SUPPORTED_FIGURE_FORMATS, SUPPORTED_TABLE_FORMATS)
    assert not any("statistical_test" in p for p in sv)
    assert not any("histogram" in p for p in sv)


def test_mode_branching_heatmaps():
    sv = build_publication_artifacts(STATEVECTOR, "statevector", ("heatmaps",),
                                     ("svg",), ())
    assert "figures/fidelity_heatmap.svg" in sv
    assert not any("js_divergence" in p or "hellinger" in p for p in sv)
    measured = build_publication_artifacts(MEASURED, "measured", ("heatmaps",), ("svg",), ())
    assert "figures/js_divergence_heatmap.svg" in measured
    assert "figures/hellinger_heatmap.svg" in measured
    assert not any("fidelity" in p for p in measured)


def test_heatmap_handles_sentinel_and_errored_runner():
    # A 3-runner report with a -1.0 sentinel row (errored/incomparable) must not crash.
    report = {
        "divergence_report": {
            "simulators": ["a", "b", "c"],
            "fidelity_matrix": [[-1.0, 1.0, -1.0], [1.0, -1.0, -1.0], [-1.0, -1.0, -1.0]],
            "pairwise_agreement": [],
        },
    }
    arts = build_publication_artifacts(report, "statevector", ("heatmaps",), ("svg",), ())
    assert "figures/fidelity_heatmap.svg" in arts
    assert _MAGIC["svg"](arts["figures/fidelity_heatmap.svg"])


def test_graceful_when_reports_absent():
    # No pairwise records -> no agreement artifacts; empty results -> empty output, no crash.
    assert build_publication_artifacts({}, "measured", PUBLICATION_CATEGORIES,
                                       SUPPORTED_FIGURE_FORMATS, SUPPORTED_TABLE_FORMATS) == {}
    no_pairwise = {"divergence_report": {"simulators": ["a", "b"], "fidelity_matrix": [[-1.0, 1.0], [1.0, -1.0]]}}
    arts = build_publication_artifacts(no_pairwise, "statevector", ("agreement", "heatmaps"), ("svg",), ("csv",))
    assert not any("agreement" in p for p in arts)   # no pairwise -> no agreement fig/table
    assert "figures/fidelity_heatmap.svg" in arts     # heatmap still produced


def test_unsupported_formats_ignored():
    arts = build_publication_artifacts(MEASURED, "measured", ("agreement",),
                                       ("svg", "bogus"), ("csv", "nope"))
    assert "figures/agreement_distribution.svg" in arts
    assert "tables/agreement.csv" in arts
    assert not any(p.endswith(".bogus") or p.endswith(".nope") for p in arts)


# --- Interactive catalog + single-artifact render (used by the Artifacts tab) ---------

def test_catalog_lists_expected_artifacts_measured():
    ids = {a["id"] for a in list_artifacts(MEASURED, "measured")}
    # existing figure/table artifacts
    assert {"agreement_distribution", "agreement", "js_divergence_heatmap",
            "hellinger_heatmap", "performance_time", "resource_memory",
            "performance", "resources", "statistical_test"} <= ids
    # new artifacts
    assert {"matrix_js", "matrix_hellinger", "metadata", "glossary"} <= ids
    assert any(i.startswith("histogram_") for i in ids)
    # statevector-only artifact absent
    assert "fidelity_heatmap" not in ids


def test_catalog_statevector_branches():
    ids = {a["id"] for a in list_artifacts(STATEVECTOR, "statevector")}
    assert "fidelity_heatmap" in ids and "matrix_fidelity" in ids
    assert not any("hellinger" in i or "js_divergence" in i for i in ids)
    assert not any(i == "statistical_test" or i.startswith("histogram_") for i in ids)
    assert "glossary" in ids


def test_catalog_entries_have_view_formats_legend():
    for a in list_artifacts(MEASURED, "measured"):
        assert a["view"] in ("image", "text")
        assert a["formats"] and a["legend"]
        if a["view"] == "image":
            assert set(a["formats"]) == set(SUPPORTED_FIGURE_FORMATS)


def test_render_artifact_image_scale_increases_size():
    small, mime, legend = render_artifact(MEASURED, "measured", "agreement_distribution", "png", 1)
    big, _, _ = render_artifact(MEASURED, "measured", "agreement_distribution", "png", 5)
    assert small[:8] == b"\x89PNG\r\n\x1a\n" and big[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(big) > len(small)  # higher dpi => more pixels/bytes
    assert mime == "image/png" and legend


def test_render_artifact_text_formats():
    for fmt in ("latex", "csv", "html", "markdown"):
        data, mime, _ = render_artifact(MEASURED, "measured", "agreement", fmt)
        assert data and isinstance(data, bytes)
    md = render_artifact(MEASURED, "measured", "agreement", "markdown")[0].decode()
    assert md.startswith("**") and "|" in md  # markdown table


def test_render_new_artifacts_content():
    # matrix-as-table
    mjs = render_artifact(MEASURED, "measured", "matrix_js", "csv")[0].decode()
    assert "qiskit" in mjs and "qibo" in mjs
    # metadata table carries provenance
    meta = render_artifact(MEASURED, "measured", "metadata", "csv")[0].decode()
    assert "qiskit" in meta
    # glossary text
    gloss = render_artifact(MEASURED, "measured", "glossary", "markdown")[0].decode()
    assert "agree_after_bit_reversal" in gloss and "consistent" in gloss


def test_render_artifact_rejects_bad_id_and_format():
    with pytest.raises(KeyError):
        render_artifact(MEASURED, "measured", "does_not_exist", "png")
    with pytest.raises(ValueError):
        render_artifact(MEASURED, "measured", "agreement", "png")  # table has no png


# --- counts_overview (total count heatmap) ------------------------------------------

def test_counts_overview_available_measured_only():
    ids = {a["id"] for a in list_artifacts(MEASURED, "measured")}
    assert "counts_overview" in ids  # >= 2 backends with counts
    assert "counts_overview" not in {a["id"] for a in list_artifacts(STATEVECTOR, "statevector")}


def test_counts_overview_renders_all_figure_formats():
    for fmt in SUPPORTED_FIGURE_FORMATS:
        data, mime, legend = render_artifact(MEASURED, "measured", "counts_overview", fmt)
        assert _MAGIC[fmt](data) and legend


def test_counts_overview_absent_with_fewer_than_two_count_backends():
    one = dict(MEASURED, raw_results=[{"simulator": "qiskit", "counts": {"001": 128}}])
    assert "counts_overview" not in {a["id"] for a in list_artifacts(one, "measured")}


def test_counts_overview_in_statistical_bundle():
    files = build_publication_artifacts(MEASURED, "measured", ("statistical",),
                                        figure_formats=("svg",), table_formats=("csv",))
    assert "figures/counts_overview.svg" in files


def test_counts_overview_heatmap_available_and_renders():
    ids = {a["id"] for a in list_artifacts(MEASURED, "measured")}
    assert "counts_overview_heatmap" in ids  # optional secondary view
    data, _, _ = render_artifact(MEASURED, "measured", "counts_overview_heatmap", "png")
    assert _MAGIC["png"](data)


def test_counts_overview_size_bounded_for_many_outcomes():
    from services.publication import (_fig_counts_overview_bars, _fig_counts_overview_heatmap,
                                      MAX_OVERVIEW_BARS, MAX_OVERVIEW_OUTCOMES)
    import matplotlib.pyplot as plt
    # 8-qubit spread across 5 backends: outcome space 256, must stay compact.
    cbs = {s: {format(i, "08b"): 1 for i in range(256)} for s in
           ["qiskit", "qibo", "cirq", "pennylane", "braket"]}
    for s in cbs:
        cbs[s]["00000000"] = 1500
    bars = _fig_counts_overview_bars(cbs, list(cbs))
    try:
        w, h = bars.get_size_inches()
        assert w <= 13.0 and h <= 5.0  # bars: capped width, never stretches with 2**n
        # x groups = shown outcomes (+ 'other'), bounded by the cap not the outcome space
        assert len(bars.axes[0].get_xticklabels()) <= MAX_OVERVIEW_BARS + 1
    finally:
        plt.close(bars)
    heat = _fig_counts_overview_heatmap(cbs, list(cbs))
    try:
        w, h = heat.get_size_inches()
        assert w <= 11.0 and h <= 10.0
        assert len(heat.axes[0].get_yticklabels()) <= MAX_OVERVIEW_OUTCOMES + 1
    finally:
        plt.close(heat)


def test_rank_outcomes_folds_noise_into_other():
    from services.publication import _rank_outcomes
    # one dominant outcome + many noise outcomes below MIN_OUTCOME_PROB
    probs = {"000": 0.9}
    for i in range(1, 40):
        probs[format(i, "03b") + format(i, "05b")] = 0.001
    outcomes = list(probs)
    kept, rest = _rank_outcomes(outcomes, lambda o: probs.get(o, 0.0), cap=20)
    assert kept == ["000"] and len(rest) == 39  # noise all folded away
    # nothing hidden when everything is significant and fits
    kept2, rest2 = _rank_outcomes(["a", "b"], lambda o: 0.5, cap=20)
    assert set(kept2) == {"a", "b"} and rest2 == []
