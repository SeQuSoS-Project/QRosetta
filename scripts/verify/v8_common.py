"""Shared pieces of the V8 statistical validation: process setup (CPU set, nice, one BLAS thread),
outcome distributions, sampled runner results, the server's measured analysis (create_counts_report
plus the verdicts the aggregator records), per-pair flags, and Monte Carlo estimates with their
standard errors and 95% intervals. Run with PYTHONPATH=rosetta-api:shared from the repository root."""

import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import math  # noqa: E402

import numpy as np  # noqa: E402
from scipy.stats import beta  # noqa: E402

ALLOWED_CPUS = frozenset(range(0, 16)) | frozenset(range(20, 32))


def set_up_process(nice=10):
    """Restrict this process (and the workers it forks) to ALLOWED_CPUS and lower its priority;
    returns the CPU set in use."""
    cpus = sorted(ALLOWED_CPUS & os.sched_getaffinity(0))
    if not cpus:
        raise SystemExit("none of CPUs 0-15, 20-31 is available to this process")
    os.sched_setaffinity(0, cpus)
    current = os.nice(0)
    if current < nice:
        os.nice(nice - current)
    return cpus


def lsb_keys(n_bits):
    """Counts keys of an n-bit register in lsb order: index i has clbit k = bit k of i, clbit 0
    rightmost."""
    return [format(i, f"0{n_bits}b") for i in range(2 ** n_bits)]


def key_for(index, n_bits, ordering):
    """The key of outcome ``index`` as a backend declaring ``ordering`` writes it."""
    key = format(index, f"0{n_bits}b")
    return key[::-1] if ordering == "msb" else key


def uniform(k):
    return np.full(k, 1.0 / k)


def peaked(k, ratio=0.6):
    """Geometric distribution over k outcomes, p_i proportional to ratio**i, in a scrambled
    order so the vector is not symmetric under bit reversal."""
    p = ratio ** np.arange(k, dtype=float)
    p = p / p.sum()
    order = np.random.default_rng(k).permutation(k)
    return p[order]


def common_and_rare(n_bits, n_common, rare_mass):
    """``n_common`` outcomes share 1 - rare_mass equally; the other 2**n_bits - n_common share
    rare_mass equally."""
    k = 2 ** n_bits
    p = np.full(k, rare_mass / (k - n_common))
    common = np.random.default_rng(n_bits * 1000 + n_common).choice(k, n_common, replace=False)
    p[common] = (1.0 - rare_mass) / n_common
    return p, np.sort(common)


def near_deterministic(eps, n_bits=2):
    """All mass on outcome 0 except ``eps`` on the all-ones outcome."""
    p = np.zeros(2 ** n_bits)
    p[0] = 1.0 - eps
    p[-1] += eps
    return p


def independent_bits(p_one):
    """Joint distribution of independent bits with P(bit k = 1) = p_one[k], lsb index."""
    p = np.array([1.0])
    for q in p_one:
        p = np.concatenate([p * (1.0 - q), p * q])
    return p


def shift(p, tv, source, target):
    """``p`` with ``tv`` moved from outcome ``source`` to outcome ``target`` (total variation tv)."""
    q = np.array(p, dtype=float)
    if q[source] < tv:
        raise ValueError("source outcome holds less than tv")
    q[source] -= tv
    q[target] += tv
    return q


def least_favourable(p, tv):
    """``p`` changed by d with |d_k| proportional to p_k (+ on the first half of the outcomes by
    mass, - on the second), so total variation = tv and sum_k d_k^2 / p_k = 4 tv^2: the
    alternative at which the platform's power model (w = TV, noncentrality 4 n_i n_j/(n_i+n_j) w^2)
    is exact up to the pooled-proportion term."""
    p = np.asarray(p, dtype=float)
    order = np.argsort(-p, kind="stable")
    sign = np.empty(len(p))
    mass = 0.0
    for idx in order:
        sign[idx] = 1.0 if mass < 0.5 - 1e-12 else -1.0
        mass += p[idx]
    plus = p[sign > 0].sum()
    if not math.isclose(plus, 0.5, abs_tol=1e-9):
        raise ValueError("outcomes cannot be split into two halves of equal mass")
    q = p + 2.0 * tv * p * sign
    if q.min() < 0:
        raise ValueError("tv too large for this distribution")
    return q


def total_variation(p, q):
    return float(0.5 * np.abs(np.asarray(p) - np.asarray(q)).sum())


def sample_counts(rng, p, shots, ordering="lsb"):
    """Multinomial counts of ``shots`` draws from ``p`` as the counts dict a backend declaring
    ``ordering`` returns (zero counts omitted)."""
    n_bits = int(round(math.log2(len(p))))
    draws = rng.multinomial(int(shots), p / p.sum())
    nz = np.flatnonzero(draws)
    return {key_for(int(i), n_bits, ordering): int(draws[i]) for i in nz}


def runner_result(name, counts, ordering, seed=None):
    """A measured runner result as the aggregator passes it to the analysis."""
    res = {"simulator": name, "qubit_ordering": ordering, "counts": counts, "dispatch_status": "ok"}
    if seed is not None:
        res["runner_seed"] = seed
    return res


def analyse(results, n_shots):
    """The server's measured analysis of ``results``: create_counts_report, then the pair verdicts
    and per-backend counts (services/aggregator._with_verdicts)."""
    from services.analysis.divergence import create_counts_report
    from services.analysis.divergence.verdicts import annotate_divergence_report

    report = create_counts_report(results, n_shots)
    annotate_divergence_report(report, results, n_shots)
    return report


def pair_flags(pair):
    """What the pipeline concluded for one recorded pair: the page's flag (pair_verdict differs),
    the full-table flag under Benjamini-Yekutieli (measured_assessment distinguishable), the
    full-table flag that also passes Holm (significant_fwer), the single-bit marginal flag, and the
    measured assessment."""
    verdict = pair["pair_verdict"]
    stat = (pair.get("metrics") or {}).get("statistical_test") or {}
    full_by = pair.get("measured_assessment") == "distinguishable"
    return {
        "differs": bool(verdict["differs"]),
        "full_by": full_by,
        "full_holm": bool(full_by and stat.get("significant_fwer")),
        "marginal": pair.get("marginal_assessment") == "marginal_distinguishable",
        "assessment": pair.get("measured_assessment"),
        "test_method": stat.get("test_method"),
    }


FLAG_KINDS = ("differs", "full_by", "full_holm", "marginal")
ASSESSMENTS = ("consistent_within_shot_noise", "inconclusive_low_shots", "ambiguous",
               "distinguishable", "not_comparable")


def run_record(report, wrong):
    """Per-run tallies over the report's pairs. ``wrong`` is the set of backend names whose
    distribution differs from the truth; a pair is correct when neither backend is wrong and
    wrong when exactly one is (pairs of two wrong backends are not counted)."""
    rec = {"correct_pairs": 0, "wrong_pairs": 0}
    for kind in FLAG_KINDS:
        rec[f"ff_{kind}"] = 0
        rec[f"tp_{kind}"] = 0
    for a in ASSESSMENTS:
        rec[f"correct_{a}"] = 0
        rec[f"wrong_{a}"] = 0
    methods = {}
    for pair in report["divergence_report"]["pairwise_agreement"] if "divergence_report" in report \
            else report["pairwise_agreement"]:
        a, b = pair["simulators"]
        n_wrong = (a in wrong) + (b in wrong)
        if n_wrong == 2:
            continue
        flags = pair_flags(pair)
        side = "correct" if n_wrong == 0 else "wrong"
        rec[f"{side}_pairs"] += 1
        rec[f"{side}_{flags['assessment']}"] = rec.get(f"{side}_{flags['assessment']}", 0) + 1
        methods[flags["test_method"]] = methods.get(flags["test_method"], 0) + 1
        for kind in FLAG_KINDS:
            if flags[kind]:
                rec[f"{'ff' if side == 'correct' else 'tp'}_{kind}"] += 1
    rec["methods"] = methods
    return rec


def clopper_pearson(k, n, level=0.95):
    """Exact two-sided interval for a binomial proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    a = (1.0 - level) / 2.0
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1.0 - a, k + 1, n - k))
    return lo, hi


def proportion(k, n):
    """{estimate, mcse, lo, hi, k, n} for k events in n independent runs (Clopper-Pearson 95%)."""
    p = k / n if n else float("nan")
    lo, hi = clopper_pearson(k, n)
    return {"estimate": p, "mcse": math.sqrt(p * (1 - p) / n) if n else float("nan"),
            "lo": lo, "hi": hi, "k": int(k), "n": int(n)}


def clustered_rate(events, totals):
    """Rate sum(events)/sum(totals) of pair-level events collected per run (pairs of one run are
    dependent), with the ratio-estimator standard error over runs and a normal 95% interval."""
    e = np.asarray(events, dtype=float)
    t = np.asarray(totals, dtype=float)
    keep = t > 0
    e, t = e[keep], t[keep]
    r = len(t)
    if r == 0 or t.sum() == 0:
        return {"estimate": float("nan"), "mcse": float("nan"), "lo": float("nan"),
                "hi": float("nan"), "k": 0, "n": 0}
    rate = e.sum() / t.sum()
    resid = e - rate * t
    se = math.sqrt((resid ** 2).sum() / (r * (r - 1))) / t.mean() if r > 1 else float("nan")
    return {"estimate": float(rate), "mcse": se, "lo": max(0.0, rate - 1.96 * se),
            "hi": min(1.0, rate + 1.96 * se), "k": int(e.sum()), "n": int(t.sum())}


def mean_with_se(values):
    v = np.asarray(values, dtype=float)
    se = float(v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else float("nan")
    m = float(v.mean())
    return {"estimate": m, "mcse": se, "lo": m - 1.96 * se, "hi": m + 1.96 * se, "n": len(v)}
