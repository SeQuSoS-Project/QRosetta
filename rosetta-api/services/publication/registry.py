# What artifacts exist for a given report, and how to render one.

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
from .selectors import _heatmap_specs, _pairwise_records
from .tables import (
    _tbl_agreement, _tbl_matrix, _tbl_metadata, _tbl_performance, _tbl_resources,
    _tbl_statistical, _txt_executed_qasm, _txt_glossary,
)

logger = get_logger("rosetta-publication")


def _iter_artifacts(results: dict, mode: str) -> List[dict]:
    """Build the list of artifact descriptors available for this report.

    Each descriptor: {id, label, group, view ('image'|'text'), formats, legend, _render}
    where _render(fmt, scale) -> bytes.
    """
    div = results.get("divergence_report", {}) or {}
    out: List[dict] = []

    def fig_artifact(aid, label, group, build_fig, legend):
        out.append({"id": aid, "label": label, "group": group, "view": "image",
                    "formats": list(SUPPORTED_FIGURE_FORMATS), "legend": legend,
                    "_render": lambda fmt, scale, bf=build_fig: _render_figure(bf, fmt, scale)})

    def table_artifact(aid, label, group, build_data, legend):
        out.append({"id": aid, "label": label, "group": group, "view": "text",
                    "formats": list(TAB_TABLE_FORMATS), "legend": legend,
                    "_render": lambda fmt, scale, bd=build_data: _table_bytes(*bd(), fmt)})

    def text_artifact(aid, label, group, build_text, formats, legend):
        out.append({"id": aid, "label": label, "group": group, "view": "text",
                    "formats": list(formats), "legend": legend,
                    "_render": lambda fmt, scale, bt=build_text: bt().encode("utf-8")})

    records = _pairwise_records(div)
    if records:
        fig_artifact("agreement_distribution", "Agreement class distribution", "Agreement",
                     lambda: _fig_agreement_distribution(div, mode),
                     "Bar chart of how many backend pairs fall into each explained-cause class"
                     + (" and shot-noise verdict" if mode == "measured" else "") + ".")
        table_artifact("agreement", "Pairwise agreement table", "Agreement",
                       lambda: _tbl_agreement(div, mode),
                       "One row per backend pair: explained-cause label, registered transform, key "
                       "metric, and (measured) statistical verdict. Analysis, not verification.")

    multi = len(div.get("simulators", [])) >= 2  # a heatmap/matrix needs at least a pair
    for key, title, base in _heatmap_specs(mode):
        if multi and isinstance(div.get(key), list) and div.get(key):
            fig_artifact(base, title.split("(")[0].strip() + " heatmap", "Divergence",
                         lambda k=key, t=title: _fig_heatmap(div, k, t),
                         f"{title}: N×N heatmap; darker = larger value. −1/diagonal shown neutral.")
            mid = {"fidelity_matrix": "matrix_fidelity",
                   "statistical_distance_matrix (js_divergence)": "matrix_js",
                   "hellinger_distance_matrix": "matrix_hellinger"}[key]
            table_artifact(mid, title.split("(")[0].strip() + " matrix (table)", "Divergence",
                           lambda k=key, t=title: _tbl_matrix(div, k, t),
                           f"{title} as a copyable N×N matrix table (raw metric).")

    if (results.get("performance_report") or {}).get("ranking"):
        fig_artifact("performance_time", "Execution-time chart", "Performance",
                     lambda: _fig_ranking_bar((results["performance_report"]["ranking"]),
                                              [("compilation_time_sec", "#2a78d6", "compilation"),
                                               ("simulation_time_sec", "#1baf7a", "simulation")],
                                              "Execution time by stage", "seconds"),
                     "Stacked compilation + simulation wall-clock time per backend (raw).")
        table_artifact("performance", "Execution-time table", "Performance",
                       lambda: _tbl_performance(results),
                       "Per-backend compilation/simulation/total time and status (raw).")

    if (results.get("resource_report") or {}).get("ranking"):
        fig_artifact("resource_memory", "Process-peak memory chart", "Resources",
                     lambda: _fig_ranking_bar((results["resource_report"]["ranking"]),
                                              [("process_peak_mb", "#2a78d6", "process peak")],
                                              "Process peak memory", "MiB"),
                     "Peak process memory per backend (raw).")
        table_artifact("resources", "Resource-usage table", "Resources",
                       lambda: _tbl_resources(results),
                       "Per-backend memory delta, process peak, theoretical SV, status (raw).")

    if mode == "measured":
        if any((r.get("metrics", {}) or {}).get("statistical_test") for r in records):
            table_artifact("statistical_test", "Statistical-test table", "Statistical",
                           lambda: _tbl_statistical(div),
                           "Chi-square + G-test p-values (raw + BH), effect size, power per pair.")
        raw = {r.get("simulator"): r.get("counts") for r in results.get("raw_results", [])
               if isinstance(r.get("counts"), dict) and r.get("counts")}
        # Total count figure: one compact outcome × backend heatmap over every backend that
        # produced counts, so many backends do not require a wall of per-pair histograms.
        if len(raw) >= 2:
            order = div.get("simulators") or [r.get("simulator") for r in results.get("raw_results", [])]
            sims_order = [s for s in order if s in raw]
            fig_artifact("counts_overview", "Count overview (all backends)", "Statistical",
                         lambda cbs=dict(raw), so=list(sims_order): _fig_counts_overview_bars(cbs, so),
                         "Clustered bar histogram of raw measured probabilities, one colour per "
                         "backend over the top outcomes (Qiskit plot_histogram convention); "
                         "low-probability outcomes are folded into 'other' (disclosed in-figure).")
            fig_artifact("counts_overview_heatmap", "Count overview heatmap (optional)", "Statistical",
                         lambda cbs=dict(raw), so=list(sims_order): _fig_counts_overview_heatmap(cbs, so),
                         "Optional compact view: outcome × backend probability heatmap; a uniform "
                         "row = agreement, a varying row = disagreement. Scales to many backends.")
        for rec in records[:MAX_HISTOGRAM_PAIRS]:
            a, b = rec.get("simulators", [None, None])
            if raw.get(a) and raw.get(b):
                slug = basename_slug(f"{a}_{b}")
                fig_artifact(f"histogram_{slug}", f"Count histogram: {a} vs {b}", "Statistical",
                             lambda ca=raw[a], cb=raw[b], aa=a, bb=b: _fig_count_histogram(ca, cb, aa, bb),
                             f"Raw measured probability distributions for {a} vs {b}.")

    if results.get("raw_results"):
        table_artifact("metadata", "Run + provenance metadata", "Metadata",
                       lambda: _tbl_metadata(results, mode),
                       "Backends, SDK versions, qubit-ordering & sampling labels, opt level, run params.")
        for r in results.get("raw_results", []):
            sim = r.get("simulator")
            if sim and r.get("transpiled_qasm"):
                text_artifact(f"circuit_{basename_slug(sim)}", f"Executed QASM: {sim}", "Circuits",
                              lambda s=sim: _txt_executed_qasm(results, s), ("qasm", "text"),
                              f"The exact transpiled OpenQASM executed by the {sim} adapter.")

    text_artifact("glossary", "Taxonomy glossary", "Reference",
                  lambda: _txt_glossary(mode), ("markdown", "text"),
                  "Definitions of every agreement class"
                  + (" and statistical verdict" if mode == "measured" else "") + ".")
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


# --- RO-Crate bundle (unchanged output: same paths, same categories) ------------------

# Which artifact ids belong to each bundle category (keeps the export bundle identical).
_BUNDLE_FIGURES = {
    "agreement": ["agreement_distribution"],
    "heatmaps": ["fidelity_heatmap", "js_divergence_heatmap", "hellinger_heatmap"],
    "performance": ["performance_time", "resource_memory"],
    "statistical": ["counts_overview", "__histograms__"],  # total heatmap + all histogram_* ids
}
_BUNDLE_TABLES = {
    "agreement": ["agreement"],
    "performance": ["performance", "resources"],
    "statistical": ["statistical_test"],
}


def build_publication_artifacts(results: dict, mode: str, categories: Tuple[str, ...],
                                figure_formats: Tuple[str, ...] = ("svg",),
                                table_formats: Tuple[str, ...] = ("csv",)) -> Dict[str, bytes]:
    """Build the selected publication artifacts as {relative_path: bytes} (RO-Crate bundle).

    Deterministic and side-effect free; generates only what the report supports. Output
    paths and category membership follow the export-bundle contract; the interactive tab
    exposes additional artifacts.
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
