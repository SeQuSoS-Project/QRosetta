"""Artifact catalog for a report, single-artifact rendering and the RO-Crate bundle builder.

The catalog (ids, labels, groups, legends, availability) is mirrored by
buildArtifactCatalog in static/js/artifact_formats.js.
"""

from typing import Dict, List, Tuple

from qrosetta_commons.helpers import get_logger

from .theme import (
    MAX_HISTOGRAM_PAIRS, MIME_TYPES, SUPPORTED_FIGURE_FORMATS,
    SUPPORTED_TABLE_FORMATS, TAB_TABLE_FORMATS,
)
from .figures import (
    _fig_agreement_distribution, _fig_count_histogram, _fig_counts_overview_bars,
    _fig_counts_overview_heatmap, _fig_heatmap, _fig_ranking_bar,
)
from .formats import _render_figure, _table_bytes, basename_slug
from .selectors import (
    COMMON_KEY_ORDER_NOTE, JS_UNIT, _circuit_name, _distinct, _heatmap_specs, _msb_counts,
    _pairwise_records, _run_label, _timing_repeated, _timing_samples,
)
from .tables import (
    _tbl_agreement, _tbl_matrix, _tbl_metadata, _tbl_performance, _tbl_resources,
    _tbl_statistical, _txt_executed_qasm, _txt_glossary,
)

logger = get_logger("rosetta-publication")


def _iter_artifacts(results: dict, mode: str) -> List[dict]:
    """Return the artifact descriptors available for this report.

    Each is {id, label, group, view ('image'|'text'), formats, legend, _render}, where
    _render(fmt, scale) -> bytes.
    """
    div = results.get("divergence_report", {}) or {}
    out: List[dict] = []

    def fig_artifact(aid, label, group, build_fig, legend):
        out.append({"id": aid, "label": label, "group": group, "view": "image",
                    "formats": list(SUPPORTED_FIGURE_FORMATS), "legend": legend,
                    "_render": lambda fmt, scale, bf=build_fig: _render_figure(bf, fmt, scale)})

    def table_artifact(aid, label, group, build_data, legend):
        out.append({"id": aid, "label": label, "group": group, "view": "text",
                    "formats": list(TAB_TABLE_FORMATS), "legend": legend, "_data": build_data,
                    "_render": lambda fmt, scale, bd=build_data: _table_bytes(*bd(), fmt)})

    def text_artifact(aid, label, group, build_text, formats, legend):
        out.append({"id": aid, "label": label, "group": group, "view": "text",
                    "formats": list(formats), "legend": legend,
                    "_render": lambda fmt, scale, bt=build_text: bt().encode("utf-8")})

    records = _pairwise_records(div)
    if records:
        fig_artifact("agreement_distribution", "Agreement class distribution", "Agreement",
                     lambda: _fig_agreement_distribution(div, mode),
                     "Bar chart of how many backend pairs fall into each agreement label "
                     "(transform-explained, residual or not comparable)"
                     + (" and shot-noise verdict" if mode == "measured" else "") + ".")
        table_artifact("agreement", "Pairwise agreement table", "Agreement",
                       lambda: _tbl_agreement(div, mode),
                       "One row per backend pair: explained-cause label, registered transform, key "
                       f"metric (direct fidelity, or JS divergence in {JS_UNIT} direct and in the "
                       "label-aligned basis), statistical verdict and measured assessment "
                       "(measured) and not-comparable reason.")

    multi = len(div.get("simulators", [])) >= 2
    for key, title, base in _heatmap_specs(mode):
        if multi and isinstance(div.get(key), list) and div.get(key):
            fig_artifact(base, title.split("(")[0].strip() + " heatmap", "Divergence",
                         lambda k=key, t=title: _fig_heatmap(div, k, t),
                         f"{title}: N×N heatmap; darker = larger value. Not-compared pairs "
                         "and the diagonal shown neutral.")
            mid = {"fidelity_matrix": "matrix_fidelity",
                   "statistical_distance_matrix (js_divergence)": "matrix_js",
                   "hellinger_distance_matrix": "matrix_hellinger"}[key]
            table_artifact(mid, title.split("(")[0].strip() + " matrix (table)", "Divergence",
                           lambda k=key, t=title: _tbl_matrix(div, k, t),
                           f"{title} as a copyable N×N matrix table (raw metric).")

    unranked_note = "runs without a rank are listed with their status and reason and have no bar."
    perf = results.get("performance_report") or {}
    repeated = _timing_repeated(results)
    if perf.get("ranking") or perf.get("unranked"):
        fig_artifact("performance_time", "Execution-time chart", "Performance",
                     lambda: _fig_ranking_bar(results, "performance_report",
                                              [("compilation_time_sec", "#2a78d6", "compilation"),
                                               ("simulation_time_sec", "#1baf7a", "simulation")],
                                              f"Wall-clock time by stage: {_circuit_name(results)}",
                                              "seconds",
                                              (f"medians of n={_timing_samples(results)} timed "
                                               "runs per backend; warm-up excluded")
                                              if repeated else
                                              (f"n={_timing_samples(results)} timing sample(s) per "
                                               "backend; timed run only, warm-up excluded")),
                     "Stacked compilation + simulation wall-clock time per backend "
                     + ("(median of each stage over the timed runs), " if repeated else "(raw), ")
                     + f"n={_timing_samples(results)} timing sample(s) per backend; GPU runs are "
                     "labelled (GPU); " + unranked_note)
        table_artifact("performance", "Execution-time table", "Performance",
                       lambda: _tbl_performance(results),
                       "Per-backend device, compilation, simulation and total wall-clock time"
                       + (" (medians, with the IQR, stdev and n of total time)" if repeated else "")
                       + ", simulation and process CPU time, and status (raw).")

    res = results.get("resource_report") or {}
    if res.get("ranking") or res.get("unranked"):
        fig_artifact("resource_memory", "Process peak RSS chart", "Resources",
                     lambda: _fig_ranking_bar(results, "resource_report",
                                              [("process_peak_rss_mb", "#2a78d6", "process peak RSS")],
                                              "Process peak RSS (whole runner process): "
                                              f"{_circuit_name(results)}", "MiB",
                                              "includes interpreter start, SDK import and warm-up; "
                                              "SDK import dominates for small circuits"),
                     "Peak RSS of each backend's simulating process over its whole life "
                     "(interpreter start, imports, warm-up and every timed run), in MiB; method: "
                     f"{_distinct(results, 'process_peak_rss_method')}. Ranked lowest first; GPU "
                     "runs are labelled (GPU) and not ranked because GPU device memory is not "
                     "measured; " + unranked_note)
        table_artifact("resources", "Resource-usage table", "Resources",
                       lambda: _tbl_resources(results),
                       "Per-backend device, process peak RSS, sim-window peak RSS and RSS delta, "
                       "theoretical statevector size, precision and status (raw).")

    if mode == "measured":
        if any((r.get("metrics", {}) or {}).get("statistical_test") for r in records):
            table_artifact("statistical_test", "Statistical-test table", "Statistical",
                           lambda: _tbl_statistical(div),
                           "Chi-square + G-test p-values (raw + BY) in the label-aligned basis, "
                           "effect size, power and pooled outcomes per pair.")
        raw = _msb_counts(results)
        run_label = _run_label(results)
        missing = []
        for r in results.get("raw_results", []):
            sim = r.get("simulator")
            if sim and sim not in raw and sim not in missing:
                missing.append(sim)
        missing_note = (f" Backends without counts are not drawn: {', '.join(missing)}."
                        if missing else "")
        if len(raw) >= 2:
            order = div.get("simulators") or [r.get("simulator") for r in results.get("raw_results", [])]
            sims_order = [s for s in order if s in raw]
            fig_artifact("counts_overview", "Count overview (all backends)", "Statistical",
                         lambda cbs=dict(raw), so=list(sims_order):
                         _fig_counts_overview_bars(cbs, so, run_label),
                         "Clustered bar histogram of measured probabilities, one colour per "
                         "backend over the top outcomes (Qiskit plot_histogram convention), "
                         f"{COMMON_KEY_ORDER_NOTE}; low-probability outcomes are folded into "
                         "'other' (disclosed in-figure)."
                         + missing_note)
            fig_artifact("counts_overview_heatmap", "Count overview heatmap (optional)", "Statistical",
                         lambda cbs=dict(raw), so=list(sims_order):
                         _fig_counts_overview_heatmap(cbs, so, run_label),
                         "Optional compact view: outcome × backend probability heatmap, "
                         f"{COMMON_KEY_ORDER_NOTE}; a uniform "
                         "row = agreement, a varying row = disagreement. Scales to many backends."
                         + missing_note)
        eligible = [rec for rec in records
                    if raw.get((rec.get("simulators") or [None, None])[0])
                    and raw.get((rec.get("simulators") or [None, None])[1])]
        cap_note = (f" Histograms are generated for the first {MAX_HISTOGRAM_PAIRS} of "
                    f"{len(eligible)} backend pairs with counts."
                    if len(eligible) > MAX_HISTOGRAM_PAIRS else "")
        for rec in eligible[:MAX_HISTOGRAM_PAIRS]:
            a, b = rec["simulators"][0], rec["simulators"][1]
            slug = basename_slug(f"{a}_{b}")
            fig_artifact(f"histogram_{slug}", f"Count histogram: {a} vs {b}", "Statistical",
                         lambda ca=raw[a], cb=raw[b], aa=a, bb=b:
                         _fig_count_histogram(ca, cb, aa, bb, run_label),
                         f"Measured probability distributions for {a} vs {b}, "
                         f"{COMMON_KEY_ORDER_NOTE}." + cap_note)

    if results.get("raw_results"):
        table_artifact("metadata", "Run + provenance metadata", "Metadata",
                       lambda: _tbl_metadata(results, mode),
                       "Backends, device, SDK versions, qubit-ordering & sampling labels, opt level, run params.")
        for r in results.get("raw_results", []):
            sim = r.get("simulator")
            if sim and r.get("transpiled_qasm"):
                text_artifact(f"circuit_{basename_slug(sim)}", f"Executed QASM: {sim}", "Circuits",
                              lambda s=sim: _txt_executed_qasm(results, s), ("qasm", "text"),
                              f"The exact transpiled OpenQASM executed by the {sim} adapter.")

    terms = ["agreement class", "not-comparable reason"]
    if mode == "measured":
        terms.append("statistical verdict")
    terms.append("unranked reason")
    text_artifact("glossary", "Taxonomy glossary", "Reference",
                  lambda: _txt_glossary(mode), ("markdown", "text"),
                  "Definitions of every " + ", ".join(terms) + ", plus the default thresholds.")
    return out


def list_artifacts(results: dict, mode: str) -> List[dict]:
    """Public catalog for the interactive tab: descriptors without the render callable."""
    return [{k: a[k] for k in ("id", "label", "group", "view", "formats", "legend")}
            for a in _iter_artifacts(results, mode)]


def render_artifact(results: dict, mode: str, artifact_id: str, fmt: str,
                    scale: int = 1) -> Tuple[bytes, str, str]:
    """Render one artifact -> (bytes, mime, legend). Raises KeyError/ValueError if invalid."""
    for a in _iter_artifacts(results, mode):
        if a["id"] == artifact_id:
            if fmt not in a["formats"]:
                raise ValueError(f"format '{fmt}' not supported for '{artifact_id}'")
            data = a["_render"](fmt, max(1, int(scale)))
            return data, MIME_TYPES.get(fmt, "application/octet-stream"), a["legend"]
    raise KeyError(artifact_id)


def describe_artifact_paths(results: dict, mode: str, paths: List[str]) -> Dict[str, str]:
    """{path: description} for bundle paths "figures/<id>.<fmt>" / "tables/<id>.<fmt>":
    the artifact legend, plus the table title and caption for tables."""
    by_id = {a["id"]: a for a in _iter_artifacts(results, mode)}
    out: Dict[str, str] = {}
    for path in paths:
        aid, _, fmt = path.rsplit("/", 1)[-1].rpartition(".")
        a = by_id.get(aid)
        if not a:
            continue
        text = a["legend"]
        if "_data" in a:
            _, _, title, caption = a["_data"]()
            where = ("The file carries no caption; it is " if fmt == "csv"
                     else "The file carries the caption ")
            text += f" {where}\"{title}. {caption}\""
        out[path] = text
    return out


_BUNDLE_FIGURES = {
    "agreement": ["agreement_distribution"],
    "heatmaps": ["fidelity_heatmap", "js_divergence_heatmap", "hellinger_heatmap"],
    "performance": ["performance_time", "resource_memory"],
    "statistical": ["counts_overview", "__histograms__"],
}
_BUNDLE_TABLES = {
    "agreement": ["agreement"],
    "performance": ["performance", "resources"],
    "statistical": ["statistical_test"],
}


def build_publication_artifacts(results: dict, mode: str, categories: Tuple[str, ...],
                                figure_formats: Tuple[str, ...] = ("svg",),
                                table_formats: Tuple[str, ...] = ("csv",)) -> Dict[str, bytes]:
    """Build the selected artifacts as {relative_path: bytes} for the RO-Crate bundle.

    Generates only what the report supports; "__histograms__" expands to every
    histogram_* artifact.
    """
    figure_formats = tuple(f for f in figure_formats if f in SUPPORTED_FIGURE_FORMATS)
    table_formats = tuple(f for f in table_formats if f in SUPPORTED_TABLE_FORMATS)
    by_id = {a["id"]: a for a in _iter_artifacts(results, mode)}
    artifacts: Dict[str, bytes] = {}
    try:
        for cat in categories:
            for aid in _BUNDLE_FIGURES.get(cat, []):
                ids = ([k for k in by_id if k.startswith("histogram_")]
                       if aid == "__histograms__" else [aid])
                for real_id in ids:
                    a = by_id.get(real_id)
                    if not a or a["view"] != "image":
                        continue
                    for fmt in figure_formats:
                        artifacts[f"figures/{real_id}.{fmt}"] = a["_render"](fmt, 1)
            for aid in _BUNDLE_TABLES.get(cat, []):
                a = by_id.get(aid)
                if not a or a["view"] != "text":
                    continue
                for fmt in table_formats:
                    artifacts[f"tables/{aid}.{fmt}"] = a["_render"](fmt, 1)
    except Exception:
        logger.error("Publication artifact generation failed", exc_info=True)
        raise
    logger.info(f"Built {len(artifacts)} publication artifact file(s)")
    return artifacts
