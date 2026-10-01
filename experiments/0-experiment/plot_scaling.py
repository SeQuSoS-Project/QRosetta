#!/usr/bin/env python3
"""Regenerate scaling figures and an agreement summary from an experiment bundle alone.

Reads performance.csv and agreement_prevalence.csv from a bundle directory or ZIP (as
written by POST /experiments or run_experiment.py) and writes, per circuit family and axis,
the median simulation time against declared qubits for every backend, with the min-max range
of its timed runs as error bars. Needs matplotlib.

    python plot_scaling.py experiment_bundle.zip --out figures
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import zipfile
from collections import defaultdict


def _read(bundle: str, name: str) -> str:
    if os.path.isdir(bundle):
        with open(os.path.join(bundle, name), encoding="utf-8") as fh:
            return fh.read()
    with zipfile.ZipFile(bundle) as zf:
        member = next(m for m in zf.namelist() if m == name or m.endswith("/" + name))
        return zf.read(member).decode("utf-8")


def _family(circuit: str) -> str:
    return re.sub(r"\s*\(\d+q\)\s*$", "", circuit).strip() or circuit


def _float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def load_rows(bundle: str) -> list:
    return list(csv.DictReader(io.StringIO(_read(bundle, "performance.csv"))))


def series(rows: list) -> dict:
    """{(axis, family): {simulator: [(qubits, median, min, max), ...]}} for successful runs."""
    out = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r.get("status") != "success":
            continue
        q, med = _float(r.get("declared_qubits")), _float(r.get("simulation_time_sec"))
        if q is None or med is None:
            continue
        lo = _float(r.get("simulation_time_sec_min")) or med
        hi = _float(r.get("simulation_time_sec_max")) or med
        out[(r["axis"], _family(r["circuit"]))][r["simulator"]].append((int(q), med, lo, hi))
    return out


def plot(data: dict, out_dir: str, fmt: str) -> list:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(out_dir, exist_ok=True)
    written = []
    for (axis, family), by_sim in sorted(data.items()):
        fig, ax = plt.subplots(figsize=(7, 4.5))
        colours = plt.get_cmap("tab20").colors
        markers = "osD^v<>PXh*"
        for k, (sim, points) in enumerate(sorted(by_sim.items())):
            points.sort()
            qs = [p[0] for p in points]
            med = [p[1] for p in points]
            err = [[p[1] - p[2] for p in points], [p[3] - p[1] for p in points]]
            ax.errorbar(qs, med, yerr=err, marker=markers[k % len(markers)], markersize=4,
                        capsize=2, color=colours[k % len(colours)], label=sim)
        ax.set_yscale("log")
        ax.set_xlabel("declared qubits")
        ax.set_ylabel("simulation time (s), median; bars: min-max of timed runs")
        ax.set_title(f"{family} - {axis}")
        ax.legend(fontsize=6, ncol=2)
        fig.tight_layout()
        path = os.path.join(out_dir, f"scaling_{re.sub(r'[^A-Za-z0-9]+', '-', family)}_{axis}.{fmt}")
        fig.savefig(path)
        plt.close(fig)
        written.append(path)
    return written


def agreement_summary(bundle: str) -> str:
    rows = csv.DictReader(io.StringIO(_read(bundle, "agreement_prevalence.csv")))
    lines = [f"{r['axis']:24s} {r['agreement_class']:34s} {r['pair_count']:>6s}  ({r['pair_scope']})"
             for r in rows]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle", help="experiment bundle directory or ZIP")
    ap.add_argument("--out", default="figures", help="output directory")
    ap.add_argument("--format", default="png", choices=["png", "pdf", "svg"])
    args = ap.parse_args()
    rows = load_rows(args.bundle)
    conditions = sorted({(r.get("exclusive"), r.get("cpu_model"), r.get("cpu_quota_cores"))
                         for r in rows if r.get("status") == "success"})
    for path in plot(series(rows), args.out, args.format):
        print(path)
    print("\nRun conditions (exclusive, CPU model, CPU quota):")
    for c in conditions:
        print("  ", c)
    print("\nAgreement classes per axis:")
    print(agreement_summary(args.bundle))
    return 0


if __name__ == "__main__":
    sys.exit(main())
