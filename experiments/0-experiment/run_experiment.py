#!/usr/bin/env python3
"""QRosetta fleet-experiment driver (the reusable "0-experiment" harness).

Runs a set of circuits across the QRosetta simulator fleet through the existing HTTP API
(`/run_batch_suite` + `/jobs/{id}`) and freezes everything needed to replay and cite the run.

The artifact builders (conformance matrix, agreement prevalence, manifest, statevector
stripping) live in `rosetta-api/services/experiment_artifacts.py` and are SHARED with the
in-app experiment runner. This driver only adds
the stdlib HTTP orchestration + on-disk freezing around those shared builders.

Reproducibility contract
------------------------
Every experiment folder is self-describing:
  * inputs/    - the EXACT QASM executed (frozen; never "regenerate grover-5q" later)
  * results/   - per-circuit reports (statevectors stripped to a hash by default; see --keep-sv)
  * conformance_matrix.csv - circuit x simulator -> success | error(signature) | timeout,
                             plus an (initially "untriaged") column for the human triage step
  * agreement_prevalence.csv - agreement-class counts over the pairs that ran successfully
  * performance.csv - circuit x simulator timings, memory and CPU context, one row per run
  * errors/    - per-simulator error signatures
  * README.txt - the integrity/triage gate
  * manifest.json - config + git SHA + timestamp + effective seed + gathered SDK versions

Two honest, separated outputs
-----------------------------
  A) conformance/robustness matrix (did it run?), and
  B) explained-disagreement prevalence (did the successes agree, and via which transform?).
These are NOT conflated, and no research question is baked in. An error is only a *finding*
after a human triages it into: (a) QRosetta adapter bug, (b) genuine SDK bug, (c) unsupported-
by-design, or (d) resource/timeout. The matrix records the raw signature; triage is manual.

Usage
-----
    python run_experiment.py --config config.example.json --out experiment-1
Requires a reachable QRosetta API (local stack or deployment). Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Import the SHARED, stdlib-only artifact builders from the API package (single source of
# truth for the frozen-bundle format). Only `services.experiment_artifacts` is imported, so
# no FastAPI/pytket runtime dependency is pulled in.
sys.path.insert(0, os.path.join(_REPO_ROOT, "rosetta-api"))
from services import experiment_artifacts as art  # noqa: E402


# --- tiny stdlib HTTP helpers ---------------------------------------------------------

def _post_json(url: str, payload: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- helpers --------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "-C", _REPO_ROOT, "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


# --- circuit resolution (freeze the exact QASM) ---------------------------------------

def resolve_circuits(cfg: dict, base_url: str, inputs_dir: str) -> list:
    """Resolve each configured circuit to a frozen QASM string written under inputs/.

    Config entry is either {"algorithm","qubits"} (preset, generated via /generate_circuit)
    or {"qasm_file","name"} (read from disk). Returns [{id, algorithm, qubits, qasm}]."""
    os.makedirs(inputs_dir, exist_ok=True)
    resolved = []
    for i, entry in enumerate(cfg["circuits"]):
        if entry.get("qasm_file"):
            path = entry["qasm_file"]
            if not os.path.isabs(path):
                path = os.path.join(_REPO_ROOT, path)
            with open(path, "r", encoding="utf-8") as fh:
                qasm = fh.read()
            name = entry.get("name") or os.path.splitext(os.path.basename(path))[0]
            algorithm, qubits = name, entry.get("qubits", 0)
        else:
            algorithm, qubits = entry["algorithm"], int(entry["qubits"])
            name = f"{algorithm}_{qubits}q"
            resp = _post_json(f"{base_url}/generate_circuit",
                              {"algorithm": algorithm, "qubits": qubits})
            qasm = resp["qasm"]
        cid = f"{i:03d}_{art.slug(name)}"
        with open(os.path.join(inputs_dir, f"{cid}.qasm"), "w", encoding="utf-8") as fh:
            fh.write(qasm)
        resolved.append({"id": cid, "algorithm": algorithm, "qubits": qubits, "qasm": qasm})
    print(f"  froze {len(resolved)} circuit(s) to {inputs_dir}")
    return resolved


# --- run one axis (a preprocessing setting) via the batch API -------------------------

def run_axis(base_url: str, circuits: list, cfg: dict, seed, apply_preprocessing: bool,
             poll_secs: int = 3) -> list:
    tasks = [{"algorithm": c["algorithm"], "qubits": int(c["qubits"]) or 0,
              "qasm_string": c["qasm"]} for c in circuits]
    payload = {
        "tasks": tasks,
        "mode": cfg["mode"],
        "optimization_level": cfg.get("optimization_level", 0),
        "timeout_seconds": cfg.get("timeout_seconds", 300),
        "timing_repeats": cfg.get("timing_repeats", 1),
        "runner_phases": cfg.get("runner_phases", {}),
        "target_simulators": cfg.get("target_simulators", []),
        "execution_target": cfg.get("execution_target", "local"),
        "apply_preprocessing": apply_preprocessing,
        "seed": seed,
        "bypass_limits": cfg.get("bypass_limits", False),
    }
    if cfg.get("n_shots") is not None:
        payload["n_shots"] = cfg["n_shots"]
    if cfg.get("thresholds"):
        payload["thresholds"] = cfg["thresholds"]

    started = _post_json(f"{base_url}/run_batch_suite", payload)
    job_id = started.get("job_id")
    if not job_id or started.get("status") == "failed":
        raise RuntimeError(f"batch failed to start: {started}")
    print(f"  job {job_id} (preprocessing={apply_preprocessing}) ...", end="", flush=True)
    while True:
        status = _get_json(f"{base_url}/jobs/{job_id}")
        prog = status.get("progress") or {}
        if prog:
            print(f"\r  job {job_id} (preprocessing={apply_preprocessing}) "
                  f"{prog.get('completed', 0)}/{prog.get('total', '?')}   ", end="", flush=True)
        if status.get("status") == "completed":
            print(" done")
            return (status.get("results") or {}).get("benchmark_summary", []) or []
        if status.get("status") == "failed":
            raise RuntimeError(f"job {job_id} failed: {status.get('error')}")
        time.sleep(poll_secs)


# --- main -----------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="QRosetta fleet-experiment driver")
    ap.add_argument("--config", required=True, help="path to the experiment config JSON")
    ap.add_argument("--out", required=True, help="output experiment folder (frozen artifact)")
    ap.add_argument("--base-url", default=None, help="override the API base_url from the config")
    ap.add_argument("--keep-sv", action="store_true",
                    help="store full statevectors (default: strip to a hash to keep results small)")
    args = ap.parse_args()

    with open(args.config, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    base_url = (args.base_url or cfg.get("base_url", "http://localhost:8000")).rstrip("/")
    out = os.path.abspath(args.out)
    inputs_dir = os.path.join(out, "inputs")
    results_dir = os.path.join(out, "results")
    errors_dir = os.path.join(out, "errors")
    for d in (out, results_dir, errors_dir):
        os.makedirs(d, exist_ok=True)

    print(f"QRosetta experiment -> {out}\n  API: {base_url}  mode: {cfg['mode']}")
    circuits = resolve_circuits(cfg, base_url, inputs_dir)

    seed = cfg.get("seed", None)  # null in config => backend generates and records one
    preprocessing_modes = cfg.get("preprocessing_modes", [True])
    conformance, prevalence, performance = [], [], []
    all_summaries = []
    effective_seeds, sdk_versions = {}, {}

    for pp in preprocessing_modes:
        axis = f"{cfg['mode']}_preproc{'On' if pp else 'Off'}"
        summary = run_axis(base_url, circuits, cfg, seed, apply_preprocessing=bool(pp))
        all_summaries += summary
        axis_dir = os.path.join(results_dir, axis)
        os.makedirs(axis_dir, exist_ok=True)
        for report in summary:
            if not args.keep_sv:
                report = art.strip_statevectors(report)
            cid = art.slug(report.get("task_name", "circuit"))
            with open(os.path.join(axis_dir, f"{cid}.json"), "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, default=str)
            if report.get("seed") is not None:
                effective_seeds[axis] = report["seed"]  # the seed actually used (recorded)
        conformance += art.build_conformance_rows(axis, summary)
        prevalence += art.build_prevalence_rows(axis, summary)
        performance += art.build_performance_rows(axis, summary)
        art.collect_sdk_versions(summary, into=sdk_versions)

    with open(os.path.join(out, "conformance_matrix.csv"), "w", encoding="utf-8") as fh:
        fh.write(art.csv_string(conformance, art.CONFORMANCE_FIELDS))
    with open(os.path.join(out, "agreement_prevalence.csv"), "w", encoding="utf-8") as fh:
        fh.write(art.csv_string(prevalence, art.PREVALENCE_FIELDS))
    with open(os.path.join(out, "performance.csv"), "w", encoding="utf-8") as fh:
        fh.write(art.csv_string(performance, art.PERFORMANCE_FIELDS))
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write(art.TRIAGE_README)

    # per-simulator error signatures for quick triage
    for sim, text in art.build_error_logs(conformance).items():
        with open(os.path.join(errors_dir, f"{art.slug(sim)}.log"), "w", encoding="utf-8") as fh:
            fh.write(text)

    manifest = art.build_manifest(
        config=cfg, git_sha=_git_sha(), api_base=base_url, requested_seed=seed,
        effective_seeds=effective_seeds, circuits=circuits, sdk_versions=sdk_versions)
    manifest["created_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["host_environment"] = art.collect_host_environment(all_summaries)
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)

    n_err = sum(1 for r in conformance if r["error_signature"])
    print(f"\nDone. {len(conformance)} (circuit x simulator) cells, {n_err} errors to triage.")
    print(f"  {os.path.join(out, 'conformance_matrix.csv')}")
    print(f"  {os.path.join(out, 'agreement_prevalence.csv')}")
    print(f"  {os.path.join(out, 'performance.csv')}")
    print(f"  {os.path.join(out, 'manifest.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
