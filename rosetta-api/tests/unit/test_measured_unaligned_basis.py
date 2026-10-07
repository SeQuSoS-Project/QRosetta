"""Measured pairs that match only in the basis their declared bit orders do not imply."""

import json

from services.analysis.divergence import create_counts_report


def _pair(order_a, counts_a, order_b, counts_b):
    report = create_counts_report([
        {"simulator": "a", "qubit_ordering": order_a, "counts": counts_a},
        {"simulator": "b", "qubit_ordering": order_b, "counts": counts_b},
    ], n_shots=8200)
    json.dumps(report, allow_nan=False)
    return report, report["pairwise_agreement"][0]


def test_same_order_match_only_after_reversal_is_a_disagreement():
    report, record = _pair("msb", {"01": 8200}, "msb", {"10": 8200})
    assert record["agreement"] == "distance_exceeds_threshold"
    assert record["metrics"]["unaligned_basis_match"] == "bit_reversal"
    assert record["measured_assessment"] == "distinguishable"
    entry = report["divergences_found"][0]
    assert entry["unaligned_basis_match"] == "bit_reversal"
    assert entry["group"].startswith("disagreement: agrees only in the basis")


def test_mixed_order_match_only_directly_is_a_disagreement():
    _, record = _pair("msb", {"01": 8200}, "lsb", {"01": 8200})
    assert record["agreement"] == "distance_exceeds_threshold"
    assert record["metrics"]["unaligned_basis_match"] == "direct"
    assert record["measured_assessment"] == "distinguishable"


def test_aligned_matches_keep_their_labels():
    _, record = _pair("msb", {"01": 8200}, "lsb", {"10": 8200})
    assert record["agreement"] == "agree_after_bit_reversal"
    assert record["metrics"]["unaligned_basis_match"] is None
    _, record = _pair("msb", {"01": 8200}, "msb", {"01": 8200})
    assert record["agreement"] == "distance_within_threshold"
    assert record["metrics"]["unaligned_basis_match"] is None
