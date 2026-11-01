"""Runs the V4 known-answer and relation cases through a live Quantum Rosetta server as a user
(POST /run_batch_suite, one job at a time), saves each report, and evaluates it with v4_check.

    v4_run.py [--base-url URL] [--out DIR] [--jobs NAME,...]

Jobs (playlist of every case, every available backend, seed fixed, no bypass_limits):
  sv-pre-L0      statevector, preprocessing on, optimization level 0
  sv-raw-L0      statevector, preprocessing off, level 0
  sv-pre-L2      statevector, preprocessing on, level 2 (each backend clamps to its highest)
  m-pre-L0       measured, preprocessing on, level 0, 8200 shots
  m-raw-L0       measured, preprocessing off, level 0, 8200 shots
Writes <out>/<job>/{request,job,report,rows}.json and <out>/summary.json. Needs numpy and scipy."""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import v4_cases
import v4_check

JOBS = {
    "sv-pre-L0": {"mode": "statevector", "apply_preprocessing": True, "optimization_level": 0},
    "sv-raw-L0": {"mode": "statevector", "apply_preprocessing": False, "optimization_level": 0},
    "sv-pre-L2": {"mode": "statevector", "apply_preprocessing": True, "optimization_level": 2},
    "m-pre-L0": {"mode": "measured", "apply_preprocessing": True, "optimization_level": 0},
    "m-raw-L0": {"mode": "measured", "apply_preprocessing": False, "optimization_level": 0},
}
SHOTS = 8200
SEED = 20261101
THRESHOLDS = {"fidelity_tolerance": 1e-5, "phase_tolerance": 1e-6, "norm_tolerance": 1e-4,
              "js_threshold": 0.01, "hellinger_threshold": 0.1}


def http(base, method, path, body=None, timeout=600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,  # noqa: S310 (scheme checked in main)
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read())


def available_backends(base):
    rows = http(base, "GET", "/runners")
    rows = rows.get("runners", rows) if isinstance(rows, dict) else rows
    if isinstance(rows, dict):
        rows = [{"id": k, **v} for k, v in rows.items()]
    return sorted(r["id"] for r in rows if r.get("available", True) and r.get("enabled", True))


def request_body(job, cases, backends):
    spec = JOBS[job]
    body = {"mode": spec["mode"],
            "tasks": [{"name": c["name"], "source": "qasm", "qasm_string": c["qasm"]} for c in cases],
            "target_simulators": backends, "optimization_level": spec["optimization_level"],
            "runner_config": {}, "runner_phases": {}, "timeout_seconds": 120, "timing_repeats": 1,
            "exclusive": False, "bypass_limits": False, "apply_preprocessing": spec["apply_preprocessing"],
            "thresholds": THRESHOLDS, "compilers": {}, "simulate": True, "seed": SEED}
    if spec["mode"] == "measured":
        body["n_shots"] = SHOTS
    return body


def wait(base, job_id, poll=10):
    misses = 0
    while True:
        try:
            info = http(base, "GET", f"/jobs/{job_id}", timeout=60)
            misses = 0
        except (urllib.error.URLError, TimeoutError) as exc:
            if getattr(exc, "code", None) == 404:
                raise SystemExit(f"job {job_id} lost (404)") from exc
            misses += 1
            if misses > 30:
                raise
            time.sleep(poll)
            continue
        if info.get("status") in ("completed", "failed", "cancelled"):
            return info
        time.sleep(poll)


def raw_by_task(report):
    out = {}
    for task in report.get("benchmark_summary") or []:
        name = (task.get("task_request") or {}).get("name") or task.get("task_name")
        out[name] = {r.get("simulator"): r for r in task.get("raw_results") or [] if isinstance(r, dict)}
    return out


def dispatched_by_task(report):
    out = {}
    for task in report.get("benchmark_summary") or []:
        name = (task.get("task_request") or {}).get("name") or task.get("task_name")
        out[name] = {runner: group.get("qasm") for group in task.get("dispatched_circuits") or []
                     for runner in group.get("runners") or []}
    return out


def run_job(base, job, out, backends):
    cases = v4_cases.build(measure=JOBS[job]["mode"] == "measured")
    folder = out / job
    folder.mkdir(parents=True, exist_ok=True)
    report_file = folder / "report.json"
    if not report_file.exists():
        body = request_body(job, cases, backends)
        (folder / "request.json").write_text(json.dumps(body, indent=1))
        job_id = http(base, "POST", "/run_batch_suite", body)["job_id"]
        print(f"{job}: job {job_id}, {len(cases)} circuits x {len(backends)} backends", file=sys.stderr, flush=True)
        info = wait(base, job_id)
        (folder / "job.json").write_text(json.dumps(info, indent=1))
        if info.get("status") != "completed":
            raise SystemExit(f"{job}: job ended {info.get('status')}: {info.get('error')}")
        with urllib.request.urlopen(base + f"/jobs/{job_id}/report", timeout=1800) as resp:  # noqa: S310
            report_file.write_bytes(resp.read())
    report = json.loads(report_file.read_text())
    rows = v4_check.evaluate(cases, raw_by_task(report), JOBS[job]["mode"], SHOTS, dispatched_by_task(report))
    (folder / "rows.json").write_text(json.dumps(rows, indent=1, default=str))
    table, fails = v4_check.summary(rows)
    return {"job": job, **JOBS[job], "cases": len(cases), "by_backend": table, "fails": fails}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--base-url", default="http://127.0.0.1:8080")
    p.add_argument("--out", type=Path, default=Path.home() / ".tmp" / "qr-verify" / "v4")
    p.add_argument("--jobs", default=",".join(JOBS))
    args = p.parse_args(argv)
    base = args.base_url.rstrip("/")
    if not base.startswith(("http://", "https://")):
        p.error("--base-url must be http:// or https://")
    backends = available_backends(base)
    args.out.mkdir(parents=True, exist_ok=True)
    config = http(base, "GET", "/config")
    results = {"base_url": base, "server": config.get("server"), "backends": backends, "jobs": []}
    for job in args.jobs.split(","):
        results["jobs"].append(run_job(base, job, args.out, backends))
        (args.out / "summary.json").write_text(json.dumps(results, indent=1, default=str))
    for job in results["jobs"]:
        statuses = {}
        for counts in job["by_backend"].values():
            for k, v in counts.items():
                statuses[k] = statuses.get(k, 0) + v
        print(f"{job['job']}: {statuses}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
