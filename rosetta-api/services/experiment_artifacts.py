"""Builders for the reproducible-experiment artifact bundle.

Imported by both the in-app experiment runner (``services.experiment``) and the
standalone CLI harness (``experiments/0-experiment/run_experiment.py``). Stdlib-only
so the CLI can import it without the API's runtime dependencies.

Bundle outputs:
  A) conformance matrix  — per (circuit x simulator) run status + error signature
  B) agreement prevalence — agreement-class counts over compared pairs, with
     not_comparable pairs counted in their own rows

Error rows carry a raw signature with ``triage='untriaged'``; classification into
adapter / SDK / by-design / resource happens during review.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json

from services.report_filters import fingerprint_statevectors

CONFORMANCE_FIELDS = ["axis", "circuit", "simulator", "status", "error_signature", "triage",
                      "circuit_id"]
PREVALENCE_FIELDS = ["axis", "agreement_class", "pair_count", "pair_scope"]

NOT_COMPARABLE = "not_comparable"

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
    "                             the sorted-key JSON) and statevector_len;\n"
    "                             metrics, labels and provenance are kept in full\n"
    "  conformance_matrix.csv   - per (circuit x simulator) run status + error signature\n"
    "  agreement_prevalence.csv - agreement-class counts over compared pairs\n"
    "                             (pair_scope=compared); pairs where a side had no usable\n"
    "                             output are counted separately (pair_scope=not_comparable)\n"
    "  errors/*.log             - per-simulator error signatures\n"
    "  manifest.json            - config, git SHA, timestamp, master seed per axis (each\n"
    "                             runner's seed is derived from it; see seed_derivation and\n"
    "                             runner_seed in the results), SDK versions\n\n"
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
    """Replace each raw statevector with a sha256 + length (see fingerprint_statevectors)."""
    return fingerprint_statevectors(report, sha256)


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


def build_prevalence_rows(axis_label: str, summary: list) -> list:
    """Agreement-class counts per axis: compared pairs (``pair_scope='compared'``), then
    not_comparable pairs in their own row (``pair_scope='not_comparable'``)."""
    counts: dict = {}
    for report in summary:
        for rec in (report.get("divergence_report") or {}).get("pairwise_agreement", []) or []:
            key = rec.get("agreement", "unknown")
            counts[key] = counts.get(key, 0) + 1
    not_comparable = counts.pop(NOT_COMPARABLE, 0)
    rows = [{"axis": axis_label, "agreement_class": k, "pair_count": v, "pair_scope": "compared"}
            for k, v in sorted(counts.items())]
    if not_comparable:
        rows.append({"axis": axis_label, "agreement_class": NOT_COMPARABLE,
                     "pair_count": not_comparable, "pair_scope": NOT_COMPARABLE})
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
                    "inputs": "inputs/", "results": "results/", "errors": "errors/",
                    "readme": "README.txt"},
        "notes": notes,
    }
