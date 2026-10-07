"""In-app reproducible experiment runner.

``worker_experiment`` runs a fleet sweep over one or more preprocessing axes as a
server-side background job, reusing the batch core (``job_manager.run_batch_tasks``),
and assembles the frozen artifact bundle from ``services.experiment_artifacts`` as a ZIP in
the job's spill directory (``job_store.job_dir``), deleted with the job. Each cell's result
file is written there as the cell finishes; memory keeps only the fields the summary tables
read.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
import zipfile
from datetime import datetime, timezone

from config import server_git_sha, server_image_digests, settings
from schemas import BatchPayload, BenchmarkTask, ExperimentPayload
from services import experiment_artifacts as art
from services.dispatcher import SEED_DERIVATION
from services.export_compiled import compiled_metrics_csv, compiler_build_files
from services.job_store import job_dir
from services.run_registry import EXCLUSIVE, releases_exclusive
from services.job_manager import (
    ACTIVE_JOBS, _resolve_seed, effective_thresholds, run_batch_tasks, start_job, task_label,
    task_qubits,
)
from qrosetta_commons.helpers import get_logger
from services.circuit_resolver import resolve_circuit_qasm

logger = get_logger("rosetta-experiment")

MAX_EXPERIMENT_CELLS = 200



def _compiled_files(compiled_reports: list) -> dict:
    """compiled_circuits/<axis>/<circuit>/<key>.qasm for every compiled text,
    compiled_circuits.csv with one row per compile record, and the lock file of each
    compiler that produced output; empty when nothing was compiled."""
    files, paths = {}, {}
    for task, report in compiled_reports:
        for record in report.get("compiled_circuits") or []:
            if isinstance(record, dict) and isinstance(record.get("transpiled_qasm"), str):
                stem = re.sub(r"[^A-Za-z0-9~_-]+", "-", str(record.get("compiler"))).strip("-") or "compiler"
                path = f"compiled_circuits/{task}/{stem}.qasm"
                files[path] = art.qasm_bytes(record["transpiled_qasm"])
                paths[(task, record.get("compiler"))] = path
    if not any(report.get("compiled_circuits") for _, report in compiled_reports):
        return {}
    files["compiled_circuits.csv"] = compiled_metrics_csv(compiled_reports, paths).encode("utf-8")
    files.update({path: data for path, (data, _) in compiler_build_files(
        [r for _, r in compiled_reports], settings.get_compiler_services()).items()})
    return files

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


_BULKY_RESULT_FIELDS = frozenset({"statevector", "counts", "transpiled_qasm"})
_KEPT_REPORT_FIELDS = ("task_name", "circuit_id", "error", "seed", "git_sha", "seed_derivation",
                       "agreement_thresholds", "resolved_runners")


def _kept_record(report: dict) -> dict:
    """The fields of a cell's report that the summary tables and manifest read after the
    cell: top-level provenance, each result without its statevector, counts and circuit
    text, the pairwise agreement records and the compile records."""
    record = {k: report[k] for k in _KEPT_REPORT_FIELDS if k in report}
    record["raw_results"] = [
        {k: v for k, v in entry.items() if k not in _BULKY_RESULT_FIELDS}
        if isinstance(entry, dict) else entry
        for entry in report.get("raw_results") or []]
    divergence = report.get("divergence_report")
    if isinstance(divergence, dict):
        record["divergence_report"] = {"pairwise_agreement": divergence.get("pairwise_agreement") or []}
    if "compiled_circuits" in report:
        record["compiled_circuits"] = report["compiled_circuits"]
    return record


def _freeze_cell(report: dict, circuit: dict, axis: str, staging: str,
                 keep_statevectors: bool) -> tuple:
    """Write one cell's result file under ``staging`` and return (its conformance rows, its
    performance rows, the kept record)."""
    report["circuit_id"] = circuit["id"]
    report["task_request"] = circuit["request"]
    if not keep_statevectors:
        report = art.strip_statevectors(report)
    path = os.path.join(staging, "results", axis, f"{circuit['id']}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(json.dumps(report, indent=2, default=str).encode("utf-8"))
    return (art.build_conformance_rows(axis, [report]), art.build_performance_rows(axis, [report]),
            _kept_record(report))


def write_bundle_zip(zip_path: str, files: dict, staging: str) -> None:
    """Zip the {relative_path: bytes} files and every file under ``staging`` (by its
    relative path) to ``zip_path``, in sorted order, one staged file in memory at a time."""
    staged = {}
    for root, _, names in os.walk(staging):
        for name in names:
            full = os.path.join(root, name)
            staged[os.path.relpath(full, staging).replace(os.sep, "/")] = full
    tmp = f"{zip_path}.tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path in sorted({*files, *staged}):
            if rel_path in files:
                zf.writestr(rel_path, files[rel_path])
            else:
                with open(staged[rel_path], "rb") as fh:
                    zf.writestr(rel_path, fh.read())
    os.replace(tmp, zip_path)


@releases_exclusive
async def worker_experiment(job_id: str, payload: ExperimentPayload):
    """Background task for POST /experiments.

    Runs every resolved circuit on every preprocessing axis with one master seed, and
    writes the bundle to ``ACTIVE_JOBS[job_id]["bundle_path"]``. The number of
    circuit-axis cells is capped at MAX_EXPERIMENT_CELLS unless bypass_limits is set.
    """
    EXCLUSIVE.set(payload.exclusive)
    runner_statuses = {}
    start_job(job_id, runner_statuses)
    staging = os.path.join(job_dir(job_id), "bundle")
    try:
        resolved, resolution_errors = await asyncio.to_thread(resolve_circuits, payload)
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
            "tasks": [{"name": f"{task_label(c['algorithm'], c['qubits'], c.get('source'))} · {lbl}", "axis": lbl, "status": "queued"}
                      for lbl in axis_labels for c in resolved],
        }
        ACTIVE_JOBS[job_id]["progress"] = progress

        conformance, prevalence, performance = [], [], []
        effective_seeds, sdk_versions = {}, {}
        thresholds_per_axis, runners_per_axis = {}, {}
        all_reports: list = []
        compiled_reports: list = []
        offset = 0
        for pp, axis in zip(axes, axis_labels):
            axis_conformance, axis_records = [], []

            async def store(index: int, report: dict, axis=axis, axis_conformance=axis_conformance,
                            axis_records=axis_records):
                circuit = resolved[index]
                if report.get("agreement_thresholds") is not None:
                    thresholds_per_axis.setdefault(axis, report["agreement_thresholds"])
                if report.get("resolved_runners"):
                    runners = runners_per_axis.setdefault(
                        axis, {"dispatched": set(), "skipped": {}})
                    runners["dispatched"].update(report["resolved_runners"]["dispatched"])
                    for skip in report["resolved_runners"]["skipped"]:
                        runners["skipped"].setdefault(skip["id"], skip["reason"])
                rows, perf_rows, record = await asyncio.to_thread(
                    _freeze_cell, report, circuit, axis, staging, payload.keep_statevectors)
                axis_conformance.extend(rows)
                performance.extend(perf_rows)
                axis_records.append(record)
                compiled_reports.append((f"{axis}/{circuit['id']}", record))
                if record.get("seed") is not None:
                    effective_seeds[axis] = record["seed"]
                return record

            batch_payload = BatchPayload(
                tasks=[BenchmarkTask(algorithm=c["algorithm"], qubits=c["qubits"],
                                     qasm_string=c["qasm"], source=c["source"]) for c in resolved],
                mode=payload.mode, n_shots=payload.n_shots,
                optimization_level=payload.optimization_level,
                runner_config=payload.runner_config, runner_phases=payload.runner_phases,
                timeout_seconds=payload.timeout_seconds,
                timing_repeats=payload.timing_repeats, exclusive=payload.exclusive,
                target_simulators=payload.target_simulators,
                execution_target=payload.execution_target, bypass_limits=payload.bypass_limits,
                apply_preprocessing=bool(pp), seed=exp_seed, thresholds=payload.thresholds,
                compilers=payload.compilers,
            )
            await run_batch_tasks(batch_payload, runner_statuses, progress,
                                  batch_seed=exp_seed, task_offset=offset, store=store)
            all_reports += axis_records
            offset += len(resolved)

            for e in resolution_errors:
                conformance.append({"axis": axis, "circuit": e["name"], "simulator": "(circuit)",
                                    "status": "resolution_error",
                                    "error_signature": str(e["error"])[:300], "triage": "untriaged",
                                    "circuit_id": e["id"]})
            conformance += axis_conformance
            prevalence += art.build_prevalence_rows(axis, axis_records)
            art.collect_sdk_versions(axis_records, into=sdk_versions)

        progress["current_index"] = None

        files: dict = _compiled_files(compiled_reports)
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
        bundle_path = os.path.join(job_dir(job_id), "bundle.zip")
        await asyncio.to_thread(write_bundle_zip, bundle_path, files, staging)
        await asyncio.to_thread(shutil.rmtree, staging, True)
        if job_id not in ACTIVE_JOBS:
            await asyncio.to_thread(shutil.rmtree, job_dir(job_id), True)
            return
        ACTIVE_JOBS[job_id] = {
            "status": "completed", "kind": "experiment", "target": payload.execution_target,
            "results": {"experiment_summary": experiment_summary},
            "runner_statuses": runner_statuses, "progress": progress,
            "bundle_path": bundle_path, "bundle_name": bundle_name, "finished_at": time.time(),
        }
        logger.info(f"--- Experiment {job_id} complete: {cells} cells, {n_err} errors to triage ---")

    except Exception as e:
        logger.error(f"Experiment {job_id} failed: {e}", exc_info=True)
        await asyncio.to_thread(shutil.rmtree, job_dir(job_id), True)
        ACTIVE_JOBS[job_id] = {"status": "failed", "kind": "experiment",
                               "target": payload.execution_target,
                               "error": str(e), "runner_statuses": runner_statuses,
                               "finished_at": time.time()}
