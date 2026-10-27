"""The page's timing tags and "Before comparing times" phrases as computed by the JavaScript
of a reference commit (default 7e02220, before the rules moved to the server) against
services.timing_caveats, on saved reports and on a synthetic corpus around the thresholds.

    python compare.py <dir with saved report JSON> [<dir> ...] [--rev 7e02220] [--synthetic 20000]

Exits non-zero on any difference. Needs node and the API's Python environment."""
import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO / "rosetta-api"), str(REPO / "shared")]
from services.timing_caveats import result_caveats, summarize  # noqa: E402

PHRASES = [("overlapping_runs", "backends ran at the same time"),
           ("server_overlapping_runs", "other jobs ran on the server"),
           ("throttled", "some runs were throttled by the CPU quota"),
           ("unstable_repeats", "some timed runs were unstable"),
           ("cross_backend_core_speeds", "runs used CPUs of different speeds"),
           ("outside_process", "some work ran outside the measured process"),
           ("single_timed_run", "one timed run per backend (n=1)")]
TAGS = {"throttled": "throttled", "outside": "outside_process", "mixed": "mixed_cores",
        "unstable": "unstable_repeats"}
HELPER_RULES = ("THROTTLE_SHOWN_SHARE", "OUTSIDE_PROCESS_SHOWN_SEC", "UNSTABLE_SPREAD")
HELPER_FUNCTIONS = ("throttleText", "outsideProcessText", "simulationCoreSpeeds", "coreClasses",
                    "mixedCoresText", "unstableText")


def _git_show(rev, path):
    return subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{path}"], capture_output=True,
                          text=True, check=True).stdout


def _grab(src, name, const=False):
    if const:
        return re.search(rf"^(?:export )?const {name} = [^\n]*\n", src, re.M).group(0).replace("export ", "")
    start = re.search(rf"^(?:export )?function {name}\(", src, re.M).start()
    depth, i = 0, src.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        if depth == 0:
            break
        i += 1
    return src[start:i + 1].replace("export function", "function") + "\n"


def write_old_rules(rev, out_dir):
    """old_rules.mjs: the tag rules of ``rev`` with formatting stubbed."""
    helpers = _git_show(rev, "rosetta-api/static/js/render_helpers.js")
    ranking = _git_show(rev, "rosetta-api/static/js/ranking_renderer.js")
    parts = ["function fmtNum(v, d = 4) { return String(v); }\n", "function fmtInt(v) { return String(v); }\n"]
    parts += [_grab(helpers, c, const=True) for c in HELPER_RULES]
    parts += [_grab(helpers, f) for f in HELPER_FUNCTIONS]
    parts += [_grab(ranking, "_timingCount"), _grab(ranking, "_timingCaveats")]
    parts.append("export { throttleText, outsideProcessText, mixedCoresText, unstableText, _timingCaveats };\n")
    (out_dir / "old_rules.mjs").write_text("".join(parts))
    (out_dir / "run_old.mjs").write_text((HERE / "run_old.mjs").read_text())


def _collect(node, out):
    if isinstance(node, dict):
        raws = node.get("raw_results")
        if isinstance(raws, list) and raws:
            out.append([r for r in raws if isinstance(r, dict)])
        for v in node.values():
            if isinstance(v, (dict, list)):
                _collect(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect(v, out)


def saved_corpus(dirs):
    reports, files = [], 0
    for d in dirs:
        for path in sorted(Path(d).rglob("*.json")):
            try:
                text = path.read_text()
                data = json.loads(text) if "raw_results" in text else None
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            before = len(reports)
            _collect(data, reports)
            files += len(reports) > before
    return reports, files


def synthetic(n_reports, seed=7):
    rng = random.Random(seed)
    pick = rng.choice
    reports = []
    for _ in range(n_reports):
        raws, exclusive = [], pick([True, False, None])
        for i in range(rng.randint(1, 5)):
            sim = pick([None, 0.0, 1e-4, 0.01, 0.1, 1.0, rng.uniform(0, 2)])
            r = {"simulator": f"b{i}", "simulation_time_sec": sim}
            if rng.random() < 0.1:
                r["error"] = "boom"
            r["simulation_throttled_sec"] = pick([None, 0, 0.0, -0.001, (sim or 0) * 0.01, (sim or 0) * 0.0099,
                                                  (sim or 0) * 0.0101, rng.uniform(0, 0.05)])
            own = pick([None, 0.0, rng.uniform(0, 1)])
            base = own or 0.0
            r["simulation_cpu_time_sec"] = own
            r["simulation_cgroup_cpu_time_sec"] = pick([None, base, base + 0.005, base + 0.0049,
                                                        base * 1.1 + 0.006, base * 1.12 + 0.006,
                                                        base + rng.uniform(0, 0.2)])
            k, lo = rng.randint(0, 5), pick([0.0, 0.01, rng.uniform(0.001, 1)])
            r["simulation_time_samples"] = pick([None, [lo * pick([1, 1.3, 1.31, 1.2999, 2]) for _ in range(k)],
                                                 [lo] + [lo * 1.3] * k])
            mhz = {str(c): pick([4000.0, 4400.0, 4401.0, 5300.0, None]) for c in range(4)}
            r["cpu_environment"] = pick([None, {"cpu_max_mhz": mhz, "cpu_quota_cores": 1.0}, {"cpu_max_mhz": mhz}])
            r["simulation_cpus"] = pick([None, [], [0], [0, 1], [1, 2, 3], [0, 3]])
            r["timing_samples"] = pick([None, 0, 1, 3, 1.0])
            r["timing_repeats"] = pick([None, 1, 2, 5])
            r["overlapping_runs"] = pick([None, 0, 1, 3])
            r["server_overlapping_runs"] = pick([None, 0, 2])
            r["exclusive"] = exclusive if rng.random() < 0.9 else pick([True, False])
            raws.append(r)
        reports.append(raws)
    return reports


def compare(reports, label, rules_dir):
    out = subprocess.run(["node", str(rules_dir / "run_old.mjs")], input=json.dumps({"reports": reports}),
                         capture_output=True, text=True, check=True)
    diffs, n_results = [], 0
    for idx, (raws, old) in enumerate(zip(reports, json.loads(out.stdout))):
        for r, tags in zip(raws, old["tags"]):
            n_results += 1
            codes = {c["code"] for c in result_caveats(r)}
            diffs += [(label, idx, r.get("simulator"), tag, tags[tag]) for tag, code in TAGS.items()
                      if tags[tag] != (code in codes)]
        codes = {c["code"] for c in summarize((str(r.get("simulator")), r) for r in raws)}
        phrases = [p for code, p in PHRASES if code in codes]
        if phrases != old["phrases"]:
            diffs.append((label, idx, "report", old["phrases"], phrases))
    print(f"{label}: {len(reports)} reports, {n_results} results, {len(diffs)} differences")
    for d in diffs[:20]:
        print("  ", d)
    return len(diffs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dirs", nargs="*")
    parser.add_argument("--rev", default="7e02220")
    parser.add_argument("--synthetic", type=int, default=20000)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        rules_dir = Path(tmp)
        write_old_rules(args.rev, rules_dir)
        saved, files = saved_corpus(args.dirs)
        print(f"saved corpus: {files} files")
        total = compare(saved, "saved", rules_dir) + compare(synthetic(args.synthetic), "synthetic", rules_dir)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
