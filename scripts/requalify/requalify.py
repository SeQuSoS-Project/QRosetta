"""Requalify a runner or compiler image on a new Python base: build the image as it is (old) and
with the candidate Dockerfile and lock (new), run one fixed-seed corpus in both side by side with
no network, compare every output field, time both on three circuits pinned to one CPU, optionally
scan both with Trivy, write the evidence file, and remove the images it built or pulled.

    requalify.py <service> <python-base@sha256:...>   prepare the candidate, then requalify
    requalify.py <service> --candidate DIR            requalify an existing candidate directory
    requalify.py <service> <base> --prepare-only      write the candidate and the wheel check only

<service> is a canonical runner or compiler id from rosetta-api/config.py (qulacs,
cirq-transformers, ...). Exit status: 0 outputs identical, 1 output differences, 3 an SDK package
has no build for the new Python (nothing built). Stdlib only."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import candidate as cand
import compare
import corpus
import engine
import registry
import report
import timing
from registry import REPO

HOME_TMP = Path.home() / ".tmp"


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("service")
    p.add_argument("new_base", nargs="?", help="python:3.N-slim@sha256:... for the candidate")
    p.add_argument("--candidate", type=Path, help="directory with Dockerfile, requirements.txt, requirements.lock")
    p.add_argument("--prepare-only", action="store_true")
    p.add_argument("--relax", action="append", default=[], help="drop this pin from the lock constraints")
    p.add_argument("--sv", type=int, default=150, help="random statevector circuits (runners) or circuits (compilers)")
    p.add_argument("--measured", type=int, default=150, help="random measured circuits (runners)")
    p.add_argument("--deep", type=int, default=4, help="deep circuits (500-3000 gates) per mode")
    p.add_argument("--max-gates", type=int, help="MAX_GATES of the random circuits (default 40)")
    p.add_argument("--single-register", action="store_true", help="one quantum register per random circuit")
    p.add_argument("--rounds", type=int, default=5, help="alternated timing rounds")
    p.add_argument("--repeats", type=int, default=5, help="timing_repeats per timed process")
    p.add_argument("--cpu", type=int, default=4, help="CPU every timed process is pinned to")
    p.add_argument("--max-load", type=float, default=4.0, help="1-minute load average above which a round is redone")
    p.add_argument("--skip-corpus", action="store_true")
    p.add_argument("--skip-timing", action="store_true")
    p.add_argument("--scan", action="store_true", help="Trivy scan of both images")
    p.add_argument("--device", action="append", default=[],
                   help="pass this device to every container (nvidia.com/gpu=all for a GPU runner)")
    p.add_argument("--keep-images", action="store_true", help="keep the images for another run")
    p.add_argument("--work", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args(argv)
    if bool(args.new_base) == bool(args.candidate):
        p.error("give exactly one of <new-base> and --candidate")
    return args


def git_sha():
    sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], check=True,
                         capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"], check=True,
                           capture_output=True, text=True).stdout.strip()
    return sha + ("-dirty" if dirty else "")


def base_facts(base):
    """Python version and glibc of a base image (pulled if missing)."""
    out = engine.run(["run", "--rm", "--network", "none", base, "python", "-c",
                      "import platform,sys;print(sys.version_info[0],sys.version_info[1],platform.libc_ver()[1])"])
    major, minor, libc = out.stdout.split()
    return (int(major), int(minor)), tuple(int(x) for x in libc.split("."))


def prepare(svc, service_id, new_base, cand_dir, relax, work, state):
    """Write the candidate into ``cand_dir``; return its prepare record (``stop`` set when an SDK
    package has no build for the new Python)."""
    if "@sha256:" not in new_base:
        raise SystemExit("the new base must be pinned by digest")
    service_dir = REPO / svc["dir"]
    dockerfile = (service_dir / "Dockerfile").read_text()
    old_bases = cand.python_bases(dockerfile)
    old_python = cand.python_of_tag(old_bases[-1]) if old_bases else None
    track_pull(new_base, state)
    new_python, glibc = base_facts(new_base)
    sdk = {cand.normalise(n) for n in registry.sdk_packages((service_dir / "main.py").read_text())}
    lock_text = (service_dir / "requirements.lock").read_text()
    pins = cand.parse_lock(lock_text)
    pypi = cand.PyPI(work / "pypi-cache", cand.extra_indexes(lock_text))
    rows = cand.wheel_check(pins, old_python, new_python, sdk, pypi, glibc)
    record = {"service": service_id, "old_bases": old_bases, "new_base": new_base, "old_python": old_python,
              "new_python": new_python, "glibc": glibc, "sdk_packages": sorted(sdk), "wheel_check": rows,
              "stop": [], "replaced": {}, "relaxed": list(relax), "manual": []}
    for row in rows:
        if row["old_wheel"] and not row["new_wheel"]:
            if row["sdk"]:
                record["stop"].append(f"{row['name']}=={row['version']} (SDK) has no build for Python "
                                      f"{new_python[0]}.{new_python[1]}")
            elif row["nearest"]:
                record["replaced"][row["name"]] = row["nearest"]
            else:
                record["stop"].append(f"{row['name']}=={row['version']} has no build for Python "
                                      f"{new_python[0]}.{new_python[1]} and no later release has one")
    if record["stop"]:
        return record
    if cand_dir.exists():
        shutil.rmtree(cand_dir)
    cand.write_constraints(cand_dir, service_dir, record["replaced"], relax)
    new_dockerfile, changes, manual = cand.rewrite_dockerfile(dockerfile, new_base, cand.snapshot_default())
    (cand_dir / "Dockerfile").write_text(new_dockerfile)
    record["dockerfile_changes"], record["manual"] = changes, manual
    env = dict(os.environ, TMPDIR=str(HOME_TMP), ENGINE=engine.ENGINE)
    cand.compile_lock(cand_dir, new_base, env)
    new_pins = cand.parse_lock((cand_dir / "requirements.lock").read_text())
    if "--no-build-isolation" in new_dockerfile and "setuptools" not in new_pins:
        version = cand.parse_lock((REPO / "rosetta-api" / "requirements.lock").read_text())["setuptools"][1]
        with open(cand_dir / "requirements.txt", "a") as fh:
            fh.write(f"setuptools=={version}\n")
        record["added"] = {"setuptools": f"{version} (the version of rosetta-api/requirements.lock): the offline "
                                          "install of shared/ needs it and the new base image does not ship it"}
        cand.compile_lock(cand_dir, new_base, env)
        new_pins = cand.parse_lock((cand_dir / "requirements.lock").read_text())
    record["lock_moves"] = cand.lock_moves(pins, new_pins)
    (cand_dir / "prepare.json").write_text(json.dumps(record, indent=1))
    return record


def track_pull(ref, state):
    """Pull ``ref`` if missing and remember it for removal."""
    if engine.image_id(ref) is None:
        engine.run(["pull", "-q", ref], capture=True)
        state.setdefault("pulled", []).append(engine.image_id(ref))
        save_state(state)


def save_state(state):
    Path(state["_path"]).write_text(json.dumps({k: v for k, v in state.items() if k != "_path"}, indent=1))


def build_images(svc, service_id, cand_dir, work, state):
    built = {}
    args = {"QROSETTA_GIT_SHA": git_sha(), "QROSETTA_IMAGE_SOURCE": "built_locally",
            "DEBIAN_SNAPSHOT": cand.snapshot_default()}
    for label, overlay in (("old", None), ("new", cand_dir)):
        ctx = work / f"context-{label}"
        digest = engine.stage_context(ctx, overlay, svc["dir"])
        for ref in engine.base_refs((ctx / svc["dir"] / "Dockerfile").read_text()):
            track_pull(ref, state)
        tag = f"localhost/qr-requal-{service_id}:{label}"
        started = time.monotonic()
        iid, fresh = engine.build(tag, ctx, svc["dir"], digest, args, work / f"build-{label}.log")
        if iid not in state.setdefault("images", []):
            state["images"].append(iid)
            save_state(state)
        built[label] = {"tag": tag, "id": iid, "rebuilt": fresh, "context_sha256": digest,
                        "build_sec": round(time.monotonic() - started, 1), "size": engine.image_size(tag),
                        "dockerfile": (ctx / svc["dir"] / "Dockerfile").read_text()}
        shutil.rmtree(ctx)
    return built


def check_imports(svc, images, work, extra=()):
    """Import ``main`` and the SDK's top-level modules in both images; stop when the new image
    fails an import the old one passes."""
    in_dir = work / "imports-in"
    if in_dir.exists():
        shutil.rmtree(in_dir)
    in_dir.mkdir(parents=True)
    shutil.copy2(Path(__file__).with_name("driver.py"), in_dir / "driver.py")
    sdk = registry.sdk_packages((REPO / svc["dir"] / "main.py").read_text())
    (in_dir / "sdk.json").write_text(json.dumps(sdk))
    memory = "1g" if svc["kind"] == "runner" else "2g"
    results = {}
    for label in ("old", "new"):
        out = work / f"imports-{label}"
        code, _ = engine.run_in_container(
            images[label]["tag"], ["python", "/home/appuser/requal-in/driver.py", "imports", svc["kind"],
                                   "/home/appuser/requal-in", "/home/appuser/requal-out"],
            in_dir, out, work / f"imports-{label}.log", memory, extra=extra, timeout=1800)
        if code != 0 or not (out / "imports.json").exists():
            raise SystemExit(f"import check in the {label} image failed; log: {work / f'imports-{label}.log'}")
        results[label] = json.loads((out / "imports.json").read_text())
    regressions = compare.import_regressions(results["old"], results["new"])
    if regressions:
        text = "\n".join(f"--- {name}\n{error}" for name, error in sorted(regressions.items()))
        raise SystemExit(f"the new image fails imports the old one passes:\n{text}")
    return results


def run_corpus(svc, images, cases, work, extra=()):
    in_dir = work / "corpus-in"
    if in_dir.exists():
        shutil.rmtree(in_dir)
    in_dir.mkdir(parents=True)
    shutil.copy2(Path(__file__).with_name("driver.py"), in_dir / "driver.py")
    with open(in_dir / "corpus.jsonl", "w") as fh:
        for case in cases:
            fh.write(json.dumps(case) + "\n")
    (in_dir / "cli_cases.json").write_text(json.dumps(corpus.cli_case_ids(cases)))
    memory = "1g" if svc["kind"] == "runner" else "2g"

    def one(label):
        out = work / f"corpus-{label}"
        code, elapsed = engine.run_in_container(
            images[label]["tag"], ["python", "/home/appuser/requal-in/driver.py", "corpus", svc["kind"],
                                   "/home/appuser/requal-in", "/home/appuser/requal-out"],
            in_dir, out, work / f"corpus-{label}.log", memory, extra=extra, timeout=8 * 3600)
        return label, {"exit": code, "elapsed_sec": round(elapsed, 1), "dir": out}

    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = dict(pool.map(one, ("old", "new")))
    for label, run in runs.items():
        if run["exit"] != 0:
            raise SystemExit(f"corpus run in the {label} image failed; log: {work / f'corpus-{label}.log'}")
    return runs


def scan(images, work, state):
    text = (REPO / "scripts" / "release" / "image.sh").read_text()
    trivy = re.search(r'^TRIVY_IMAGE="([^"]+)"', text, re.M).group(1)
    track_pull(trivy, state)
    scan_dir = work / "scan"
    cache = HOME_TMP / "trivy-cache"
    scan_dir.mkdir(exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    for label, image in images.items():
        tar = scan_dir / f"{label}.tar"
        engine.run(["save", "-q", "--format", "docker-archive", "-o", str(tar), image["tag"]])
        report_name = f"trivy-{label}.json"
        engine.run(["run", "--rm", "-v", f"{scan_dir}:/scan:Z", "-v", f"{cache}:/root/.cache/trivy:Z", trivy,
                    "image", "--quiet", "--scanners", "vuln", "--format", "json", "--output",
                    f"/scan/{report_name}", "--input", f"/scan/{label}.tar"], timeout=3600)
        tar.unlink()
        data = json.loads((scan_dir / report_name).read_text())
        counts = {"all": {}, "fixed": {}}
        for res in data.get("Results") or []:
            for vuln in res.get("Vulnerabilities") or []:
                sev = vuln.get("Severity", "UNKNOWN")
                counts["all"][sev] = counts["all"].get(sev, 0) + 1
                if vuln.get("FixedVersion"):
                    counts["fixed"][sev] = counts["fixed"].get(sev, 0) + 1
        out[label] = {"trivy": trivy, "counts": counts}
    return out


def cleanup(state):
    removed = engine.remove_images(list(reversed(state.get("images", []))) + state.get("pulled", []))
    state["removed"] = removed
    state["images"], state["pulled"] = [], []
    save_state(state)
    return removed


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    services = registry.services()
    if args.service not in services:
        raise SystemExit(f"unknown service {args.service!r}; one of {', '.join(sorted(services))}")
    svc = services[args.service]
    work = args.work or HOME_TMP / "requal" / args.service
    work.mkdir(parents=True, exist_ok=True)
    report_path = args.report or REPO / "docs" / "audits" / "2026-10-28-overnight" / "requal" / f"{args.service}.md"
    state_path = work / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    state["_path"] = str(state_path)
    cand_dir = args.candidate or work / "candidate"
    evidence = {"service": args.service, "svc": svc, "args": {k: str(v) for k, v in vars(args).items()},
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "git_sha": git_sha()}
    try:
        if args.new_base:
            record = prepare(svc, args.service, args.new_base, cand_dir, args.relax, work, state)
        else:
            path = cand_dir / "prepare.json"
            record = json.loads(path.read_text()) if path.exists() else {}
        evidence["prepare"] = record
        if record.get("stop"):
            evidence["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            report.write(report_path, evidence)
            print(f"STOP: {'; '.join(record['stop'])}\nwrote {report_path}", file=sys.stderr)
            return 3
        if args.prepare_only:
            print(f"candidate in {cand_dir}", file=sys.stderr)
            return 0
        images = build_images(svc, args.service, cand_dir, work, state)
        evidence["images"] = {k: {kk: vv for kk, vv in v.items()} for k, v in images.items()}
        evidence["imports"] = check_imports(svc, images, work, engine.device_args(args.device))
        if not args.skip_corpus:
            cases = corpus.build(svc["kind"], svc["levels"], args.sv, args.measured, args.deep,
                                 args.single_register, args.max_gates)
            runs = run_corpus(svc, images, cases, work, engine.device_args(args.device))
            evidence["corpus_runs"] = {k: {"exit": v["exit"], "elapsed_sec": v["elapsed_sec"]} for k, v in runs.items()}
            evidence["corpus"] = compare.compare_corpus(runs["old"]["dir"], runs["new"]["dir"], cases, args.service)
            evidence["cli_check"] = (compare.compare_cli(runs["old"]["dir"], "old")
                                     + compare.compare_cli(runs["new"]["dir"], "new"))
            evidence["selftest"] = {k: compare.selftest_lines((v["dir"] / "selftest.txt").read_text())
                                    for k, v in runs.items()}
            envs = {k: json.loads((v["dir"] / "environment.json").read_text()) for k, v in runs.items()}
            evidence["environment"] = {k: {"python": v["python"], "libc": v["libc"]} for k, v in envs.items()}
            evidence["distribution_moves"] = compare.distribution_moves(envs["old"], envs["new"])
        if not args.skip_timing and svc["kind"] == "runner":
            rounds = timing.run(images, args, work)
            evidence["timing_rounds"] = [{k: v for k, v in r.items() if k != "results"} for r in rounds]
            evidence["timing"] = timing.summarise(rounds)
            (work / "timing-raw.json").write_text(json.dumps(rounds))
        if args.scan:
            evidence["scan"] = scan(images, work, state)
    finally:
        if not args.keep_images:
            evidence["removed"] = cleanup(state)
        evidence["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        (work / "evidence.json").write_text(json.dumps(evidence, indent=1, default=str))
    report.write(report_path, evidence)
    print(f"wrote {report_path}", file=sys.stderr)
    corpus_diff = [d for d in evidence.get("corpus", {}).get("differences", []) if d["class"] != "known_jitter"]
    return 1 if corpus_diff else 0


if __name__ == "__main__":
    sys.exit(main())
