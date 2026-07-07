"""Builders for the reproducible-experiment artifact bundle.

Imported by both the in-app experiment runner (``services.experiment``) and the
standalone CLI harness (``experiments/0-experiment/run_experiment.py``). Stdlib-only
so the CLI can import it without the API's runtime dependencies.

Bundle outputs:
  A) conformance matrix  — per (circuit x simulator) run status + error signature
  B) agreement prevalence — agreement-class counts over the pairs that ran

Error rows carry a raw signature with ``triage='untriaged'``; classification into
adapter / SDK / by-design / resource happens during review.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json

# Column orders for the two CSV outputs.
CONFORMANCE_FIELDS = ["axis", "circuit", "simulator", "status", "error_signature", "triage"]
PREVALENCE_FIELDS = ["axis", "agreement_class", "pair_count"]

# Plain-text notice shipped at the root of every bundle.
TRIAGE_README = (
    "QRosetta reproducible-experiment bundle\n"
    "=======================================\n\n"
    "This folder freezes one fleet run so it can be replayed and cited:\n"
    "  inputs/                  - the exact OpenQASM executed\n"
    "  results/<axis>/*.json    - per-circuit reports (statevectors stripped to a sha256 by\n"
    "                             default; metrics, labels and provenance kept in full)\n"
    "  conformance_matrix.csv   - per (circuit x simulator) run status + error signature\n"
    "  agreement_prevalence.csv - agreement-class counts over the pairs that ran\n"
    "  errors/*.log             - per-simulator error signatures\n"
    "  manifest.json            - config + git SHA + timestamp + effective seed + SDK versions\n\n"
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


def slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in str(text).lower()).strip("-") or "circuit"


def strip_statevectors(report: dict) -> dict:
    """Replace each raw statevector with a sha256 + length so results stay small but remain
    verifiable for reproducibility. Everything else (metrics, labels, provenance) is kept.

    Mutates and returns ``report`` (the caller passes a copy when it must keep the original)."""
    for r in report.get("raw_results", []) or []:
        sv = r.get("statevector")
        if sv is not None and not isinstance(sv, str):
            r["statevector"] = None
            r["statevector_sha256"] = sha256(sv)
            r["statevector_len"] = len(sv) if hasattr(sv, "__len__") else None
    return report


def _runner_status(entry: dict) -> tuple:
    if entry.get("error"):
        sig = str(entry["error"]).strip().splitlines()[0][:300]
        low = sig.lower()
        kind = "timeout" if "timeout" in low or "timed out" in low else "error"
        return kind, sig
    return "success", ""


def build_conformance_rows(axis_label: str, summary: list) -> list:
    """One row per (circuit x simulator): run status + untriaged error signature."""
    rows = []
    for report in summary:
        circuit = report.get("task_name", "?")
        if report.get("error") and not report.get("raw_results"):
            rows.append({"axis": axis_label, "circuit": circuit, "simulator": "(circuit)",
                         "status": "circuit_error", "error_signature": str(report["error"])[:300],
                         "triage": "untriaged"})
            continue
        for entry in report.get("raw_results", []) or []:
            status, sig = _runner_status(entry)
            rows.append({"axis": axis_label, "circuit": circuit,
                         "simulator": entry.get("simulator", "?"), "status": status,
                         "error_signature": sig, "triage": "untriaged" if sig else ""})
    return rows


def build_prevalence_rows(axis_label: str, summary: list) -> list:
    """Agreement-class counts over the pairs that ran successfully, per axis."""
    counts: dict = {}
    for report in summary:
        for rec in (report.get("divergence_report") or {}).get("pairwise_agreement", []) or []:
            key = rec.get("agreement", "unknown")
            counts[key] = counts.get(key, 0) + 1
    return [{"axis": axis_label, "agreement_class": k, "pair_count": v}
            for k, v in sorted(counts.items())]


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
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def build_manifest(*, config: dict, git_sha: str, api_base: str, requested_seed,
                   effective_seeds: dict, circuits: list, sdk_versions: dict,
                   image_digests: dict = None, extra_notes: str = "") -> dict:
    """Full-provenance manifest. ``circuits`` is [{id, algorithm, qubits, qasm}]."""
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
        "circuits": [{"id": c["id"], "algorithm": c["algorithm"], "qubits": c["qubits"],
                      "qasm_sha256": sha256(c["qasm"])} for c in circuits],
        "executed_sdk_versions": sdk_versions,
        "image_digests": image_digests or {},
        "outputs": {"conformance_matrix": "conformance_matrix.csv",
                    "agreement_prevalence": "agreement_prevalence.csv",
                    "inputs": "inputs/", "results": "results/", "errors": "errors/",
                    "readme": "README.txt"},
        "notes": notes,
    }
