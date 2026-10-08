"""Single-bit marginal tests, a secondary analysis of measured pairs.

For each comparable pair and each classical bit, the two backends' counts of that bit being
0 and 1 form a 2 x 2 table, tested with Pearson's chi-square and the Williams-corrected G
test. Every tested bit of every pair is one family under Holm's step-down correction at alpha,
which bounds the chance of any false flag in the report by alpha whatever the other bits do;
a bit differs when both tests are significant after correction. Equal
marginals, so a differing marginal shows the distributions differ; marginals that do not
differ do not show that the distributions agree. The pair's measured_assessment is not
changed by this analysis.
"""

import numpy as np
from scipy.stats import chi2 as _chi2_dist, chi2_contingency

from .common import STAT_TEST_ALPHA, STAT_TEST_DELTA_TV, STAT_TEST_TARGET_POWER
from .statistics import (
    MIN_EXPECTED_COUNT, _holm_adjust, _power_at_shots, _williams_q, effective_total_shots,
)

MARGINAL_RULE = (
    "Per classical bit: 2 x 2 table of the two backends' counts of the bit being 0 and 1, in "
    "the pair's label-aligned basis; Pearson chi-square and Williams-corrected G, both "
    "required significant after Holm's correction over every tested bit of every pair (the "
    "family-wise error rate, the chance of any false flag in the report, is at most alpha). A "
    "bit with an expected count below 5, or constant in both samples, is not tested. This "
    "family is separate from the full-table family, each at alpha. Equal distributions have equal "
    "marginals, so a differing bit shows the two distributions differ; no differing bit "
    "does not show that they agree, and measured_assessment is unchanged.")


def marginal_counts(counts: dict):
    """(ones per key position, total shots) for a counts dict with equal-length bit keys;
    None when the keys are not all the same length of at least 2."""
    keys = list(counts)
    if not keys or len({len(k) for k in keys}) != 1 or len(keys[0]) < 2:
        return None
    bits = np.frombuffer("".join(keys).encode(), dtype=np.uint8).reshape(len(keys), -1) - ord("0")
    weights = np.array([float(counts[k]) for k in keys])
    return (bits * weights[:, None]).sum(axis=0), float(weights.sum())


def _clbit_index(position: int, n_bits: int, ordering) -> int:
    """Flat classical-bit index of a key position (lsb keys put clbit 0 rightmost)."""
    return n_bits - 1 - position if ordering == "lsb" else position


def marginal_block(counts_i: dict, counts_j_aligned: dict, ordering_i):
    """The per-bit tables and raw test results for one pair, or None when the keys do not
    allow single-bit marginals."""
    a, b = marginal_counts(counts_i), marginal_counts(counts_j_aligned)
    if a is None or b is None or len(a[0]) != len(b[0]):
        return None
    (ones_i, n_i), (ones_j, n_j) = a, b
    n_bits = len(ones_i)
    bits = []
    for pos in range(n_bits):
        table = np.array([[n_i - ones_i[pos], ones_i[pos]], [n_j - ones_j[pos], ones_j[pos]]])
        p_i, p_j = ones_i[pos] / n_i, ones_j[pos] / n_j
        entry = {"position": pos, "clbit": _clbit_index(pos, n_bits, ordering_i),
                 "p_one": [float(p_i), float(p_j)], "difference": float(p_i - p_j),
                 "tested": False, "not_tested_reason": None, "chi2_p_value": None, "g_p_value": None}
        column = table.sum(axis=0)
        if column.min() == 0:
            entry["not_tested_reason"] = "constant_in_both"
        else:
            expected = np.outer(table.sum(axis=1), column) / table.sum()
            if expected.min() >= MIN_EXPECTED_COUNT:
                chi2_stat, chi2_p, _, _ = chi2_contingency(table, correction=False)
                g_raw, _, _, _ = chi2_contingency(table, correction=False, lambda_="log-likelihood")
                g_stat = g_raw / _williams_q(table)
                entry.update(tested=True, chi2_p_value=float(chi2_p),
                             g_p_value=float(_chi2_dist.sf(g_stat, 1)))
            else:
                entry["not_tested_reason"] = "low_expected_counts"
        bits.append(entry)
    return {"n_bits": n_bits, "n_shots": [n_i, n_j], "bits": bits, "assessment": None}


def apply_marginal_correction(blocks, alpha=STAT_TEST_ALPHA, delta=STAT_TEST_DELTA_TV):
    """Holm over every tested bit of every block; fills each bit's adjusted p-values and
    ``differs``, each block's ``assessment`` and ``differing_clbits``; returns the summary."""
    tested = [(block, bit) for block in blocks for bit in block["bits"] if bit["tested"]]
    m = len(tested)
    summary = {"rule": MARGINAL_RULE, "alpha": alpha, "correction": "Holm", "family_size": m,
               "error_control": "family-wise error rate (any false flag in the report) at most alpha"}
    if m:
        chi2_holm = _holm_adjust([bit["chi2_p_value"] for _, bit in tested])
        g_holm = _holm_adjust([bit["g_p_value"] for _, bit in tested])
        for (_, bit), p_chi2, p_g in zip(tested, chi2_holm, g_holm):
            bit["chi2_p_value_holm"] = float(p_chi2)
            bit["g_p_value_holm"] = float(p_g)
            bit["differs"] = bool(p_chi2 < alpha and p_g < alpha)
        alpha_used = alpha / m
        summary["power"] = {
            "delta_p_one": delta, "target_power": STAT_TEST_TARGET_POWER, "alpha_used": alpha_used,
            "model": ("power to detect a difference of delta_p_one in P(bit = 1) at alpha/m (Holm's "
                      "first step), df = 1, w = delta_p_one, noncentrality 4*n_i*n_j/(n_i+n_j) * w^2 "
                      "(as for the full table)")}
    counts = {}
    for block in blocks:
        differing = [bit["clbit"] for bit in block["bits"] if bit.get("differs")]
        if differing:
            assessment = "marginal_distinguishable"
        elif any(bit["tested"] for bit in block["bits"]):
            assessment = "no_marginal_difference_detected"
        else:
            assessment = "not_tested"
        block["assessment"] = assessment
        block["differing_clbits"] = sorted(differing)
        if m:
            block["power_to_detect_delta"] = _power_at_shots(
                summary["power"]["alpha_used"], delta, 1, effective_total_shots(*block["n_shots"]))
        counts[assessment] = counts.get(assessment, 0) + 1
    summary["assessment_counts"] = counts
    return summary
