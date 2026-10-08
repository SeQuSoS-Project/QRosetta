"""Shot-noise-aware homogeneity tests, power model, and multiple-comparison correction.

The tests treat the two backends' counts as independent multinomial samples. Backends that
sampled from a shared seed may draw correlated samples, which the tests do not model; each
test block records whether the pair shared a runner seed.
"""

from typing import NamedTuple

import numpy as np
from scipy.stats import chi2 as _chi2_dist, chi2_contingency, ncx2
from scipy.optimize import brentq

from .common import STAT_TEST_ALPHA, STAT_TEST_DELTA_TV, STAT_TEST_TARGET_POWER

POWER_MODEL = (
    "min_cohens_w at alpha/(m*c_m) on the tested table (w = delta_tv_tested = delta_tv minus "
    "the most total variation the tested table can hide: the smaller of the two backends' "
    "probabilities in a pooled bin of two or more rare outcomes, or the larger of their "
    "probabilities on rare outcomes left out of the table; power is alpha/(m*c_m) when "
    "delta_tv_tested <= 0; df = tested outcome bins - 1, at least 1; noncentrality 4*n_i*n_j/(n_i+n_j) * w^2, "
    "which is (n_i+n_j) * w^2 for equal shots and is limited by the smaller sample; "
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
    for that TV distance (``effective_total_shots`` for unequal rows). The noncentrality is
    lambda = N_total * w^2 on ``df`` = K - 1
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


def effective_total_shots(n_i, n_j):
    """4 n_i n_j / (n_i + n_j): the shot total that gives the noncentrality of a 2 x K test.

    With rows of n_i and n_j shots the noncentrality is (n_i n_j / N) sum_k d_k^2 / m_k
    (d = p - q, m = pooled proportions, N = n_i + n_j), at least 4 (n_i n_j / N) TV^2 by
    Cauchy-Schwarz. For equal rows this is N TV^2; a small row bounds it whatever the other.
    """
    n_i, n_j = float(n_i), float(n_j)
    return 4.0 * n_i * n_j / (n_i + n_j) if n_i + n_j > 0 else 0.0


def _power_at_shots(alpha, delta_tv, df, n_effective):
    """Power to detect ``delta_tv`` on ``df`` at noncentrality ``n_effective * delta_tv^2``.

    ``n_effective`` is ``effective_total_shots`` of the two rows (2n for n shots each).
    """
    crit = _chi2_dist.ppf(1 - alpha, df)
    return float(1 - ncx2.cdf(crit, df, n_effective * (delta_tv ** 2)))


def _tested_gap(table, delta_tv):
    """(delta_tv minus the total variation the tested table cannot see, that amount).

    Outcomes left out of the table hide up to the larger of the two backends' probabilities
    on them; a pooled bin of two or more outcomes hides up to the smaller of the two
    backends' probabilities in it; a bin holding one outcome hides nothing."""
    if table.untested_outcomes:
        share = float(max(table.untested_i / table.n_i, table.untested_j / table.n_j))
    elif table.pooled_outcomes >= 2 and len(table.t_i):
        share = float(min(table.t_i[-1] / table.t_i.sum(), table.t_j[-1] / table.t_j.sum()))
    else:
        return float(delta_tv), 0.0
    return float(delta_tv) - share, share


def _power_on_pooled_table(alpha, delta_tv, p_i, p_j, shots):
    """Power at ``shots`` per backend for the table the observed proportions pool into."""
    table = _pool_rare_outcomes(p_i * shots, p_j * shots)
    gap, _share = _tested_gap(table, delta_tv)
    if gap <= 0:
        return 0.0
    return _power_at_shots(
        alpha, gap, max(len(table.t_i) - 1, 1), effective_total_shots(shots, shots))


def _shots_per_backend_with_pooling(alpha, target_power, delta_tv, p_i, p_j):
    """Smallest shots per backend at which the power on the pooled table of the observed
    proportions reaches ``target_power``; None when MAX_SHOTS does not suffice."""
    hi = _max_shots_per_backend()
    if _power_on_pooled_table(alpha, delta_tv, p_i, p_j, hi) < target_power:
        return None
    lo = 1
    while lo < hi:
        mid = (lo + hi) // 2
        if _power_on_pooled_table(alpha, delta_tv, p_i, p_j, mid) >= target_power:
            hi = mid
        else:
            lo = mid + 1
    return int(lo)


UNSEEN_MASS_LIMIT = 0.5
LOWER_BOUND_UNSEEN_MASS = 0.5 * STAT_TEST_DELTA_TV


def _good_turing_unseen(row):
    """Good-Turing estimate of the probability of outcomes not yet observed: the share of
    shots in outcomes seen exactly once."""
    n = row.sum()
    return float((row == 1).sum() / n) if n else 1.0


def _set_power(block, alpha, m_pairs):
    """Fill ``block["power"]`` for a family of ``m_pairs`` tests at alpha/(m_pairs*c_m).

    Power is evaluated at ``delta_tv_tested``. When rare outcomes were pooled, the
    recommended shots come from pooling the observed proportions at each candidate count
    (``_shots_per_backend_with_pooling``), since pooling changes with the shot count."""
    power = block["power"]
    m = max(int(m_pairs), 1)
    c_m = _by_constant(m)
    alpha_used = alpha / (m * c_m)
    n_shots = list(block["n_shots"].values())
    n_effective = effective_total_shots(*n_shots)
    gap = power.get("delta_tv_tested", power["delta_tv"])
    proportions = block.get("_observed_proportions")
    if block.get("support_characterised") is False:
        recommended = None
    elif power.get("pooled_probability") and proportions is not None:
        recommended = _shots_per_backend_with_pooling(
            alpha_used, power["target_power"], power["delta_tv"], *proportions)
    else:
        recommended = _shots_per_backend_for_target_power(
            alpha_used, power["target_power"], gap, power["df"])
    power.update({
        "alpha_used": alpha_used,
        "m_pairs": int(m_pairs),
        "c_m": c_m,
        "correction": CORRECTION,
        "power_to_detect_delta_at_observed_shots": (
            _power_at_shots(alpha_used, gap, power["df"], n_effective) if gap > 0 else alpha_used),
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
        return _pool_rare_outcomes(p_i * shots, p_j * shots).ok

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


class PooledTable(NamedTuple):
    """The tested 2 x K table after rare outcomes are pooled.

    ``pooled_outcomes`` counts the outcomes merged into the last column (0 when it holds
    one); ``untested_outcomes`` counts outcomes left out of the table, whose counts are
    ``untested_i`` and ``untested_j``; ``n_i`` and ``n_j`` are the full row totals."""
    t_i: np.ndarray
    t_j: np.ndarray
    pooled_outcomes: int
    ok: bool
    untested_outcomes: int = 0
    untested_i: float = 0.0
    untested_j: float = 0.0
    n_i: float = 0.0
    n_j: float = 0.0


def _pool_rare_outcomes(row_i, row_j):
    """Pool outcome columns with an expected count below MIN_EXPECTED_COUNT into one bin.

    The bin is the table's last column and holds only rare outcomes. It is accepted when its
    expected counts reach MIN_EXPECTED_COUNT or the table meets Cochran's rule (no expected
    count below 1, at most 20% below 5). Otherwise, with two or more common columns, it stays
    its own column when its expected counts are at least 1 and is left out of the table when
    they are below 1. ``ok`` is False when no table with at least two columns and adequate
    expected counts exists: every outcome is rare, or one common outcome remains beside an
    undersized bin.
    """
    row_i, row_j = np.asarray(row_i), np.asarray(row_j)
    n_i, n_j = row_i.sum(), row_j.sum()
    n_total = n_i + n_j
    col = row_i + row_j
    min_share = min(n_i, n_j) / n_total
    order = np.argsort(col, kind="stable")
    rare = col[order] * min_share < MIN_EXPECTED_COUNT
    kept = order[~rare]
    n_pooled = int(rare.sum())
    pooled_i, pooled_j = row_i[order[rare]].sum(), row_j[order[rare]].sum()
    totals = {"n_i": float(n_i), "n_j": float(n_j)}

    t_i, t_j = row_i[kept], row_j[kept]
    if n_pooled:
        t_i, t_j = np.append(t_i, pooled_i), np.append(t_j, pooled_j)
    expected = np.outer([n_i, n_j], t_i + t_j) / n_total
    reported = n_pooled if n_pooled > 1 else 0
    if len(t_i) < 2:
        ok = bool((expected >= MIN_EXPECTED_COUNT).all())
        return PooledTable(t_i, t_j, reported, ok and not n_pooled, **totals)
    if not n_pooled or expected[:, -1].min() >= MIN_EXPECTED_COUNT or _cochran_ok(expected):
        return PooledTable(t_i, t_j, reported, True, **totals)
    if len(kept) < 2:
        return PooledTable(t_i, t_j, n_pooled, False, **totals)
    if expected[:, -1].min() >= 1.0:
        return PooledTable(t_i, t_j, reported, True, **totals)
    return PooledTable(t_i[:-1], t_j[:-1], 0, True, n_pooled,
                       float(pooled_i), float(pooled_j), **totals)


def _williams_q(table):
    """Williams' correction divisor for the G statistic of an R x C contingency table:
    q = 1 + (N sum 1/r_i - 1)(N sum 1/c_j - 1) / (6 N (R-1)(C-1))."""
    n = table.sum()
    rows, cols = table.sum(axis=1), table.sum(axis=0)
    r, c = table.shape
    return float(1.0 + (n * np.sum(1.0 / rows) - 1.0) * (n * np.sum(1.0 / cols) - 1.0)
                 / (6.0 * n * (r - 1) * (c - 1)))


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
    basis_source="declared_qubit_ordering",
):
    """Pearson chi-square and G-test (with Williams' correction) of homogeneity between two
    count vectors.

    ``counts_j`` is already aligned to ``basis``. Outcomes with zero counts in both rows are
    dropped; outcomes with an expected count below 5 are pooled into one bin
    (``pooled_outcomes``), or left out when that bin is below an expected count of 1 and
    breaks Cochran's rule (``untested_outcomes``). A table with a single outcome bin is tested against the empty
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

    pooled_table = _pool_rare_outcomes(row_i, row_j)
    t_i, t_j, pooled_outcomes, counts_ok = pooled_table[:4]
    df = max(len(t_i) - 1, 1)
    gap, pooled_share = _tested_gap(pooled_table, delta_tv)
    unseen = max(_good_turing_unseen(row_i), _good_turing_unseen(row_j))
    characterised = unseen <= UNSEEN_MASS_LIMIT
    block = {
        "basis": basis,
        "basis_source": basis_source,
        "n_shots": {sim_i: int(round(n_i)), sim_j: int(round(n_j))},
        "alpha": alpha,
        "shared_seed": _shared_seed(res_i, res_j),
        "observed_outcomes": len(outcomes),
        "pooled_outcomes": int(pooled_outcomes),
        "untested_outcomes": int(pooled_table.untested_outcomes),
        "tested_outcome_bins": int(len(t_i)),
        "effect_size": {
            "total_variation": total_variation,
            "cramers_v": None,
        },
        "power": {
            "delta_tv": delta_tv,
            "delta_tv_tested": gap,
            "pooled_probability": pooled_share,
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
        "unseen_mass_good_turing": unseen,
        "support_characterised": characterised,
        "recommendation_is_lower_bound": bool(characterised and unseen > LOWER_BOUND_UNSEEN_MASS),
        "shots_per_backend_for_expected_counts": (
            None if counts_ok or not characterised
            else _shots_per_backend_for_expected_counts(row_i, row_j)),
        "inconclusive_reason": None,
        "resolvable_by_more_shots": None,
        "verdict": None,
        "_observed_proportions": (p_i, p_j),
    }
    _set_power(block, alpha, 1)

    if len(t_i) < 2:
        block["chi2"].update({"statistic": 0.0, "dof": df, "p_value": 1.0})
        block["g_test"].update({"statistic": 0.0, "dof": df, "p_value": 1.0})
        block["effect_size"]["cramers_v"] = 0.0
        return block

    table = np.vstack([t_i, t_j])
    chi2_stat, chi2_p, dof, _ = chi2_contingency(table, correction=False)
    g_raw, _g_p_raw, _, _ = chi2_contingency(table, correction=False, lambda_="log-likelihood")
    q = _williams_q(table)
    g_stat = g_raw / q
    g_p = float(_chi2_dist.sf(g_stat, dof))

    block["effect_size"]["cramers_v"] = float(np.sqrt(chi2_stat / n_total))
    block["chi2"].update({
        "statistic": float(chi2_stat),
        "dof": int(dof),
        "p_value": float(chi2_p),
    })
    block["g_test"].update({
        "statistic_uncorrected": float(g_raw),
        "williams_q": float(q),
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


def _holm_adjust(pvalues):
    """Holm step-down adjusted p-values, clipped to 1, in input order."""
    m = len(pvalues)
    if m == 0:
        return []
    pvals = np.asarray(pvalues, dtype=float)
    order = np.argsort(pvals)
    ranked = np.maximum.accumulate(pvals[order] * (m - np.arange(m)))
    adjusted = np.empty(m)
    adjusted[order] = np.clip(ranked, 0.0, 1.0)
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
        "adjusted_p_values": ["benjamini_yekutieli", "benjamini_hochberg", "holm", "bonferroni"],
        "fwer_note": ("significant_fwer on a distinguishable pair: both tests also pass Holm's "
                      "family-wise correction, so the flag does not rely on other pairs' "
                      "discoveries raising the BY threshold"),
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
        holm = _holm_adjust(raw)
        for rec, p_raw, p_by, p_bh, p_holm in zip(stat_records, raw, by, bh, holm):
            rec[test]["p_value_by"] = float(p_by)
            rec[test]["p_value_bh"] = float(p_bh)
            rec[test]["p_value_holm"] = float(p_holm)
            rec[test]["significant_holm"] = bool(p_holm < alpha)
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
        uncharacterised = rec.get("support_characterised") is False
        if rec["low_count_warning"]:
            verdict = "inconclusive_low_shots"
            rec["inconclusive_reason"] = "low_expected_counts"
            rec["resolvable_by_more_shots"] = (
                None if uncharacterised
                else rec.get("shots_per_backend_for_expected_counts") is not None)
        elif chi2_sig and g_sig:
            verdict = "distinguishable"
            rec["significant_fwer"] = bool(
                rec["chi2"]["significant_holm"] and rec["g_test"]["significant_holm"])
        elif not chi2_sig and not g_sig:
            if power_at_obs is not None and power_at_obs < target:
                verdict = "inconclusive_low_shots"
                rec["inconclusive_reason"] = "low_power"
                recommended = power.get("recommended_shots_per_backend")
                rec["resolvable_by_more_shots"] = (
                    None if uncharacterised else bool(
                        recommended is not None and recommended <= _max_shots_per_backend()))
            else:
                verdict = "consistent"
        else:
            verdict = "ambiguous"
        rec["verdict"] = verdict
        rec.pop("_observed_proportions", None)
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    return {**summary, "verdict_counts": verdict_counts, "n_significant_by": n_sig}
