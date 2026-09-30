"""Tests for pooling rare outcomes before the chi-square / G tests: small tables with known
results, and a wide sparse table that must pool in linear time."""
import time

import numpy as np

from services.analysis.divergence.statistics import _pool_rare_outcomes


def test_no_pooling_when_every_column_is_large():
    t_i, t_j, pooled, ok = _pool_rare_outcomes(np.array([50, 60]), np.array([55, 45]))
    assert (list(t_i), list(t_j), pooled, ok) == ([50, 60], [55, 45], 0, True)


def test_undersized_pool_absorbs_the_smallest_kept_column():
    t_i, t_j, pooled, ok = _pool_rare_outcomes(np.array([1, 2, 100, 90]),
                                               np.array([2, 1, 95, 99]))
    assert ok and pooled == 3
    assert list(t_i) == [100, 93] and list(t_j) == [95, 102]


def test_one_rare_column_left_in_place_when_cochran_holds():
    t_i, t_j, pooled, ok = _pool_rare_outcomes(np.array([2, 8, 8, 8, 8, 8]),
                                               np.array([1, 8, 8, 8, 8, 8]))
    assert ok and pooled == 0
    assert list(t_i) == [8, 8, 8, 8, 8, 2] and list(t_j) == [8, 8, 8, 8, 8, 1]


def test_all_rare_columns_are_untestable():
    t_i, t_j, pooled, ok = _pool_rare_outcomes(np.array([1, 0, 1]), np.array([0, 1, 1]))
    assert not ok


def test_wide_sparse_table_pools_in_linear_time():
    rng = np.random.default_rng(0)
    n = 2 ** 16
    row_i = np.bincount(rng.integers(0, n, 8192), minlength=n)
    row_j = np.bincount(rng.integers(0, n, 8192), minlength=n)
    start = time.perf_counter()
    _pool_rare_outcomes(row_i, row_j)
    assert time.perf_counter() - start < 1.0
