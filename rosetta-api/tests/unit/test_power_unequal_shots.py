"""Power of the two-sample tests when the backends' shot totals differ."""

import numpy as np
import pytest
from scipy.stats import chi2_contingency

from services.analysis.divergence.marginals import apply_marginal_correction, marginal_block
from services.analysis.divergence.statistics import (
    _apply_multiple_comparison_correction, _power_at_shots, _statistical_agreement_test,
    effective_total_shots,
)


def _verdict(counts_i, counts_j):
    block = _statistical_agreement_test(counts_i, counts_j, "lsb", "a", "b")
    _apply_multiple_comparison_correction([block])
    return block


def test_equal_shots_unchanged():
    assert effective_total_shots(4100, 4100) == 8200
    assert _power_at_shots(0.05, 0.05, 1, effective_total_shots(1000, 1000)) == pytest.approx(
        _power_at_shots(0.05, 0.05, 1, 2000))


def test_small_second_sample_is_inconclusive():
    block = _verdict({"0": 4100, "1": 4100}, {"0": 30, "1": 20})
    power = block["power"]["power_to_detect_delta_at_observed_shots"]
    assert power == pytest.approx(0.1086, abs=1e-3)
    assert block["verdict"] == "inconclusive_low_shots"
    assert block["inconclusive_reason"] == "low_power"
    assert block["power"]["shots_per_backend_for_target_power"] == 1570
    assert block["power"]["recommended_shots_per_backend"] == 1800


@pytest.mark.parametrize("n_i,n_j", [(8200, 50), (8200, 400), (300, 5000)])
def test_power_matches_rejection_rate(n_i, n_j):
    rng = np.random.default_rng(n_i + n_j)
    p, q, alpha, runs = [0.5, 0.5], [0.45, 0.55], 0.05, 2000
    rejected = sum(
        chi2_contingency(np.vstack([rng.multinomial(n_i, p), rng.multinomial(n_j, q)]),
                         correction=False)[1] < alpha
        for _ in range(runs))
    model = _power_at_shots(alpha, 0.05, 1, effective_total_shots(n_i, n_j))
    assert abs(rejected / runs - model) < 0.035


def test_marginal_power_uses_effective_total():
    block = marginal_block({"00": 4100, "11": 4100}, {"00": 25, "11": 25}, "lsb")
    apply_marginal_correction([block])
    expected = _power_at_shots(
        block_alpha(block), 0.05, 1, effective_total_shots(8200, 50))
    assert block["power_to_detect_delta"] == pytest.approx(expected)
    assert block["power_to_detect_delta"] < 0.2


def block_alpha(block):
    return 0.05 / sum(bit["tested"] for bit in block["bits"])
