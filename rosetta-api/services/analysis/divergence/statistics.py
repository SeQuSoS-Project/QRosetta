"""Shot-noise-aware homogeneity tests, power model, and multiple-comparison correction.

The tests treat the two backends' counts as independent multinomial samples. Backends that
sampled from a shared seed may draw correlated samples, which the tests do not model; each
test block records whether the pair shared a runner seed.
"""

import numpy as np
from scipy.stats import chi2 as _chi2_dist, chi2_contingency, ncx2
from scipy.optimize import brentq

from .common import STAT_TEST_ALPHA, STAT_TEST_DELTA_TV, STAT_TEST_TARGET_POWER

POWER_MODEL = (
    "min_cohens_w at alpha/(m*c_m) (w = delta_tv; df = tested outcome bins - 1, at least 1; "
    "m = comparable pairs in the report, the family BY corrects over; c_m = sum_{i=1..m} 1/i). "
    "alpha/(m*c_m) is the threshold Benjamini-Yekutieli applies to a single discovery, so the "
    "power is a lower bound for detecting one wrong backend under the rule that both tests "
    "are significant after BY."
)
MIN_EXPECTED_COUNT = 5.0
CORRECTION = "BY"
FDR_DEPENDENCE_NOTE = (
    "Benjamini-Yekutieli controls the false discovery rate at q = alpha under arbitrary "
    "dependence between the p-values. Pairs that share a backend reuse its sample, so their "
    "p-values are dependent; BY does not assume independence or positive dependence. Its "
    "threshold is alpha*i/(m*c_m) with c_m = sum_{i=1..m} 1/i."
)


def _by_constant(m):
    """c_m = sum_{i=1..m} 1/i, the Benjamini-Yekutieli dependence constant (1.0 for m <= 1)."""
    return float(sum(1.0 / i for i in range(1, max(int(m), 1) + 1)))


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


def _set_power(block, alpha, m_pairs):
    """Fill ``block["power"]`` for a family of ``m_pairs`` tests at alpha/(m_pairs*c_m)."""
    power = block["power"]
    m = max(int(m_pairs), 1)
    c_m = _by_constant(m)
    alpha_used = alpha / (m * c_m)
    n_shots = list(block["n_shots"].values())
    n_total = float(sum(n_shots))
    recommended = _shots_per_backend_for_target_power(
        alpha_used, power["target_power"], power["delta_tv"], power["df"])
    power.update({
        "alpha_used": alpha_used,
        "m_pairs": int(m_pairs),
        "c_m": c_m,
        "correction": CORRECTION,
        "power_to_detect_delta_at_observed_shots": _power_at_shots(
            alpha_used, power["delta_tv"], power["df"], n_total),
        "shots_per_backend_for_target_power": recommended,
        "recommended_shots_per_backend": recommended,
        "recommended_exceeds_actual": (
            None if recommended is None else bool(recommended > min(n_shots))),
    })


def _max_shots_per_backend():
    from config import settings
    return int(settings.MAX_SHOTS)


def _shots_per_backend_for_expected_counts(row_i, row_j):
    """Smallest shots per backend at which the observed proportions pool into a testable table.

    Both rows are scaled to the same shots per backend, keeping each row's observed
    proportions. None when no count up to the platform's MAX_SHOTS suffices.
    """
    p_i = row_i / row_i.sum()
    p_j = row_j / row_j.sum()

    def testable(shots):
        return _pool_rare_outcomes(p_i * shots, p_j * shots)[3]

    hi = _max_shots_per_backend()
    if not testable(hi):
        return None
    lo = 1
    while lo < hi:
        mid = (lo + hi) // 2
        if testable(mid):
            hi = mid
        else:
            lo = mid + 1
    return int(lo)


def _shared_seed(res_i, res_j):
    """True/False if both results carry a runner_seed, else None."""
    if res_i is None or res_j is None:
        return None
    seed_i = res_i.get("runner_seed")
    seed_j = res_j.get("runner_seed")
    if seed_i is None or seed_j is None:
        return None
    return bool(seed_i == seed_j)


def _cochran_ok(expected):
    """True when no expected count is below 1 and at most 20% are below MIN_EXPECTED_COUNT."""
    return bool(expected.min() >= 1.0 and (expected < MIN_EXPECTED_COUNT).mean() <= 0.2)


def _pool_rare_outcomes(row_i, row_j):
    """Pool outcome columns with an expected count below MIN_EXPECTED_COUNT into one bin.

    Returns (row_i, row_j, pooled_outcomes, ok). The pooled bin is kept when its own
    expected counts reach MIN_EXPECTED_COUNT or the table meets Cochran's rule; otherwise
    the smallest remaining column is merged into it while two or more columns would remain.
    ``ok`` is False when no testable table with at least two columns and adequate expected
    counts exists. ``pooled_outcomes`` counts the observed outcomes merged into the bin.
    """
    n_i, n_j = row_i.sum(), row_j.sum()
    n_total = n_i + n_j
    col = row_i + row_j
    min_share = min(n_i, n_j) / n_total
    order = [int(k) for k in np.argsort(col, kind="stable")]
    pooled = [k for k in order if col[k] * min_share < MIN_EXPECTED_COUNT]
    kept = [k for k in order if k not in pooled]

    def table(kept_cols, pooled_cols):
        cols_i = [row_i[k] for k in kept_cols]
        cols_j = [row_j[k] for k in kept_cols]
        if pooled_cols:
            cols_i.append(sum(row_i[k] for k in pooled_cols))
            cols_j.append(sum(row_j[k] for k in pooled_cols))
        return np.array(cols_i), np.array(cols_j)

    while True:
        t_i, t_j = table(kept, pooled)
        expected = np.outer([n_i, n_j], t_i + t_j) / n_total
        if len(t_i) < 2:
            ok = bool((expected >= MIN_EXPECTED_COUNT).all())
            return t_i, t_j, len(pooled) if len(pooled) > 1 else 0, ok and not pooled
        if not pooled or expected[:, -1].min() >= MIN_EXPECTED_COUNT or _cochran_ok(expected):
            return t_i, t_j, len(pooled) if len(pooled) > 1 else 0, True
        if len(kept) < 2:
            return t_i, t_j, len(pooled), False
        pooled.append(kept.pop(0))


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
    dropped; outcomes with an expected count below 5 are pooled into one bin
    (``pooled_outcomes``). A table with a single outcome bin is tested against the empty
    complement bin: statistic 0 on 1 degree of freedom. ``low_count_warning`` is set when no
    pooling gives adequate expected counts. Power is evaluated on the tested table's degrees
    of freedom. Multiple-comparison correction and the verdict are filled in by
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

    t_i, t_j, pooled_outcomes, counts_ok = _pool_rare_outcomes(row_i, row_j)
    df = max(len(t_i) - 1, 1)
    block = {
        "basis": basis,
        "basis_source": "declared_qubit_ordering",
        "n_shots": {sim_i: int(round(n_i)), sim_j: int(round(n_j))},
        "alpha": alpha,
        "shared_seed": _shared_seed(res_i, res_j),
        "observed_outcomes": len(outcomes),
        "pooled_outcomes": int(pooled_outcomes),
        "tested_outcome_bins": int(len(t_i)),
        "effect_size": {
            "total_variation": total_variation,
            "cramers_v": None,
        },
        "power": {
            "delta_tv": delta_tv,
            "target_power": target_power,
            "model": POWER_MODEL,
            "df": df,
        },
        "chi2": {
            "statistic": None,
            "dof": None,
            "p_value": None,
            "p_value_by": None,
            "p_value_bh": None,
            "p_value_bonferroni": None,
            "significant_by": None,
        },
        "g_test": {
            "statistic": None,
            "dof": None,
            "p_value": None,
            "p_value_by": None,
            "p_value_bh": None,
            "p_value_bonferroni": None,
            "significant_by": None,
        },
        "low_count_warning": not counts_ok,
        "shots_per_backend_for_expected_counts": (
            None if counts_ok else _shots_per_backend_for_expected_counts(row_i, row_j)),
        "inconclusive_reason": None,
        "resolvable_by_more_shots": None,
        "verdict": None,
    }
    _set_power(block, alpha, 1)

    if len(t_i) < 2:
        block["chi2"].update({"statistic": 0.0, "dof": df, "p_value": 1.0})
        block["g_test"].update({"statistic": 0.0, "dof": df, "p_value": 1.0})
        block["effect_size"]["cramers_v"] = 0.0
        return block

    table = np.vstack([t_i, t_j])
    chi2_stat, chi2_p, dof, _ = chi2_contingency(table, correction=False)
    g_stat, g_p, _, _ = chi2_contingency(table, correction=False, lambda_="log-likelihood")

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


def _step_up_adjust(pvalues, scale):
    """Step-up adjusted p-values min_{k>=i} p_(k) * m * scale / k, clipped to 1, in input order."""
    m = len(pvalues)
    if m == 0:
        return []
    pvals = np.asarray(pvalues, dtype=float)
    order = np.argsort(pvals)
    ranked = pvals[order] * m * scale / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    ranked = np.clip(ranked, 0.0, 1.0)
    adjusted = np.empty(m)
    adjusted[order] = ranked
    return adjusted.tolist()


def _bh_adjust(pvalues):
    """Benjamini-Hochberg step-up adjusted p-values, aligned to input order."""
    return _step_up_adjust(pvalues, 1.0)


def _by_adjust(pvalues):
    """Benjamini-Yekutieli adjusted p-values (BH scaled by c_m), aligned to input order."""
    return _step_up_adjust(pvalues, _by_constant(len(pvalues)))


def _apply_multiple_comparison_correction(stat_records, alpha=STAT_TEST_ALPHA):
    """Fill BY, BH and Bonferroni adjusted p-values and verdicts across the pairwise family.

    ``stat_records`` holds one ``statistical_test`` block per tested pair. Correction is
    applied per test (chi-square and G-test) across all pairs; significance is BY-adjusted
    p < alpha. BH-adjusted p-values are recorded for reference. Power is recomputed at
    alpha/(m*c_m) for the m pairs of the family before the verdicts are assigned.
    """
    m = len(stat_records)
    c_m = _by_constant(m) if m else None
    summary = {
        "family_size": m,
        "alpha": alpha,
        "correction": CORRECTION,
        "c_m": c_m,
        "power_alpha": alpha / (m * c_m) if m else None,
        "power_model": POWER_MODEL,
        "adjusted_p_values": ["benjamini_yekutieli", "benjamini_hochberg", "bonferroni"],
        "fdr_dependence_note": FDR_DEPENDENCE_NOTE,
    }
    if m == 0:
        return {**summary, "verdict_counts": {}, "n_significant_by": {"chi2": 0, "g_test": 0}}

    for rec in stat_records:
        _set_power(rec, alpha, m)
        rec["correction"] = CORRECTION

    for test in ("chi2", "g_test"):
        raw = [rec[test]["p_value"] for rec in stat_records]
        by = _by_adjust(raw)
        bh = _bh_adjust(raw)
        for rec, p_raw, p_by, p_bh in zip(stat_records, raw, by, bh):
            rec[test]["p_value_by"] = float(p_by)
            rec[test]["p_value_bh"] = float(p_bh)
            rec[test]["p_value_bonferroni"] = float(min(p_raw * m, 1.0))
            rec[test]["significant_by"] = bool(p_by < alpha)

    verdict_counts = {}
    n_sig = {"chi2": 0, "g_test": 0}
    for rec in stat_records:
        chi2_sig = rec["chi2"]["significant_by"]
        g_sig = rec["g_test"]["significant_by"]
        n_sig["chi2"] += int(bool(chi2_sig))
        n_sig["g_test"] += int(bool(g_sig))
        power = rec.get("power") or {}
        power_at_obs = power.get("power_to_detect_delta_at_observed_shots")
        target = power.get("target_power", STAT_TEST_TARGET_POWER)
        if rec["low_count_warning"]:
            verdict = "inconclusive_low_shots"
            rec["inconclusive_reason"] = "low_expected_counts"
            rec["resolvable_by_more_shots"] = rec.get("shots_per_backend_for_expected_counts") is not None
        elif chi2_sig and g_sig:
            verdict = "distinguishable"
        elif not chi2_sig and not g_sig:
            if power_at_obs is not None and power_at_obs < target:
                verdict = "inconclusive_low_shots"
                rec["inconclusive_reason"] = "low_power"
                recommended = power.get("recommended_shots_per_backend")
                rec["resolvable_by_more_shots"] = bool(
                    recommended is not None and recommended <= _max_shots_per_backend())
            else:
                verdict = "consistent"
        else:
            verdict = "ambiguous"
        rec["verdict"] = verdict
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    return {**summary, "verdict_counts": verdict_counts, "n_significant_by": n_sig}
