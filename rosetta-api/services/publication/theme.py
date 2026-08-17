# Publication artifacts: shared constants, deterministic matplotlib setup, palette.
#
# The palette, glossary wording and ordering here are what the RO-Crate export and the
# browser's Artifacts tab both render from, so changes are visible in published output.

# Turns a QRosetta results dict into publication-grade figures (SVG/PNG/PDF via
# matplotlib) and tables (LaTeX/CSV/HTML/Markdown/XLSX). Every artifact is generated
# deterministically from the stored report data, preserves provenance, and labels raw
# metrics vs transformed analysis evidence. Two entry points share the same builders:
#   * build_publication_artifacts(...)  -> {relative_path: bytes}  (RO-Crate bundle)
#   * list_artifacts(...) / render_artifact(...)                    (interactive tab)

import threading

import matplotlib
matplotlib.use("Agg")  # headless, deterministic — before pyplot import
import matplotlib.pyplot as plt

# pyplot keeps global state and is not thread-safe. Callers render figures off the event
# loop (asyncio.to_thread), so serialize every figure build+save+close through this lock.
_MPL_LOCK = threading.Lock()
from matplotlib.colors import LinearSegmentedColormap

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-publication")

SUPPORTED_FIGURE_FORMATS = ("svg", "png", "pdf")
SUPPORTED_TABLE_FORMATS = ("latex", "csv", "html", "xlsx")          # RO-Crate bundle
TAB_TABLE_FORMATS = ("latex", "csv", "html", "markdown", "xlsx")    # interactive tab
PUBLICATION_CATEGORIES = ("agreement", "heatmaps", "performance", "statistical")

MAX_HISTOGRAM_PAIRS = 12
# Cap distinct outcomes drawn in a count figure. Outcome space is 2**n, so an uncapped
# figure grows without bound (unusable in a paper). Beyond this we keep the highest-
# probability outcomes and fold the rest into a single "other" bucket. MIN_OUTCOME_PROB
# drops outcomes that are pure shot noise (below this on every backend) into "other" too,
# so a concentrated distribution renders as a few rows/bars rather than a wall of zeros.
MAX_HISTOGRAM_OUTCOMES = 24   # pairwise grouped-bar histogram
MAX_OVERVIEW_BARS = 12        # multi-backend clustered-bar histogram (default total)
MAX_OVERVIEW_OUTCOMES = 20    # multi-backend outcome × backend heatmap (optional)
MIN_OUTCOME_PROB = 0.01
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
# Distinct categorical hues for per-backend series in the clustered count histogram.
_CATEGORICAL = ["#2a78d6", "#1baf7a", "#e0812a", "#8b5cf6", "#e34948", "#0d9488",
                "#d6a400", "#d64f9e", "#6b7280", "#3b3f95", "#7a9e2f", "#c2410c",
                "#0e7490", "#9d174d"]

# Human-readable definitions reused by the glossary artifact + figure/table legends.
_AGREEMENT_GLOSSARY = [
    ("agree_directly", "Outputs match directly, no transform needed."),
    ("agree_up_to_global_phase", "Match after removing an overall (unobservable) global phase."),
    ("agree_after_bit_reversal", "Match after reversing qubit/bit order (an endianness convention)."),
    ("agree_after_qubit_permutation", "Match after a bounded qubit permutation (≤6 qubits)."),
    ("residual_disagreement", "Statevector disagreement not explained by any registered transform."),
    ("distance_within_threshold", "Measured distributions within the JS/Hellinger thresholds "
     "(heuristic, configurable; the shot-noise statistical test is the rigorous verdict)."),
    ("distance_exceeds_threshold", "Measured distributions exceed the (heuristic, configurable) "
     "thresholds after registered transforms; see the statistical test for significance."),
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


def _prob_cmap():
    # White-anchored ramp: probability 0 reads as an empty (white) cell, so "this backend
    # never produced this outcome" is visually blank rather than pale blue.
    cmap = LinearSegmentedColormap.from_list("qrosetta_prob", ["#ffffff"] + _SEQ_BLUE)
    cmap.set_bad(_NEUTRAL_FILL)
    return cmap


def _rank_outcomes(all_outcomes, max_prob, cap: int, min_prob: float = MIN_OUTCOME_PROB):
    """Pick which outcomes to draw, folding the rest into an aggregated "other" bucket.

    Keeps the highest-probability outcomes that clear ``min_prob`` on at least one backend,
    capped at ``cap`` so the figure stays a publishable size. Returns ``(kept_sorted,
    rest)`` where ``rest`` is the list of folded outcomes ([] when nothing is hidden).
    ``max_prob(outcome) -> float`` gives the largest probability across the compared sides.
    """
    ranked = sorted(all_outcomes, key=max_prob, reverse=True)
    signif = [o for o in ranked if max_prob(o) >= min_prob] or ranked[:1]
    if len(signif) == len(all_outcomes) and len(signif) <= cap:
        return sorted(signif), []          # everything significant and it all fits
    kept = sorted(signif[:cap - 1])         # reserve one slot for the "other" bucket
    kept_set = set(kept)
    return kept, [o for o in all_outcomes if o not in kept_set]
