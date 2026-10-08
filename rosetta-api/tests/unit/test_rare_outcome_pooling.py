"""Tests for pooling rare outcomes before the chi-square / G tests: small tables with known
results, the few-outcome tables where a rare bin must not absorb a common outcome, and a wide
sparse table that must pool in linear time."""
import time

import numpy as np
import pytest

from services.analysis.divergence import create_counts_report
from services.analysis.divergence.statistics import _pool_rare_outcomes, _tested_gap


def test_no_pooling_when_every_column_is_large():
    table = _pool_rare_outcomes(np.array([50, 60]), np.array([55, 45]))
    assert (list(table.t_i), list(table.t_j), table.pooled_outcomes, table.ok) == (
        [50, 60], [55, 45], 0, True)


def test_small_pool_beside_two_common_columns_stays_its_own_bin():
    table = _pool_rare_outcomes(np.array([1, 2, 100, 90]), np.array([2, 1, 95, 99]))
    assert table.ok and table.pooled_outcomes == 2 and table.untested_outcomes == 0
    assert list(table.t_i) == [90, 100, 3] and list(table.t_j) == [99, 95, 3]


def test_undersized_pool_beside_one_common_column_is_tested_exactly():
    table = _pool_rare_outcomes(np.array([1, 2, 100]), np.array([2, 1, 99]))
    assert table.ok and table.exact and table.pooled_outcomes == 2
    assert list(table.t_i) == [100, 3] and list(table.t_j) == [99, 3]


def test_single_rare_outcome_beside_one_common_column_is_not_counted_as_pooled():
    table = _pool_rare_outcomes(np.array([8199, 1]), np.array([8199, 1]))
    assert table.ok and table.exact and table.pooled_outcomes == 0 and table.untested_outcomes == 0


def test_two_rare_outcomes_alone_are_tested_exactly():
    table = _pool_rare_outcomes(np.array([2, 1]), np.array([1, 3]))
    assert table.ok and table.exact and len(table.t_i) == 2 and table.pooled_outcomes == 0


def test_exact_p_values_match_fisher_and_the_hypergeometric_tail():
    from scipy.stats import fisher_exact
    from services.analysis.divergence.statistics import _exact_conditional_p_values
    for table in ([[8199, 1], [8199, 1]], [[8200, 0], [8197, 3]], [[8190, 10], [8200, 0]], [[3, 2], [1, 4]]):
        p_chi2, p_g = _exact_conditional_p_values(table)
        assert abs(p_chi2 - fisher_exact(table)[1]) < 1e-12
        assert 0 < p_g <= 1
    assert _exact_conditional_p_values([[8199, 1], [8199, 1]])[0] == pytest.approx(1.0)


def test_near_deterministic_correct_pair_is_consistent_and_its_record_agrees():
    stat = create_counts_report([
        {"simulator": "a", "counts": {"0": 8199, "1": 1}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"0": 8199, "1": 1}, "qubit_ordering": "lsb"},
    ], n_shots=8200)["pairwise_agreement"][0]["metrics"]["statistical_test"]
    assert stat["test_method"] == "exact_conditional" and stat["chi2"]["method"] == "exact_conditional"
    assert stat["verdict"] == "consistent" and stat["low_count_warning"] is False
    assert stat["power"]["power_to_detect_delta_at_observed_shots"] >= 0.8
    assert stat["power"]["recommended_exceeds_actual"] is False


def test_near_deterministic_wrong_pair_is_distinguishable():
    stat = create_counts_report([
        {"simulator": "a", "counts": {"0": 8200}, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": {"0": 8191, "1": 9}, "qubit_ordering": "lsb"},
    ], n_shots=8200)["pairwise_agreement"][0]["metrics"]["statistical_test"]
    assert stat["test_method"] == "exact_conditional"
    assert stat["chi2"]["p_value"] < 0.01 and stat["verdict"] == "distinguishable"


def test_one_rare_column_left_in_place_when_cochran_holds():
    table = _pool_rare_outcomes(np.array([2, 8, 8, 8, 8, 8]), np.array([1, 8, 8, 8, 8, 8]))
    assert table.ok and table.pooled_outcomes == 0
    assert list(table.t_i) == [8, 8, 8, 8, 8, 2] and list(table.t_j) == [8, 8, 8, 8, 8, 1]


def test_pool_below_one_expected_count_is_left_out():
    table = _pool_rare_outcomes(np.array([1, 240, 7600, 240]), np.array([0, 250, 7590, 241]))
    assert table.ok and table.untested_outcomes == 1 and table.pooled_outcomes == 0
    assert len(table.t_i) == 3
    gap, share = _tested_gap(table, 0.05)
    assert share == 1 / 8081 and gap == 0.05 - 1 / 8081


def test_all_rare_columns_are_untestable():
    assert not _pool_rare_outcomes(np.array([1, 0, 1]), np.array([0, 1, 1])).ok


def test_rare_outcome_does_not_drain_the_power_of_a_few_outcome_table():
    a = {"00": 7710, "01": 4, "10": 243, "11": 243}
    b = {"00": 7708, "01": 5, "10": 241, "11": 246}
    stat = create_counts_report([
        {"simulator": "a", "counts": a, "qubit_ordering": "lsb"},
        {"simulator": "b", "counts": b, "qubit_ordering": "lsb"},
    ], n_shots=8200)["pairwise_agreement"][0]["metrics"]["statistical_test"]
    assert stat["tested_outcome_bins"] == 4
    assert stat["power"]["delta_tv_tested"] == 0.05
    assert stat["power"]["power_to_detect_delta_at_observed_shots"] > 0.99
    assert stat["verdict"] == "consistent"


def test_wide_sparse_table_pools_in_linear_time():
    rng = np.random.default_rng(0)
    n = 2 ** 16
    row_i = np.bincount(rng.integers(0, n, 8192), minlength=n)
    row_j = np.bincount(rng.integers(0, n, 8192), minlength=n)
    start = time.perf_counter()
    _pool_rare_outcomes(row_i, row_j)
    assert time.perf_counter() - start < 1.0
