# Helpers shared by the statevector and counts halves of the analysis.

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-divergence")

# Significance level per pairwise test.
STAT_TEST_ALPHA = 0.05
# Target power for the shot-budget recommendation.
STAT_TEST_TARGET_POWER = 0.8
# Total-variation effect size the budget is sized to detect.
STAT_TEST_DELTA_TV = 0.05

# Above this qubit count the exhaustive permutation search is not attempted.
MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS = 6


def _json_float(value):
    """Convert numpy scalar values to JSON-safe floats."""
    if value is None:
        return None
    return float(value)
