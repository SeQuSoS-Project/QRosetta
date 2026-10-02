"""Builders for the reproducible-experiment artifact bundle.

Imported by both the in-app experiment runner (``services.experiment``) and the
standalone CLI harness (``experiments/0-experiment/run_experiment.py``). Stdlib-only
so the CLI can import it without the API's runtime dependencies.

Bundle outputs:
  A) conformance matrix  — per (circuit x simulator) run status + error signature
  B) agreement prevalence — pair counts per class over compared pairs, with
     not_comparable pairs counted in their own rows. Measured pairs are counted by
     measured_assessment (the shot-noise verdict), with the distance labels of each class
     in a secondary column; statevector pairs by agreement label.
  C) performance table    — per (circuit x simulator) timing, memory and CPU context,
     one row per run, for cross-circuit and cross-size comparison

Error rows carry a raw signature with ``triage='untriaged'``; classification into
adapter / SDK / by-design / resource happens during review.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re

from services.report_filters import fingerprint_statevectors

CONFORMANCE_FIELDS = ["axis", "circuit", "simulator", "status", "error_signature", "triage",
                      "circuit_id"]
PERFORMANCE_FIELDS = [
    "axis", "circuit", "circuit_id", "declared_qubits", "simulator", "status", "device",
    "precision", "sampling_method", "n_shots", "timing_repeats", "timing_statistic",
    "compilation_time_sec", "simulation_time_sec", "simulation_time_sec_stdev",
    "simulation_time_sec_min", "simulation_time_sec_max", "simulation_cpu_time_sec",
    "simulation_cgroup_cpu_time_sec", "simulation_throttled_sec", "compilation_throttled_sec", "execution_time_sec",
    "memory_usage_mb", "process_peak_mb", "process_peak_rss_mb",
    "theoretical_statevector_mb", "gate_count", "circuit_depth", "queue_wait_sec",
    "concurrent_runs", "overlapping_runs", "server_overlapping_runs", "dispatch_phase",
    "exclusive", "exclusive_wait_sec",
    "cpu_model", "cpu_quota_cores", "cpu_affinity_setting", "memory_limit_mib",
    "simulation_cpus", "simulation_cpu_max_mhz", "simulation_time_samples",
    "simulation_cpus_samples", "compilation_time_sec_stdev", "compilation_time_samples",
]
PREVALENCE_FIELDS = ["axis", "count_basis", "agreement_class", "pair_count", "pair_scope",
                     "distance_labels"]

NOT_COMPARABLE = "not_comparable"

_VERDICT_TO_ASSESSMENT = {"consistent": "consistent_within_shot_noise",
                          "distinguishable": "distinguishable", "ambiguous": "ambiguous",
                          "inconclusive_low_shots": "inconclusive_low_shots"}

_DISPATCH_TO_CONFORMANCE = {"ok": "success", "error": "error", "timeout": "timeout",
                            "offline": "offline"}

TRIAGE_README = (
    "QRosetta reproducible-experiment bundle\n"
    "=======================================\n\n"
    "This folder freezes one fleet run so it can be replayed and cited:\n"
    "  inputs/<id>.qasm         - each circuit as submitted; the text each runner received\n"
    "                             is under dispatched_circuits in the per-circuit report\n"
    "  results/<axis>/<id>.json - per-circuit reports, named by circuit id. By default each\n"
    "                             statevector is replaced by statevector_sha256 (sha256 of the\n"
    "                             Base64-decoded complex128 bytes; for list-form vectors, of\n"
    "                             the sorted-key JSON) and statevector_length (also\n"
    "                             written as statevector_len);\n"
    "                             metrics, labels and provenance are kept in full\n"
    "  conformance_matrix.csv   - per (circuit x simulator) run status + error signature\n"
    "  performance.csv          - per (circuit x simulator) timings, memory and CPU context,\n"
    "                             one row per run. Times are medians over timing_repeats\n"
    "                             timed runs (min/max/stdev beside them; stdev empty for one\n"
    "                             run). simulation_throttled_sec is the part of\n"
    "                             simulation_time_sec the CPU quota held the runner;\n"
    "                             simulation_cgroup_cpu_time_sec above simulation_cpu_time_sec\n"
    "                             means work ran outside the simulating process.\n"
    "                             simulation_cpu_max_mhz is the maximum frequency of each CPU\n"
    "                             the run was on (cores of different speeds give different\n"
    "                             times). Failed runs have empty metric cells. Memory fields\n"
    "                             are MiB of host RSS; see metric_scope in results/.\n"
    "                             simulation_time_samples lists every timed run (';'), and\n"
    "                             simulation_cpus_samples the CPUs of each ('|' between runs).\n"
    "                             exclusive is true when the job ran one backend at a time\n"
    "                             with no other run on the server; server_overlapping_runs\n"
    "                             counts runs of other jobs that overlapped this one.\n"
    "                             concurrent_runs is the number of runs dispatched in the\n"
    "                             same phase (itself included); overlapping_runs counts the\n"
    "                             other runs of the job that were running at some time this\n"
    "                             one was (other users' runs are not counted). Runs that share\n"
    "                             the host's cores and memory bandwidth are slower.\n"
    "  compiled_circuits.csv    - when compile-only services ran: one row per compile record\n"
    "                             (status, gate_count, multi_qubit_gate_count, circuit_depth,\n"
    "                             gate_counts per gate name, output file). gate_count counts\n"
    "                             statements, so it is not comparable across compilers that\n"
    "                             write different gate sets. The texts are under\n"
    "                             compiled_circuits/<axis>/<circuit>/; each compiler's build\n"
    "                             files (Dockerfile, lock file, patches, Quartz's ECC set) are\n"
    "                             under compilers/<name>/ when their sha256 matches the image.\n"
    "  agreement_prevalence.csv - pair counts per class over compared pairs\n"
    "                             (pair_scope=compared); pairs where a side had no usable\n"
    "                             output are counted separately (pair_scope=not_comparable).\n"
    "                             count_basis says what the class is: measured pairs are\n"
    "                             counted by measured_assessment (the shot-noise verdict:\n"
    "                             consistent_within_shot_noise, distinguishable, ambiguous,\n"
    "                             inconclusive_low_shots), and distance_labels lists the\n"
    "                             descriptive distance labels within each class as\n"
    "                             label:count; statevector pairs are counted by agreement\n"
    "                             label. A distance label such as agree_after_bit_reversal\n"
    "                             on a distinguishable pair is not an agreement.\n"
    "  errors/*.log             - per-simulator error signatures\n"
    "  manifest.json            - config as requested (nulls mean server defaults) and\n"
    "                             effective_config (the seed, agreement thresholds and runner\n"
    "                             ids actually used; hashed as effective_config_sha256), git\n"
    "                             SHA, timestamp, master seed per axis (each runner's seed is\n"
    "                             derived from it; see seed_derivation and runner_seed in the\n"
    "                             results), thresholds and runners per axis, SDK versions.\n"
    "                             To replay, submit inputs/*.qasm as literal circuits with\n"
    "                             the values in effective_config (not the preset names).\n\n"
    "Reading the CSVs:\n"
    "  * The conformance matrix and the prevalence table are separate outputs: a cell\n"
    "    that failed to run carries no agreement information.\n"
    "  * Each error row records a raw signature with triage='untriaged'. Classify each\n"
    "    error as adapter / SDK / by-design / resource and update the column before\n"
    "    reporting it as a result.\n"
    "  * Each agreement label carries its registered transform and numerical effect in\n"
    "    the per-pair records under results/.\n"
    "  * The exhaustive qubit-permutation search is bounded; larger pairs report\n"
    "    attempted=false with a reason. Disclose this bound in any prevalence analysis.\n"
)


def sha256(obj) -> str:
    """Stable sha256 over any JSON-able object (sorted keys, str fallback)."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def qasm_bytes(qasm: str) -> bytes:
    """The bytes written to inputs/<id>.qasm for ``qasm``."""
    return qasm.encode("utf-8")


def recorded_value(summary: list, key: str, missing=("", "unknown")):
    """First value of ``key`` across the per-circuit reports that is not None or in ``missing``."""
    for report in summary:
        value = (report or {}).get(key)
        if value is not None and value not in missing:
            return value
    return None


def slug(text: str) -> str:
    """Lowercase alphanumeric slug with '-' separators ('circuit' if empty)."""
    return "".join(c if c.isalnum() else "-" for c in str(text).lower()).strip("-") or "circuit"


def strip_statevectors(report: dict) -> dict:
    """Replace each raw statevector with statevector_sha256 and statevector_length (see
    fingerprint_statevectors)."""
    fingerprint_statevectors(report, sha256)
    for entry in report.get("raw_results", []) or []:
        if isinstance(entry, dict) and "statevector_len" in entry:
            entry.setdefault("statevector_length", entry["statevector_len"])
    return report


def _runner_status(entry: dict) -> tuple:
    """(status, error signature). Uses the dispatcher's ``dispatch_status`` when present;
    reports without it fall back to matching 'timeout' in the error text."""
    dispatch_status = entry.get("dispatch_status")
    if not entry.get("error"):
        return _DISPATCH_TO_CONFORMANCE.get(dispatch_status, "success"), ""
    sig = str(entry["error"]).strip().splitlines()[0][:300]
    if dispatch_status in _DISPATCH_TO_CONFORMANCE:
        return _DISPATCH_TO_CONFORMANCE[dispatch_status], sig
    low = sig.lower()
    return ("timeout" if "timeout" in low or "timed out" in low else "error"), sig


def build_conformance_rows(axis_label: str, summary: list) -> list:
    """One row per (circuit x simulator): run status + untriaged error signature."""
    rows = []
    for report in summary:
        circuit = report.get("task_name", "?")
        circuit_id = report.get("circuit_id", "")
        if report.get("error") and not report.get("raw_results"):
            rows.append({"axis": axis_label, "circuit": circuit, "simulator": "(circuit)",
                         "status": "circuit_error", "error_signature": str(report["error"])[:300],
                         "triage": "untriaged", "circuit_id": circuit_id})
            continue
        for entry in report.get("raw_results", []) or []:
            status, sig = _runner_status(entry)
            rows.append({"axis": axis_label, "circuit": circuit,
                         "simulator": entry.get("simulator", "?"), "status": status,
                         "error_signature": sig, "triage": "untriaged" if sig else "",
                         "circuit_id": circuit_id})
    return rows


_QREG_RE = re.compile(r"\bqreg\s+\w+\s*\[\s*(\d+)\s*\]\s*;")
_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)


def _declared_qubits(qasm):
    """Sum of every qreg size in ``qasm``; None without QASM."""
    if not qasm:
        return None
    return sum(int(n) for n in _QREG_RE.findall(_COMMENT_RE.sub("", qasm)))


def _samples_extreme(entry: dict, pick):
    samples = entry.get("simulation_time_samples")
    if isinstance(samples, list) and samples and all(isinstance(v, (int, float)) for v in samples):
        return pick(samples)
    value = entry.get("simulation_time_sec")
    return value if isinstance(value, (int, float)) else None


def build_performance_rows(axis_label: str, summary: list) -> list:
    """One row per (circuit x simulator) with the run's timing, memory and CPU context;
    metric cells are None for a failed run."""
    rows = []
    for report in summary:
        circuit = report.get("task_name", "?")
        qubits = _declared_qubits(report.get("input_qasm"))
        for entry in report.get("raw_results", []) or []:
            status, _ = _runner_status(entry)
            ok = status == "success"
            env = entry.get("cpu_environment") or {}
            cpus = entry.get("simulation_cpus") or []
            mhz = env.get("cpu_max_mhz") or {}
            row = {"axis": axis_label, "circuit": circuit,
                   "circuit_id": report.get("circuit_id", ""), "declared_qubits": qubits,
                   "simulator": entry.get("simulator", "?"), "status": status,
                   "device": entry.get("device"), "precision": entry.get("precision"),
                   "sampling_method": entry.get("sampling_method"),
                   "n_shots": entry.get("n_shots"),
                   "cpu_model": env.get("cpu_model"),
                   "cpu_quota_cores": env.get("cpu_quota_cores"),
                   "simulation_cpus": ";".join(str(c) for c in cpus),
                   "simulation_cpu_max_mhz": ";".join(
                       str(mhz.get(str(c))) if mhz.get(str(c)) is not None else ""
                       for c in cpus)}
            for key in ("timing_repeats", "timing_statistic", "compilation_time_sec",
                        "simulation_time_sec", "simulation_time_sec_stdev",
                        "simulation_cpu_time_sec", "simulation_cgroup_cpu_time_sec",
                        "simulation_throttled_sec",
                        "compilation_throttled_sec", "execution_time_sec", "memory_usage_mb",
                        "process_peak_mb", "process_peak_rss_mb",
                        "theoretical_statevector_mb", "gate_count", "circuit_depth"):
                row[key] = entry.get(key) if ok else None
            row["queue_wait_sec"] = entry.get("queue_wait_sec")
            for key in ("concurrent_runs", "overlapping_runs", "server_overlapping_runs",
                        "dispatch_phase", "exclusive", "exclusive_wait_sec"):
                row[key] = entry.get(key)
            row["cpu_affinity_setting"] = env.get("cpu_affinity_setting")
            row["memory_limit_mib"] = env.get("memory_limit_mib")
            samples = entry.get("simulation_time_samples")
            row["simulation_time_samples"] = (
                ";".join(repr(v) for v in samples) if ok and isinstance(samples, list) else None)
            row["compilation_time_sec_stdev"] = entry.get("compilation_time_sec_stdev") if ok else None
            comp = entry.get("compilation_time_samples")
            row["compilation_time_samples"] = (
                ";".join(repr(v) for v in comp) if ok and isinstance(comp, list) else None)
            cpu_samples = entry.get("simulation_cpus_samples")
            row["simulation_cpus_samples"] = (
                "|".join(";".join(str(c) for c in (run or [])) for run in cpu_samples)
                if ok and isinstance(cpu_samples, list) else None)
            row["simulation_time_sec_min"] = _samples_extreme(entry, min) if ok else None
            row["simulation_time_sec_max"] = _samples_extreme(entry, max) if ok else None
            if ok and row["timing_repeats"] is None:
                row["timing_repeats"] = entry.get("timing_samples")
            rows.append(row)
    return rows


def _measured_class(rec: dict) -> str:
    """measured_assessment of a measured pair record, else the class its verdict implies."""
    if rec.get("agreement") == NOT_COMPARABLE:
        return NOT_COMPARABLE
    if rec.get("measured_assessment"):
        return rec["measured_assessment"]
    verdict = ((rec.get("metrics") or {}).get("statistical_test") or {}).get("verdict")
    return _VERDICT_TO_ASSESSMENT.get(verdict, "unassessed")


def build_prevalence_rows(axis_label: str, summary: list) -> list:
    """Pair counts per class and axis: compared pairs (``pair_scope='compared'``), then
    not_comparable pairs in their own row (``pair_scope='not_comparable'``).

    Measured pairs (``mode='measured'`` or a ``measured_assessment``) are counted by
    measured_assessment (``count_basis='measured_assessment'``) and ``distance_labels``
    holds "label:count" for the distance labels in that class, joined by "; ". Other pairs
    are counted by agreement label (``count_basis='agreement_label'``)."""
    counts: dict = {}
    labels: dict = {}
    basis = "agreement_label"
    for report in summary:
        for rec in (report.get("divergence_report") or {}).get("pairwise_agreement", []) or []:
            label = rec.get("agreement", "unknown")
            if rec.get("mode") == "measured" or "measured_assessment" in rec:
                basis = "measured_assessment"
                key = _measured_class(rec)
                per_class = labels.setdefault(key, {})
                per_class[label] = per_class.get(label, 0) + 1
            else:
                key = label
            counts[key] = counts.get(key, 0) + 1

    def row(key, count, scope):
        per_class = labels.get(key, {})
        return {"axis": axis_label, "count_basis": basis, "agreement_class": key,
                "pair_count": count, "pair_scope": scope,
                "distance_labels": "; ".join(f"{k}:{v}" for k, v in sorted(per_class.items()))}

    not_comparable = counts.pop(NOT_COMPARABLE, 0)
    rows = [row(k, v, "compared") for k, v in sorted(counts.items())]
    if not_comparable:
        rows.append(row(NOT_COMPARABLE, not_comparable, NOT_COMPARABLE))
    return rows


def collect_sdk_versions(summary: list, into: dict = None) -> dict:
    """Ground-truth executed SDK versions per simulator, first-seen wins."""
    versions: dict = into if into is not None else {}
    for report in summary:
        for entry in report.get("raw_results", []) or []:
            sim, sdk = entry.get("simulator"), entry.get("sdk_versions")
            if sim and sdk and sim not in versions:
                versions[sim] = sdk
    return versions


def build_error_logs(conformance_rows: list) -> dict:
    """Group error signatures per simulator -> {slug(sim): 'errors/<slug>.log' text}."""
    per_sim: dict = {}
    for row in conformance_rows:
        if row.get("error_signature"):
            per_sim.setdefault(row["simulator"], []).append(
                f"[{row['axis']}] {row['circuit']}: {row['error_signature']}")
    return {sim: "\n".join(lines) + "\n" for sim, lines in per_sim.items()}


def csv_string(rows: list, fields: list) -> str:
    """Render ``rows`` as CSV with ``fields`` as the header; missing keys are blank."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def collect_runner_images(reports: list) -> dict:
    """``{simulator: runner_image}`` for every result that recorded its image."""
    images = {}
    for report in reports or []:
        for result in (report or {}).get("raw_results", []) or []:
            if not isinstance(result, dict):
                continue
            image = result.get("runner_image")
            if image and not str(image).startswith("not recorded"):
                images[str(result.get("simulator"))] = image
    return images


def collect_host_environment(reports: list) -> dict:
    """Distinct CPU models, CPU quotas, affinity settings and runtime environments
    recorded by the runs of every report."""
    models, quotas, affinity, runtimes = set(), set(), set(), set()
    for report in reports:
        for entry in (report or {}).get("raw_results", []) or []:
            env = entry.get("cpu_environment") or {}
            if env.get("cpu_model"):
                models.add(env["cpu_model"])
            if "cpu_quota_cores" in env:
                quotas.add(env["cpu_quota_cores"])
            if "cpu_affinity_setting" in env:
                affinity.add(env["cpu_affinity_setting"])
            if entry.get("runtime_environment"):
                runtimes.add(json.dumps(entry["runtime_environment"], sort_keys=True))
    return {"cpu_models": sorted(models),
            "cpu_quota_cores": sorted(quotas, key=lambda q: (q is None, q or 0)),
            "cpu_affinity_settings": sorted(affinity, key=lambda a: (a is None, a or "")),
            "runtime_environments": [json.loads(r) for r in sorted(runtimes)]}


def build_manifest(*, config: dict, git_sha: str, api_base: str, requested_seed,
                   effective_seeds: dict, circuits: list, sdk_versions: dict,
                   image_digests: dict = None, extra_notes: str = "",
                   seed_derivation: str = None) -> dict:
    """Bundle manifest. ``circuits`` is [{id, algorithm, qubits, qasm}]; each ``qasm_sha256``
    is the sha256 of the bytes in inputs/<id>.qasm."""
    notes = (
        "Error signatures are recorded with triage='untriaged': classify each as adapter / "
        "SDK / by-design / resource before reporting it as a result. Base images are pinned "
        "in the runner Dockerfiles (@sha256); record the deployed digests in 'image_digests' "
        "for a citable release. The exhaustive qubit-permutation search is bounded (disclose "
        "the bound in any prevalence analysis)."
    )
    if extra_notes:
        notes = f"{notes} {extra_notes}"
    return {
        "git_sha": git_sha,
        "qrosetta_api": api_base,
        "config": config,
        "config_sha256": sha256(config),
        "requested_seed": requested_seed,
        "effective_seeds_per_axis": effective_seeds,
        "seed_derivation": seed_derivation or "not recorded",
        "circuits": [{"id": c["id"], "algorithm": c["algorithm"], "qubits": c["qubits"],
                      "qasm_file": f"inputs/{c['id']}.qasm",
                      "qasm_sha256": hashlib.sha256(qasm_bytes(c["qasm"])).hexdigest()}
                     for c in circuits],
        "executed_sdk_versions": sdk_versions,
        "image_digests": image_digests or ("not recorded: the deployment did not set "
                                           "QROSETTA_IMAGE_DIGESTS"),
        "outputs": {"conformance_matrix": "conformance_matrix.csv",
                    "agreement_prevalence": "agreement_prevalence.csv",
                    "performance": "performance.csv",
                    "inputs": "inputs/", "results": "results/", "errors": "errors/",
                    "readme": "README.txt"},
        "notes": notes,
    }
