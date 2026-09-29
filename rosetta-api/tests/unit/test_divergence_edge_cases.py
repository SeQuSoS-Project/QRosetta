"""Adversarial tests for agreement metrics: tolerances, norms, malformed counts, statistics."""

import json
import math
from itertools import permutations

import numpy as np
import pytest
from pydantic import ValidationError

import services.analysis.divergence.reports as reports_module
from schemas.benchmark import AgreementThresholds, BatchPayload, ExperimentPayload, MeasuredQasmPayload
from services.analysis.divergence import (
    DEFAULT_NORM_TOLERANCE,
    _best_counts_qubit_permutation_metrics,
    _counts_distance_metrics,
    _counts_probability_vector,
    _permute_counts,
    _shots_per_backend_for_target_power,
    _statevector_inner_metrics,
    create_counts_report,
    create_divergence_report,
)


def _record(report, sim_a, sim_b):
    return next(r for r in report["pairwise_agreement"] if r["simulators"] == [sim_a, sim_b])


def _strict_json(report):
    json.dumps(report, allow_nan=False)


def _near_one_pair(infidelity):
    return [
        {"simulator": "a", "statevector": [1.0, 0.0], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": [math.sqrt(1 - infidelity), math.sqrt(infidelity)],
         "qubit_ordering": "msb"},
    ]


def test_infidelity_1e8_with_tolerance_1e12_is_residual_disagreement():
    report = create_divergence_report(_near_one_pair(1e-8), thresholds={"fidelity_tolerance": 1e-12})
    record = _record(report, "a", "b")
    assert record["agreement"] == "residual_disagreement"
    assert record["metrics"]["direct_fidelity"] == pytest.approx(1 - 1e-8, abs=1e-15)
    assert record["metrics"]["direct_fidelity"] < 1.0
    assert report["divergences_found"][0]["type"] == "Fidelity"
    _strict_json(report)


def test_infidelity_1e8_with_default_tolerance_agrees_without_rounding_fidelity():
    report = create_divergence_report(_near_one_pair(1e-8))
    record = _record(report, "a", "b")
    assert record["agreement"] == "agree_directly"
    assert record["metrics"]["fidelity_tolerance"] == 1e-5
    assert record["metrics"]["direct_fidelity"] < 1.0
    assert report["fidelity_matrix"][0][1] < 1.0


def test_infidelity_above_default_tolerance_disagrees():
    record = _record(create_divergence_report(_near_one_pair(1e-4)), "a", "b")
    assert record["agreement"] == "residual_disagreement"


def test_inner_metrics_never_round_fidelity_and_clamp_to_one():
    sv = np.array([1.0, 0.0], dtype=complex)
    near = np.array([math.sqrt(1 - 1e-6), math.sqrt(1e-6)], dtype=complex)
    fidelity, _ = _statevector_inner_metrics(sv, near, 1e-5, 1e-12)
    assert fidelity == pytest.approx(1 - 1e-6, abs=1e-14)
    over = np.array([1.0 + 1e-9, 0.0], dtype=complex)
    fidelity_over, _ = _statevector_inner_metrics(sv, over, 1e-5, 1e-12)
    assert fidelity_over == 1.0


def test_norm_three_vector_is_not_a_plain_agreement():
    report = create_divergence_report([
        {"simulator": "a", "statevector": [3.0, 0.0], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": [1.0, 0.0], "qubit_ordering": "msb"},
    ])
    record = _record(report, "a", "b")
    assert record["agreement"] == "agree_after_normalization"
    assert record["metrics"]["unnormalized_input"] is True
    assert record["metrics"]["normalized_agreement"] == "agree_directly"
    assert record["metrics"]["norms"] == {"a": 3.0, "b": 1.0}
    assert record["metrics"]["norm_tolerance"] == DEFAULT_NORM_TOLERANCE
    normalization = [d for d in report["divergences_found"] if d["type"] == "Normalization"]
    assert normalization == [{"type": "Normalization", "simulators": ["a"], "norm": 3.0}]


def test_unnormalized_disagreeing_pair_stays_residual():
    record = _record(create_divergence_report([
        {"simulator": "a", "statevector": [3.0, 0.0], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": [0.0, 1.0], "qubit_ordering": "msb"},
    ]), "a", "b")
    assert record["agreement"] == "residual_disagreement"
    assert record["metrics"]["unnormalized_input"] is True
    assert record["metrics"]["normalized_agreement"] is None


def test_normalized_pair_reports_unnormalized_input_false():
    record = _record(create_divergence_report(_near_one_pair(0.0)), "a", "b")
    assert record["metrics"]["unnormalized_input"] is False
    assert record["metrics"]["normalized_agreement"] is None


def test_norm_tolerance_is_configurable():
    rows = [
        {"simulator": "a", "statevector": [1.001, 0.0], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": [1.0, 0.0], "qubit_ordering": "msb"},
    ]
    assert _record(create_divergence_report(rows), "a", "b")["agreement"] == "agree_after_normalization"
    loose = create_divergence_report(rows, thresholds={"norm_tolerance": 0.01})
    assert _record(loose, "a", "b")["agreement"] == "agree_directly"


def test_default_norm_tolerance_ignores_single_precision_rounding():
    amp = math.sqrt(0.99999797 ** 2 / 2)
    rows = [
        {"simulator": "a", "statevector": [amp, amp], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": [math.sqrt(0.5), math.sqrt(0.5)], "qubit_ordering": "msb"},
    ]
    record = _record(create_divergence_report(rows), "a", "b")
    assert DEFAULT_NORM_TOLERANCE == 1e-4
    assert record["metrics"]["unnormalized_input"] is False
    assert record["agreement"] == "agree_directly"


def test_none_threshold_values_keep_defaults():
    record = _record(create_divergence_report(
        _near_one_pair(1e-8),
        thresholds={"fidelity_tolerance": None, "phase_tolerance": None, "norm_tolerance": None},
    ), "a", "b")
    assert record["metrics"]["fidelity_tolerance"] == 1e-5
    assert record["metrics"]["phase_tolerance"] == 1e-12
    assert record["metrics"]["norm_tolerance"] == DEFAULT_NORM_TOLERANCE


def test_statevector_divergence_is_cross_group_is_bool():
    report = create_divergence_report([
        {"simulator": "a", "statevector": [1.0, 0.0], "qubit_ordering": "msb"},
        {"simulator": "b", "statevector": [0.0, 1.0], "qubit_ordering": "msb"},
        {"simulator": "c", "statevector": [0.0, 1.0], "qubit_ordering": "lsb"},
    ])
    flags = {tuple(d["simulators"]): d["is_cross_group"] for d in report["divergences_found"]}
    assert flags[("a", "b")] is False
    assert flags[("a", "c")] is True
    assert all(isinstance(d["simulators"], list) for d in report["divergences_found"])


def test_all_zero_counts_are_not_comparable():
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 0, "1": 0}},
        {"simulator": "b", "counts": {"0": 5, "1": 5}},
    ], n_shots=10)
    record = _record(report, "a", "b")
    assert record["agreement"] == "not_comparable"
    assert record["metrics"]["reason"] == "zero_total_counts"
    assert report["statistical_distance_matrix (js_divergence)"][0][1] is None
    _strict_json(report)


@pytest.mark.parametrize("value", ["5", True, None, [5]])
def test_non_numeric_counts_are_not_comparable(value):
    record = _record(create_counts_report([
        {"simulator": "a", "counts": {"0": value, "1": 5}},
        {"simulator": "b", "counts": {"0": 5, "1": 5}},
    ], n_shots=10), "a", "b")
    assert record["agreement"] == "not_comparable"
    assert record["metrics"]["reason"] == "non_numeric_counts"


def test_numpy_integer_counts_are_accepted():
    record = _record(create_counts_report([
        {"simulator": "a", "counts": {"0": np.int64(5), "1": np.int64(5)}},
        {"simulator": "b", "counts": {"0": 5, "1": 5}},
    ], n_shots=10), "a", "b")
    assert record["agreement"] == "distance_within_threshold"


def test_single_shot_per_backend_is_comparable_and_json_safe():
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 1}},
        {"simulator": "b", "counts": {"1": 1}},
    ], n_shots=1)
    record = _record(report, "a", "b")
    assert record["agreement"] == "distance_exceeds_threshold"
    assert record["metrics"]["statistical_test"]["verdict"] == "inconclusive_low_shots"
    assert record["metrics"]["js_divergence"] == pytest.approx(math.log(2))
    _strict_json(report)


def test_identical_distributions_with_different_totals_agree_and_record_mismatch():
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 50, "1": 50}},
        {"simulator": "b", "counts": {"0": 500, "1": 500}},
    ], n_shots=100)
    record = _record(report, "a", "b")
    assert record["metrics"]["js_divergence"] == 0.0
    assert record["metrics"]["hellinger_distance"] == 0.0
    assert record["agreement"] == "distance_within_threshold"
    assert record["metrics"]["shot_total_mismatch"] == {
        "observed": {"a": 100, "b": 1000}, "requested": 100,
    }
    assert record["metrics"]["statistical_test"]["effect_size"]["total_variation"] == 0.0


def test_requested_shots_differing_from_observed_totals_does_not_distort_distances():
    rows = [
        {"simulator": "a", "counts": {"0": 60, "1": 40}},
        {"simulator": "b", "counts": {"0": 60, "1": 40}},
    ]
    matched = _record(create_counts_report([dict(r) for r in rows], n_shots=100), "a", "b")
    mismatched = _record(create_counts_report([dict(r) for r in rows], n_shots=1000), "a", "b")
    assert matched["metrics"]["shot_total_mismatch"] is None
    assert mismatched["metrics"]["shot_total_mismatch"] == {
        "observed": {"a": 100, "b": 100}, "requested": 1000,
    }
    assert mismatched["metrics"]["js_divergence"] == matched["metrics"]["js_divergence"]


def test_probability_vector_normalises_by_observed_total():
    pv = _counts_probability_vector({"0": 3, "1": 1}, ["0", "1"])
    assert pv.tolist() == [0.75, 0.25]


def test_zero_count_column_shared_by_both_rows_does_not_abort_report():
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 10, "1": 0}},
        {"simulator": "b", "counts": {"0": 10, "1": 0}},
        {"simulator": "c", "counts": {"0": 5, "1": 5}},
    ], n_shots=10)
    assert len(report["pairwise_agreement"]) == 3
    assert _record(report, "a", "b")["metrics"]["statistical_test"]["verdict"] == "consistent"
    _strict_json(report)


def test_per_pair_exception_is_not_comparable_and_other_pairs_survive(monkeypatch):
    original = reports_module._statistical_agreement_test

    def flaky(counts_i, counts_j, basis, sim_i, sim_j, **kwargs):
        if sim_i == "a" and sim_j == "b":
            raise ValueError("table rejected")
        return original(counts_i, counts_j, basis, sim_i, sim_j, **kwargs)

    monkeypatch.setattr(reports_module, "_statistical_agreement_test", flaky)
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 5, "1": 5}},
        {"simulator": "b", "counts": {"0": 5, "1": 5}},
        {"simulator": "c", "counts": {"0": 5, "1": 5}},
    ], n_shots=10)
    failed = _record(report, "a", "b")
    assert failed["agreement"] == "not_comparable"
    assert failed["metrics"]["reason"] == "comparison_error"
    assert "table rejected" in failed["metrics"]["details"]["error"]
    assert _record(report, "a", "c")["agreement"] == "distance_within_threshold"
    assert report["statistical_test_summary"]["family_size"] == 2
    assert report["statistical_distance_matrix (js_divergence)"][0][1] is None


def test_nan_metric_is_not_comparable_never_zero(monkeypatch):
    monkeypatch.setattr(reports_module, "_counts_distance_metrics", lambda p, q: (float("nan"), 0.0))
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 5, "1": 5}},
        {"simulator": "b", "counts": {"0": 5, "1": 5}},
    ], n_shots=10)
    record = _record(report, "a", "b")
    assert record["agreement"] == "not_comparable"
    assert record["metrics"]["reason"] == "nonfinite_metric"
    assert report["statistical_distance_matrix (js_divergence)"][0][1] is None
    _strict_json(report)


def test_distance_metrics_propagate_nan():
    js, _ = _counts_distance_metrics(np.array([0.0, 0.0]), np.array([0.0, 0.0]))
    assert math.isnan(js)


def test_g_test_is_uncorrected_at_one_degree_of_freedom():
    counts_a = {"0": 30, "1": 10}
    counts_b = {"0": 20, "1": 20}
    stat = _record(create_counts_report([
        {"simulator": "a", "counts": counts_a},
        {"simulator": "b", "counts": counts_b},
    ], n_shots=40), "a", "b")["metrics"]["statistical_test"]
    observed = np.array([[30, 10], [20, 20]], dtype=float)
    expected = observed.sum(1, keepdims=True) * observed.sum(0, keepdims=True) / observed.sum()
    g_manual = 2 * float((observed * np.log(observed / expected)).sum())
    chi2_manual = float(((observed - expected) ** 2 / expected).sum())
    assert stat["g_test"]["dof"] == 1
    assert stat["g_test"]["statistic"] == pytest.approx(g_manual)
    assert stat["chi2"]["statistic"] == pytest.approx(chi2_manual)


def test_power_model_uses_observed_degrees_of_freedom():
    stat = _record(create_counts_report([
        {"simulator": "a", "counts": {"00": 250, "01": 250, "10": 250, "11": 250}},
        {"simulator": "b", "counts": {"00": 250, "01": 250, "10": 250, "11": 250}},
    ], n_shots=1000), "a", "b")["metrics"]["statistical_test"]
    assert stat["power"]["df"] == 3
    assert stat["power"]["shots_per_backend_for_target_power"] == _shots_per_backend_for_target_power(
        0.05, 0.8, 0.05, df=3
    )
    assert stat["power"]["shots_per_backend_for_target_power"] > _shots_per_backend_for_target_power(
        0.05, 0.8, 0.05, df=1
    )
    assert "df" in stat["power"]["model"]


def test_two_outcome_power_model_keeps_df_one_budget():
    stat = _record(create_counts_report([
        {"simulator": "a", "counts": {"0": 500, "1": 500}},
        {"simulator": "b", "counts": {"0": 500, "1": 500}},
    ], n_shots=1000), "a", "b")["metrics"]["statistical_test"]
    assert stat["power"]["df"] == 1
    assert stat["power"]["shots_per_backend_for_target_power"] == 1570


@pytest.mark.parametrize("seed_a,seed_b,expected", [(7, 7, True), (7, 8, False), (7, None, None)])
def test_shared_seed_is_recorded(seed_a, seed_b, expected):
    rows = [
        {"simulator": "a", "counts": {"0": 5, "1": 5}, "runner_seed": seed_a},
        {"simulator": "b", "counts": {"0": 5, "1": 5}, "runner_seed": seed_b},
    ]
    record = _record(create_counts_report(rows, n_shots=10), "a", "b")
    assert record["metrics"]["statistical_test"]["shared_seed"] is expected
    assert record["provenance"]["runner_seed"] == {"a": seed_a, "b": seed_b}


def test_shared_seed_is_null_without_runner_seeds():
    record = _record(create_counts_report([
        {"simulator": "a", "counts": {"0": 5, "1": 5}},
        {"simulator": "b", "counts": {"0": 5, "1": 5}},
    ], n_shots=10), "a", "b")
    assert record["metrics"]["statistical_test"]["shared_seed"] is None


def _score(counts_i, counts_j, permutation):
    permuted = _permute_counts(counts_j, permutation)
    outcomes = sorted(set(counts_i) | set(permuted))
    js, h = _counts_distance_metrics(
        _counts_probability_vector(counts_i, outcomes),
        _counts_probability_vector(permuted, outcomes),
    )
    return js + h


def test_counts_permutation_search_returns_best_not_first_within_threshold():
    """(0, 2, 1) is within the default thresholds and comes first; (2, 0, 1) is exact."""
    counts_i = {"000": 1000, "100": 505, "010": 495}
    counts_j = {"000": 1000, "001": 505, "100": 495}
    candidates = [p for p in permutations(range(3)) if p not in ((0, 1, 2), (2, 1, 0))]
    scores = {p: _score(counts_i, counts_j, p) for p in candidates}
    assert 0 < scores[(0, 2, 1)] < 0.01 + 0.1
    assert scores[(2, 0, 1)] == 0.0

    best = _best_counts_qubit_permutation_metrics(counts_i, counts_j)
    assert best["permutation"] == [2, 0, 1]
    assert best["js_divergence"] == 0.0

    record = _record(create_counts_report([
        {"simulator": "a", "counts": counts_i},
        {"simulator": "b", "counts": counts_j},
    ], n_shots=2000), "a", "b")
    assert record["agreement"] == "agree_after_qubit_permutation"
    assert record["transform_effect"]["permutation"] == [2, 0, 1]
    assert record["metrics"]["statistical_test"]["effect_size"]["total_variation"] == 0.0


def test_counts_permutation_ties_keep_lexicographically_first():
    counts = {"000": 50, "111": 50}
    best = _best_counts_qubit_permutation_metrics(counts, dict(counts))
    assert best["permutation"] == [0, 2, 1]


def test_counts_report_declares_js_unit_nats():
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 10}},
        {"simulator": "b", "counts": {"1": 10}},
    ], n_shots=10)
    assert report["js_divergence_unit"] == "nats"
    assert _record(report, "a", "b")["metrics"]["js_divergence"] == pytest.approx(math.log(2))


def test_counts_divergences_found_is_cross_group_is_bool():
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 10}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"1": 10}, "qubit_ordering": "lsb"},
    ], n_shots=10)
    assert report["divergences_found"][0]["is_cross_group"] is False


@pytest.mark.parametrize("model,extra", [
    (MeasuredQasmPayload, {"qasm_string": "x"}),
    (BatchPayload, {"tasks": [], "mode": "measured"}),
    (ExperimentPayload, {"circuits": []}),
])
@pytest.mark.parametrize("shots", [0, -1])
def test_n_shots_must_be_positive(model, extra, shots):
    with pytest.raises(ValidationError):
        model(n_shots=shots, **extra)
    assert model(n_shots=1, **extra).n_shots == 1


def test_agreement_threshold_defaults():
    thresholds = AgreementThresholds()
    assert thresholds.fidelity_tolerance == 1e-5
    assert thresholds.phase_tolerance == 1e-12
    assert thresholds.norm_tolerance == DEFAULT_NORM_TOLERANCE
    assert thresholds.js_threshold == 0.01
    assert thresholds.hellinger_threshold == 0.1


def test_schema_thresholds_flow_into_report():
    report = create_divergence_report(_near_one_pair(1e-8), thresholds=AgreementThresholds().model_dump())
    record = _record(report, "a", "b")
    assert record["agreement"] == "agree_directly"
    assert record["metrics"]["norm_tolerance"] == DEFAULT_NORM_TOLERANCE


def test_measured_assessment_combines_distance_label_and_verdict():
    report = create_counts_report([
        {"simulator": "a", "counts": {"0": 6, "1": 4}},
        {"simulator": "b", "counts": {"0": 4, "1": 6}},
        {"simulator": "c", "counts": {"0": 0, "1": 0}},
    ], n_shots=10)
    ab = _record(report, "a", "b")
    assert ab["agreement"] == "distance_exceeds_threshold"
    assert ab["metrics"]["statistical_test"]["verdict"] == "consistent"
    assert ab["measured_assessment"] == "consistent_within_shot_noise"
    assert _record(report, "a", "c")["measured_assessment"] == "not_comparable"
    assert report["statistical_test_summary"]["measured_assessment_counts"] == {
        "consistent_within_shot_noise": 1, "not_comparable": 2}


def test_matrices_use_null_for_uncompared_pairs_and_exact_self_values():
    counts = create_counts_report([
        {"simulator": "a", "counts": {"0": 5, "1": 5}},
        {"simulator": "b", "counts": {"0": 0, "1": 0}},
    ], n_shots=10)
    assert counts["statistical_distance_matrix (js_divergence)"] == [[0.0, None], [None, None]]
    assert counts["hellinger_distance_matrix"] == [[0.0, None], [None, None]]
    sv = create_divergence_report([
        {"simulator": "a", "statevector": [1.0, 0.0]},
        {"simulator": "b", "error": "boom"},
    ])
    assert sv["fidelity_matrix"] == [[1.0, None], [None, None]]
    assert sv["relative_phase_matrix"] == [[0.0, None], [None, None]]
    _strict_json(counts)
