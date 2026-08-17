# Cross-backend agreement analysis.
#
# Split into focused modules behind this facade. Every name that was importable from
# services.analysis.divergence when it was a single module still is, so callers and
# tests are unaffected by the split.

from .common import (
    MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS,
    STAT_TEST_ALPHA,
    STAT_TEST_DELTA_TV,
    STAT_TEST_TARGET_POWER,
    _json_float,
    logger,
)
from .classification import (
    _classify_counts_pair,
    _classify_statevector_pair,
    _counts_not_comparable_record,
    _pair_provenance,
    _run_status,
    _statevector_not_comparable_record,
)
from .counts import (
    _best_counts_qubit_permutation_metrics,
    _bit_reversed_counts,
    _counts_bit_length,
    _counts_distance_metrics,
    _counts_invalid_reason,
    _counts_probability_vector,
    _normalize_counts,
    _permute_counts,
    calculate_hellinger_distance,
)
from .reports import create_counts_report, create_divergence_report
from .statevector import (
    _best_statevector_qubit_permutation_metrics,
    _bit_reversed_statevector,
    _normalize_statevector,
    _permute_statevector,
    _statevector_inner_metrics,
    _statevector_invalid_reason,
    _statevector_qubit_count,
    parse_statevector,
)
from .statistics import (
    _apply_multiple_comparison_correction,
    _bh_adjust,
    _shots_per_backend_for_target_power,
    _statistical_agreement_test,
)

__all__ = [
    # The public surface.
    "create_divergence_report",
    "create_counts_report",
    "parse_statevector",
    "calculate_hellinger_distance",
    # Tuning constants.
    "MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS",
    "STAT_TEST_ALPHA",
    "STAT_TEST_DELTA_TV",
    "STAT_TEST_TARGET_POWER",
    # Internals re-exported so the pre-split import path keeps working.
    "_apply_multiple_comparison_correction",
    "_best_counts_qubit_permutation_metrics",
    "_best_statevector_qubit_permutation_metrics",
    "_bh_adjust",
    "_bit_reversed_counts",
    "_bit_reversed_statevector",
    "_classify_counts_pair",
    "_classify_statevector_pair",
    "_counts_bit_length",
    "_counts_distance_metrics",
    "_counts_invalid_reason",
    "_counts_not_comparable_record",
    "_counts_probability_vector",
    "_json_float",
    "_normalize_counts",
    "_normalize_statevector",
    "_pair_provenance",
    "_permute_counts",
    "_permute_statevector",
    "_run_status",
    "_shots_per_backend_for_target_power",
    "_statevector_inner_metrics",
    "_statevector_invalid_reason",
    "_statevector_not_comparable_record",
    "_statevector_qubit_count",
    "_statistical_agreement_test",
    "logger",
]
