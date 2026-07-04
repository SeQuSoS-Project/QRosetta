# Publication-ready artifact engine — deterministic figures + tables from a report.
#
# Turns a QRosetta results dict into publication-grade figures (SVG/PNG/PDF via
# matplotlib) and tables (LaTeX/CSV/HTML/Markdown/XLSX). Artifact/usability feature,
# NOT a new scientific claim: every artifact is generated deterministically from the
# stored report data, preserves provenance, and labels raw metrics vs transformed
# analysis evidence. Two entry points share the same builders:
#   * build_publication_artifacts(...)  -> {relative_path: bytes}  (RO-Crate bundle)
#   * list_artifacts(...) / render_artifact(...)                    (interactive tab)

import csv
import io
from datetime import datetime
from html import escape as _html_escape
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # headless, deterministic — before pyplot import
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
from openpyxl import Workbook

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-publication")

SUPPORTED_FIGURE_FORMATS = ("svg", "png", "pdf")
SUPPORTED_TABLE_FORMATS = ("latex", "csv", "html", "xlsx")          # RO-Crate bundle
TAB_TABLE_FORMATS = ("latex", "csv", "html", "markdown", "xlsx")    # interactive tab
PUBLICATION_CATEGORIES = ("agreement", "heatmaps", "performance", "statistical")

MAX_HISTOGRAM_PAIRS = 12
BASE_DPI = 150  # logical/screen dpi; raster dpi = BASE_DPI * scale

MIME_TYPES = {
    "svg": "image/svg+xml", "png": "image/png", "pdf": "application/pdf",
    "csv": "text/csv", "latex": "application/x-latex", "html": "text/html",
    "markdown": "text/markdown", "text": "text/plain", "qasm": "text/x-qasm",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# --- Deterministic matplotlib configuration -------------------------------------------
plt.rcParams.update({
    "figure.dpi": BASE_DPI, "savefig.dpi": BASE_DPI,
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"], "font.size": 10,
    "axes.titlesize": 12, "axes.labelsize": 10,
    "axes.edgecolor": "#c3c2b7", "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "svg.hashsalt": "qrosetta-publication", "svg.fonttype": "none",
})

# --- Palette (validated subset of the dataviz reference palette) ----------------------
_INK = "#0b0b0b"
_MUTED = "#898781"
_NEUTRAL_FILL = "#e1e0d9"
AGREEMENT_COLORS = {
    "agree_directly": "#008300", "distance_within_threshold": "#008300",
    "agree_up_to_global_phase": "#1baf7a", "agree_after_bit_reversal": "#2a78d6",
    "agree_after_qubit_permutation": "#4a3aa7",
    "residual_disagreement": "#e34948", "distance_exceeds_threshold": "#e34948",
    "not_comparable": _MUTED,
}
VERDICT_COLORS = {
    "consistent": "#0ca30c", "distinguishable": "#d03b3b",
    "inconclusive_low_shots": _MUTED, "ambiguous": "#fab219",
}
_AGREEMENT_ORDER = [
    "agree_directly", "agree_up_to_global_phase", "agree_after_bit_reversal",
    "agree_after_qubit_permutation", "residual_disagreement",
    "distance_within_threshold", "distance_exceeds_threshold", "not_comparable",
]
_VERDICT_ORDER = ["consistent", "distinguishable", "inconclusive_low_shots", "ambiguous"]
_SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# Human-readable definitions reused by the glossary artifact + figure/table legends.
_AGREEMENT_GLOSSARY = [
    ("agree_directly", "Outputs match directly, no transform needed."),
    ("agree_up_to_global_phase", "Match after removing an overall (unobservable) global phase."),
    ("agree_after_bit_reversal", "Match after reversing qubit/bit order (an endianness convention)."),
    ("agree_after_qubit_permutation", "Match after a bounded qubit permutation (≤6 qubits)."),
    ("residual_disagreement", "Statevector disagreement not explained by any registered transform."),
    ("distance_within_threshold", "Measured distributions within the JS/Hellinger thresholds."),
    ("distance_exceeds_threshold", "Measured distributions exceed thresholds after registered transforms."),
    ("not_comparable", "At least one side lacks usable output; the pair cannot be compared."),
]
_VERDICT_GLOSSARY = [
    ("consistent", "Shot-noise test finds no significant difference (after FDR correction)."),
    ("distinguishable", "Both tests find a significant difference after FDR correction."),
    ("inconclusive_low_shots", "Expected counts too low for a reliable test."),
    ("ambiguous", "The chi-square and G-test disagree (rare)."),
]


def _blue_cmap():
    cmap = LinearSegmentedColormap.from_list("qrosetta_blue", _SEQ_BLUE)
    cmap.set_bad(_NEUTRAL_FILL)
    return cmap


# --- Format helpers -------------------------------------------------------------------

def _savefig_bytes(fig, fmt: str, scale: int = 1) -> bytes:
    buf = io.BytesIO()
    metadata = {"svg": {"Date": None}, "pdf": {"CreationDate": None},
                "png": {"Software": None}}[fmt]
    fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=BASE_DPI * max(1, scale),
                metadata=metadata)
    return buf.getvalue()


def _render_figure(build_fig, fmt: str, scale: int = 1) -> bytes:
    """Build a fresh figure, render one format, and always close it (no figure leak)."""
    fig = build_fig()
    try:
        return _savefig_bytes(fig, fmt, scale)
    finally:
        plt.close(fig)


def _fmt_num(v: Any, digits: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return "—" if np.isnan(v) else f"{v:.{digits}f}"
    return str(v)


_LATEX_ESCAPE = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _latex_escape(text: Any) -> str:
    return "".join(_LATEX_ESCAPE.get(ch, ch) for ch in str(text))


def basename_slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


def _render_latex(headers, rows, title, caption) -> str:
    col_spec = "l" * len(headers)
    lines = [
        "% Requires \\usepackage{booktabs}",
        "\\begin{table}[htbp]", "  \\centering",
        f"  \\caption{{{_latex_escape(title)}. {_latex_escape(caption)}}}",
        f"  \\label{{tab:{basename_slug(title)}}}",
        f"  \\begin{{tabular}}{{{col_spec}}}", "    \\toprule",
        "    " + " & ".join(_latex_escape(h) for h in headers) + " \\\\", "    \\midrule",
    ]
    for r in rows:
        lines.append("    " + " & ".join(_latex_escape(c) for c in r) + " \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def _render_csv(headers, rows) -> str:
    sio = io.StringIO()
    w = csv.writer(sio)
    w.writerow(headers)
    w.writerows(rows)
    return sio.getvalue()


def _render_html(headers, rows, title, caption) -> str:
    head = "".join(f"<th>{_html_escape(str(h))}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_html_escape(str(c))}</td>" for c in r) + "</tr>"
                   for r in rows)
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<style>body{font-family:system-ui,sans-serif;color:#0b0b0b;margin:1rem}"
        "table{border-collapse:collapse;font-size:13px}"
        "caption{caption-side:top;text-align:left;font-weight:600;margin-bottom:.4rem}"
        "th,td{border-bottom:1px solid #e1e0d9;padding:4px 10px;text-align:left}"
        "thead th{border-bottom:2px solid #c3c2b7}"
        ".cap{color:#52514e;font-weight:400;font-size:12px}</style>"
        f"<table><caption>{_html_escape(title)}"
        f"<div class='cap'>{_html_escape(caption)}</div></caption>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def _render_markdown(headers, rows, title, caption) -> str:
    def esc(x):
        return str(x).replace("|", "\\|")
    lines = [f"**{title}** — {caption}", "",
             "| " + " | ".join(esc(h) for h in headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(esc(c) for c in r) + " |")
    lines.append("")
    return "\n".join(lines)


_FIXED_XLSX_EPOCH = datetime(2020, 1, 1, 0, 0, 0)


def _render_xlsx(headers, rows, title, caption) -> bytes:
    wb = Workbook()
    wb.properties.created = _FIXED_XLSX_EPOCH
    wb.properties.modified = _FIXED_XLSX_EPOCH
    wb.properties.creator = "QRosetta"
    ws = wb.active
    ws.title = "Table"
    ws.append([title])
    ws.append([caption])
    ws.append(headers)
    for r in rows:
        ws.append([("" if c is None else c) for c in r])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _table_bytes(headers, rows, title, caption, fmt: str) -> bytes:
    if fmt == "csv":
        return _render_csv(headers, rows).encode("utf-8")
    if fmt == "latex":
        return _render_latex(headers, rows, title, caption).encode("utf-8")
    if fmt == "html":
        return _render_html(headers, rows, title, caption).encode("utf-8")
    if fmt == "markdown":
        return _render_markdown(headers, rows, title, caption).encode("utf-8")
    if fmt == "xlsx":
        return _render_xlsx(headers, rows, title, caption)
    raise ValueError(f"unsupported table format: {fmt}")


# --- Data access helpers --------------------------------------------------------------

def _pairwise_records(divergence_report: dict) -> List[dict]:
    recs = divergence_report.get("pairwise_agreement")
    return recs if isinstance(recs, list) else []


def _pair_key(rec: dict) -> str:
    s = rec.get("simulators", ["?", "?"])
    return f"{s[0]} × {s[1]}"


def _key_metric(rec: dict) -> Any:
    m = rec.get("metrics", {})
    return m.get("direct_fidelity") if rec.get("mode") == "statevector" else m.get("js_divergence")


def _heatmap_specs(mode: str):
    if mode == "statevector":
        return [("fidelity_matrix", "Raw statevector fidelity (no transform)", "fidelity_heatmap")]
    return [
        ("statistical_distance_matrix (js_divergence)", "Raw Jensen–Shannon divergence", "js_divergence_heatmap"),
        ("hellinger_distance_matrix", "Raw Hellinger distance", "hellinger_heatmap"),
    ]


# --- Figure builders (return a Figure) ------------------------------------------------

def _fig_agreement_distribution(divergence_report: dict, mode: str):
    records = _pairwise_records(divergence_report)
    counts = {}
    for r in records:
        counts[r.get("agreement", "unknown")] = counts.get(r.get("agreement", "unknown"), 0) + 1
    labels = [c for c in _AGREEMENT_ORDER if c in counts] + [c for c in counts if c not in _AGREEMENT_ORDER]
    values = [counts[c] for c in labels]
    colors = [AGREEMENT_COLORS.get(c, _MUTED) for c in labels]
    summary = divergence_report.get("statistical_test_summary")
    has_v = bool(summary and summary.get("verdict_counts"))
    ncols = 2 if has_v else 1
    fig, axes = plt.subplots(1, ncols, figsize=(6.5 * ncols, 4.2))
    axes = axes if has_v else [axes]
    ax = axes[0]
    bars = ax.bar(range(len(labels)), values, color=colors, width=0.72)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([l.replace("_", "\n") for l in labels], fontsize=8)
    ax.set_ylabel("pair count"); ax.set_title("Explained-cause agreement classes")
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v, str(v), ha="center", va="bottom", fontsize=9)
    ax.margins(y=0.15)
    if has_v:
        vc = summary["verdict_counts"]
        vlab = [v for v in _VERDICT_ORDER if v in vc] + [v for v in vc if v not in _VERDICT_ORDER]
        vval = [vc[v] for v in vlab]
        ax2 = axes[1]
        vb = ax2.bar(range(len(vlab)), vval, color=[VERDICT_COLORS.get(v, _MUTED) for v in vlab], width=0.72)
        ax2.set_xticks(range(len(vlab)))
        ax2.set_xticklabels([v.replace("_", "\n") for v in vlab], fontsize=8)
        ax2.set_ylabel("pair count"); ax2.set_title("Shot-noise statistical verdicts")
        for b, v in zip(vb, vval):
            ax2.text(b.get_x() + b.get_width() / 2, v, str(v), ha="center", va="bottom", fontsize=9)
        ax2.margins(y=0.15)
    fig.suptitle("Cross-simulator agreement (analysis over registered transforms)", fontsize=11)
    return fig


def _fig_heatmap(divergence_report: dict, key: str, title: str):
    labels = divergence_report.get("simulators", [])
    arr = np.array(divergence_report[key], dtype=float)
    mask = (arr == -1.0)
    np.fill_diagonal(mask, True)
    masked = np.ma.masked_array(arr, mask=mask)
    n = len(labels)
    fig, ax = plt.subplots(figsize=(max(4.5, 0.6 * n + 2), max(4.0, 0.6 * n + 1.5)))
    im = ax.imshow(masked, cmap=_blue_cmap(), aspect="equal", vmin=0.0)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_title(title)
    if n <= 12:
        for i in range(n):
            for j in range(n):
                if not masked.mask[i, j]:
                    ax.text(j, i, f"{arr[i, j]:.2f}", ha="center", va="center", fontsize=7, color=_INK)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    return fig


def _fig_ranking_bar(ranking, value_keys, title, xlabel):
    rows = [r for r in ranking if r.get("simulator")]
    sims = [r["simulator"] for r in rows]
    fig, ax = plt.subplots(figsize=(max(5.0, 0.5 * len(sims) + 2), 4.2))
    y = np.arange(len(sims)); left = np.zeros(len(sims))
    for key, color, label in value_keys:
        vals = np.array([(r.get(key) or 0.0) if r.get("status") == "success" else 0.0 for r in rows])
        ax.barh(y, vals, left=left, color=color, label=label, height=0.7)
        left += vals
    ax.set_yticks(y); ax.set_yticklabels(sims, fontsize=8); ax.invert_yaxis()
    ax.set_xlabel(xlabel); ax.set_title(title)
    if len(value_keys) > 1:
        ax.legend(fontsize=8, frameon=False)
    return fig


def _fig_count_histogram(counts_a, counts_b, a, b):
    outcomes = sorted(set(counts_a) | set(counts_b))
    na, nb = sum(counts_a.values()), sum(counts_b.values())
    pa = [counts_a.get(o, 0) / na if na else 0 for o in outcomes]
    pb = [counts_b.get(o, 0) / nb if nb else 0 for o in outcomes]
    x = np.arange(len(outcomes))
    fig, ax = plt.subplots(figsize=(max(5.0, 0.5 * len(outcomes) + 2), 3.8))
    ax.bar(x - 0.2, pa, width=0.38, color="#2a78d6", label=str(a))
    ax.bar(x + 0.2, pb, width=0.38, color="#1baf7a", label=str(b))
    ax.set_xticks(x); ax.set_xticklabels(outcomes, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("probability"); ax.set_title(f"Measured distribution: {a} vs {b} (raw counts)")
    ax.legend(fontsize=8, frameon=False)
    return fig


# --- Table builders (return headers, rows, title, caption) ----------------------------

def _tbl_agreement(divergence_report: dict, mode: str):
    records = _pairwise_records(divergence_report)
    measured = mode == "measured"
    headers = ["Pair", "Agreement", "Registered transform",
               "Fidelity" if not measured else "JS divergence"]
    if measured:
        headers.append("Stat verdict")
    rows = []
    for r in records:
        row = [_pair_key(r), r.get("agreement", "—"), r.get("registered_transform") or "—",
               _fmt_num(_key_metric(r))]
        if measured:
            row.append(((r.get("metrics", {}) or {}).get("statistical_test") or {}).get("verdict", "—"))
        rows.append(row)
    caption = ("Analysis over the registered-transform lattice; each label reports the transform "
               "whose numerical effect explains the pair. Not a ground-truth verification.")
    return headers, rows, "Pairwise explained-cause agreement", caption


def _tbl_performance(results: dict):
    ranking = (results.get("performance_report") or {}).get("ranking", [])
    headers = ["Rank", "Simulator", "Compilation (s)", "Simulation (s)", "Total (s)", "Status"]
    rows = [[i + 1, r.get("simulator", "—"), _fmt_num(r.get("compilation_time_sec"), 6),
             _fmt_num(r.get("simulation_time_sec"), 6), _fmt_num(r.get("execution_time_sec"), 6),
             r.get("status", "—")] for i, r in enumerate(ranking)]
    return headers, rows, "Execution timing", "Wall-clock timings measured by QRosetta (raw)."


def _tbl_resources(results: dict):
    ranking = (results.get("resource_report") or {}).get("ranking", [])
    headers = ["Rank", "Simulator", "Mem delta (MiB)", "Process peak (MiB)", "Theoretical SV (MiB)", "Status"]
    rows = [[i + 1, r.get("simulator", "—"), _fmt_num(r.get("memory_usage_mb")),
             _fmt_num(r.get("process_peak_mb"), 1), _fmt_num(r.get("theoretical_statevector_mb")),
             r.get("status", "—")] for i, r in enumerate(ranking)]
    return headers, rows, "Resource usage", "Memory measured by QRosetta (raw)."


def _tbl_statistical(divergence_report: dict):
    records = [r for r in _pairwise_records(divergence_report)
               if (r.get("metrics", {}) or {}).get("statistical_test")]
    headers = ["Pair", "Basis", "chi2 p", "chi2 p (BH)", "G-test p", "G-test p (BH)",
               "Total variation", "Cramér's V", "Power@obs", "Shots/backend for power", "Verdict"]
    rows = []
    for r in records:
        st = r["metrics"]["statistical_test"]
        ef, pw, chi2, gt = (st.get("effect_size", {}), st.get("power", {}),
                            st.get("chi2", {}), st.get("g_test", {}))
        rows.append([_pair_key(r), st.get("basis", "—"),
                     _fmt_num(chi2.get("p_value")), _fmt_num(chi2.get("p_value_bh")),
                     _fmt_num(gt.get("p_value")), _fmt_num(gt.get("p_value_bh")),
                     _fmt_num(ef.get("total_variation")), _fmt_num(ef.get("cramers_v")),
                     _fmt_num(pw.get("power_to_detect_delta_at_observed_shots"), 3),
                     pw.get("shots_per_backend_for_target_power", "—"), st.get("verdict", "—")])
    caption = ("Shot-noise-aware homogeneity tests (chi-square + G-test) with BH-corrected p-values, "
               "effect size, and prospective power. Parallel evidence; does not override the label.")
    return headers, rows, "Shot-noise statistical test", caption


def _tbl_matrix(divergence_report: dict, key: str, title: str):
    labels = divergence_report.get("simulators", [])
    mat = divergence_report[key]
    headers = [""] + list(labels)
    rows = []
    for i, s1 in enumerate(labels):
        row = [s1]
        for j in range(len(labels)):
            v = mat[i][j]
            row.append("—" if (i == j or v == -1.0) else _fmt_num(v))
        rows.append(row)
    caption = f"{title} (raw metric; −1 / diagonal shown as —). Symmetric matrix."
    return headers, rows, title, caption


def _tbl_metadata(results: dict, mode: str):
    headers = ["Simulator", "SDK versions", "Qubit ordering", "Sampling method", "Opt level", "Status"]
    rows = []
    for r in results.get("raw_results", []):
        sim = r.get("simulator", "—")
        sdk = ", ".join(f"{k}={v}" for k, v in (r.get("sdk_versions") or {}).items()) or "—"
        rows.append([sim, sdk, r.get("qubit_ordering", "—"), r.get("sampling_method", "—"),
                     r.get("optimization_level", "—"), "error" if r.get("error") else "completed"])
    n_shots = results.get("n_shots")
    seed = results.get("seed")
    run_line = f"mode={mode}"
    if n_shots is not None:
        run_line += f", n_shots={n_shots}"
    if seed is not None:
        run_line += f", seed={seed}"
    caption = f"Run + provenance metadata ({run_line}). Ground-truth executed versions and endpoint labels."
    return headers, rows, "Run and provenance metadata", caption


# --- Text-blob builders (return str) --------------------------------------------------

def _txt_glossary(mode: str) -> str:
    lines = ["# QRosetta agreement taxonomy — glossary", "",
             "Agreement classes (registered-transform lattice):", ""]
    for label, desc in _AGREEMENT_GLOSSARY:
        lines.append(f"- **{label}** — {desc}")
    if mode == "measured":
        lines += ["", "Shot-noise statistical verdicts (parallel evidence; do not override the label):", ""]
        for label, desc in _VERDICT_GLOSSARY:
            lines.append(f"- **{label}** — {desc}")
    lines += ["", "Every registered transform is reported with its numerical effect and provenance; "
              "QRosetta never silently alters runner outputs, and agreement analysis is not "
              "ground-truth verification."]
    return "\n".join(lines)


def _txt_executed_qasm(results: dict, runner: str) -> str:
    for r in results.get("raw_results", []):
        if r.get("simulator") == runner:
            tq = r.get("transpiled_qasm")
            header = (f"// Executed (transpiled) OpenQASM for backend: {runner}\n"
                      f"// This is the exact circuit the {runner} adapter ran (after preprocessing).\n")
            return header + (tq or "// (no transpiled QASM recorded for this runner)")
    return f"// no result for runner {runner}"


# --- Artifact registry ----------------------------------------------------------------

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

    for key, title, base in _heatmap_specs(mode):
        if isinstance(div.get(key), list) and div.get(key):
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
               if isinstance(r.get("counts"), dict)}
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
    "statistical": ["__histograms__"],  # all histogram_* ids
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

    Deterministic and side-effect free; generates only what the report supports. Output paths
    and category membership are unchanged from FIX-019 (the interactive tab exposes more).
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
