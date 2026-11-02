"""V8 p-value calibration under the null: raw (uncorrected) p-values of Pearson chi-square, Williams G
and the exact conditional test as the server computes them for one pair, over the asymptotic,
pooling, left-out-outcome, exact-test, lsb x msb, 1-bit-key and unequal-shot branches, plus the
single-bit marginal tests and Williams' correction on a 65,536-bin table.

    PYTHONPATH=rosetta-api:shared python scripts/verify/v8_calibration.py --out DIR [--samples N]

Each sample is two independent backends drawn from the same distribution and analysed by
create_counts_report (so the label-aligned basis is chosen as on the server). Writes
DIR/calibration_summary.csv (P(p <= a) with MCSE at a = 0.001, 0.01, 0.05, KS distance from
uniform), DIR/calibration_hist.csv (counts per p-value bin) and DIR/qq_<generator>.png."""

import argparse
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import v8_common as c

import numpy as np
from scipy.stats import chi2 as chi2_dist
from scipy.stats import kstest

MASTER_SEED = 20261103
LEVELS = (0.001, 0.01, 0.05)
BINS = np.array([0, 1e-4, 1e-3, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7,
                 0.8, 0.9, 1.0 + 1e-12])


def generators():
    """name -> (p, shots_a, shots_b, ordering_b, description, samples factor)."""
    two_rare = np.array([0.4998, 0.4998, 0.0002, 0.0002])
    many_rare, _ = c.common_and_rare(8, 4, 0.03)
    untested, _ = c.common_and_rare(8, 4, 6e-5)
    return {
        "asymptotic-uniform-2": (c.uniform(2), 8200, 8200, "lsb", "2 outcomes, 8200 each", 1),
        "asymptotic-uniform-16": (c.uniform(16), 8200, 8200, "lsb", "16 outcomes, 8200 each", 1),
        "asymptotic-peaked-16": (c.peaked(16), 8200, 8200, "lsb",
                                 "geometric 16 outcomes, rare tail pooled", 1),
        "pooled-two-rare": (two_rare, 8200, 8200, "lsb", "two rare outcomes pooled, kept as a "
                            "column", 1),
        "pooled-many-rare": (many_rare, 8200, 8200, "lsb", "4 common + 252 rare (0.03)", 1),
        "untested-outcomes": (untested, 8200, 8200, "lsb", "4 common + 252 rare (6e-5), bin left "
                              "out", 1),
        "exact-small-table": (np.array([0.98, 0.02]), 100, 100, "lsb",
                              "2 outcomes (0.98, 0.02), 100 shots each: exact conditional", 1),
        "exact-near-deterministic": (c.near_deterministic(2e-4), 8200, 8200, "lsb",
                                     "P(11) = 2e-4: exact conditional or degenerate", 1),
        "basis-lsb-msb-16": (c.peaked(16), 8200, 8200, "msb", "peaked 16, second backend msb", 1),
        "single-bit-lsb-msb": (np.array([0.3, 0.7]), 8200, 8200, "msb",
                               "1-bit keys, lsb x msb declared", 1),
        "unequal-8200v50": (c.uniform(4), 8200, 50, "lsb", "uniform 4, 8200 vs 50", 1),
        "unequal-8200v400": (c.uniform(4), 8200, 400, "lsb", "uniform 4, 8200 vs 400", 1),
        "marginal-2bit": (c.independent_bits([0.3, 0.6]), 8200, 8200, "lsb",
                          "single-bit marginal tests, 2 independent bits", 1),
    }


GENERATORS = generators()
NAMES = list(GENERATORS)


def one_sample(name, run):
    p, n_a, n_b, order_b, _desc, _f = GENERATORS[name]
    g = NAMES.index(name)
    rng_a = np.random.default_rng([MASTER_SEED, g, run, 0])
    rng_b = np.random.default_rng([MASTER_SEED, g, run, 1])
    results = [c.runner_result("a", c.sample_counts(rng_a, p, n_a, "lsb"), "lsb", seed=1),
               c.runner_result("b", c.sample_counts(rng_b, p, n_b, order_b), order_b, seed=2)]
    report = c.analyse(results, None)
    pair = report["pairwise_agreement"][0]
    metrics = pair.get("metrics") or {}
    if name == "marginal-2bit":
        bits = (metrics.get("marginal_test") or {}).get("bits") or []
        return [{"chi2": b["chi2_p_value"], "g": b["g_p_value"], "branch": "marginal"}
                for b in bits if b["tested"]]
    stat = metrics.get("statistical_test") or {}
    branch = stat.get("test_method")
    if stat.get("untested_outcomes"):
        branch += "+untested"
    elif stat.get("pooled_outcomes"):
        branch += "+pooled"
    branch += f"|{stat.get('basis')}/{stat.get('basis_source')}"
    return [{"chi2": stat["chi2"]["p_value"], "g": stat["g_test"]["p_value"], "branch": branch}]


def williams_sample(run):
    """Raw p-values of the Williams-corrected and uncorrected G and of chi-square for 16-bit
    uniform counts, 1e6 shots per backend, from _statistical_agreement_test."""
    from services.analysis.divergence.statistics import _statistical_agreement_test
    p = c.uniform(2 ** 16)
    rng = np.random.default_rng([MASTER_SEED, 777, run])
    a = c.sample_counts(rng, p, 1_000_000)
    b = c.sample_counts(rng, p, 1_000_000)
    stat = _statistical_agreement_test(a, b, "direct", "a", "b")
    g = stat["g_test"]
    return [{"chi2": stat["chi2"]["p_value"], "g": g["p_value"],
             "g_uncorrected": float(chi2_dist.sf(g["statistic_uncorrected"], g["dof"])),
             "branch": stat["test_method"]}]


def _chunk(args):
    name, runs = args
    out = []
    for r in runs:
        out.extend(williams_sample(r) if name == "williams-65536" else one_sample(name, r))
    return name, out


def calibration_rows(name, samples, tests):
    rows = []
    for test in tests:
        p = np.array([s[test] for s in samples], dtype=float)
        n = len(p)
        row = {"generator": name, "test": test, "n": n}
        for a in LEVELS:
            k = int((p <= a).sum())
            est = k / n
            mcse = math.sqrt(a * (1 - a) / n)
            row[f"P(p<={a:g})"] = est
            row[f"mcse_at_{a:g}"] = mcse
            row[f"ok_at_{a:g}"] = bool(est <= a + 2 * mcse)
        ks = kstest(p, "uniform")
        row["ks_d"] = float(ks.statistic)
        row["ks_p"] = float(ks.pvalue)
        row["share_p_eq_1"] = float((p >= 1 - 1e-12).mean())
        branches = {}
        for s in samples:
            branches[s["branch"]] = branches.get(s["branch"], 0) + 1
        row["branches"] = json.dumps(branches, sort_keys=True)
        rows.append(row)
    return rows


def qq_plot(path, name, samples, tests):
    """-log10 QQ plot against the uniform distribution; points above the diagonal are p-values
    smaller than a calibrated test gives. The numbers are in calibration_hist.csv."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    style = {"chi2": ("#2a78d6", "o", "Pearson chi-square"), "g": ("#eb6834", "s", "G (Williams)"),
             "g_uncorrected": ("#1baf7a", "^", "G uncorrected")}
    fig, ax = plt.subplots(figsize=(4.4, 4.4), dpi=130, facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    top = 0.0
    for test in tests:
        colour, marker, label = style[test]
        p = np.sort(np.clip([s[test] for s in samples], 1e-300, 1.0))
        n = len(p)
        x = -np.log10((np.arange(1, n + 1) - 0.5) / n)
        y = -np.log10(p)
        ax.plot(x, y, marker, ms=2.5, mew=0, color=colour, label=label, alpha=0.8)
        top = max(top, x.max(), y.max())
    ax.plot([0, top], [0, top], color="#55554f", lw=1.0, label="calibrated")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.grid(color="#e4e3dc", lw=0.6)
    ax.set_xlabel("expected -log10 p (uniform)", color="#33332f")
    ax.set_ylabel("observed -log10 p", color="#33332f")
    ax.set_title(name, fontsize=9, color="#1c1c1a")
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=20000)
    ap.add_argument("--williams-samples", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=200)
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args(argv)
    cpus = c.set_up_process()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [("williams-65536", list(range(i, min(i + 20, args.williams_samples))))
             for i in range(0, args.williams_samples, 20)]
    for name in NAMES:
        tasks += [(name, list(range(i, min(i + args.chunk, args.samples))))
                  for i in range(0, args.samples, args.chunk)]
    samples = {n: [] for n in ["williams-65536", *NAMES]}
    start = time.time()
    with Pool(args.workers or len(cpus)) as pool:
        for done, (name, recs) in enumerate(pool.imap_unordered(_chunk, tasks), 1):
            samples[name].extend(recs)
            if done % 50 == 0 or done == len(tasks):
                print(f"{done}/{len(tasks)} chunks, {time.time() - start:.0f} s", flush=True)
    rows = []
    for name, recs in samples.items():
        tests = ("chi2", "g", "g_uncorrected") if name == "williams-65536" else ("chi2", "g")
        rows += calibration_rows(name, recs, tests)
        if not args.no_plots:
            qq_plot(out / f"qq_{name}.png", name, recs, tests)
    header = list(rows[0])
    lines = [",".join(header)]
    for r in rows:
        lines.append(",".join(f'"{r[h]}"' if h == "branches" else str(r[h]) for h in header))
    (out / "calibration_summary.csv").write_text("\n".join(lines) + "\n")
    hist = ["generator,test," + ",".join(f"[{BINS[i]:g},{min(BINS[i + 1], 1):g})"
                                          for i in range(len(BINS) - 1))]
    for name, recs in samples.items():
        tests = ("chi2", "g", "g_uncorrected") if name == "williams-65536" else ("chi2", "g")
        for test in tests:
            counts, _ = np.histogram([s[test] for s in recs], bins=BINS)
            hist.append(f"{name},{test}," + ",".join(str(int(x)) for x in counts))
    (out / "calibration_hist.csv").write_text("\n".join(hist) + "\n")
    descriptions = {n: GENERATORS[n][4] for n in NAMES}
    descriptions["williams-65536"] = "65,536 uniform outcomes, 1e6 shots per backend"
    (out / "calibration.json").write_text(json.dumps(
        {"master_seed": MASTER_SEED, "cpus": cpus, "wall_seconds": time.time() - start,
         "descriptions": descriptions, "rows": rows}, indent=1))
    print(f"wrote {out / 'calibration_summary.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
