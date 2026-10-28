"""Timing phase of the requalification harness: the three circuits of
scripts/adapter_paths/time_paths.py through ``main.py --endpoint`` in a process each, in containers
with no network, ``--cpus 1.0 --memory 1g``, pinned with taskset and QROSETTA_CPU_AFFINITY to one
CPU; image order alternated per round; a round whose 1-minute load average before or after
exceeds ``--max-load`` is redone (at most three attempts). Stdlib only."""

import json
import re
import shutil
import statistics
import sys
import time
from pathlib import Path

import corpus
import engine


def loadavg():
    return float(Path("/proc/loadavg").read_text().split()[0])


def cpu_busy():
    stats = {}
    for line in Path("/proc/stat").read_text().splitlines():
        m = re.match(r"cpu(\d+) (.*)", line)
        if m:
            values = [int(x) for x in m.group(2).split()]
            stats[int(m.group(1))] = (sum(values) - values[3] - values[4], sum(values))
    return stats


def siblings(cpu):
    text = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list").read_text().strip()
    out = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def run(images, args, work):
    in_dir = work / "timing-in"
    if in_dir.exists():
        shutil.rmtree(in_dir)
    (in_dir / "timing").mkdir(parents=True)
    shutil.copy2(Path(__file__).with_name("driver.py"), in_dir / "driver.py")
    for name, spec in corpus.timing_payloads(args.repeats).items():
        (in_dir / "timing" / name).write_text(json.dumps(spec))
    cpus = siblings(args.cpu)
    devices = engine.device_args(getattr(args, "device", []))
    rounds = []
    for number in range(args.rounds):
        order = ("old", "new") if number % 2 == 0 else ("new", "old")
        for attempt in range(1, 4):
            waited = 0
            while loadavg() > args.max_load and waited < 900:
                time.sleep(30)
                waited += 30
            before, busy_before = loadavg(), cpu_busy()
            results = {}
            for label in order:
                out = work / f"timing-r{number}-{label}"
                engine.run_in_container(
                    images[label]["tag"], ["python", "/home/appuser/requal-in/driver.py", "timing", "runner",
                                           "/home/appuser/requal-in", "/home/appuser/requal-out"],
                    in_dir, out, work / f"timing-r{number}-{label}.log", "1g", extra=["--cpus", "1.0", *devices],
                    env={"QROSETTA_CPU_AFFINITY": str(args.cpu)}, prefix=("taskset", "-c", str(args.cpu)),
                    timeout=3600)
                results[label] = {p.name: json.loads(p.read_text()) for p in out.glob("*.json")}
                shutil.rmtree(out)
            after, busy_after = loadavg(), cpu_busy()
            busy = {c: round(100 * (busy_after[c][0] - busy_before[c][0])
                             / max(1, busy_after[c][1] - busy_before[c][1]), 1) for c in cpus}
            row = {"round": number, "attempt": attempt, "order": order, "load_before": before,
                   "load_after": after, "cpu_busy_percent": busy, "waited_sec": waited,
                   "accepted": before <= args.max_load and after <= args.max_load, "results": results}
            rounds.append(row)
            print(f"timing round {number} attempt {attempt}: load {before:.2f} -> {after:.2f}"
                  f"{'' if row['accepted'] else ' (redone)'}", file=sys.stderr)
            if row["accepted"]:
                break
    return rounds


def summarise(rounds):
    """{case: {label: {compilation_ms, simulation_ms, total_ms, peak_rss_mib, samples, cpus}}}."""
    cells = {}
    for row in rounds:
        if not row["accepted"]:
            continue
        for label, results in row["results"].items():
            for name, result in results.items():
                cell = cells.setdefault(name, {}).setdefault(label, {"comp": [], "sim": [], "rss": [],
                                                                     "cpus": set(), "errors": 0,
                                                                     "outputs": set(), "throttled": 0.0})
                if result.get("error") or result.get("harness_error"):
                    cell["errors"] += 1
                    continue
                cell["comp"] += result.get("compilation_time_samples") or []
                cell["sim"] += result.get("simulation_time_samples") or []
                cell["rss"].append(result.get("process_peak_rss_mb"))
                cell["cpus"].update(result.get("simulation_cpus") or [])
                cell["throttled"] += sum(x or 0 for x in result.get("simulation_throttled_samples") or [])
                out = result.get("statevector") or result.get("counts")
                cell["outputs"].add(json.dumps(out, sort_keys=True))
    summary = {}
    for name, labels in cells.items():
        for label, c in labels.items():
            comp = statistics.median(c["comp"]) * 1000 if c["comp"] else None
            sim = statistics.median(c["sim"]) * 1000 if c["sim"] else None
            totals = [a + b for a, b in zip(c["comp"], c["sim"], strict=True)]
            summary.setdefault(name, {})[label] = {
                "compilation_ms": comp, "simulation_ms": sim,
                "total_ms": statistics.median(totals) * 1000 if totals else None,
                "peak_rss_mib": statistics.median([x for x in c["rss"] if x is not None]) if c["rss"] else None,
                "samples": len(c["sim"]), "cpus": sorted(c["cpus"]), "errors": c["errors"],
                "distinct_outputs": len(c["outputs"]), "output_digest": sorted(c["outputs"])[:1],
                "throttled_sec": c["throttled"],
            }
    return summary
