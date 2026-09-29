"""Shot-noise-aware homogeneity tests, power model, and multiple-comparison correction.

The tests treat the two backends' counts as independent multinomial samples. Backends that
sampled from a shared seed may draw correlated samples, which the tests do not model; each
test block records whether the pair shared a runner seed.
"""

import numpy as np
from scipy.stats import chi2 as _chi2_dist, chi2_contingency, ncx2
from scipy.optimize import brentq

from .common import STAT_TEST_ALPHA, STAT_TEST_DELTA_TV, STAT_TEST_TARGET_POWER

POWER_MODEL = "min_cohens_w (w = delta_tv, df = observed outcomes - 1)"


def _shots_per_backend_for_target_power(alpha, target_power, delta_tv, df=1):
    """Shots per backend for power ``target_power`` against a total-variation gap ``delta_tv``.

    For a 2 x K homogeneity test with equal shots per backend, Cohen's w satisfies w >= TV
    for every alternative (Cauchy-Schwarz), so w = delta_tv is the least favourable effect
    for that TV distance. The noncentrality is lambda = N_total * w^2 on ``df`` = K - 1
    degrees of freedom. The result is exact for the outcome support supplied; if the true
    support is larger than the observed one, the budget can be too small.
    """
    if delta_tv <= 0 or df < 1:
        return None
    crit = _chi2_dist.ppf(1 - alpha, df)
    lam_required = brentq(
        lambda lam: ncx2.cdf(crit, df, lam) - (1 - target_power),
        0.0,
        1.0e6,
    )
    n_total = lam_required / (delta_tv ** 2)
    return int(np.ceil(n_total / 2.0))


def _power_at_shots(alpha, delta_tv, df, n_total):
    """Power to detect ``delta_tv`` with ``n_total`` shots across both backends, on ``df``."""
    crit = _chi2_dist.ppf(1 - alpha, df)
    return float(1 - ncx2.cdf(crit, df, n_total * (delta_tv ** 2)))


def _shared_seed(res_i, res_j):
    """True/False if both results carry a runner_seed, else None."""
    if res_i is None or res_j is None:
        return None
    seed_i = res_i.get("runner_seed")
    seed_j = res_j.get("runner_seed")
    if seed_i is None or seed_j is None:
        return None
    return bool(seed_i == seed_j)


def _statistical_agreement_test(
    counts_i,
    counts_j,
    basis,
    sim_i,
    sim_j,
    alpha=STAT_TEST_ALPHA,
    target_power=STAT_TEST_TARGET_POWER,
    delta_tv=STAT_TEST_DELTA_TV,
    res_i=None,
    res_j=None,
):
    """Uncorrected Pearson chi-square and G-test of homogeneity between two count vectors.

    ``counts_j`` is already aligned to ``basis``. Outcomes with zero counts in both rows are
    dropped before testing. Family-wise correction and the verdict are filled in by
    ``_apply_multiple_comparison_correction``. Raises ValueError if scipy rejects the table.
    """
    outcomes = [
        o for o in sorted(set(counts_i) | set(counts_j))
        if float(counts_i.get(o, 0)) + float(counts_j.get(o, 0)) > 0
    ]
    row_i = np.array([float(counts_i.get(o, 0)) for o in outcomes])
    row_j = np.array([float(counts_j.get(o, 0)) for o in outcomes])
    n_i = float(row_i.sum())
    n_j = float(row_j.sum())
    n_total = n_i + n_j

    p_i = row_i / n_i
    p_j = row_j / n_j
    total_variation = float(0.5 * np.abs(p_i - p_j).sum())

    df = max(len(outcomes) - 1, 1)
    block = {
        "basis": basis,
        "n_shots": {sim_i: int(round(n_i)), sim_j: int(round(n_j))},
        "alpha": alpha,
        "shared_seed": _shared_seed(res_i, res_j),
        "effect_size": {
            "total_variation": total_variation,
            "cramers_v": None,
        },
        "power": {
            "delta_tv": delta_tv,
            "target_power": target_power,
            "model": POWER_MODEL,
            "df": df,
            "power_to_detect_delta_at_observed_shots": _power_at_shots(alpha, delta_tv, df, n_total),
            "shots_per_backend_for_target_power": _shots_per_backend_for_target_power(
                alpha, target_power, delta_tv, df
            ),
        },
        "chi2": {
            "statistic": None,
            "dof": None,
            "p_value": None,
            "p_value_bh": None,
            "p_value_bonferroni": None,
            "significant_bh": None,
        },
        "g_test": {
            "statistic": None,
            "dof": None,
            "p_value": None,
            "p_value_bh": None,
            "p_value_bonferroni": None,
            "significant_bh": None,
        },
        "low_count_warning": False,
        "verdict": None,
    }

    if len(outcomes) < 2:
        block["chi2"].update({"statistic": 0.0, "dof": 0, "p_value": 1.0})
        block["g_test"].update({"statistic": 0.0, "dof": 0, "p_value": 1.0})
        block["effect_size"]["cramers_v"] = 0.0
        return block

    table = np.vstack([row_i, row_j])
    chi2_stat, chi2_p, dof, expected = chi2_contingency(table, correction=False)
    g_stat, g_p, _, _ = chi2_contingency(table, correction=False, lambda_="log-likelihood")

    block["low_count_warning"] = bool((expected < 5).any())
    block["effect_size"]["cramers_v"] = float(np.sqrt(chi2_stat / n_total))
    block["chi2"].update({
        "statistic": float(chi2_stat),
        "dof": int(dof),
        "p_value": float(chi2_p),
    })
    block["g_test"].update({
        "statistic": float(g_stat),
        "dof": int(dof),
        "p_value": float(g_p),
    })
    return block


def _bh_adjust(pvalues):
    """Benjamini-Hochberg step-up adjusted p-values, aligned to input order."""
    m = len(pvalues)
    if m == 0:
        return []
    pvals = np.asarray(pvalues, dtype=float)
    order = np.argsort(pvals)
    ranked = pvals[order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    ranked = np.clip(ranked, 0.0, 1.0)
    adjusted = np.empty(m)
    adjusted[order] = ranked
    return adjusted.tolist()


def _apply_multiple_comparison_correction(stat_records, alpha=STAT_TEST_ALPHA):
    """Fill BH/Bonferroni-adjusted p-values and verdicts across the pairwise family.

    ``stat_records`` holds one ``statistical_test`` block per tested pair. Correction is
    applied per test (chi-square and G-test) across all pairs.
    """
    m = len(stat_records)
    if m == 0:
        return {
            "family_size": 0,
            "alpha": alpha,
            "correction": ["benjamini_hochberg", "bonferroni"],
            "verdict_counts": {},
            "n_significant_bh": {"chi2": 0, "g_test": 0},
        }

    for test in ("chi2", "g_test"):
        raw = [rec[test]["p_value"] for rec in stat_records]
        bh = _bh_adjust(raw)
        for rec, p_raw, p_bh in zip(stat_records, raw, bh):
            p_bonf = min(p_raw * m, 1.0)
            rec[test]["p_value_bh"] = float(p_bh)
            rec[test]["p_value_bonferroni"] = float(p_bonf)
            rec[test]["significant_bh"] = bool(p_bh < alpha)

    verdict_counts = {}
    n_sig = {"chi2": 0, "g_test": 0}
    for rec in stat_records:
        chi2_sig = rec["chi2"]["significant_bh"]
        g_sig = rec["g_test"]["significant_bh"]
        n_sig["chi2"] += int(bool(chi2_sig))
        n_sig["g_test"] += int(bool(g_sig))
        if rec["low_count_warning"]:
            verdict = "inconclusive_low_shots"
        elif chi2_sig and g_sig:
            verdict = "distinguishable"
        elif not chi2_sig and not g_sig:
            verdict = "consistent"
        else:
            verdict = "ambiguous"
        rec["verdict"] = verdict
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    return {
        "family_size": m,
        "alpha": alpha,
        "correction": ["benjamini_hochberg", "bonferroni"],
        "verdict_counts": verdict_counts,
        "n_significant_bh": n_sig,
    }
