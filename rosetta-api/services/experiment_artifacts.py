"""Pure, dependency-free builders for the reproducible-experiment artifact bundle.

This module is the SINGLE SOURCE OF TRUTH for how a fleet run is frozen into a citable
artifact (conformance matrix + agreement prevalence + manifest + statevector stripping).
It is imported by BOTH:

  * the in-app experiment runner (``services.experiment`` -> ``routers.experiment``), and
  * the standalone CLI harness (``experiments/0-experiment/run_experiment.py``),

so the two can never drift. Keep it STDLIB-ONLY (no FastAPI / pytket / numpy imports) so the
stdlib-only CLI can import it without pulling the API's runtime dependencies.

Two honest, separated outputs — never conflated:
  A) conformance matrix  — did each (circuit x simulator) cell RUN? (success/error/timeout)
  B) agreement prevalence — of the pairs that ran, did they agree, and via which transform?

An error is a *finding* only after a human triages it into (a) QRosetta adapter bug,
(b) genuine SDK bug, (c) unsupported-by-design, or (d) resource/timeout. This module records
the raw signature and marks it ``untriaged``; it NEVER auto-classifies.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json

# Column orders for the two CSV outputs (kept here so both callers write identical headers).
CONFORMANCE_FIELDS = ["axis", "circuit", "simulator", "status", "error_signature", "triage"]
PREVALENCE_FIELDS = ["axis", "agreement_class", "pair_count"]

# Plain-text integrity notice shipped at the root of every bundle. This is load-bearing:
# it is what keeps a downstream reader from mistaking the raw CSVs for findings.
TRIAGE_README = (
    "QRosetta reproducible-experiment bundle\n"
    "=======================================\n\n"
    "This folder freezes one fleet run so it can be replayed and cited. It is self-describing:\n"
    "  inputs/                  - the EXACT OpenQASM executed (never 'regenerate later')\n"
    "  results/<axis>/*.json    - per-circuit reports (statevectors stripped to a sha256 by\n"
    "                             default; metrics, labels and provenance are kept in full)\n"
    "  conformance_matrix.csv   - (A) did each circuit x simulator cell RUN? + error signature\n"
    "  agreement_prevalence.csv - (B) of the pairs that ran, which agreement class + count\n"
    "  errors/*.log             - per-simulator error signatures for quick triage\n"
    "  manifest.json            - config + git SHA + timestamp + effective seed + SDK versions\n\n"
    "INTEGRITY GATE (read before quoting anything):\n"
    "  * (A) and (B) are SEPARATE. A cell that failed to run is NOT a disagreement.\n"
    "  * The error signatures and the prevalence counts are NOT findings on their own.\n"
    "    Every error must be triaged by a human into exactly one of:\n"
    "      (a) QRosetta adapter bug   (b) genuine SDK bug\n"
    "      (c) unsupported-by-design  (d) resource / timeout\n"
    "    before it is reported as a result. The 'triage' column starts as 'untriaged'.\n"
    "  * Every agreement label already carries its transform and numerical effect in the\n"
    "    per-pair records; no transform is ever silently applied.\n"
    "  * The exhaustive qubit-permutation search is bounded (see MAX_EXHAUSTIVE_QUBIT_\n"
    "    PERMUTATION_QUBITS); larger pairs report attempted=false, not a guess. Disclose this\n"
    "    cap in any prevalence analysis.\n"
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
    """(A) One row per (circuit x simulator): did it run? + untriaged error signature."""
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
    """(B) Agreement-class counts over the pairs that ran successfully, per axis."""
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
        "Error signatures are recorded but NOT auto-triaged: classify each into adapter / SDK "
        "/ by-design / resource before treating it as a finding. Container image digests are "
        "pinned in the runner Dockerfiles (@sha256, FIX-014); record the deployed digests in "
        "'image_digests' before a citable release. The exhaustive qubit-permutation search is "
        "bounded (disclose the cap in any prevalence analysis)."
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
