"""In-app reproducible experiment runner.

``worker_experiment`` runs a fleet sweep over one or more preprocessing axes as a
server-side background job, reusing the batch core (``job_manager.run_batch_tasks``),
and assembles the frozen artifact bundle from ``services.experiment_artifacts`` as an
in-memory ZIP (nothing is written to server disk).
"""
from __future__ import annotations

import io
import json
import time
import zipfile
from datetime import datetime, timezone

from config import server_git_sha, server_image_digests
from schemas import BatchPayload, BenchmarkTask, ExperimentPayload
from services import experiment_artifacts as art
from services.dispatcher import SEED_DERIVATION
from services.job_manager import (
    ACTIVE_JOBS, _resolve_seed, effective_thresholds, run_batch_tasks, task_label, task_qubits,
)
from qrosetta_commons.helpers import get_logger
from services.circuit_resolver import resolve_circuit_qasm

logger = get_logger("rosetta-experiment")

MAX_EXPERIMENT_CELLS = 200


def resolve_circuits(payload: ExperimentPayload) -> tuple:
    """Resolve every configured circuit to a frozen QASM string.

    Returns (resolved, errors) where resolved = [{id, algorithm, qubits, qasm, source,
    request}] and errors = [{id, name, error}] for circuits that could not be resolved.
    ``request`` is the circuit entry as submitted (source, algorithm, qubits, literal flag). Resolution
    failures are recorded per circuit and do not abort the experiment.
    """
    resolved, errors = [], []
    for i, entry in enumerate(payload.circuits):
        source = (entry.source or "preset").lower()
        try:
            qasm = resolve_circuit_qasm(
                entry.source, entry.algorithm, entry.qubits, entry.qasm_string, mode=payload.mode
            )
        except Exception as e:
            qasm, error = None, str(e)
        qubits = task_qubits(entry, qasm)
        name = entry.name or (
            (f"{entry.algorithm}_{qubits}q" if qubits else entry.algorithm)
            if entry.algorithm else f"circuit_{i}"
        )
        cid = f"{i:03d}_{art.slug(name)}"
        if qasm is None:
            errors.append({"id": cid, "name": name, "error": error})
            continue
        resolved.append({"id": cid, "algorithm": entry.algorithm or name,
                         "qubits": qubits, "qasm": qasm, "source": source,
                         "request": {"source": source, "algorithm": entry.algorithm,
                                     "qubits": entry.qubits,
                                     "literal_qasm": bool(entry.qasm_string)}})
    return resolved, errors


def effective_config(payload: ExperimentPayload, seed, thresholds: dict,
                     dispatched: list) -> dict:
    """The request with every default it ran under filled in: the master seed used, the
    effective agreement thresholds and the runner ids actually dispatched."""
    config = payload.model_dump()
    config["seed"] = seed
    config["thresholds"] = thresholds
    config["target_simulators"] = list(dispatched)
    return config


def _axis_label(mode: str, pp: bool) -> str:
    """Axis name, e.g. 'measured_preprocOn'."""
    return f"{mode}_preproc{'On' if pp else 'Off'}"


async def worker_experiment(job_id: str, payload: ExperimentPayload):
    """Background task for POST /experiments.

    Runs every resolved circuit on every preprocessing axis with one master seed, and
    stores the bundle files in ``ACTIVE_JOBS[job_id]["bundle_files"]``. The number of
    circuit-axis cells is capped at MAX_EXPERIMENT_CELLS unless bypass_limits is set.
    """
    runner_statuses = {}
    ACTIVE_JOBS[job_id]["status"] = "processing"
    ACTIVE_JOBS[job_id]["runner_statuses"] = runner_statuses
    try:
        resolved, resolution_errors = resolve_circuits(payload)
        axes = payload.preprocessing_modes
        if not resolved:
            raise ValueError("No circuits could be resolved: "
                             + "; ".join(f"{e['name']}: {e['error']}" for e in resolution_errors))

        cells = len(resolved) * len(axes)
        if cells > MAX_EXPERIMENT_CELLS and not payload.bypass_limits:
            raise ValueError(
                f"Experiment too large: {len(resolved)} circuits x {len(axes)} axes = {cells} "
                f"circuit-axis runs exceeds the cap of {MAX_EXPERIMENT_CELLS}. Reduce the "
                f"selection or set bypass_limits.")

        exp_seed = _resolve_seed(payload.seed) if payload.mode == "measured" else None

        axis_labels = [_axis_label(payload.mode, bool(pp)) for pp in axes]
        progress = {
            "total": cells, "completed": 0, "current_index": None,
            "tasks": [{"name": f"{task_label(c['algorithm'], c['qubits'])} · {lbl}", "status": "queued"}
                      for lbl in axis_labels for c in resolved],
        }
        ACTIVE_JOBS[job_id]["progress"] = progress

        conformance, prevalence, performance = [], [], []
        effective_seeds, sdk_versions = {}, {}
        thresholds_per_axis, runners_per_axis = {}, {}
        all_reports: list = []
        result_files: dict = {}
        offset = 0
        for pp, axis in zip(axes, axis_labels):
            batch_payload = BatchPayload(
                tasks=[BenchmarkTask(algorithm=c["algorithm"], qubits=c["qubits"],
                                     qasm_string=c["qasm"], source=c["source"]) for c in resolved],
                mode=payload.mode, n_shots=payload.n_shots,
                optimization_level=payload.optimization_level,
                runner_config=payload.runner_config, runner_phases=payload.runner_phases,
                timeout_seconds=payload.timeout_seconds,
                timing_repeats=payload.timing_repeats,
                target_simulators=payload.target_simulators,
                execution_target=payload.execution_target, bypass_limits=payload.bypass_limits,
                apply_preprocessing=bool(pp), seed=exp_seed, thresholds=payload.thresholds,
            )
            summary, _ = await run_batch_tasks(batch_payload, runner_statuses, progress,
                                               batch_seed=exp_seed, task_offset=offset)
            all_reports += summary
            offset += len(resolved)

            for e in resolution_errors:
                conformance.append({"axis": axis, "circuit": e["name"], "simulator": "(circuit)",
                                    "status": "resolution_error",
                                    "error_signature": str(e["error"])[:300], "triage": "untriaged",
                                    "circuit_id": e["id"]})

            for circuit, report in zip(resolved, summary):
                report["circuit_id"] = circuit["id"]
                report["task_request"] = circuit["request"]
                if report.get("agreement_thresholds") is not None:
                    thresholds_per_axis.setdefault(axis, report["agreement_thresholds"])
                if report.get("resolved_runners"):
                    runners = runners_per_axis.setdefault(
                        axis, {"dispatched": set(), "skipped": {}})
                    runners["dispatched"].update(report["resolved_runners"]["dispatched"])
                    for skip in report["resolved_runners"]["skipped"]:
                        runners["skipped"].setdefault(skip["id"], skip["reason"])
                if not payload.keep_statevectors:
                    report = art.strip_statevectors(report)
                result_files[f"results/{axis}/{circuit['id']}.json"] = json.dumps(
                    report, indent=2, default=str).encode("utf-8")
                if report.get("seed") is not None:
                    effective_seeds[axis] = report["seed"]

            conformance += art.build_conformance_rows(axis, summary)
            prevalence += art.build_prevalence_rows(axis, summary)
            performance += art.build_performance_rows(axis, summary)
            art.collect_sdk_versions(summary, into=sdk_versions)

        progress["current_index"] = None

        files: dict = dict(result_files)
        for c in resolved:
            files[f"inputs/{c['id']}.qasm"] = art.qasm_bytes(c["qasm"])
        files["conformance_matrix.csv"] = art.csv_string(
            conformance, art.CONFORMANCE_FIELDS).encode("utf-8")
        files["performance.csv"] = art.csv_string(
            performance, art.PERFORMANCE_FIELDS).encode("utf-8")
        files["agreement_prevalence.csv"] = art.csv_string(
            prevalence, art.PREVALENCE_FIELDS).encode("utf-8")
        for sim, text in art.build_error_logs(conformance).items():
            files[f"errors/{art.slug(sim)}.log"] = text.encode("utf-8")
        files["README.txt"] = art.TRIAGE_README.encode("utf-8")

        if payload.mode == "measured":
            seed_derivation = art.recorded_value(all_reports, "seed_derivation") or SEED_DERIVATION
        else:
            seed_derivation = "not applicable (statevector mode has no sampling seed)"
        manifest = art.build_manifest(
            config=payload.model_dump(),
            git_sha=art.recorded_value(all_reports, "git_sha") or server_git_sha(),
            api_base="in-app",
            requested_seed=payload.seed, effective_seeds=effective_seeds, circuits=resolved,
            sdk_versions=sdk_versions, image_digests=server_image_digests(),
            extra_notes=(f"Resolution errors: {len(resolution_errors)}."
                         if resolution_errors else ""),
            seed_derivation=seed_derivation)
        resolved_runners = {
            axis: {"dispatched": sorted(r["dispatched"]),
                   "skipped": [{"id": k, "reason": v} for k, v in sorted(r["skipped"].items())]}
            for axis, r in runners_per_axis.items()}
        dispatched = sorted({sim for r in resolved_runners.values() for sim in r["dispatched"]})
        run_config = effective_config(payload, exp_seed,
                                      effective_thresholds(payload.thresholds), dispatched)
        manifest["effective_config"] = run_config
        manifest["effective_config_sha256"] = art.sha256(run_config)
        manifest["effective_thresholds_per_axis"] = {
            axis: thresholds_per_axis.get(axis, run_config["thresholds"]) for axis in axis_labels}
        manifest["resolved_runners_per_axis"] = resolved_runners
        manifest["job_id"] = job_id
        manifest["runner_images"] = art.collect_runner_images(all_reports)
        manifest["host_environment"] = art.collect_host_environment(all_reports)
        manifest["label"] = payload.label
        manifest["created_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["mode"] = payload.mode
        manifest["preprocessing_axes"] = axis_labels
        files["manifest.json"] = json.dumps(manifest, indent=2, default=str).encode("utf-8")

        n_err = sum(1 for r in conformance if r.get("error_signature"))
        bundle_name = f"experiment_{art.slug(payload.label) if payload.label else job_id[:8]}"

        experiment_summary = {
            "label": payload.label, "mode": payload.mode, "axes": axis_labels,
            "requested_seed": payload.seed, "effective_seeds_per_axis": effective_seeds,
            "effective_config_sha256": manifest["effective_config_sha256"],
            "resolved_runners_per_axis": resolved_runners,
            "circuits": [{"id": c["id"], "algorithm": c["algorithm"], "qubits": c["qubits"],
                          "source": c["source"]} for c in resolved],
            "resolution_errors": resolution_errors,
            "conformance": conformance, "prevalence": prevalence,
            "sdk_versions": sdk_versions, "error_count": n_err,
            "cells": cells, "bundle_ready": True, "bundle_name": bundle_name,
            "job_id": job_id,
        }
        ACTIVE_JOBS[job_id] = {
            "status": "completed", "kind": "experiment", "target": payload.execution_target,
            "results": {"experiment_summary": experiment_summary},
            "runner_statuses": runner_statuses, "progress": progress,
            "bundle_files": files, "bundle_name": bundle_name, "finished_at": time.time(),
        }
        logger.info(f"--- Experiment {job_id} complete: {cells} cells, {n_err} errors to triage ---")

    except Exception as e:
        logger.error(f"Experiment {job_id} failed: {e}", exc_info=True)
        ACTIVE_JOBS[job_id] = {"status": "failed", "kind": "experiment",
                               "target": payload.execution_target,
                               "error": str(e), "runner_statuses": runner_statuses,
                               "finished_at": time.time()}


def build_bundle_zip(files: dict) -> bytes:
    """Zip the {relative_path: bytes} bundle in memory, files in sorted order."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path in sorted(files):
            zf.writestr(rel_path, files[rel_path])
    return buf.getvalue()
