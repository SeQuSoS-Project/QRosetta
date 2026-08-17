# Shot-noise-aware hypothesis testing and multiple-comparison correction.

import numpy as np
from scipy.stats import chi2 as _chi2_dist, chi2_contingency, ncx2
from scipy.optimize import brentq

from .common import STAT_TEST_ALPHA, STAT_TEST_DELTA_TV, STAT_TEST_TARGET_POWER


def _shots_per_backend_for_target_power(alpha, target_power, delta_tv):
    """Shots per backend needed to detect a total-variation difference of ``delta_tv``.

    Prospective shot budget under a deliberately conservative two-outcome alternative:
    two outcomes carry all the probability mass and differ by +/- delta_tv between the
    two backends, so the pooled cell probabilities are 0.5 each and Cohen's w reduces to
    exactly ``delta_tv`` on a single degree of freedom. This is the *largest* shot budget
    among alternatives with the same total-variation distance (smallest w), so it does not
    under-state the required shots. Deterministic; scipy-only.
    """
    if delta_tv <= 0:
        return None
    crit = _chi2_dist.ppf(1 - alpha, 1)
    # Required noncentrality lambda so that power == target_power at df=1.
    lam_required = brentq(
        lambda lam: ncx2.cdf(crit, 1, lam) - (1 - target_power),
        0.0,
        1.0e6,
    )
    n_total = lam_required / (delta_tv ** 2)  # lambda = N * w^2, w = delta_tv
    return int(np.ceil(n_total / 2.0))


def _statistical_agreement_test(
    counts_i,
    counts_j,
    basis,
    sim_i,
    sim_j,
    alpha=STAT_TEST_ALPHA,
    target_power=STAT_TEST_TARGET_POWER,
    delta_tv=STAT_TEST_DELTA_TV,
):
    """Shot-noise-aware homogeneity test between two count distributions.

    ``counts_j`` is already aligned to the registered transform named by ``basis`` (direct
    counts, bit-reversed keys, or permuted keys), so the statistical verdict is computed on
    the same basis the explained-cause label selected. Returns descriptive metrics plus raw
    chi-square and G-test p-values; family-wise correction and the final verdict are filled
    in a second pass over all pairs.
    """
    outcomes = sorted(set(counts_i) | set(counts_j))
    row_i = np.array([float(counts_i.get(o, 0)) for o in outcomes])
    row_j = np.array([float(counts_j.get(o, 0)) for o in outcomes])
    n_i = float(row_i.sum())
    n_j = float(row_j.sum())

    p_i = row_i / n_i
    p_j = row_j / n_j
    total_variation = float(0.5 * np.abs(p_i - p_j).sum())

    block = {
        "basis": basis,
        "n_shots": {sim_i: int(round(n_i)), sim_j: int(round(n_j))},
        "alpha": alpha,
        "effect_size": {
            "total_variation": total_variation,
            "cramers_v": None,
        },
        "power": {
            "delta_tv": delta_tv,
            "target_power": target_power,
            "model": "two_outcome_conservative (Cohen's w = delta_tv, df=1)",
            "power_to_detect_delta_at_observed_shots": None,
            "shots_per_backend_for_target_power": _shots_per_backend_for_target_power(
                alpha, target_power, delta_tv
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

    # Prospective sensitivity: with the shots actually used, power to detect a delta_tv
    # difference (same conservative df=1 model). Not post-hoc/observed-effect power.
    n_total = n_i + n_j
    crit_ref = _chi2_dist.ppf(1 - alpha, 1)
    lam_at_observed = n_total * (delta_tv ** 2)
    block["power"]["power_to_detect_delta_at_observed_shots"] = float(
        1 - ncx2.cdf(crit_ref, 1, lam_at_observed)
    )

    # A single shared outcome (K < 2) is a degenerate contingency table (df 0): the two
    # backends put all mass on the same bitstring, so they are trivially consistent.
    if len(outcomes) < 2:
        block["chi2"].update({"statistic": 0.0, "dof": 0, "p_value": 1.0})
        block["g_test"].update({"statistic": 0.0, "dof": 0, "p_value": 1.0})
        block["effect_size"]["cramers_v"] = 0.0
        return block

    table = np.vstack([row_i, row_j])
    chi2_stat, chi2_p, dof, expected = chi2_contingency(table, correction=False)
    g_stat, g_p, _, _ = chi2_contingency(table, lambda_="log-likelihood")

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
    # Enforce monotonicity (step-up): each adjusted value is the running min from the top.
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    ranked = np.clip(ranked, 0.0, 1.0)
    adjusted = np.empty(m)
    adjusted[order] = ranked
    return adjusted.tolist()


def _apply_multiple_comparison_correction(stat_records, alpha=STAT_TEST_ALPHA):
    """Fill BH/Bonferroni-adjusted p-values and verdicts across the pairwise family.

    ``stat_records`` is the list of ``statistical_test`` blocks (one per comparable pair).
    Correction is applied per test (chi-square and G-test) across all pairs, so the fleet's
    many pairwise comparisons do not inflate the false-discovery rate.
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
