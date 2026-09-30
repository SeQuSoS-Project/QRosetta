"""Tests for the pairwise evidence records in divergence reports."""

import json
import math

from services.analysis.divergence import (
    MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS,
    _bh_adjust,
    _shots_per_backend_for_target_power,
    create_counts_report,
    create_divergence_report,
)


def _record(report, sim_a, sim_b):
    pair = [sim_a, sim_b]
    return next(item for item in report["pairwise_agreement"] if item["simulators"] == pair)


def _assert_strict_json(report):
    """A report must never carry NaN/Inf; strict JSON serialization must succeed."""
    json.dumps(report, allow_nan=False)


def test_statevector_pairwise_evidence_preserves_matrices_and_labels_direct_agreement():
    report = create_divergence_report([
        {
            "simulator": "a",
            "statevector": ["1", "0"],
            "qubit_ordering": "lsb",
            "sdk_versions": {"sdk-a": "1.0"},
        },
        {
            "simulator": "b",
            "statevector": ["1", "0"],
            "qubit_ordering": "lsb",
            "sdk_versions": {"sdk-b": "2.0"},
        },
    ])

    assert report["fidelity_matrix"] == [[1.0, 1.0], [1.0, 1.0]]
    assert "pairwise_agreement" in report

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "agree_directly"
    assert evidence["registered_transform"] == "identity"
    assert evidence["metrics"]["direct_fidelity"] == 1.0
    assert evidence["metrics"]["direct_relative_phase_rad"] == 0.0
    assert evidence["provenance"]["qubit_ordering"] == {"a": "lsb", "b": "lsb"}
    assert evidence["provenance"]["sdk_versions"] == {
        "a": {"sdk-a": "1.0"},
        "b": {"sdk-b": "2.0"},
    }


def test_statevector_pairwise_evidence_three_runners_memoized_decode_is_consistent():
    """Each vector is reused across several pairs through the decode cache."""
    report = create_divergence_report([
        {"simulator": "a", "statevector": ["1", "0"], "qubit_ordering": "lsb"},
        {"simulator": "b", "statevector": ["1", "0"], "qubit_ordering": "lsb"},
        {"simulator": "c", "statevector": ["0", "1"], "qubit_ordering": "lsb"},
    ])

    assert report["fidelity_matrix"] == [
        [1.0, 1.0, 0.0],
        [1.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    assert _record(report, "a", "b")["agreement"] == "agree_directly"
    assert _record(report, "a", "c")["agreement"] == "residual_disagreement"
    assert _record(report, "b", "c")["agreement"] == "residual_disagreement"
    _assert_strict_json(report)


def test_statevector_pairwise_evidence_labels_global_phase_only_when_phase_nonzero():
    report = create_divergence_report([
        {"simulator": "a", "statevector": ["1", "0"], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": ["1j", "0"], "qubit_ordering": "msb"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "agree_up_to_global_phase"
    assert evidence["registered_transform"] == "global_phase_alignment"
    assert evidence["metrics"]["direct_fidelity"] == 1.0
    assert math.isclose(evidence["metrics"]["direct_relative_phase_rad"], math.pi / 2)
    assert math.isclose(evidence["transform_effect"]["relative_phase_delta_rad"], -math.pi / 2)
    assert evidence["transform_effect"]["relative_phase_after_alignment_rad"] == 0.0


def test_statevector_pairwise_evidence_labels_bit_reversal_for_one_hot_ordering_probe():
    lsb_one_hot = ["0", "1", "0", "0", "0", "0", "0", "0"]
    msb_one_hot = ["0", "0", "0", "0", "1", "0", "0", "0"]

    report = create_divergence_report([
        {"simulator": "lsb_backend", "statevector": lsb_one_hot, "qubit_ordering": "lsb"},
        {"simulator": "msb_backend", "statevector": msb_one_hot, "qubit_ordering": "msb"},
    ])

    assert report["fidelity_matrix"][0][1] == 0.0
    assert report["fidelity_matrix"][1][0] == 0.0

    evidence = _record(report, "lsb_backend", "msb_backend")
    assert evidence["agreement"] == "agree_after_bit_reversal"
    assert evidence["registered_transform"] == "bit_reversal"
    assert evidence["metrics"]["direct_fidelity"] == 0.0
    assert evidence["metrics"]["bit_reversed_fidelity"] == 1.0
    assert evidence["metrics"]["is_cross_group"] is True
    assert evidence["transform_effect"]["fidelity_delta"] == 1.0
    assert evidence["transform_effect"]["fidelity_after_transform"] == 1.0
    assert evidence["transform_effect"]["relative_phase_after_transform_rad"] == 0.0


def test_statevector_pairwise_evidence_labels_bounded_qubit_permutation():
    target = ["0"] * 8
    target[4] = "1"  # 100
    permuted = ["0"] * 8
    permuted[2] = "1"  # 010, fixed by permutation [1, 0, 2]

    report = create_divergence_report([
        {"simulator": "target", "statevector": target, "qubit_ordering": "msb"},
        {"simulator": "permuted", "statevector": permuted, "qubit_ordering": "msb"},
    ])

    evidence = _record(report, "target", "permuted")
    assert evidence["agreement"] == "agree_after_qubit_permutation"
    assert evidence["registered_transform"] == "qubit_permutation"
    assert evidence["metrics"]["direct_fidelity"] == 0.0
    assert evidence["metrics"]["bit_reversed_fidelity"] == 0.0
    assert evidence["metrics"]["qubit_permutation"]["attempted"] is True
    assert evidence["metrics"]["qubit_permutation"]["permutation"] == [1, 0, 2]
    assert evidence["metrics"]["qubit_permutation"]["fidelity"] == 1.0
    assert evidence["transform_effect"]["permutation"] == [1, 0, 2]
    assert evidence["transform_effect"]["fidelity_after_transform"] == 1.0


def test_statevector_pairwise_evidence_reports_permutation_not_attempted_above_cap():
    """One qubit above the cap, the search must decline rather than run n! transposes."""
    over_cap = MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS + 1
    vector = ["0"] * (2 ** over_cap)
    vector[0] = "1"

    report = create_divergence_report([
        {"simulator": "a", "statevector": vector, "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": vector, "qubit_ordering": "msb"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "agree_directly"
    assert evidence["metrics"]["qubit_permutation"]["attempted"] is False
    assert evidence["metrics"]["qubit_permutation"]["reason"] == "too_many_qubits"
    assert evidence["metrics"]["qubit_permutation"]["n_qubits"] == over_cap


def test_statevector_pairwise_evidence_attempts_permutation_at_the_cap():
    """At exactly the cap the search must run, so the cap is inclusive as documented."""
    at_cap = MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS
    vector = ["0"] * (2 ** at_cap)
    vector[0] = "1"

    report = create_divergence_report([
        {"simulator": "a", "statevector": vector, "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": vector, "qubit_ordering": "msb"},
    ])

    permutation = _record(report, "a", "b")["metrics"]["qubit_permutation"]
    assert permutation["attempted"] is True
    assert permutation["reason"] is None
    assert permutation["n_qubits"] == at_cap


def test_statevector_pairwise_evidence_labels_residual_when_current_registered_modes_do_not_explain():
    report = create_divergence_report([
        {"simulator": "a", "statevector": ["1", "0"], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": ["0", "1"], "qubit_ordering": "msb"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "residual_disagreement"
    assert evidence["registered_transform"] is None
    assert evidence["transform_effect"] is None
    assert evidence["metrics"]["direct_fidelity"] == 0.0


def test_statevector_pairwise_evidence_records_not_comparable_pairs():
    report = create_divergence_report([
        {"simulator": "a", "statevector": ["1", "0"], "qubit_ordering": "msb"},
        {"simulator": "b", "error": "runner failed"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "missing_statevector"
    assert evidence["run_status"] == {"a": "completed", "b": "error"}


def test_counts_pairwise_evidence_labels_current_threshold_decision_and_keeps_matrices():
    report = create_counts_report([
        {
            "simulator": "a",
            "counts": {"0": 10, "1": 0},
            "qubit_ordering": "lsb",
            "sampling_method": "native",
            "seed": 7,
        },
        {
            "simulator": "b",
            "counts": {"0": 0, "1": 10},
            "qubit_ordering": "msb",
            "sampling_method": "sv_sample",
            "seed": 7,
        },
    ], n_shots=10)

    assert "statistical_distance_matrix (js_divergence)" in report
    assert "hellinger_distance_matrix" in report
    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "distance_exceeds_threshold"
    assert evidence["registered_transform"] == "identity_threshold_check"
    assert evidence["metrics"]["n_shots"] == 10
    assert evidence["metrics"]["is_cross_group"] is True
    assert evidence["provenance"]["sampling_method"] == {"a": "native", "b": "sv_sample"}
    assert evidence["provenance"]["seed"] == {"a": 7, "b": 7}


def test_counts_pairwise_evidence_labels_bit_reversal_for_one_hot_ordering_probe():
    report = create_counts_report([
        {
            "simulator": "lsb_backend",
            "counts": {"001": 128},
            "qubit_ordering": "lsb",
            "sampling_method": "native",
        },
        {
            "simulator": "msb_backend",
            "counts": {"100": 128},
            "qubit_ordering": "msb",
            "sampling_method": "sv_sample",
        },
    ], n_shots=128)

    evidence = _record(report, "lsb_backend", "msb_backend")
    assert evidence["agreement"] == "agree_after_bit_reversal"
    assert evidence["registered_transform"] == "bit_reversal"
    assert evidence["metrics"]["js_divergence"] > evidence["metrics"]["js_threshold"]
    assert evidence["metrics"]["hellinger_distance"] > evidence["metrics"]["hellinger_threshold"]
    assert evidence["metrics"]["bit_reversed_js_divergence"] == 0.0
    assert evidence["metrics"]["bit_reversed_hellinger_distance"] == 0.0
    assert evidence["metrics"]["is_cross_group"] is True
    assert evidence["transform_effect"]["js_divergence_after_transform"] == 0.0
    assert evidence["transform_effect"]["hellinger_distance_after_transform"] == 0.0


def test_counts_pairwise_evidence_labels_bounded_qubit_permutation():
    report = create_counts_report([
        {"simulator": "target", "counts": {"100": 128}, "qubit_ordering": "msb"},
        {"simulator": "permuted", "counts": {"010": 128}, "qubit_ordering": "msb"},
    ], n_shots=128)

    evidence = _record(report, "target", "permuted")
    assert evidence["agreement"] == "agree_after_qubit_permutation"
    assert evidence["registered_transform"] == "qubit_permutation"
    assert evidence["metrics"]["js_divergence"] > evidence["metrics"]["js_threshold"]
    assert evidence["metrics"]["bit_reversed_js_divergence"] > evidence["metrics"]["js_threshold"]
    assert evidence["metrics"]["qubit_permutation"]["attempted"] is True
    assert evidence["metrics"]["qubit_permutation"]["permutation"] == [1, 0, 2]
    assert evidence["metrics"]["qubit_permutation"]["js_divergence"] == 0.0
    assert evidence["metrics"]["qubit_permutation"]["hellinger_distance"] == 0.0
    assert evidence["transform_effect"]["permutation"] == [1, 0, 2]
    assert evidence["transform_effect"]["js_divergence_after_transform"] == 0.0


def test_counts_pairwise_evidence_records_not_comparable_pairs():
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 10}, "qubit_ordering": "lsb"},
        {"simulator": "b", "error": "runner failed"},
    ], n_shots=10)

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "missing_counts"
    assert evidence["run_status"] == {"a": "completed", "b": "error"}


def test_statevector_zero_norm_is_not_comparable_without_nan_leak():
    report = create_divergence_report([
        {"simulator": "a", "statevector": ["0", "0"], "qubit_ordering": "lsb"},
        {"simulator": "b", "statevector": ["1", "0"], "qubit_ordering": "lsb"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "zero_norm_statevector"
    _assert_strict_json(report)


def test_statevector_nonfinite_is_not_comparable_without_nan_leak():
    report = create_divergence_report([
        {"simulator": "a", "statevector": ["nan", "0"], "qubit_ordering": "lsb"},
        {"simulator": "b", "statevector": ["1", "0"], "qubit_ordering": "lsb"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "nonfinite_statevector"
    _assert_strict_json(report)


def test_statevector_empty_is_not_comparable():
    report = create_divergence_report([
        {"simulator": "a", "statevector": [], "qubit_ordering": "lsb"},
        {"simulator": "b", "statevector": ["1", "0"], "qubit_ordering": "lsb"},
    ])

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "empty_statevector"
    _assert_strict_json(report)


def test_counts_empty_is_not_comparable():
    report = create_counts_report([
        {"simulator": "a", "counts": {}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"01": 128}, "qubit_ordering": "lsb"},
    ], n_shots=128)

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "empty_counts"
    assert evidence["metrics"]["details"] == {"a": "empty_counts"}
    _assert_strict_json(report)


def test_counts_negative_is_not_comparable_without_inf_leak():
    report = create_counts_report([
        {"simulator": "a", "counts": {"01": -5, "00": 133}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"01": 128}, "qubit_ordering": "lsb"},
    ], n_shots=128)

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "negative_counts"
    _assert_strict_json(report)


def test_counts_nonstring_key_is_not_comparable():
    report = create_counts_report([
        {"simulator": "a", "counts": {1: 128}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"01": 128}, "qubit_ordering": "lsb"},
    ], n_shots=128)

    evidence = _record(report, "a", "b")
    assert evidence["agreement"] == "not_comparable"
    assert evidence["metrics"]["reason"] == "invalid_bitstring_key"
    _assert_strict_json(report)


def test_counts_permutation_reports_inconsistent_bitstring_lengths():
    """Different key widths: the permutation search reports why it was not attempted."""
    report = create_counts_report([
        {"simulator": "a", "counts": {"01": 128}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"010": 128}, "qubit_ordering": "lsb"},
    ], n_shots=128)

    evidence = _record(report, "a", "b")
    permutation = evidence["metrics"]["qubit_permutation"]
    assert permutation["attempted"] is False
    assert permutation["reason"] == "inconsistent_bitstring_lengths"
    _assert_strict_json(report)


def test_bh_adjust_matches_hand_computed():
    adjusted = _bh_adjust([0.01, 0.02, 0.03, 0.04, 0.05])
    assert all(math.isclose(a, 0.05) for a in adjusted)
    assert _bh_adjust([]) == []


def test_shots_for_target_power_reference_value():
    """df=1, alpha=0.05, power=0.8, TV=0.05 gives 1570 shots per backend."""
    assert _shots_per_backend_for_target_power(0.05, 0.8, 0.05) == 1570


def test_statistical_test_consistent_for_identical_distributions():
    report = create_counts_report([
        {"simulator": "a", "counts": {"00": 1000, "11": 1000}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"00": 1000, "11": 1000}, "qubit_ordering": "lsb"},
    ], n_shots=2000)

    evidence = _record(report, "a", "b")
    stat = evidence["metrics"]["statistical_test"]
    assert stat["basis"] == "direct"
    assert stat["verdict"] == "consistent"
    assert stat["effect_size"]["total_variation"] == 0.0
    assert stat["chi2"]["significant_bh"] is False
    assert stat["g_test"]["significant_bh"] is False
    assert evidence["agreement"] == "distance_within_threshold"
    _assert_strict_json(report)


def test_statistical_test_distinguishable_for_clearly_different_distributions():
    report = create_counts_report([
        {"simulator": "a", "counts": {"00": 900, "11": 100}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"00": 100, "11": 900}, "qubit_ordering": "lsb"},
    ], n_shots=1000)

    evidence = _record(report, "a", "b")
    stat = evidence["metrics"]["statistical_test"]
    assert stat["verdict"] == "distinguishable"
    assert stat["chi2"]["significant_bh"] is True
    assert stat["g_test"]["significant_bh"] is True
    assert stat["effect_size"]["total_variation"] > 0.5
    _assert_strict_json(report)


def test_statistical_test_inconclusive_for_low_shots():
    report = create_counts_report([
        {"simulator": "a", "counts": {"00": 2, "11": 2, "01": 1}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"00": 3, "11": 1, "10": 1}, "qubit_ordering": "lsb"},
    ], n_shots=5)

    evidence = _record(report, "a", "b")
    stat = evidence["metrics"]["statistical_test"]
    assert stat["low_count_warning"] is True
    assert stat["verdict"] == "inconclusive_low_shots"
    _assert_strict_json(report)


def test_statistical_test_uses_label_aligned_basis():
    """Declared lsb vs msb: the test runs on bit-reversed keys."""
    report = create_counts_report([
        {"simulator": "lsb_backend", "counts": {"001": 2000}, "qubit_ordering": "lsb"},
        {"simulator": "msb_backend", "counts": {"100": 2000}, "qubit_ordering": "msb"},
    ], n_shots=2000)

    evidence = _record(report, "lsb_backend", "msb_backend")
    assert evidence["agreement"] == "agree_after_bit_reversal"
    stat = evidence["metrics"]["statistical_test"]
    assert stat["basis"] == "bit_reversal"
    assert stat["effect_size"]["total_variation"] == 0.0
    assert stat["verdict"] == "consistent"
    _assert_strict_json(report)


def test_statistical_test_summary_and_fdr_across_family():
    report = create_counts_report([
        {"simulator": "a", "counts": {"00": 500, "11": 500}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"00": 500, "11": 500}, "qubit_ordering": "lsb"},
        {"simulator": "c", "counts": {"00": 900, "11": 100}, "qubit_ordering": "lsb"},
    ], n_shots=1000)

    summary = report["statistical_test_summary"]
    assert summary["family_size"] == 3  # C(3,2) comparable pairs
    assert summary["alpha"] == 0.05
    assert "benjamini_hochberg" in summary["correction"]
    for pair in report["pairwise_agreement"]:
        stat = pair["metrics"]["statistical_test"]
        assert stat["chi2"]["p_value_bh"] is not None
        assert stat["chi2"]["p_value_bonferroni"] is not None
        assert stat["verdict"] in {
            "consistent", "distinguishable", "inconclusive_low_shots", "ambiguous",
        }
    _assert_strict_json(report)


def test_measured_thresholds_are_configurable_and_recorded():
    """Custom js/Hellinger thresholds flow through, flip the label, and are recorded."""
    rows = [
        {"simulator": "a", "counts": {"00": 80, "01": 20}, "qubit_ordering": "lsb", "sampling_method": "native"},
        {"simulator": "b", "counts": {"00": 20, "01": 80}, "qubit_ordering": "lsb", "sampling_method": "native"},
    ]
    default = _record(create_counts_report([dict(x) for x in rows], 100), "a", "b")
    loose = _record(create_counts_report([dict(x) for x in rows], 100,
                                         thresholds={"js_threshold": 0.9, "hellinger_threshold": 0.9}), "a", "b")
    assert default["agreement"] == "distance_exceeds_threshold"
    assert loose["agreement"] == "distance_within_threshold"
    assert default["metrics"]["js_threshold"] == 0.01
    assert loose["metrics"]["js_threshold"] == 0.9 and loose["metrics"]["hellinger_threshold"] == 0.9
    _assert_strict_json(loose)


def test_statevector_tolerance_is_configurable_and_recorded():
    rows = [
        {"simulator": "a", "statevector": [1.0, 0.0], "qubit_ordering": "lsb"},
        {"simulator": "b", "statevector": [1.0, 0.0], "qubit_ordering": "lsb"},
    ]
    rep = create_divergence_report([dict(x) for x in rows], thresholds={"fidelity_tolerance": 1e-6})
    assert _record(rep, "a", "b")["metrics"]["fidelity_tolerance"] == 1e-6
    rep0 = create_divergence_report([dict(x) for x in rows])
    assert _record(rep0, "a", "b")["metrics"]["fidelity_tolerance"] == 1e-5


def _cu3_counts(order, shots=100000):
    """Exact-expectation counts of h;h;cu3(pi/3,pi/5,pi/7);h;h on 2 qubits, keyed lsb or msb."""
    probs = {(0, 0): 0.6962853291580542, (0, 1): 0.11132261253686346,
             (1, 0): 0.08106944576821805, (1, 1): 0.11132261253686346}
    counts = {}
    for (q0, q1), p in probs.items():
        key = f"{q1}{q0}" if order == "lsb" else f"{q0}{q1}"
        counts[key] = round(p * shots)
    return counts


def test_cross_label_pair_is_tested_in_label_aligned_basis():
    report = create_counts_report([
        {"simulator": "qiskit", "counts": _cu3_counts("lsb"), "qubit_ordering": "lsb"},
        {"simulator": "cirq", "counts": _cu3_counts("msb"), "qubit_ordering": "msb"},
    ], n_shots=100000)
    rec = _record(report, "qiskit", "cirq")
    m = rec["metrics"]
    assert m["js_divergence"] <= 0.01
    assert m["js_divergence"] > 1e-3
    assert m["label_aligned_basis"] == "bit_reversal"
    assert m["label_aligned_js_divergence"] == m["bit_reversed_js_divergence"] == 0.0
    assert rec["agreement"] == "agree_after_bit_reversal"
    assert m["statistical_test"]["basis"] == "bit_reversal"
    assert rec["measured_assessment"] == "consistent_within_shot_noise"
    assert report["divergences_found"] == []


def test_same_label_pair_is_tested_directly_even_when_reversal_is_closer():
    report = create_counts_report([
        {"simulator": "a", "counts": _cu3_counts("msb"), "qubit_ordering": "msb"},
        {"simulator": "b", "counts": _cu3_counts("lsb"), "qubit_ordering": "msb"},
    ], n_shots=100000)
    rec = _record(report, "a", "b")
    assert rec["metrics"]["label_aligned_basis"] == "direct"
    assert rec["metrics"]["statistical_test"]["basis"] == "direct"
    assert rec["measured_assessment"] == "distinguishable"


def test_rare_outcome_pooling_and_recommendation_flag():
    stat = _record(create_counts_report([
        {"simulator": "a", "counts": {"0": 99998, "1": 2}},
        {"simulator": "b", "counts": {"0": 99998, "1": 2}},
    ], n_shots=100000), "a", "b")["metrics"]["statistical_test"]
    assert stat["verdict"] == "inconclusive_low_shots"
    assert stat["inconclusive_reason"] == "low_expected_counts"
    assert stat["power"]["recommended_shots_per_backend"] == 1570
    assert stat["power"]["recommended_exceeds_actual"] is False

    stat = _record(create_counts_report([
        {"simulator": "a", "counts": {"00": 1000, "11": 993, "01": 5, "10": 2}},
        {"simulator": "b", "counts": {"00": 1000, "11": 996, "01": 3, "10": 1}},
    ], n_shots=2000), "a", "b")["metrics"]["statistical_test"]
    assert stat["pooled_outcomes"] == 2
    assert stat["tested_outcome_bins"] == 3
    assert stat["low_count_warning"] is False
    assert stat["chi2"]["dof"] == stat["power"]["df"] == 2
    assert stat["verdict"] == "consistent"


def test_single_outcome_tables_use_one_degree_of_freedom_and_low_count_checks():
    one = _record(create_counts_report([
        {"simulator": "a", "counts": {"0": 1}}, {"simulator": "b", "counts": {"0": 1}},
    ], n_shots=1), "a", "b")["metrics"]["statistical_test"]
    assert one["low_count_warning"] is True
    assert one["verdict"] == "inconclusive_low_shots"
    assert one["inconclusive_reason"] == "low_expected_counts"

    ten = _record(create_counts_report([
        {"simulator": "a", "counts": {"00": 10}}, {"simulator": "b", "counts": {"00": 10}},
    ], n_shots=10), "a", "b")["metrics"]["statistical_test"]
    assert ten["chi2"]["dof"] == ten["power"]["df"] == 1
    assert ten["low_count_warning"] is False
    assert ten["verdict"] == "inconclusive_low_shots"
    assert ten["inconclusive_reason"] == "low_power"
    assert ten["power"]["recommended_exceeds_actual"] is True

    many = _record(create_counts_report([
        {"simulator": "a", "counts": {"00": 2048}}, {"simulator": "b", "counts": {"00": 2048}},
    ], n_shots=2048), "a", "b")["metrics"]["statistical_test"]
    assert many["verdict"] == "consistent"


def test_power_is_evaluated_at_bonferroni_alpha_over_the_comparable_pairs():
    backends = [{"simulator": s, "counts": {"0": 1000, "1": 1000}} for s in "abcde"]
    report = create_counts_report(backends, n_shots=2000)
    power = _record(report, "a", "b")["metrics"]["statistical_test"]["power"]
    assert power["m_pairs"] == 10
    assert power["alpha_used"] == 0.05 / 10
    assert power["recommended_shots_per_backend"] == _shots_per_backend_for_target_power(
        0.005, 0.8, 0.05) == 2663
    assert power["power_to_detect_delta_at_observed_shots"] < 0.8
    assert "alpha/m" in power["model"]
    summary = report["statistical_test_summary"]
    assert summary["power_alpha"] == 0.005 and "PRDS" in summary["fdr_dependence_note"]
    assert summary["verdict_counts"] == {"inconclusive_low_shots": 10}

    enough = [{"simulator": s, "counts": {"0": 1332, "1": 1331}} for s in "abcde"]
    stat = _record(create_counts_report(enough, n_shots=2663), "a", "b")["metrics"]["statistical_test"]
    assert stat["power"]["power_to_detect_delta_at_observed_shots"] >= 0.8
    assert stat["verdict"] == "consistent"


def test_divergence_reports_record_analysis_version_and_effective_thresholds():
    from services.analysis.divergence import ANALYSIS_VERSION
    counts = create_counts_report([
        {"simulator": "a", "counts": {"0": 5}}, {"simulator": "b", "counts": {"0": 5}},
    ], n_shots=5, thresholds={"js_threshold": 0.2})
    assert counts["analysis_version"] == ANALYSIS_VERSION
    assert counts["agreement_thresholds"]["js_threshold"] == 0.2
    assert counts["agreement_thresholds"]["hellinger_threshold"] == 0.1
    sv = create_divergence_report([
        {"simulator": "a", "statevector": ["1", "0"]}, {"simulator": "b", "statevector": ["1", "0"]},
    ])
    assert sv["analysis_version"] == ANALYSIS_VERSION
    assert set(sv["agreement_thresholds"]) == {"fidelity_tolerance", "phase_tolerance", "norm_tolerance"}


def test_low_expected_counts_reports_whether_more_shots_can_resolve_it():
    fixable = _record(create_counts_report([
        {"simulator": "a", "counts": {"0": 99997, "1": 3}},
        {"simulator": "b", "counts": {"0": 99997, "1": 3}},
    ], n_shots=100000), "a", "b")["metrics"]["statistical_test"]
    assert fixable["inconclusive_reason"] == "low_expected_counts"
    assert fixable["resolvable_by_more_shots"] is True
    assert 100000 < fixable["shots_per_backend_for_expected_counts"] <= 1_000_000

    unfixable = _record(create_counts_report([
        {"simulator": "a", "counts": {"0": 999999, "1": 1}},
        {"simulator": "b", "counts": {"0": 1000000}},
    ], n_shots=1000000), "a", "b")["metrics"]["statistical_test"]
    assert unfixable["inconclusive_reason"] == "low_expected_counts"
    assert unfixable["resolvable_by_more_shots"] is False
    assert unfixable["shots_per_backend_for_expected_counts"] is None

    low_power = _record(create_counts_report([
        {"simulator": "a", "counts": {"00": 10}}, {"simulator": "b", "counts": {"00": 10}},
    ], n_shots=10), "a", "b")["metrics"]["statistical_test"]
    assert low_power["inconclusive_reason"] == "low_power"
    assert low_power["resolvable_by_more_shots"] is True
