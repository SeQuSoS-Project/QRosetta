"""In-app reproducible experiment runner.

``worker_experiment`` runs a fleet sweep over one or more preprocessing axes as a
server-side background job, reusing the batch core (``job_manager.run_batch_tasks``),
and assembles the frozen artifact bundle from ``services.experiment_artifacts`` as an
in-memory ZIP (nothing is written to server disk).
"""
from __future__ import annotations

import io
import os
import time
import zipfile
from datetime import datetime, timezone

from schemas import BatchPayload, BenchmarkTask, ExperimentPayload
from services import experiment_artifacts as art
from services.job_manager import ACTIVE_JOBS, run_batch_tasks, _resolve_seed
from qrosetta_commons.helpers import get_logger
from services.circuit_resolver import resolve_circuit_qasm

logger = get_logger("rosetta-experiment")

# One experiment = circuits x axes x fleet. Caps the circuit-axis units so a request
# cannot spawn an unbounded number of runner calls / K8s Job pods (bypass_limits skips it).
MAX_EXPERIMENT_CELLS = 200


def _server_git_sha() -> str:
    """Git SHA injected at build/deploy time; the API image ships no .git, so this
    reports 'unknown' when the env slot is unset."""
    return (os.getenv("QROSETTA_GIT_SHA") or os.getenv("GIT_SHA") or "unknown").strip() or "unknown"


def _server_image_digests() -> dict:
    """Deployed container image digests, if injected at deploy time (JSON env)."""
    raw = os.getenv("QROSETTA_IMAGE_DIGESTS")
    if not raw:
        return {}
    try:
        import json
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


def resolve_circuits(payload: ExperimentPayload) -> tuple:
    """Resolve every configured circuit to a frozen QASM string.

    Returns (resolved, errors) where resolved = [{id, algorithm, qubits, qasm, source}] and
    errors = [{id, name, error}] for circuits that could not be resolved. Resolution
    failures are recorded per circuit and do not abort the experiment.
    """
    resolved, errors = [], []
    for i, entry in enumerate(payload.circuits):
        source = (entry.source or "preset").lower()
        name = entry.name or (
            f"{entry.algorithm}_{entry.qubits}q" if entry.algorithm else f"circuit_{i}"
        )
        cid = f"{i:03d}_{art.slug(name)}"
        try:
            qasm = resolve_circuit_qasm(
                entry.source, entry.algorithm, entry.qubits, entry.qasm_string, mode=payload.mode
            )
            resolved.append({"id": cid, "algorithm": entry.algorithm or name,
                             "qubits": int(entry.qubits or 0), "qasm": qasm, "source": source})
        except Exception as e:
            errors.append({"id": cid, "name": name, "error": str(e)})
    return resolved, errors


def _axis_label(mode: str, pp: bool) -> str:
    return f"{mode}_preproc{'On' if pp else 'Off'}"


async def worker_experiment(job_id: str, payload: ExperimentPayload):
    runner_statuses = {}
    ACTIVE_JOBS[job_id]["status"] = "processing"
    ACTIVE_JOBS[job_id]["runner_statuses"] = runner_statuses
    try:
        resolved, resolution_errors = resolve_circuits(payload)
        axes = payload.preprocessing_modes or [True]
        if not resolved:
            raise ValueError("No circuits could be resolved: "
                             + "; ".join(f"{e['name']}: {e['error']}" for e in resolution_errors))

        cells = len(resolved) * len(axes)
        if cells > MAX_EXPERIMENT_CELLS and not payload.bypass_limits:
            raise ValueError(
                f"Experiment too large: {len(resolved)} circuits x {len(axes)} axes = {cells} "
                f"circuit-axis runs exceeds the cap of {MAX_EXPERIMENT_CELLS}. Reduce the "
                f"selection or set bypass_limits.")

        # One seed shared across every circuit and axis (measured mode; statevector is
        # exact and seedless).
        exp_seed = _resolve_seed(payload.seed) if payload.mode == "measured" else None

        # Cumulative progress across all axes, in the exact shape the batch UI already renders.
        axis_labels = [_axis_label(payload.mode, bool(pp)) for pp in axes]
        progress = {
            "total": cells, "completed": 0, "current_index": None,
            "tasks": [{"name": f"{c['algorithm']} ({c['qubits']}q) · {lbl}", "status": "queued"}
                      for lbl in axis_labels for c in resolved],
        }
        ACTIVE_JOBS[job_id]["progress"] = progress

        conformance, prevalence = [], []
        effective_seeds, sdk_versions = {}, {}
        result_files: dict = {}  # results/<axis>/<slug>.json -> bytes
        offset = 0
        for pp, axis in zip(axes, axis_labels):
            batch_payload = BatchPayload(
                tasks=[BenchmarkTask(algorithm=c["algorithm"], qubits=c["qubits"],
                                     qasm_string=c["qasm"]) for c in resolved],
                mode=payload.mode, n_shots=payload.n_shots,
                optimization_level=payload.optimization_level,
                runner_config=payload.runner_config, runner_phases=payload.runner_phases,
                timeout_seconds=payload.timeout_seconds,
                target_simulators=payload.target_simulators,
                execution_target=payload.execution_target, bypass_limits=payload.bypass_limits,
                apply_preprocessing=bool(pp), seed=exp_seed, thresholds=payload.thresholds,
            )
            summary, _ = await run_batch_tasks(batch_payload, runner_statuses, progress,
                                               batch_seed=exp_seed, task_offset=offset)
            offset += len(resolved)

            # Add rows for circuits that never made it into the batch (resolution failures).
            for e in resolution_errors:
                conformance.append({"axis": axis, "circuit": e["name"], "simulator": "(circuit)",
                                    "status": "resolution_error",
                                    "error_signature": str(e["error"])[:300], "triage": "untriaged"})

            import json
            for report in summary:
                if not payload.keep_statevectors:
                    report = art.strip_statevectors(report)
                cid = art.slug(report.get("task_name", "circuit"))
                result_files[f"results/{axis}/{cid}.json"] = json.dumps(
                    report, indent=2, default=str).encode("utf-8")
                if report.get("seed") is not None:
                    effective_seeds[axis] = report["seed"]

            conformance += art.build_conformance_rows(axis, summary)
            prevalence += art.build_prevalence_rows(axis, summary)
            art.collect_sdk_versions(summary, into=sdk_versions)

        progress["current_index"] = None

        # --- assemble the frozen bundle (in memory; nothing persisted to disk) ---
        files: dict = dict(result_files)
        for c in resolved:
            files[f"inputs/{c['id']}.qasm"] = c["qasm"].encode("utf-8")
        files["conformance_matrix.csv"] = art.csv_string(
            conformance, art.CONFORMANCE_FIELDS).encode("utf-8")
        files["agreement_prevalence.csv"] = art.csv_string(
            prevalence, art.PREVALENCE_FIELDS).encode("utf-8")
        for sim, text in art.build_error_logs(conformance).items():
            files[f"errors/{art.slug(sim)}.log"] = text.encode("utf-8")
        files["README.txt"] = art.TRIAGE_README.encode("utf-8")

        manifest = art.build_manifest(
            config=payload.model_dump(), git_sha=_server_git_sha(), api_base="in-app",
            requested_seed=payload.seed, effective_seeds=effective_seeds, circuits=resolved,
            sdk_versions=sdk_versions, image_digests=_server_image_digests(),
            extra_notes=(f"Resolution errors: {len(resolution_errors)}."
                         if resolution_errors else ""))
        manifest["label"] = payload.label
        manifest["created_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["mode"] = payload.mode
        manifest["preprocessing_axes"] = axis_labels
        import json
        files["manifest.json"] = json.dumps(manifest, indent=2, default=str).encode("utf-8")

        n_err = sum(1 for r in conformance if r.get("error_signature"))
        bundle_name = f"experiment_{art.slug(payload.label) if payload.label else job_id[:8]}"

        # JSON-safe summary for the UI (bundle bytes are kept OUT of results so /jobs stays
        # serializable; the ZIP is fetched from GET /experiments/{id}/bundle).
        experiment_summary = {
            "label": payload.label, "mode": payload.mode, "axes": axis_labels,
            "requested_seed": payload.seed, "effective_seeds_per_axis": effective_seeds,
            "circuits": [{"id": c["id"], "algorithm": c["algorithm"], "qubits": c["qubits"],
                          "source": c["source"]} for c in resolved],
            "resolution_errors": resolution_errors,
            "conformance": conformance, "prevalence": prevalence,
            "sdk_versions": sdk_versions, "error_count": n_err,
            "cells": cells, "bundle_ready": True, "bundle_name": bundle_name,
        }
        ACTIVE_JOBS[job_id] = {
            "status": "completed", "target": payload.execution_target,
            "results": {"experiment_summary": experiment_summary},
            "runner_statuses": runner_statuses, "progress": progress,
            "bundle_files": files, "bundle_name": bundle_name, "finished_at": time.time(),
        }
        logger.info(f"--- Experiment {job_id} complete: {cells} cells, {n_err} errors to triage ---")

    except Exception as e:
        logger.error(f"Experiment {job_id} failed: {e}", exc_info=True)
        ACTIVE_JOBS[job_id] = {"status": "failed", "target": payload.execution_target,
                               "error": str(e), "runner_statuses": runner_statuses,
                               "finished_at": time.time()}


def build_bundle_zip(files: dict) -> bytes:
    """Zip the assembled {relative_path: bytes} bundle in memory (deterministic file order)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path in sorted(files):
            zf.writestr(rel_path, files[rel_path])
    return buf.getvalue()
