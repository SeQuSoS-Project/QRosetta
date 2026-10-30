"""Old-vs-new evidence for the disconnect watcher of the runner and compiler HTTP scaffolding,
through each image's own server (in_image.py) in containers with no network:

    evidence.py <service> --old TAG --new TAG [--outputs] [--timing] [--disconnect] --work DIR
    evidence.py <service> --new TAG --disconnect --work DIR        (one image: the watcher works)

--outputs   the requalification corpus (scripts/requalify/corpus.py, smaller by default) over HTTP
            in both images, compared field by field (scripts/requalify/compare.py)
--timing    --rounds alternated rounds of --count requests per circuit, timing_repeats --repeats,
            ``--cpus 1.0 --memory 1g`` (2g for compilers), pinned with taskset and
            QROSETTA_CPU_AFFINITY to --cpu; a round whose 1-minute load average before or after
            exceeds --max-load is redone (at most three attempts); --only <circuit> limits the
            circuits; each round records how busy the CPU and its hyperthread siblings were while
            each image ran
--disconnect  a request dropped mid-run and one dropped while queued (in_image.py disconnect)

Images are made beforehand (tags localhost/qr-requal-*, label org.qrosetta.image.project=requal)
and are not removed here. Writes evidence.json in --work. Stdlib only."""

import argparse
import json
import shutil
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "requalify"))
sys.path.insert(0, str(REPO / "scripts" / "adapter_paths"))
import compare  # noqa: E402
import corpus  # noqa: E402
import engine  # noqa: E402
import registry  # noqa: E402
import time_paths  # noqa: E402
from timing import cpu_busy, siblings  # noqa: E402

TIMED = ("compilation_time_sec", "simulation_time_sec", "cpu_time_sec", "process_peak_rss_mb")


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("service")
    p.add_argument("--old")
    p.add_argument("--new", required=True)
    p.add_argument("--outputs", action="store_true")
    p.add_argument("--timing", action="store_true")
    p.add_argument("--disconnect", action="store_true")
    p.add_argument("--sv", type=int, default=40)
    p.add_argument("--measured", type=int, default=40)
    p.add_argument("--deep", type=int, default=2)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--only", action="append", default=[], help="timing circuits to run (file stem), default all")
    p.add_argument("--count", type=int, default=15)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--cpu", type=int, default=4)
    p.add_argument("--max-load", type=float, default=4.0)
    p.add_argument("--work", type=Path, required=True)
    return p.parse_args(argv)


def stage(work, name, files):
    """``work/name`` holding in_image.py and ``files`` ({relative path: JSON-able or text})."""
    in_dir = work / name
    if in_dir.exists():
        shutil.rmtree(in_dir)
    in_dir.mkdir(parents=True)
    shutil.copy2(Path(__file__).with_name("in_image.py"), in_dir / "in_image.py")
    for rel, value in files.items():
        (in_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        (in_dir / rel).write_text(value if isinstance(value, str) else json.dumps(value))
    return in_dir


def in_container(tag, mode, in_dir, out, log, memory, extra=(), env=None, prefix=()):
    code, elapsed = engine.run_in_container(
        tag, ["python", "/home/appuser/requal-in/in_image.py", mode, "/home/appuser/requal-in",
              "/home/appuser/requal-out"], in_dir, out, log, memory, extra=extra, env=env, prefix=prefix,
        timeout=8 * 3600)
    if code != 0:
        raise SystemExit(f"{mode} in {tag} exited {code}; log: {log}")
    return elapsed


def run_outputs(args, svc, work):
    cases = corpus.build(svc["kind"], svc["levels"], args.sv, args.measured, args.deep)
    if svc["kind"] == "compiler":
        cases = [dict(c, endpoint="compile") for c in cases]
    in_dir = stage(work, "outputs-in", {"corpus.jsonl": "".join(json.dumps(c) + "\n" for c in cases)})
    memory = "1g" if svc["kind"] == "runner" else "2g"

    def one(label):
        tag = getattr(args, label)
        return label, in_container(tag, "outputs", in_dir, work / f"outputs-{label}", work / f"outputs-{label}.log",
                                   memory)

    with ThreadPoolExecutor(max_workers=2) as pool:
        elapsed = dict(pool.map(one, ("old", "new")))
    summary = compare.compare_corpus(work / "outputs-old", work / "outputs-new", cases, args.service)
    return {"cases": len(cases), "elapsed_sec": elapsed, **summary}


def timing_payloads(svc, repeats, count):
    if svc["kind"] == "compiler":
        return {"compile-16q_400g.json": {"endpoint": "compile", "count": count,
                                          "payload": {"circuit_data": time_paths.deep(16, 400, 2),
                                                      "optimization_level": 1}}}
    measured = time_paths.timing_cases(True)["qft16"]
    return {
        "sv-qft16.json": {"endpoint": "run", "count": count,
                          "payload": {"circuit_data": time_paths.qft(16), "timing_repeats": repeats}},
        "sv-18q_3000g.json": {"endpoint": "run", "count": count,
                              "payload": {"circuit_data": time_paths.deep(18, 3000, 3), "timing_repeats": repeats}},
        "measured-qft16.json": {"endpoint": "run_measured", "count": count,
                                "payload": {"circuit_data": measured, "timing_repeats": repeats,
                                            "n_shots": 8200, "seed": 1}},
    }


def loadavg():
    return float(Path("/proc/loadavg").read_text().split()[0])


def run_timing(args, svc, work):
    files = {f"timing/{name}": spec for name, spec in timing_payloads(svc, args.repeats, args.count).items()
             if not args.only or name[:-len(".json")] in args.only}
    in_dir = stage(work, "timing-in", files)
    memory = "1g" if svc["kind"] == "runner" else "2g"
    cpus = "1.0" if svc["kind"] == "runner" else "2.0"
    rounds = []
    for number in range(args.rounds):
        order = ("old", "new") if number % 2 == 0 else ("new", "old")
        for attempt in range(1, 4):
            waited = 0
            while loadavg() > args.max_load and waited < 900:
                time.sleep(30)
                waited += 30
            before = loadavg()
            results, busy = {}, {}
            for label in order:
                out = work / f"timing-r{number}-{label}"
                busy_before = cpu_busy()
                in_container(getattr(args, label), "timing", in_dir, out, work / f"timing-r{number}-{label}.log",
                             memory, extra=["--cpus", cpus], env={"QROSETTA_CPU_AFFINITY": str(args.cpu)},
                             prefix=("taskset", "-c", str(args.cpu)))
                busy_after = cpu_busy()
                busy[label] = {c: round(100 * (busy_after[c][0] - busy_before[c][0])
                                        / max(1, busy_after[c][1] - busy_before[c][1]), 1)
                               for c in siblings(args.cpu)}
                results[label] = {p.stem: [json.loads(line) for line in p.read_text().splitlines()]
                                  for p in out.glob("*.jsonl")}
                shutil.rmtree(out)
            after = loadavg()
            row = {"round": number, "attempt": attempt, "order": order, "load_before": before, "load_after": after,
                   "waited_sec": waited, "cpu_busy_percent": busy, "accepted": before <= args.max_load and after <= args.max_load,
                   "results": results}
            rounds.append(row)
            print(f"timing round {number} attempt {attempt}: load {before:.2f} -> {after:.2f}"
                  f"{'' if row['accepted'] else ' (redone)'}", file=sys.stderr)
            if row["accepted"]:
                break
    return rounds


def summarise(rounds):
    """{circuit: {label: {metric: {median_of_round_medians, round_medians}}, errors, outputs}}."""
    cells = {}
    for row in rounds:
        if not row["accepted"]:
            continue
        for label, circuits in row["results"].items():
            for name, requests in circuits.items():
                cell = cells.setdefault(name, {}).setdefault(label, {"rounds": [], "errors": 0, "outputs": set()})
                values = {}
                for req in requests:
                    result = req["result"]
                    if not isinstance(result, dict) or result.get("error"):
                        cell["errors"] += 1
                        continue
                    for key in (*TIMED, "wall_sec", "worker_cpu_sec"):
                        value = req.get(key) if key in ("wall_sec", "worker_cpu_sec") else result.get(key)
                        if value is not None:
                            values.setdefault(key, []).append(value)
                    out = result.get("statevector") or result.get("counts") or result.get("transpiled_qasm")
                    cell["outputs"].add(json.dumps(out, sort_keys=True))
                cell["rounds"].append({k: statistics.median(v) for k, v in values.items()})
    summary = {}
    for name, labels in cells.items():
        for label, cell in labels.items():
            metrics = {}
            for key in {k for r in cell["rounds"] for k in r}:
                per_round = [r[key] for r in cell["rounds"] if key in r]
                metrics[key] = {"median_of_round_medians": statistics.median(per_round), "round_medians": per_round}
            summary.setdefault(name, {})[label] = {"metrics": metrics, "errors": cell["errors"],
                                                   "distinct_outputs": len(cell["outputs"])}
        if len(labels) == 2:
            outs = [labels[label]["outputs"] for label in ("old", "new")]
            summary[name]["same_outputs"] = outs[0] == outs[1]
    return summary


def disconnect_spec(svc):
    if svc["kind"] == "compiler":
        slow = {"circuit_data": time_paths.deep(16, 3000, 5), "optimization_level": 2,
                "hard_timeout_seconds": 300, "max_queue_wait_seconds": 300}
        medium = {"circuit_data": time_paths.deep(10, 600, 6), "optimization_level": 2,
                  "hard_timeout_seconds": 300, "max_queue_wait_seconds": 300}
        fast = {"circuit_data": time_paths.qft(3), "optimization_level": 1,
                "hard_timeout_seconds": 300, "max_queue_wait_seconds": 300}
        return {"slow": {"endpoint": "compile", "payload": slow}, "medium": {"endpoint": "compile", "payload": medium},
                "fast": {"endpoint": "compile", "payload": fast}, "drop_after_sec": 2.0}
    slow = {"circuit_data": time_paths.deep(18, 3000, 3), "timing_repeats": 10,
            "hard_timeout_seconds": 300, "max_queue_wait_seconds": 300}
    medium = {"circuit_data": time_paths.qft(16), "timing_repeats": 10,
              "hard_timeout_seconds": 300, "max_queue_wait_seconds": 300}
    fast = {"circuit_data": time_paths.qft(3), "hard_timeout_seconds": 300, "max_queue_wait_seconds": 300}
    return {"slow": {"endpoint": "run", "payload": slow}, "medium": {"endpoint": "run", "payload": medium},
            "fast": {"endpoint": "run", "payload": fast}, "drop_after_sec": 4.0}


def run_disconnect(args, svc, work):
    in_dir = stage(work, "disconnect-in", {"disconnect.json": disconnect_spec(svc)})
    memory = "1g" if svc["kind"] == "runner" else "2g"
    out = {}
    for label in ("old", "new"):
        tag = getattr(args, label)
        if not tag:
            continue
        target = work / f"disconnect-{label}"
        in_container(tag, "disconnect", in_dir, target, work / f"disconnect-{label}.log", memory)
        out[label] = json.loads((target / "disconnect.json").read_text())
    return out


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    svc = registry.services()[args.service]
    args.work.mkdir(parents=True, exist_ok=True)
    evidence = {"service": args.service, "old": args.old, "new": args.new,
                "images": {label: engine.image_id(tag) for label, tag in (("old", args.old), ("new", args.new)) if tag},
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    if args.disconnect:
        evidence["disconnect"] = run_disconnect(args, svc, args.work)
    if args.outputs:
        evidence["outputs"] = run_outputs(args, svc, args.work)
    if args.timing:
        rounds = run_timing(args, svc, args.work)
        (args.work / "timing-raw.json").write_text(json.dumps(rounds))
        evidence["timing_rounds"] = [{k: v for k, v in r.items() if k != "results"} for r in rounds]
        evidence["timing"] = summarise(rounds)
    evidence["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (args.work / "evidence.json").write_text(json.dumps(evidence, indent=1, default=str))
    print(json.dumps({k: v for k, v in evidence.items() if k not in ("timing_rounds",)}, indent=1, default=str)[:20000])


if __name__ == "__main__":
    main()
