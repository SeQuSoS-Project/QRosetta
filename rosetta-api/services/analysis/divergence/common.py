"""Constants and helpers shared by the statevector and counts halves of the analysis."""

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-divergence")

ANALYSIS_VERSION = "divergence-2026.10.08.3"

STAT_TEST_ALPHA = 0.05
STAT_TEST_TARGET_POWER = 0.8
STAT_TEST_DELTA_TV = 0.05

# Every pair is scored over n! - 2 permutations of its bits; over a 91-pair comparison (14 backends)
# a measured report takes 0.76 s at 6 bits and 2.9 s at 7, a statevector report 0.07 s and 0.47 s.
MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS = 7

DEFAULT_FIDELITY_TOLERANCE = 1e-5
DEFAULT_PHASE_TOLERANCE = 1e-6
DEFAULT_NORM_TOLERANCE = 1e-4
DEFAULT_JS_THRESHOLD = 0.01
DEFAULT_HELLINGER_THRESHOLD = 0.1

JS_DIVERGENCE_UNIT = "nats"


def _json_float(value):
    """Convert numpy scalar values to JSON-safe floats."""
    if value is None:
        return None
    return float(value)


def _threshold(thresholds, key, default):
    """Return ``thresholds[key]``, or ``default`` when the key is absent or None."""
    value = (thresholds or {}).get(key)
    return default if value is None else value
