"""Publication artifact constants, deterministic matplotlib setup, palette and glossary text.

The glossary entries are mirrored by static/js/artifact_formats.js.
"""

import threading

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-publication")

_MPL_LOCK = threading.Lock()

SUPPORTED_FIGURE_FORMATS = ("svg", "png", "pdf")
SUPPORTED_TABLE_FORMATS = ("latex", "csv", "html", "xlsx")
TAB_TABLE_FORMATS = ("latex", "csv", "html", "markdown", "xlsx")
PUBLICATION_CATEGORIES = ("agreement", "heatmaps", "performance", "statistical")

MAX_HISTOGRAM_PAIRS = 12
MAX_HISTOGRAM_OUTCOMES = 24
MAX_OVERVIEW_BARS = 12
MAX_OVERVIEW_OUTCOMES = 20
MIN_OUTCOME_PROB = 0.01
BASE_DPI = 150

MIME_TYPES = {
    "svg": "image/svg+xml", "png": "image/png", "pdf": "application/pdf",
    "csv": "text/csv", "latex": "application/x-latex", "html": "text/html",
    "markdown": "text/markdown", "text": "text/plain", "qasm": "text/x-qasm",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

plt.rcParams.update({
    "figure.dpi": BASE_DPI, "savefig.dpi": BASE_DPI,
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"], "font.size": 10,
    "axes.titlesize": 12, "axes.labelsize": 10,
    "axes.edgecolor": "#c3c2b7", "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "svg.hashsalt": "qrosetta-publication", "svg.fonttype": "none",
})

_INK = "#0b0b0b"
_MUTED = "#898781"
_NEUTRAL_FILL = "#e1e0d9"
AGREEMENT_COLORS = {
    "agree_directly": "#008300", "distance_within_threshold": "#008300",
    "agree_up_to_global_phase": "#1baf7a", "agree_after_bit_reversal": "#2a78d6",
    "agree_after_qubit_permutation": "#4a3aa7", "agree_after_normalization": "#d6a400",
    "residual_disagreement": "#e34948", "distance_exceeds_threshold": "#e34948",
    "not_comparable": _MUTED,
}
VERDICT_COLORS = {
    "consistent": "#0ca30c", "distinguishable": "#d03b3b",
    "inconclusive_low_shots": _MUTED, "ambiguous": "#fab219",
}
_AGREEMENT_ORDER = [
    "agree_directly", "agree_up_to_global_phase", "agree_after_bit_reversal",
    "agree_after_qubit_permutation", "agree_after_normalization", "residual_disagreement",
    "distance_within_threshold", "distance_exceeds_threshold", "not_comparable",
]
_VERDICT_ORDER = ["consistent", "distinguishable", "inconclusive_low_shots", "ambiguous"]
_SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
_CATEGORICAL = ["#2a78d6", "#1baf7a", "#e0812a", "#8b5cf6", "#e34948", "#0d9488",
                "#d6a400", "#d64f9e", "#6b7280", "#3b3f95", "#7a9e2f", "#c2410c",
                "#0e7490", "#9d174d"]

_AGREEMENT_GLOSSARY = [
    ("agree_directly", "Outputs match directly, no transform needed."),
    ("agree_up_to_global_phase", "Match after removing an overall (unobservable) global phase."),
    ("agree_after_bit_reversal", "Match after reversing qubit/bit order (an endianness convention)."),
    ("agree_after_qubit_permutation", "Match after a bounded qubit permutation (≤7 qubits)."),
    ("agree_after_normalization", "At least one input statevector has a norm differing from 1 by "
     "more than norm_tolerance; the normalised vectors agree. metrics.normalized_agreement "
     "holds the label the normalised pair receives."),
    ("residual_disagreement", "Statevector disagreement not explained by any registered transform."),
    ("distance_within_threshold", "Measured distributions within the JS-divergence and Hellinger "
     "thresholds (descriptive, configurable; the shot-noise statistical test gives the "
     "significance verdict)."),
    ("distance_exceeds_threshold", "Measured distributions exceed the (descriptive, configurable) "
     "thresholds after registered transforms; see the statistical test for significance."),
    ("not_comparable", "At least one side lacks usable output; the pair cannot be compared. "
     "metrics.reason names the cause."),
]
_NOT_COMPARABLE_GLOSSARY = [
    ("missing_statevector", "A run returned no statevector."),
    ("statevector_parse_error", "A returned statevector could not be decoded."),
    ("empty_statevector", "A statevector has no amplitudes."),
    ("nonfinite_statevector", "A statevector contains NaN or infinite amplitudes."),
    ("zero_norm_statevector", "A statevector has norm 0."),
    ("shape_mismatch", "The two statevectors have different lengths."),
    ("missing_counts", "A run returned no counts."),
    ("empty_counts", "A counts dictionary is empty."),
    ("invalid_bitstring_key", "A counts key is not a non-empty string."),
    ("non_numeric_counts", "A count value is not a real number (strings and booleans included)."),
    ("nonfinite_counts", "A count value is NaN or infinite."),
    ("negative_counts", "A count value is negative."),
    ("zero_total_counts", "A counts dictionary sums to 0."),
    ("nonfinite_metric", "A distance metric evaluated to NaN or infinity."),
    ("comparison_error", "The comparison raised an exception; metrics.details.error holds the message."),
]
_VERDICT_GLOSSARY = [
    ("consistent", "Neither the chi-square test nor the G-test is significant after BH (FDR) correction."),
    ("distinguishable", "Both tests are significant after BH (FDR) correction."),
    ("inconclusive_low_shots", "Expected counts too low for a reliable test."),
    ("ambiguous", "Exactly one of the chi-square test and the G-test is significant after BH (FDR) correction."),
]
_UNRANKED_GLOSSARY = [
    ("runner_error", "The run returned an error."),
    ("missing_timing", "The run returned no execution_time_sec."),
    ("missing_process_peak_rss", "The run returned no process_peak_rss_mb."),
]
_THRESHOLD_DEFAULTS = ("fidelity_tolerance = 1e-5, phase_tolerance = 1e-12 rad, "
                       "norm_tolerance = 1e-6, js_threshold = 0.01 nats, "
                       "hellinger_threshold = 0.1")


def _blue_cmap():
    """Sequential blue colormap; masked cells use the neutral fill."""
    cmap = LinearSegmentedColormap.from_list("qrosetta_blue", _SEQ_BLUE)
    cmap.set_bad(_NEUTRAL_FILL)
    return cmap


def _prob_cmap():
    """White-anchored blue colormap for probabilities; masked cells use the neutral fill."""
    cmap = LinearSegmentedColormap.from_list("qrosetta_prob", ["#ffffff"] + _SEQ_BLUE)
    cmap.set_bad(_NEUTRAL_FILL)
    return cmap


def _rank_outcomes(all_outcomes, max_prob, cap: int, min_prob: float = MIN_OUTCOME_PROB):
    """Return ``(kept_sorted, rest)``: outcomes to draw and outcomes folded into "other".

    Keeps the highest-probability outcomes with ``max_prob(o) >= min_prob``, at most
    ``cap`` including the "other" slot; ``rest`` is [] when nothing is folded.
    """
    ranked = sorted(all_outcomes, key=max_prob, reverse=True)
    signif = [o for o in ranked if max_prob(o) >= min_prob] or ranked[:1]
    if len(signif) == len(all_outcomes) and len(signif) <= cap:
        return sorted(signif), []
    kept = sorted(signif[:cap - 1])
    kept_set = set(kept)
    return kept, [o for o in all_outcomes if o not in kept_set]
