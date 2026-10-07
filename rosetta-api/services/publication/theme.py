"""Publication artifact constants, deterministic matplotlib setup, palette and glossary text.

The glossary entries are mirrored by static/js/artifact_formats.js.
"""

import threading
from contextlib import contextmanager

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from qrosetta_commons.helpers import get_logger

from services.analysis.divergence.common import ANALYSIS_VERSION

logger = get_logger("rosetta-publication")

_MPL_LOCK = threading.Lock()

SUPPORTED_FIGURE_FORMATS = ("svg", "png", "pdf")
SUPPORTED_TABLE_FORMATS = ("latex", "csv", "html", "xlsx")
TAB_TABLE_FORMATS = ("latex", "csv", "html", "markdown", "xlsx")

BASE_DPI = 150

FIGURE_SIZES = {
    "auto": None,
    "single": {"inches": (3.5, 2.6), "font": 7.0},
    "double": {"inches": (7.0, 3.6), "font": 8.0},
    "slide": {"inches": (13.33, 7.5), "font": 16.0},
}
_SIZE = threading.local()


@contextmanager
def figure_size(size: str = "auto"):
    """Within the block, figures take the preset's size and base font size ("auto" keeps
    each figure's own size)."""
    preset = FIGURE_SIZES.get(size)
    previous = getattr(_SIZE, "preset", None)
    _SIZE.preset = preset
    try:
        if preset is None:
            yield
            return
        f = preset["font"]
        with plt.rc_context({"font.size": f, "axes.titlesize": f * 1.1, "axes.labelsize": f,
                             "xtick.labelsize": f * 0.9, "ytick.labelsize": f * 0.9,
                             "legend.fontsize": f * 0.85, "figure.titlesize": f * 1.15}):
            yield
    finally:
        _SIZE.preset = previous


def _figsize(default):
    """``default`` (width, height) in inches, or the active size preset's."""
    preset = getattr(_SIZE, "preset", None)
    return preset["inches"] if preset else default

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
    "text.parse_math": False,
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
    ("agree_directly", "Outputs match directly, no transform needed. For a statevector pair "
     "this requires the same declared qubit ordering, or a one-qubit circuit, where bit "
     "reversal is the identity."),
    ("agree_up_to_global_phase", "Match after removing the global phase offset arg⟨a|b⟩ "
     "between the two states, which is unobservable. An offset within phase_tolerance is "
     "reported as 0 and the pair agrees directly."),
    ("agree_after_bit_reversal", "Match after reversing qubit/bit order, the transform the "
     "declared orderings imply when one backend is lsb and the other msb. A statevector pair "
     "gets this label only for such a pair; transform_effect.global_phase_aligned is true "
     "when a global phase offset remains after the reversal. For a measured pair whose "
     "declared bit orders differ the label means the pair agrees in the label-aligned "
     "(bit-reversed) basis; it is used by convention even when the direct distances are "
     "equal too, as for GHZ-type outcomes that bit reversal leaves unchanged."),
    ("agree_after_qubit_permutation", "Disagreement: agrees only after an undeclared qubit "
     "permutation (searched up to ≤7 qubits). No declared ordering implies the permutation, "
     "so the pair is counted as a disagreement."),
    ("agree_after_normalization", "At least one input statevector has a norm differing from 1 by "
     "more than norm_tolerance; the normalised vectors agree. metrics.normalized_agreement "
     "holds the label the normalised pair receives. The default norm_tolerance (1e-4) lies "
     "above complex64 rounding, which leaves norms about 2e-6 from 1."),
    ("residual_disagreement", "Statevector disagreement in the label-aligned basis that no "
     "registered transform explains. metrics.unaligned_basis_match is \"direct\" or "
     "\"bit_reversal\" when the pair matches only in the basis its declared orderings do not "
     "imply, as when an lsb and an msb backend return equal vectors for an asymmetric state."),
    ("distance_within_threshold", "Measured distributions within the JS-divergence and Hellinger "
     "thresholds without a bit-order transform, for a pair whose declared bit orders agree "
     "(descriptive, configurable; the shot-noise statistical test gives the significance "
     "verdict)."),
    ("distance_exceeds_threshold", "Measured distributions exceed the (descriptive, configurable) "
     "thresholds in the label-aligned basis. metrics.unaligned_basis_match is \"direct\" or "
     "\"bit_reversal\" when they are within the thresholds only in the basis the declared bit "
     "orders do not imply; otherwise no qubit permutation brings them within. See the "
     "statistical test for significance."),
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
    ("consistent", "Neither the chi-square test nor the G-test is significant after "
     "Benjamini-Yekutieli (BY, FDR) correction over the m comparable pairs, and the power to "
     "detect a total-variation gap of 0.05 at the observed shots is at least 0.8. Power is "
     "that of the chi-square test at alpha/(m·c_m) (power.alpha_used, power.m_pairs, "
     "power.c_m; c_m = 1 + 1/2 + ... + 1/m), the threshold BY applies to a single discovery, "
     "on df = tested outcome bins - 1 with Cohen's w = 0.05: a lower bound for detecting one "
     "wrong backend."),
    ("distinguishable", "Both tests are significant after BY (FDR) correction. BY keeps the "
     "expected share of false discoveries among flagged pairs at most q = 0.05 under any "
     "dependence between the tests, including pairs that share one backend's sample; a "
     "flagged pair can still be a false discovery."),
    ("inconclusive_low_shots", "Expected counts stay below 5 after pooling rare outcomes "
     "(inconclusive_reason = low_expected_counts), or neither test is significant and the "
     "power at alpha/(m·c_m) to detect a total-variation gap of 0.05 is below 0.8 "
     "(inconclusive_reason = low_power). resolvable_by_more_shots is false when no shot count "
     "up to the platform maximum would give a testable table (low_expected_counts) or the "
     "target power (low_power); shots_per_backend_for_expected_counts gives the count that "
     "would. power.recommended_exceeds_actual is true when the recommended shots per backend "
     "exceed the shots used."),
    ("ambiguous", "Exactly one of the chi-square test and the G-test is significant after BY (FDR) correction."),
]
_ASSESSMENT_GLOSSARY = [
    ("consistent_within_shot_noise", "The shot-noise verdict is consistent: neither test "
     "separates the distributions at a shot count with power of at least 0.8, whatever the "
     "distance label."),
    ("distinguishable", "The shot-noise verdict is distinguishable: the distributions differ "
     "beyond sampling noise, subject to the FDR share of false discoveries."),
    ("ambiguous", "Exactly one of the two tests is significant."),
    ("inconclusive_low_shots", "The shot count cannot separate the distributions: expected "
     "counts stay below 5 after pooling, or the test is not significant at power below 0.8 "
     "(evaluated at alpha/(m·c_m))."),
    ("not_comparable", "At least one side lacks usable counts."),
]
_UNRANKED_GLOSSARY = [
    ("runner_error", "The run returned an error; its metrics are shown as —."),
    ("runner_timeout", "The run exceeded its time budget; its metrics are shown as —."),
    ("runner_offline", "The runner could not be reached; its metrics are shown as —."),
    ("missing_timing", "The run returned no execution_time_sec."),
    ("missing_process_peak_rss", "The run returned no process_peak_rss_mb."),
    ("gpu_memory_not_measured", "The run executed on a GPU. The memory fields are host RSS "
     "and do not include GPU device memory, so the run is not ranked by memory."),
]
_MEASUREMENT_NOTES = [
    "Global phase offset arg⟨a|b⟩: the phase of the inner product of two normalised "
    "statevectors. It is a global-phase difference between the states, not a relative phase "
    "between components of one superposition. The JSON fields relative_phase_matrix and "
    "*relative_phase* keep their names for compatibility.",
    "Label-aligned basis: for a pair whose declared qubit orderings differ (lsb vs msb) the "
    "second backend's output is bit-reversed (statevector amplitudes or counts keys); "
    "otherwise it is compared directly, and on a one-qubit circuit bit reversal is the "
    "identity. Statevector labels, the statistical tests and the label-aligned distances use "
    "this basis; the direct values are recorded as well.",
    "Outcomes with an expected count below 5 are pooled into one bin before the chi-square "
    "and G-tests; statistical_test.pooled_outcomes gives how many were pooled.",
    "Benjamini-Yekutieli controls the false discovery rate at q = alpha under arbitrary "
    "dependence between the p-values; pairs that share a backend reuse its sample and are "
    "dependent. Its threshold is alpha·i/(m·c_m) with c_m = 1 + 1/2 + ... + 1/m. BH-adjusted "
    "p-values are recorded for reference (p_value_bh) and do not set the verdict.",
]
_ANALYSIS_VERSION_NOTE = (
    f"Analysis version {ANALYSIS_VERSION} (analysis_version in each divergence report). The "
    "labels and verdicts are a function of the outputs and of the analysis rules; verdicts "
    "computed under different analysis versions may differ for identical counts.")
_THRESHOLD_DEFAULTS = ("fidelity_tolerance = 1e-5, phase_tolerance = 1e-6 rad, "
                       "norm_tolerance = 1e-4, js_threshold = 0.01 nats, "
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


def _log_axis(ax, which: str = "y"):
    """Log scale on ``which`` with plain tick labels (0.01, 1e-04): mathtext is off, so the
    default log labels would print their TeX source."""
    axis = ax.yaxis if which == "y" else ax.xaxis
    (ax.set_yscale if which == "y" else ax.set_xscale)("log")
    axis.set_major_locator(LogLocator(base=10))
    axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    axis.set_minor_formatter(NullFormatter())
