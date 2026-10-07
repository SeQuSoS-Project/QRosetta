"""Artifact catalog for a report and single-artifact rendering.

The catalog (ids, labels, groups, legends, availability) is mirrored by
buildArtifactCatalog in static/js/artifact_catalog.js; items.py builds crate files from it.
"""

from typing import Dict, List, Optional

from qrosetta_commons.helpers import get_logger

from .theme import MIME_TYPES, SUPPORTED_FIGURE_FORMATS, TAB_TABLE_FORMATS
from .figures import _fig_agreement_distribution, _fig_heatmap, _fig_ranking_bar
from .figures_counts import fig_counts, fig_hamming, fig_marginals, fig_rank
from .distributions import (
    count_probabilities, counts_legend, hamming_legend, marginals_legend, rank_legend,
    tbl_counts, tbl_hamming, tbl_marginals, tbl_rank,
)
from .subset import subset_results
from .views import VIEW_OF_ARTIFACT, ParameterError, normalize_params
from .formats import _render_figure, _table_bytes, basename_slug
from .selectors import (
    JS_UNIT, _circuit_name, _distinct, _heatmap_specs, _pairwise_records, _timing_repeated,
    _timing_samples,
)
from .tables import (
    _tbl_agreement, _tbl_matrix, _tbl_metadata, _tbl_performance, _tbl_resources,
    _tbl_statistical, _txt_executed_qasm, _txt_glossary,
)

logger = get_logger("rosetta-publication")


def _iter_artifacts(results: dict, mode: str, params: Optional[Dict[str, dict]] = None,
                    only: Optional[str] = None) -> List[dict]:
    """Return the artifact descriptors available for this report.

    Each is {id, label, group, view ('image'|'text'), view_id, formats, legend, _render},
    where _render(fmt, scale) -> bytes; ``legend`` is a string or a callable returning it
    (_legend resolves either). ``params`` maps a view id to its normalised
    parameters (normalize_params); views not in it use their defaults. Figures render at the
    view's size preset and title setting. ``only`` keeps just that artifact, so a render
    builds one descriptor instead of the catalog.
    """
    div = results.get("divergence_report", {}) or {}
    out: List[dict] = []
    params = dict(params or {})

    def vp(aid):
        vid = VIEW_OF_ARTIFACT.get(aid)
        if vid is None:
            return None, {}
        if vid not in params:
            params[vid] = normalize_params(vid, {}, results)
        return vid, params[vid]

    def want(*aids):
        return only is None or only in aids

    def fig_artifact(aid, label, group, build_fig, legend):
        if not want(aid):
            return
        vid, p = vp(aid)
        out.append({"id": aid, "label": label, "group": group, "view": "image", "view_id": vid,
                    "formats": list(SUPPORTED_FIGURE_FORMATS), "legend": legend,
                    "_render": lambda fmt, scale, bf=build_fig: _render_figure(
                        bf, fmt, scale, p.get("size", "auto"), p.get("title", True))})

    def table_artifact(aid, label, group, build_data, legend):
        if not want(aid):
            return
        vid, _ = vp(aid)
        out.append({"id": aid, "label": label, "group": group, "view": "text", "view_id": vid,
                    "formats": list(TAB_TABLE_FORMATS), "legend": legend, "_data": build_data,
                    "_render": lambda fmt, scale, bd=build_data: _table_bytes(*bd(), fmt)})

    def text_artifact(aid, label, group, build_text, formats, legend):
        if not want(aid):
            return
        vid, _ = vp(aid)
        out.append({"id": aid, "label": label, "group": group, "view": "text", "view_id": vid,
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
        _, pt = vp("performance_time")
        stages = {"stacked": [("compilation_time_sec", "#2a78d6", "compilation"),
                              ("simulation_time_sec", "#1baf7a", "simulation")],
                  "simulation": [("simulation_time_sec", "#1baf7a", "simulation")],
                  "compilation": [("compilation_time_sec", "#2a78d6", "compilation")]}[pt["stage"]]
        stage_text = {"stacked": "Stacked compilation + simulation", "simulation": "Simulation",
                      "compilation": "Compilation"}[pt["stage"]]
        log = pt["xscale"] == "log" and pt["stage"] != "stacked"
        fig_artifact("performance_time", "Execution-time chart", "Performance",
                     lambda: _fig_ranking_bar(results, "performance_report", stages,
                                              f"Wall-clock time by stage: {_circuit_name(results)}",
                                              "seconds",
                                              (f"medians of n={_timing_samples(results)} timed "
                                               "runs per backend; warm-up excluded")
                                              if repeated else
                                              (f"n={_timing_samples(results)} timing sample(s) per "
                                               "backend; timed run only, warm-up excluded"),
                                              xscale="log" if log else "linear"),
                     f"{stage_text} wall-clock time per backend "
                     + ("(median of each stage over the timed runs), " if repeated else "(raw), ")
                     + f"n={_timing_samples(results)} timing sample(s) per backend; GPU runs are "
                     "labelled (GPU); " + unranked_note
                     + (" Logarithmic time axis." if log else ""))
        table_artifact("performance", "Execution-time table", "Performance",
                       lambda: _tbl_performance(results),
                       "Per-backend device, compilation, simulation and total wall-clock time"
                       + (" (medians, with the IQR, stdev and n of total time)" if repeated else "")
                       + ", simulation and process CPU time, and status (raw).")

    res = results.get("resource_report") or {}
    if res.get("ranking") or res.get("unranked"):
        _, pr = vp("resource_memory")
        if pr["metric"] == "memory_delta":
            fig_artifact("resource_memory", "Process peak RSS chart", "Resources",
                         lambda: _fig_ranking_bar(results, "resource_report",
                                                  [("memory_usage_mb", "#2a78d6", "sim-window RSS delta")],
                                                  "Sim-window RSS delta: "
                                                  f"{_circuit_name(results)}", "MiB",
                                                  "first timed run; bars in resource-ranking order"),
                         "Sim-window RSS delta of each backend (peak minus RSS at monitor entry over "
                         "the pre-execute step and simulation window of the first timed run), in "
                         f"MiB; method: {_distinct(results, 'memory_method')}. It reads near 0 when "
                         "the simulation reuses memory the warm-up freed. Bars follow the resource "
                         "ranking (process peak RSS); GPU runs are labelled (GPU); " + unranked_note)
        else:
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
        if count_probabilities(results)["sims"]:
            if want("counts_overview", "counts_table"):
                _, pc = vp("counts_overview")
                fig_artifact("counts_overview", "Count comparison", "Statistical",
                             lambda: fig_counts(results, pc), lambda: counts_legend(results, pc))
                table_artifact("counts_table", "Count comparison (table)", "Statistical",
                               lambda: tbl_counts(results, pc),
                               "Measured probability of each shown outcome (rows) per backend (columns).")
            if want("qubit_marginals", "qubit_marginals_table"):
                _, pm = vp("qubit_marginals")
                fig_artifact("qubit_marginals", "Single-bit marginals", "Statistical",
                             lambda: fig_marginals(results, pm), lambda: marginals_legend(results, pm))
                table_artifact("qubit_marginals_table", "Single-bit marginals (table)", "Statistical",
                               lambda: tbl_marginals(results, pm),
                               "P(c[j] = 1) for each classical bit j (rows) per backend (columns).")
            if want("hamming_weight", "hamming_weight_table"):
                _, ph = vp("hamming_weight")
                fig_artifact("hamming_weight", "Hamming-weight distribution", "Statistical",
                             lambda: fig_hamming(results, ph), lambda: hamming_legend(results, ph))
                table_artifact("hamming_weight_table", "Hamming-weight distribution (table)",
                               "Statistical", lambda: tbl_hamming(results, ph),
                               "Probability of each Hamming weight (rows) per backend (columns).")
            if want("rank_probability", "rank_probability_table"):
                _, pk = vp("rank_probability")
                fig_artifact("rank_probability", "Outcome probabilities by rank", "Statistical",
                             lambda: fig_rank(results, pk), lambda: rank_legend(results, pk))
                table_artifact("rank_probability_table", "Outcome spread (table)", "Statistical",
                               lambda: tbl_rank(results, pk),
                               "Per backend: shots, observed outcomes, largest probability and the "
                               "outcomes covering 50% and 90% of the shots.")

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


def _legend(a: dict) -> str:
    """The artifact's legend, computing it when it is deferred."""
    return a["legend"]() if callable(a["legend"]) else a["legend"]


def list_artifacts(results: dict, mode: str, params: Optional[Dict[str, dict]] = None) -> List[dict]:
    """The catalog without render callables, legends resolved: the reference the browser's
    buildArtifactCatalog is tested against. ``params`` maps a view id to raw parameters."""
    norm = {vid: normalize_params(vid, p, results) for vid, p in (params or {}).items()}
    return [{**{k: a[k] for k in ("id", "label", "group", "view", "view_id", "formats")},
             "legend": _legend(a)} for a in _iter_artifacts(results, mode, norm)]


def _scoped(results: dict, view_id: Optional[str], params: Optional[dict]):
    """(report restricted to the view's backends, normalised params by view id)."""
    if view_id is None:
        if params:
            raise ParameterError("this artifact takes no parameters")
        return results, {}
    p = normalize_params(view_id, params, results)
    scoped = subset_results(results, p["backends"]) if p["backends"] else results
    return scoped, {view_id: p}


def render_artifact(results: dict, mode: str, artifact_id: str, fmt: str, scale: int = 1,
                    params: Optional[dict] = None, with_legend: bool = True):
    """Render one artifact with its view's ``params`` -> (bytes, mime, legend or None).
    Raises KeyError for an unknown artifact and ParameterError for a bad format or
    parameter."""
    scoped, norm = _scoped(results, VIEW_OF_ARTIFACT.get(artifact_id), params)
    for a in _iter_artifacts(scoped, mode, norm, only=artifact_id):
        if fmt not in a["formats"]:
            raise ParameterError(f"format '{fmt}' not supported for '{artifact_id}'")
        data = a["_render"](fmt, max(1, int(scale)))
        return (data, MIME_TYPES.get(fmt, "application/octet-stream"),
                _legend(a) if with_legend else None)
    raise KeyError(artifact_id)
