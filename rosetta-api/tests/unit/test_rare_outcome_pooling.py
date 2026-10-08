"""Tests for pooling rare outcomes before the chi-square / G tests: small tables with known
results, the few-outcome tables where a rare bin must not absorb a common outcome, and a wide
sparse table that must pool in linear time."""
import time

import numpy as np

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


def test_undersized_pool_beside_one_common_column_is_untestable():
    table = _pool_rare_outcomes(np.array([1, 2, 100]), np.array([2, 1, 99]))
    assert not table.ok and table.pooled_outcomes == 2
    assert list(table.t_i) == [100, 3] and list(table.t_j) == [99, 3]


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
