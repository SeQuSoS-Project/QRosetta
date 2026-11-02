"""V8 Monte Carlo of the measured-mode verdicts: false flags, FWER/FDR and power of the server's own
analysis (create_counts_report + the verdicts the aggregator records) on seeded synthetic runs.

    PYTHONPATH=rosetta-api:shared python scripts/verify/false_flags.py --out DIR [--runs N]
        [--only NAME,...] [--workers W]

Every scenario has 14 backends (b00..b13) sampled independently; b13 is the wrong backend where a
scenario has one. Run r of scenario s uses numpy generators seeded (MASTER_SEED, s, r, backend), so
results do not depend on the worker count. Writes DIR/false_flags.json (per-run tallies summarised
per scenario) and DIR/false_flags.csv. Workers are pinned to CPUs 0-15 and 20-31 at nice 10."""

import argparse
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import v8_common as c

import numpy as np

MASTER_SEED = 20261102
N_BACKENDS = 14
SHOTS = 8200
WRONG = "b13"
STATED_SHOTS = {2: 4444, 4: 5435, 8: 6619, 16: 8199}


def _backends(truth, wrong_p=None, shots=SHOTS, wrong_shots=None, msb=()):
    out = []
    for b in range(N_BACKENDS):
        name = f"b{b:02d}"
        is_wrong = name == WRONG
        p = wrong_p if (is_wrong and wrong_p is not None) else truth
        n = wrong_shots if (is_wrong and wrong_shots is not None) else shots
        out.append({"name": name, "p": p, "shots": n, "ordering": "msb" if b in msb else "lsb"})
    return out


def scenarios():
    """name -> {group, description, backends, wrong (set of names), runs_factor}."""
    s = {}

    def add(name, group, description, backends, wrong=(), factor=1.0):
        s[name] = {"group": group, "description": description, "backends": backends,
                   "wrong": set(wrong), "runs_factor": factor}

    for k in (2, 4, 8, 16):
        add(f"A-null-uniform-{k}", "A", f"all 14 correct, uniform over {k} outcomes, 8200 shots",
            _backends(c.uniform(k)), factor=2)
    add("A-null-peaked-16", "A", "all 14 correct, geometric (ratio 0.6) over 16 outcomes",
        _backends(c.peaked(16)))
    add("A-null-mixed-order-16", "A", "all 14 correct, peaked 16 outcomes, b07-b13 declare msb "
        "(lsb x msb pairs tested after bit reversal)", _backends(c.peaked(16), msb=range(7, 14)))
    for k in (2, 4, 8, 16):
        u = c.uniform(k)
        add(f"B-shift05-{k}", "B", f"b13 moves 0.05 from outcome 0 to 1 (TV 0.05), uniform {k}, "
            "8200 shots", _backends(u, c.shift(u, 0.05, 0, 1)), {WRONG})
        add(f"B-leastfav05-{k}-stated", "B", f"b13 least-favourable TV 0.05 (w = TV), uniform {k}, "
            f"{STATED_SHOTS[k]} shots (the stated recommendation)",
            _backends(u, c.least_favourable(u, 0.05), shots=STATED_SHOTS[k]), {WRONG})
        add(f"B-gross40-{k}", "B", f"b13 least-favourable TV 0.40, uniform {k}, 8200 shots",
            _backends(u, c.least_favourable(u, 0.40)), {WRONG}, factor=2)
    for small in (50, 400):
        add(f"C-null-{small}", "C", f"all correct, uniform 4, b13 has {small} shots, others 8200",
            _backends(c.uniform(4), wrong_shots=small))
        p2 = np.array([0.5, 0.5])
        add(f"C-wrong05-{small}", "C", f"(0.5, 0.5) vs b13 (0.45, 0.55) with {small} shots "
            "(TV 0.05)", _backends(p2, np.array([0.45, 0.55]), wrong_shots=small), {WRONG})
    for eps in (2e-4, 1e-3, 5e-3):
        add(f"D-null-eps{eps:g}", "D", f"all correct, P(00) = 1 - {eps:g}, P(11) = {eps:g}",
            _backends(c.near_deterministic(eps)))
    truth = c.near_deterministic(1e-3)
    add("D-defect05", "D", "P(11) = 0.001; b13 moves 0.05 from 00 to 01 (TV 0.05)",
        _backends(truth, c.shift(truth, 0.05, 0, 1)), {WRONG})
    flipped = np.array([truth[1], truth[0], truth[3], truth[2]])
    add("D-defect-bitflip", "D", "P(11) = 0.001; b13 flips clbit 0 (00 -> 01, 11 -> 10)",
        _backends(truth, flipped), {WRONG})
    two_rare = np.array([0.4998, 0.4998, 0.0002, 0.0002])
    add("E-null-two-rare", "E", "P = (0.4998, 0.4998, 0.0002, 0.0002): the two rare outcomes are "
        "pooled into their own bin, which stays a column", _backends(two_rare))
    add("E-wrong05-two-rare", "E", "as E-null-two-rare; b13 moves 0.05 from outcome 0 to 1",
        _backends(two_rare, c.shift(two_rare, 0.05, 0, 1)), {WRONG})
    pool, common = c.common_and_rare(8, 4, 0.03)
    add("E-null-pooled", "E", "8-bit keys, 4 common outcomes (0.97) and 252 rare (0.03 total): "
        "rare outcomes pooled into one bin", _backends(pool))
    untested, _ = c.common_and_rare(8, 4, 6e-5)
    add("E-null-untested", "E", "8-bit keys, 4 common outcomes and 252 rare sharing 6e-5: the "
        "pooled bin is left out (untested_outcomes)", _backends(untested))
    add("E-wrong05-pooled", "E", "as E-null-pooled; b13 moves 0.05 between two common outcomes",
        _backends(pool, c.shift(pool, 0.05, common[0], common[1])), {WRONG})
    half = [0.5] * 16
    add("F-marginal-null", "F", "16 independent bits, P(1) = 0.5 each, all correct",
        _backends(c.independent_bits(half)))
    shifted = [0.55] * 4 + [0.5] * 12
    add("F-marginal-wrong", "F", "16 independent bits; b13 has P(1) = 0.55 on clbits 0-3",
        _backends(c.independent_bits(half), c.independent_bits(shifted)), {WRONG})
    return s


SCENARIOS = scenarios()
NAMES = list(SCENARIOS)


def one_run(name, run):
    spec = SCENARIOS[name]
    s_index = NAMES.index(name)
    results = []
    for b_index, b in enumerate(spec["backends"]):
        rng = np.random.default_rng([MASTER_SEED, s_index, run, b_index])
        counts = c.sample_counts(rng, b["p"], b["shots"], b["ordering"])
        results.append(c.runner_result(b["name"], counts, b["ordering"],
                                       seed=MASTER_SEED * 100 + b_index))
    report = c.analyse(results, SHOTS)
    return c.run_record(report, spec["wrong"])


def _chunk(args):
    name, runs = args
    return name, [one_run(name, r) for r in runs]


def summarise(name, records):
    spec = SCENARIOS[name]
    n = len(records)
    out = {"scenario": name, "group": spec["group"], "description": spec["description"],
           "runs": n, "wrong_backends": sorted(spec["wrong"])}
    for kind in c.FLAG_KINDS:
        out[f"any_false_flag_{kind}"] = c.proportion(sum(r[f"ff_{kind}"] > 0 for r in records), n)
        out[f"pair_false_flag_{kind}"] = c.clustered_rate(
            [r[f"ff_{kind}"] for r in records], [r["correct_pairs"] for r in records])
        if spec["wrong"]:
            out[f"pair_power_{kind}"] = c.clustered_rate(
                [r[f"tp_{kind}"] for r in records], [r["wrong_pairs"] for r in records])
            out[f"fdr_{kind}"] = c.mean_with_se(
                [r[f"ff_{kind}"] / max(r[f"ff_{kind}"] + r[f"tp_{kind}"], 1) for r in records])
    for side in ("correct", "wrong"):
        total = sum(r[f"{side}_pairs"] for r in records)
        if total:
            out[f"{side}_assessments"] = {a: sum(r.get(f"{side}_{a}", 0) for r in records) / total
                                          for a in c.ASSESSMENTS}
    methods = {}
    for r in records:
        for m, k in r["methods"].items():
            methods[str(m)] = methods.get(str(m), 0) + k
    out["test_methods"] = methods
    return out


def recommended_shots():
    """The platform's minimum and recommended shots per backend for 14 backends (m = 91) at
    TV 0.05, power 0.8, df = k - 1, against the stated 4444/5435/6619/8199."""
    from services.analysis.divergence.statistics import (
        _by_constant, _shots_per_backend_for_target_power, _with_margin)
    m = 91
    alpha = 0.05 / (m * _by_constant(m))
    rows = {}
    for k in (2, 4, 8, 16):
        minimum = _shots_per_backend_for_target_power(alpha, 0.8, 0.05, k - 1)
        rows[k] = {"minimum": minimum, "recommended": _with_margin(minimum),
                   "stated": STATED_SHOTS[k]}
    return rows


def unequal_shots_single_pair(runs):
    """Raw (single-test, alpha 0.05) chi-square rejection rate of (0.5, 0.5) vs (0.45, 0.55) through
    _statistical_agreement_test, against the power model and the stated 0.111/0.494/0.386."""
    from services.analysis.divergence.statistics import _power_at_shots, effective_total_shots
    from services.analysis.divergence.statistics import _statistical_agreement_test
    stated = {(8200, 50): (0.111, 0.109), (8200, 400): (0.494, 0.497), (300, 5000): (0.386, 0.391)}
    out = {}
    for (n_i, n_j), (mc_stated, model_stated) in stated.items():
        rejected = 0
        for r in range(runs):
            rng = np.random.default_rng([MASTER_SEED, 999, n_i, n_j, r])
            ci = c.sample_counts(rng, np.array([0.5, 0.5]), n_i)
            cj = c.sample_counts(rng, np.array([0.45, 0.55]), n_j)
            block = _statistical_agreement_test(ci, cj, "direct", "a", "b")
            rejected += block["chi2"]["p_value"] < 0.05
        out[f"{n_i}v{n_j}"] = {"rejection": c.proportion(rejected, runs),
                               "model": _power_at_shots(0.05, 0.05, 1,
                                                        effective_total_shots(n_i, n_j)),
                               "stated_monte_carlo": mc_stated, "stated_model": model_stated}
    return out


def _fmt(x):
    return "" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.6g}"


def write_csv(path, summaries):
    cols = ["scenario", "runs"]
    metrics = []
    for kind in c.FLAG_KINDS:
        metrics += [f"any_false_flag_{kind}", f"pair_false_flag_{kind}", f"pair_power_{kind}",
                    f"fdr_{kind}"]
    header = cols + [f"{m}_{f}" for m in metrics for f in ("estimate", "mcse", "lo", "hi")]
    lines = [",".join(header)]
    for s in summaries:
        row = [s["scenario"], str(s["runs"])]
        for m in metrics:
            v = s.get(m) or {}
            row += [_fmt(v.get(f)) for f in ("estimate", "mcse", "lo", "hi")]
        lines.append(",".join(row))
    Path(path).write_text("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", type=int, default=2000, help="runs per scenario (x runs_factor)")
    ap.add_argument("--only", default="", help="comma-separated scenario names")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=20)
    args = ap.parse_args(argv)
    cpus = c.set_up_process()
    workers = args.workers or len(cpus)
    names = [n for n in NAMES if not args.only or n in args.only.split(",")]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for name in names:
        total = int(round(args.runs * SCENARIOS[name]["runs_factor"]))
        tasks += [(name, list(range(i, min(i + args.chunk, total))))
                  for i in range(0, total, args.chunk)]
    tasks.sort(key=lambda t: (not t[0].startswith("F-"), t[0], t[1][0]))
    records = {n: [] for n in names}
    start = time.time()
    with Pool(workers) as pool:
        for done, (name, recs) in enumerate(pool.imap_unordered(_chunk, tasks), 1):
            records[name].extend(recs)
            if done % 50 == 0 or done == len(tasks):
                print(f"{done}/{len(tasks)} chunks, {time.time() - start:.0f} s", flush=True)
    summaries = [summarise(n, records[n]) for n in names]
    result = {"master_seed": MASTER_SEED, "cpus": cpus, "workers": workers,
              "wall_seconds": time.time() - start, "scenarios": summaries,
              "recommended_shots": recommended_shots(),
              "unequal_shots_single_pair": unequal_shots_single_pair(max(args.runs, 2000) * 2)}
    (out_dir / "false_flags.json").write_text(json.dumps(result, indent=1, default=float))
    write_csv(out_dir / "false_flags.csv", summaries)
    print(f"wrote {out_dir / 'false_flags.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
