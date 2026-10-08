"""RO-Crate 1.1 export (Process Run Crate profile) of a single-circuit or batch report."""

import copy
import io
import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from config import settings
from qrosetta_commons.helpers import get_logger
from services.export_compiled import (
    COMPILED_METRICS_PATH, compile_actions, compile_provenance, compiled_circuit_files,
    compiled_metrics_csv, compiler_applications, compiler_keys, compiler_build_entity,
    compiler_build_files, strip_compiled_text,
)
from services.analysis.divergence.common import (
    ANALYSIS_VERSION, DEFAULT_FIDELITY_TOLERANCE, DEFAULT_HELLINGER_THRESHOLD,
    DEFAULT_JS_THRESHOLD, DEFAULT_NORM_TOLERANCE, DEFAULT_PHASE_TOLERANCE,
)
from services.experiment_artifacts import sha256 as _json_sha256
from services.report_filters import (
    OMITTED_FOR_DISPLAY,
    fingerprint_statevectors,
    is_display_placeholder,
    remove_statevectors,
    statevector_inventory,
)

logger = get_logger("rosetta-exporter")

PROCESS_RUN_CRATE_PROFILE = "https://w3id.org/ro/wfrun/process/0.5"
REPOSITORY_URL = "https://github.com/SeQuSoS-Project/QRosetta"
_GIT_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_ACTION_STATUS_COMPLETED = "http://schema.org/CompletedActionStatus"
_ACTION_STATUS_FAILED = "http://schema.org/FailedActionStatus"
NOT_RECORDED = "not recorded"

_RUN_CONFIG_FIELDS = (
    "execution_mode", "platform_version", "git_sha", "image_digests", "apply_preprocessing",
    "optimization_level", "runner_config", "runner_phases", "effective_runner_phases",
    "exclusive", "timeout_seconds", "timing_repeats", "timing_statistic",
    "timeout_scope", "agreement_thresholds", "n_shots", "seed", "seed_derivation",
    "bypass_limits", "started_at", "finished_at",
)


_THRESHOLD_DEFAULTS = {
    "statevector": {"fidelity_tolerance": DEFAULT_FIDELITY_TOLERANCE,
                    "phase_tolerance": DEFAULT_PHASE_TOLERANCE,
                    "norm_tolerance": DEFAULT_NORM_TOLERANCE},
    "measured": {"js_threshold": DEFAULT_JS_THRESHOLD,
                 "hellinger_threshold": DEFAULT_HELLINGER_THRESHOLD},
}


def _recorded_commit(ctx: "ExportContext") -> Optional[str]:
    """The report's git_sha when it is a hexadecimal commit id, else None."""
    sha = _shared_scalar(ctx, "git_sha")
    sha = str(sha).strip().lower() if sha else ""
    return sha if _GIT_SHA.match(sha) else None


def _source_url(ctx: "ExportContext", path: str = "") -> str:
    """Repository URL pinned to the recorded commit: the commit page for the whole tree,
    ``tree/<sha>/<path>`` for a directory; the repository root when no commit is recorded."""
    sha = _recorded_commit(ctx)
    if not sha:
        return REPOSITORY_URL
    return f"{REPOSITORY_URL}/tree/{sha}/{path}" if path else f"{REPOSITORY_URL}/commit/{sha}"


def _entity_ref_id(key: str) -> str:
    """Sanitize a (possibly virtual '~opt~run') runner key into a safe @id fragment."""
    return (key or "unknown").replace("~", "-").replace(" ", "_")


_ARTIFACT_ENCODING = {
    "svg": "image/svg+xml", "png": "image/png", "pdf": "application/pdf",
    "csv": "text/csv", "latex": "application/x-latex", "tex": "application/x-latex",
    "html": "text/html", "md": "text/markdown", "markdown": "text/markdown",
    "txt": "text/plain", "json": "application/json",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _artifact_encoding_format(path: str) -> str:
    return _ARTIFACT_ENCODING.get(path.rsplit(".", 1)[-1], "application/octet-stream")


def _generate_publication_artifacts(ctx: "ExportContext") -> tuple:
    """(files, descriptions) for the requested publication figures/tables; ({}, {}) when
    none are requested. ``categories`` stand for their views at the defaults
    (categories_to_items). A batch report gets one set per task under figures/<task_id>/,
    tables/<task_id>/ and reference/<task_id>/; a parameter error names the task. The
    publication engine (and matplotlib) is imported only then."""
    sel = ctx.publication_artifacts
    if not sel or not (sel.get("categories") or sel.get("items")):
        return {}, {}
    from services.publication import ParameterError, build_publication_items, categories_to_items
    items = categories_to_items(sel.get("categories") or [], sel.get("figure_formats") or ["svg"],
                                sel.get("table_formats") or ["csv"]) + list(sel.get("items") or [])
    files: Dict[str, bytes] = {}
    descriptions: Dict[str, str] = {}
    for task in _iter_tasks(ctx):
        report = task.report
        try:
            built, described = build_publication_items(report, ctx.mode, items, task=task.label)
        except ParameterError as exc:
            if task.task_id is None:
                raise
            raise ParameterError(f"circuit {task.label}: {exc}") from None
        for path, data in built.items():
            if task.task_id is None:
                files[path] = data
                descriptions[path] = described.get(path, "")
                continue
            folder, name = path.split("/", 1)
            scoped = f"{folder}/{task.task_id}/{name}"
            files[scoped] = data
            descriptions[scoped] = f"Task {task.label}. " + described.get(path, "")
    return files, descriptions


@dataclass
class _TaskView:
    """One circuit within the export.

    A single-circuit report yields one view with ``task_id=None`` (paths at the crate root,
    ``#run-<runner>`` ids). A batch report (``{"benchmark_summary": [...]}``) yields one
    view per task, with paths and ids scoped by ``task_id``.
    """
    task_id: Optional[str]
    label: Optional[str]
    input_qasm: str
    raw_results: List[dict]
    report: dict = field(default_factory=dict)


def _slugify(name: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return slug or fallback


def _iter_tasks(ctx: "ExportContext") -> List[_TaskView]:
    benchmark_summary = ctx.results.get("benchmark_summary")
    if isinstance(benchmark_summary, list) and benchmark_summary:
        tasks: List[_TaskView] = []
        seen_ids = set()
        for i, task_result in enumerate(benchmark_summary):
            if not isinstance(task_result, dict):
                continue
            label = task_result.get("task_name") or f"task {i}"
            task_id = _slugify(label, f"task-{i}")
            base_id, suffix = task_id, 1
            while task_id in seen_ids:
                suffix += 1
                task_id = f"{base_id}-{suffix}"
            seen_ids.add(task_id)
            tasks.append(_TaskView(
                task_id=task_id,
                label=label,
                input_qasm=task_result.get("input_qasm", ""),
                raw_results=[r for r in task_result.get("raw_results", []) if isinstance(r, dict)],
                report=task_result,
            ))
        return tasks
    return [_TaskView(
        task_id=None,
        label=None,
        input_qasm=ctx.qasm_string,
        raw_results=[r for r in ctx.results.get("raw_results", []) if isinstance(r, dict)],
        report=ctx.results,
    )]


def _circuit_path(task: _TaskView) -> str:
    return "circuit.qasm" if task.task_id is None else f"circuits/{task.task_id}.qasm"


RUNNER_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(~opt\d+~run\d+)?$")


def _file_stem(sim: str) -> str:
    """``sim`` with every character outside [A-Za-z0-9~_-] replaced, safe as a file name."""
    return re.sub(r"[^A-Za-z0-9~_-]+", "-", str(sim)).strip("-") or "runner"


def invalid_runner_keys(results: dict) -> list:
    """Simulator keys in a report (single or batch) that are not runner ids or
    ``<id>~opt<L>~run<N>`` self-comparison keys."""
    reports = results.get("benchmark_summary") if isinstance(results.get("benchmark_summary"), list) else [results]
    bad = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        for r in report.get("raw_results") or []:
            sim = r.get("simulator") if isinstance(r, dict) else None
            if sim is not None and not RUNNER_KEY_RE.match(str(sim)):
                bad.append(str(sim))
        for record in report.get("dispatched_circuits") or []:
            for sim in (record.get("runners") or []) if isinstance(record, dict) else []:
                if not RUNNER_KEY_RE.match(str(sim)):
                    bad.append(str(sim))
        bad += [key for key in compiler_keys(report) if not RUNNER_KEY_RE.match(key)]
    return sorted(set(bad))


def _compiled_files(task: _TaskView) -> List[dict]:
    return compiled_circuit_files(task.report, task.task_id, task.label,
                                  lambda folder, key: _task_scoped_path(folder, task, key))


def _task_scoped_path(folder: str, task: _TaskView, sim: str) -> str:
    stem = _file_stem(sim)
    return f"{folder}/{stem}.qasm" if task.task_id is None else f"{folder}/{task.task_id}/{stem}.qasm"


def _member(dir_name: str, rel_path: str) -> str:
    """``dir_name/rel_path``; ValueError for a path that is absolute or has a '..' part."""
    parts = str(rel_path).replace("\\", "/").split("/")
    if str(rel_path).startswith("/") or any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"unsafe path in export: {rel_path!r}")
    return f"{dir_name}/{rel_path}"


def _batch_tasks(results: dict) -> list:
    summary = results.get("benchmark_summary")
    return [t for t in summary if isinstance(t, dict)] if isinstance(summary, list) else []


def _shared_scalar(ctx: "ExportContext", key: str):
    """A report-wide value: the top-level copy, else the copy in the first batch task that
    records it (a task that failed before dispatch records none)."""
    if key in ctx.results:
        return ctx.results.get(key)
    return next((t.get(key) for t in _batch_tasks(ctx.results) if key in t), None)


def infer_export_mode(results: dict) -> str:
    """The report's own ``mode`` when it records one; else 'measured' if the report or any
    batch task has n_shots, else 'statevector'."""
    if results.get("mode") in ("statevector", "measured"):
        return results["mode"]
    if "n_shots" in results or any("n_shots" in t for t in _batch_tasks(results)):
        return "measured"
    return "statevector"


REPORT_SOURCES = {
    "server_job": ("This crate was built from the server's own copy of a job it ran."),
    "upload": ("This crate was built from a saved run whose report its owner uploaded; its "
               "contents are as the owner supplied them, not produced by this server's run."),
    "not_recorded": ("This crate was built from a saved run stored before the server recorded "
                     "where saved reports come from."),
    "client_supplied": ("This crate was built from a report supplied in the export request. Its "
                        "contents, including any git SHA, platform version, SDK versions and "
                        "circuit texts, are as the requester supplied them; this server did not "
                        "produce or check them."),
}


def _report_source(results: dict, route: str) -> str:
    if route == "server_job":
        return "server_job"
    if route == "saved_run":
        saved = results.get("saved_from")
        return saved if saved in ("server_job", "upload") else "not_recorded"
    return "client_supplied"


def build_export_context(results: dict, payload, route: str = "client_request") -> "ExportContext":
    """Assemble an ExportContext from a report and an ExportPayload. ``route`` is how the
    export obtained the report: ``server_job`` (the server's copy of a job), ``saved_run``
    (a run from history) or ``client_request`` (the request body); it decides the crate's
    recorded report_source, which no report field can override."""
    source = _report_source(results, route)
    results = {**{k: v for k, v in results.items() if k != "saved_from"},
               **({"saved_from": source} if source in ("server_job", "upload") else {})}
    return ExportContext(
        qasm_string=results.get("input_qasm", results.get("qasm_string", "")),
        results=results,
        report_source=source,
        mode=infer_export_mode(results),
        runner_services=settings.get_runner_services(),
        include_statevectors=payload.include_statevectors,
        author_name=payload.author_name,
        author_affiliation=payload.author_affiliation,
        publication_artifacts=(
            payload.publication_artifacts.model_dump()
            if payload.publication_artifacts else None
        ),
    )


def _canonical_sim_id(simulator: str) -> str:
    """Strip a '~opt~run' suffix back to the canonical runner id."""
    return (simulator or "").split("~", 1)[0]


class ExportFormat(str, Enum):
    """Supported export formats."""
    RO_CRATE = "ro-crate"


@dataclass
class ExportContext:
    """Everything an export format needs.

    ``runner_services`` is the exporting server's registry, used only when the report
    carries no ``runner_registry`` recorded at run time. ``timestamp`` is the export time
    (millisecond ISO 8601).
    """
    qasm_string: str
    results: dict
    mode: str
    runner_services: Dict[str, Any]
    report_source: str = "client_supplied"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    )
    include_statevectors: bool = False
    author_name: Optional[str] = None
    author_affiliation: Optional[str] = None
    publication_artifacts: Optional[Dict[str, Any]] = None
    circuit_features: Optional[Dict[str, Any]] = None
    suite_source: Optional[str] = None
    hardware_anchor: Optional[Dict[str, Any]] = None


# --- report lookups --------------------------------------------------------------------

def _runner_dir_name(svc: dict) -> str:
    """Runner directory / infrastructure name from a registry entry's base_url."""
    return (svc or {}).get("base_url", "").split("://", 1)[-1].split(":", 1)[0].split("/", 1)[0]


def _runner_base_paths(dir_name: str) -> List[str]:
    return [
        os.path.join(os.getcwd(), "runners", dir_name),
        os.path.join(os.getcwd(), "..", "runners", dir_name),
    ]


def _read_runner_lock(dir_name: str) -> Optional[bytes]:
    """The runner's requirements.lock bytes, or None when not on disk."""
    for base in _runner_base_paths(dir_name):
        path = os.path.join(base, "requirements.lock")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return f.read()
            except OSError:
                return None
    return None


def _runner_lock_files(ctx: "ExportContext") -> Dict[str, bytes]:
    """{crate path: bytes} of requirements.lock for each runner used, where found on disk."""
    out: Dict[str, bytes] = {}
    for runner in _extract_runners_used(ctx):
        dir_name = _runner_dir_name(ctx.runner_services.get(_canonical_sim_id(runner), {}))
        if not dir_name or f"runners/{dir_name}/requirements.lock" in out:
            continue
        data = _read_runner_lock(dir_name)
        if data is not None:
            out[f"runners/{dir_name}/requirements.lock"] = data
    return out


def _get_runner_version(runner_id: str) -> str:
    """Quantum-SDK pins from the runner's requirements.txt, or 'unknown'."""
    svc = settings.get_runner_services().get(runner_id)
    if not svc:
        return "unknown"
    dir_name = _runner_dir_name(svc)
    if not dir_name:
        return "unknown"

    base_paths = _runner_base_paths(dir_name)

    versions = []
    keywords = ["qiskit", "cirq", "qulacs", "pennylane", "qibo", "pytket", "cuquantum",
                "torch", "quimb", "myqlm", "qrisp", "pyquil"]
    for base in base_paths:
        req_path = os.path.join(base, "requirements.txt")
        if os.path.exists(req_path):
            try:
                with open(req_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if "==" in line:
                            pkg_name, pkg_version = line.split("==", 1)
                            if any(k in pkg_name.lower() for k in keywords):
                                versions.append(f"{pkg_name.strip()} {pkg_version.strip()}")
                    if not versions:
                        f.seek(0)
                        for line in f:
                            if "==" in line:
                                versions.append(line.strip().replace("==", " "))
                                break
            except Exception:
                pass
            break

    return ", ".join(versions) if versions else "unknown"


def _iter_raw_results(ctx: ExportContext):
    """Yield every per-runner raw result across single runs and batch summaries."""
    for task in _iter_tasks(ctx):
        yield from task.raw_results


def _extract_sdk_versions(ctx: ExportContext, runner_name: str) -> dict:
    """SDK versions the runner reported in its result, or {}."""
    for r in _iter_raw_results(ctx):
        if r.get("simulator") == runner_name:
            versions = r.get("sdk_versions")
            if isinstance(versions, dict) and versions:
                return versions
    return {}


def _extract_runners_used(ctx: ExportContext) -> List[str]:
    runners_used: List[str] = []
    for r in _iter_raw_results(ctx):
        sim = r.get("simulator")
        if sim and sim not in runners_used:
            runners_used.append(sim)
    return runners_used


def _dispatched_circuit_files(task: _TaskView) -> List[dict]:
    """``[{sim, path, qasm, group, api_preprocessing_applied}]`` for every runner key the
    report records a dispatched circuit for."""
    files = []
    for record in task.report.get("dispatched_circuits") or []:
        if not isinstance(record, dict) or not record.get("qasm"):
            continue
        for sim in record.get("runners") or []:
            if sim:
                files.append({
                    "sim": sim,
                    "path": _task_scoped_path("dispatched_circuits", task, sim),
                    "qasm": record["qasm"],
                    "group": record.get("group"),
                    "api_preprocessing_applied": record.get("api_preprocessing_applied") or [],
                })
    return files


def _transpiled_circuit_files(task: _TaskView) -> List[dict]:
    """``[{sim, path, qasm}]`` for the first transpiled_qasm each runner key reported."""
    files, seen = [], set()
    for r in task.raw_results:
        sim, tq = r.get("simulator"), r.get("transpiled_qasm")
        if tq and sim and sim not in seen:
            seen.add(sim)
            files.append({"sim": sim, "path": _task_scoped_path("transpiled_circuits", task, sim),
                          "qasm": tq})
    return files


def _iter_pairwise_agreement_records(ctx: ExportContext):
    for task in _iter_tasks(ctx):
        divergence_report = task.report.get("divergence_report")
        if isinstance(divergence_report, dict):
            for record in divergence_report.get("pairwise_agreement", []) or []:
                if isinstance(record, dict):
                    yield record


def _increment_nested_count(target: dict, *keys: str) -> None:
    current = target
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    leaf = keys[-1]
    current[leaf] = current.get(leaf, 0) + 1


def _build_pairwise_agreement_summary(ctx: ExportContext) -> Optional[dict]:
    records = list(_iter_pairwise_agreement_records(ctx))
    if not records:
        return None

    summary = {
        "location": "results.json divergence_report.pairwise_agreement",
        "record_count": len(records),
        "by_mode": {},
        "by_agreement": {},
        "by_registered_transform": {},
        "by_statistical_verdict": {},
        "by_measured_assessment": {},
        "by_marginal_assessment": {},
        "description": (
            "Counts of agreement labels, registered transforms, and (for measured "
            "mode) shot-noise statistical verdicts, measured assessments and single-bit "
            "marginal assessments (marginal_distinguishable: a classical bit's marginal "
            "differs after Holm's correction, so the distributions differ). The full "
            "per-pair metrics and provenance records are preserved in results.json."
        ),
    }
    for record in records:
        mode = record.get("mode") or "unknown"
        agreement = record.get("agreement") or "unknown"
        transform = record.get("registered_transform") or "none"
        summary["by_mode"][mode] = summary["by_mode"].get(mode, 0) + 1
        _increment_nested_count(summary["by_agreement"], mode, agreement)
        _increment_nested_count(summary["by_registered_transform"], mode, transform)
        verdict = ((record.get("metrics") or {}).get("statistical_test") or {}).get("verdict")
        if verdict:
            _increment_nested_count(summary["by_statistical_verdict"], mode, verdict)
        if record.get("measured_assessment"):
            _increment_nested_count(summary["by_measured_assessment"], mode,
                                    record["measured_assessment"])
        if record.get("marginal_assessment"):
            _increment_nested_count(summary["by_marginal_assessment"], mode,
                                    record["marginal_assessment"])

    for key in ("by_statistical_verdict", "by_measured_assessment", "by_marginal_assessment"):
        if not summary[key]:
            del summary[key]
    return summary


# --- provenance.json -------------------------------------------------------------------

def _run_configuration(ctx: ExportContext) -> dict:
    """Run-time configuration recorded in the report; 'not recorded' for absent fields."""
    config = {}
    for key in _RUN_CONFIG_FIELDS:
        value = _shared_scalar(ctx, key)
        if key in ("n_shots", "seed", "seed_derivation") and ctx.mode != "measured":
            continue
        config[key] = NOT_RECORDED if value is None else value
    requested = _shared_scalar(ctx, "agreement_thresholds")
    config["agreement_thresholds"] = _effective_thresholds(ctx, requested)
    config["agreement_thresholds_requested"] = (
        requested if requested is not None else "none (defaults applied)")
    config["analysis_version"] = _analysis_version(ctx)
    tasks = _iter_tasks(ctx)
    if config.get("effective_runner_phases") == NOT_RECORDED:
        phases = {r["simulator"]: r["dispatch_phase"] for t in tasks[:1]
                  for r in t.report.get("raw_results") or []
                  if isinstance(r, dict) and r.get("simulator") and "dispatch_phase" in r}
        if phases:
            config["effective_runner_phases"] = phases
    if any(t.task_id is not None for t in tasks):
        config["agreement_thresholds_by_task"] = {
            t.task_id: _task_effective_thresholds(ctx, t, requested) for t in tasks}
        config["task_requests"] = {
            t.task_id: {"task_name": t.label,
                        "request": t.report.get("task_request", NOT_RECORDED)}
            for t in tasks}
    if ctx.mode == "measured" and config.get("seed_derivation") == NOT_RECORDED:
        config["seed_derivation"] = "not recorded (every runner received the report seed unchanged)"
    return config


def _effective_thresholds(ctx: ExportContext, requested) -> dict:
    """Thresholds the analysis applied for this mode: the first report's recorded
    agreement_thresholds when present; otherwise defaults, overridden by the request's
    non-null values, overridden by the values recorded in the pairwise records."""
    tasks = _iter_tasks(ctx)
    return _task_effective_thresholds(ctx, tasks[0], requested) if tasks else dict(
        _THRESHOLD_DEFAULTS.get(ctx.mode, {}))


def _task_effective_thresholds(ctx: ExportContext, task: "_TaskView", requested) -> dict:
    """Effective thresholds of one report (see _effective_thresholds)."""
    divergence_report = task.report.get("divergence_report")
    recorded = (divergence_report or {}).get("agreement_thresholds") \
        if isinstance(divergence_report, dict) else None
    if isinstance(recorded, dict) and recorded:
        return dict(recorded)
    effective = dict(_THRESHOLD_DEFAULTS.get(ctx.mode, {}))
    for key, value in (requested if isinstance(requested, dict) else {}).items():
        if key in effective and value is not None:
            effective[key] = value
    pending = set(effective)
    records = (divergence_report or {}).get("pairwise_agreement") \
        if isinstance(divergence_report, dict) else None
    for record in records or []:
        metrics = (record or {}).get("metrics") or {}
        for key in list(pending):
            if metrics.get(key) is not None:
                effective[key] = metrics[key]
                pending.discard(key)
        if not pending:
            break
    return effective


def _analysis_version(ctx: ExportContext):
    """The divergence reports' analysis_version: one string when every report agrees, else
    {task_id: version}. Reports that predate the field are "not recorded"."""
    versions = {}
    for task in _iter_tasks(ctx):
        divergence_report = task.report.get("divergence_report")
        version = (divergence_report.get("analysis_version")
                   if isinstance(divergence_report, dict) else None)
        versions[task.task_id] = version or NOT_RECORDED
    distinct = set(versions.values())
    if len(distinct) == 1:
        return distinct.pop()
    return versions


def _per_task(ctx: ExportContext, fn) -> Any:
    """``fn(task)`` for a single-circuit report, ``{task_id: fn(task)}`` for a batch."""
    tasks = _iter_tasks(ctx)
    if len(tasks) == 1 and tasks[0].task_id is None:
        return fn(tasks[0])
    return {t.task_id: fn(t) for t in tasks}


def _recorded_registry(ctx: ExportContext) -> tuple:
    """(registry, source): the run-time registry when recorded, else the exporter's."""
    recorded = _shared_scalar(ctx, "runner_registry")
    if isinstance(recorded, dict) and recorded:
        return recorded, "recorded at run time"
    return ctx.runner_services, "exporting server configuration (not recorded at run time)"


def _build_provenance(ctx: ExportContext) -> dict:
    """provenance.json: run configuration, per-runner registry entries, seeds and images."""
    runners_used = _extract_runners_used(ctx)
    registry, registry_source = _recorded_registry(ctx)
    tasks = _iter_tasks(ctx)
    is_batch = any(t.task_id is not None for t in tasks)

    runner_configs = {}
    for name in runners_used:
        svc = registry.get(_canonical_sim_id(name), {})
        per_task = {}
        for task in tasks:
            for r in task.raw_results:
                if r.get("simulator") == name:
                    per_task[task.task_id] = r
                    break
        first = next(iter(per_task.values()), {})
        entry = {
            "enabled": svc.get("enabled", False),
            "capabilities": svc.get("capabilities", []),
            "optimization_levels": {str(k): v for k, v in svc.get("optimization_levels", {}).items()},
            "sdk_versions": _extract_sdk_versions(ctx, name),
            "runner_image": first.get("runner_image", NOT_RECORDED),
        }
        if is_batch:
            entry["preprocessing_applied_by_task"] = {
                tid: r.get("preprocessing_applied", []) for tid, r in per_task.items()}
            if ctx.mode == "measured":
                entry["runner_seed_by_task"] = {
                    tid: r.get("runner_seed", NOT_RECORDED) for tid, r in per_task.items()}
        else:
            entry["preprocessing_applied"] = first.get("preprocessing_applied", [])
            if ctx.mode == "measured":
                entry["runner_seed"] = first.get("runner_seed", NOT_RECORDED)
        if ctx.mode == "measured":
            entry["seed_honoured"] = first.get("seed_honoured", svc.get("honours_seed", NOT_RECORDED))
        runner_configs[name] = entry

    provenance = {
        "platform": "Quantum Rosetta",
        "exporter_platform_version": settings.PLATFORM_VERSION,
        "exporter_analysis_version": ANALYSIS_VERSION,
        "export_timestamp": ctx.timestamp,
        "execution_mode": ctx.mode,
        "canonical_input_format": "OpenQASM 2.0",
        "run_configuration": _run_configuration(ctx),
        "api_preprocessing_applied": _per_task(
            ctx, lambda t: t.report.get("api_preprocessing_applied", NOT_RECORDED)),
        "runner_registry_source": registry_source,
        "runners_used": runners_used,
        "runner_configurations": runner_configs,
    }

    pairwise_summary = _build_pairwise_agreement_summary(ctx)
    if pairwise_summary:
        provenance["pairwise_agreement_evidence"] = pairwise_summary
    if ctx.suite_source:
        provenance["suite_source"] = ctx.suite_source
    if ctx.circuit_features:
        provenance["circuit_features"] = ctx.circuit_features
    if ctx.hardware_anchor:
        provenance["hardware_anchor"] = ctx.hardware_anchor
    provenance["report_source"] = ctx.report_source
    provenance["report_source_meaning"] = REPORT_SOURCES[ctx.report_source]
    compiles = compile_provenance([(t.task_id, t.report) for t in tasks])
    if compiles:
        provenance["compile_only_services"] = compiles
    return provenance


def _statevector_description(ctx: ExportContext) -> str:
    """Sentence for results.json describing which statevectors it carries."""
    if ctx.mode != "statevector":
        return ""
    if not ctx.include_statevectors:
        return (" Raw statevectors excluded from this export; each result that had one "
                "carries statevector_sha256 (sha256 of the Base64-decoded complex128 bytes, "
                "or of the sorted-key JSON for a list-form vector; statevector_digest_input "
                "says which) and statevector_length (amplitude count).")
    inv = statevector_inventory(ctx.results)
    parts = []
    if inv["present"]:
        parts.append(f" Includes raw statevectors for {inv['present']} backend result(s).")
    if inv["omitted_for_display"]:
        parts.append(f" {inv['omitted_for_display']} result(s) carry no statevector: the "
                     f"exported copy held the display placeholder "
                     f"({OMITTED_FOR_DISPLAY}=true).")
    if inv["storage"]:
        parts.append(" Statevectors were removed when this report was saved to run history.")
    elif inv["absent"] and not inv["present"]:
        parts.append(" The exported report carried no statevectors.")
    return "".join(parts)


# --- ro-crate-metadata.json ------------------------------------------------------------

def _build_ro_crate_metadata(ctx: ExportContext,
                             artifact_paths: Optional[List[str]] = None,
                             artifact_descriptions: Optional[Dict[str, str]] = None,
                             lock_paths: Optional[List[str]] = None,
                             compiler_files: Optional[Dict[str, tuple]] = None) -> dict:
    """Build the RO-Crate 1.1 metadata descriptor (JSON-LD). ``compiler_files`` maps each
    compiler build file's crate path to (bytes, check), as ``compiler_build_files`` returns."""
    graph: List[dict] = []
    artifact_paths = artifact_paths or []
    artifact_descriptions = artifact_descriptions or {}
    compiler_files = compiler_files or {}
    lock_paths = set(lock_paths or []) | set(compiler_files)
    agent_ref: Optional[dict] = None

    tasks = _iter_tasks(ctx)
    is_batch = any(t.task_id is not None for t in tasks)
    dispatched = {id(t): _dispatched_circuit_files(t) for t in tasks}
    transpiled = {id(t): _transpiled_circuit_files(t) for t in tasks}
    has_dispatched = any(dispatched.values())
    has_transpiled = any(transpiled.values())
    compiled = {id(t): _compiled_files(t) for t in tasks}
    platform_version = _shared_scalar(ctx, "platform_version") or settings.PLATFORM_VERSION

    graph.append({
        "@type": "CreativeWork",
        "@id": "ro-crate-metadata.json",
        "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
        "about": {"@id": "./"}
    })

    contents = ["the input OpenQASM 2.0 circuit" + ("s" if is_batch else "")]
    if has_dispatched:
        contents.append("the exact circuit text dispatched to each backend")
    if has_transpiled:
        contents.append("the transpiled circuit each backend reported executing")
    if any(compiled.values()):
        contents.append("the input and output circuit of each compile-only service (not simulated)")
    contents.append("results.json (cross-simulator analysis, performance and resource reports, "
                    "and per-runner raw results)")
    contents.append("provenance.json (run configuration, runner registry, SDK versions, seeds, "
                    "and the git SHA and runner image references where recorded)")
    if any(p.startswith("runners/") for p in lock_paths):
        contents.append("each runner's pinned environment as runners/<runner>/requirements.lock")
    if compiler_files:
        contents.append("the build files of each compile-only service whose image ran (Dockerfile, "
                        "pinned environment, patches, build sources, generated data) under "
                        "compilers/<compiler>/, each with the check that admitted it")
    if artifact_paths:
        contents.append("publication figures and tables under figures/ and tables/"
                        + (" (one folder per task)" if is_batch else "")
                        + ", each described below with its legend and, for tables, its caption")
    root_entity: dict = {
        "@id": "./",
        "@type": "Dataset",
        "conformsTo": [
            {"@id": "https://w3id.org/ro/crate/1.1"},
            {"@id": PROCESS_RUN_CRATE_PROFILE},
        ],
        "name": f"Quantum Rosetta Benchmark Export — {ctx.timestamp}",
        "description": (
            "Quantum simulator benchmark results exported from Quantum Rosetta. Contains "
            + "; ".join(contents) + ". Each backend execution is recorded as a "
            "CreateAction per the Process Run Crate profile. " + REPORT_SOURCES[ctx.report_source]
        ),
        "datePublished": ctx.timestamp,
        "license": {"@id": "#license"},
        "hasPart": [{"@id": _circuit_path(t)} for t in tasks if t.input_qasm] + [
            {"@id": "results.json"},
            {"@id": "provenance.json"},
        ],
        "mentions": [],
    }

    if ctx.author_name:
        author_id = "#author"
        root_entity["author"] = {"@id": author_id}
        agent_ref = {"@id": author_id}
        author_entity: dict = {"@id": author_id, "@type": "Person", "name": ctx.author_name}
        if ctx.author_affiliation:
            org_id = "#affiliation"
            author_entity["affiliation"] = {"@id": org_id}
            graph.append({"@id": org_id, "@type": "Organization", "name": ctx.author_affiliation})
        graph.append(author_entity)

    graph.append(root_entity)

    graph.append({
        "@id": "#license",
        "@type": "CreativeWork",
        "name": "CC BY 4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
    })

    for task in tasks:
        if not task.input_qasm:
            continue
        graph.append({
            "@id": _circuit_path(task),
            "@type": "File",
            "name": f"{task.task_id}.qasm" if task.task_id else "circuit.qasm",
            "description": (
                f"Input OpenQASM 2.0 circuit for '{task.label}', as submitted."
                if task.task_id else
                "Input OpenQASM 2.0 circuit, as submitted."
            ),
            "encodingFormat": "text/x-qasm",
            "programmingLanguage": {"@id": "#openqasm2"},
        })

    results_desc = (
        "Benchmark analysis results: divergence, pairwise agreement evidence records when "
        "available, performance and resource reports, and per-runner raw results."
        + _statevector_description(ctx)
    )
    graph.append({
        "@id": "results.json",
        "@type": "File",
        "name": "results.json",
        "description": results_desc,
        "encodingFormat": "application/json",
    })

    graph.append({
        "@id": "provenance.json",
        "@type": "File",
        "name": "provenance.json",
        "description": (
            "Run configuration recorded at run time (preprocessing flag, timeout and its scope, "
            "runner_config, agreement thresholds, seeds and their derivation, git SHA, "
            "timestamps; 'not recorded' where the report lacks a field), API-side circuit "
            "changes, runner registry entries, executed SDK versions, and runner image "
            "references."
        ),
        "encodingFormat": "application/json",
    })

    for task in tasks:
        suffix = f" for '{task.label}'." if task.task_id else "."
        for f in dispatched[id(task)]:
            notes = f["api_preprocessing_applied"]
            graph.append({
                "@id": f["path"],
                "@type": "File",
                "name": f"{f['sim']}.qasm",
                "description": (
                    f"The exact OpenQASM text the API sent to the {f['sim']} runner"
                    + suffix
                    + (" API-side changes from the input circuit: " + "; ".join(notes)
                       if notes else " Identical to the input circuit.")
                ),
                "encodingFormat": "text/x-qasm",
                "programmingLanguage": {"@id": "#openqasm2"},
            })
            root_entity["hasPart"].append({"@id": f["path"]})
        for f in transpiled[id(task)]:
            graph.append({
                "@id": f["path"],
                "@type": "File",
                "name": f"{f['sim']}.qasm",
                "description": (
                    f"The transpiled and preprocessed QASM 2.0 the {f['sim']} backend adapter "
                    f"reported executing" + suffix
                ),
                "encodingFormat": "text/x-qasm",
                "programmingLanguage": {"@id": "#openqasm2"},
            })
            root_entity["hasPart"].append({"@id": f["path"]})
        for f in compiled[id(task)]:
            graph.append({"@id": f["path"], "@type": "File", "name": f["name"],
                          "description": f["description"], "encodingFormat": "text/x-qasm",
                          "programmingLanguage": {"@id": "#openqasm2"}})
            root_entity["hasPart"].append({"@id": f["path"]})
        for action in compile_actions(task.report, task.task_id, task.label, compiled[id(task)],
                                      settings.get_compiler_services()):
            graph.append(action)
            root_entity["mentions"].append({"@id": action["@id"]})
    graph.extend(compiler_applications([t.report for t in tasks], settings.get_compiler_services(),
                                       trusted=ctx.report_source == "server_job",
                                       build_paths=list(compiler_files)))
    for path in sorted(compiler_files):
        data, check = compiler_files[path]
        graph.append(compiler_build_entity(path, data, check))
        root_entity["hasPart"].append({"@id": path})

    graph.append({
        "@id": "https://w3id.org/ro/crate/1.1",
        "@type": "CreativeWork",
        "name": "RO-Crate 1.1",
        "version": "1.1",
    })
    graph.append({
        "@id": PROCESS_RUN_CRATE_PROFILE,
        "@type": "CreativeWork",
        "name": "Process Run Crate",
        "version": "0.5",
    })
    graph.append({
        "@id": "#quantum-rosetta",
        "@type": "SoftwareApplication",
        "name": "Quantum Rosetta",
        "softwareVersion": platform_version,
        "description": (
            "Microservices platform for cross-simulator quantum circuit benchmarking "
            "using OpenQASM 2.0 as the canonical input format. Orchestrates each backend "
            "execution and computes cross-simulator agreement evidence."
        ),
        "url": _source_url(ctx),
    })
    graph.append({
        "@id": "#openqasm2",
        "@type": "ComputerLanguage",
        "name": "OpenQASM 2.0",
        "url": "https://arxiv.org/abs/1707.03429",
    })

    n_shots = _shared_scalar(ctx, "n_shots")
    seed = _shared_scalar(ctx, "seed")
    derived_seeds = bool(_shared_scalar(ctx, "seed_derivation"))
    shared_param_refs: List[dict] = []
    if ctx.mode == "measured" and n_shots is not None:
        graph.append({"@id": "#param-n_shots", "@type": "PropertyValue",
                      "name": "n_shots", "value": n_shots})
        shared_param_refs.append({"@id": "#param-n_shots"})
    if seed is not None:
        graph.append({
            "@id": "#param-seed",
            "@type": "PropertyValue",
            "name": "seed",
            "value": seed,
            "description": (
                "Master RNG seed; each runner received a seed derived from it and its result "
                "key (see provenance.json run_configuration.seed_derivation)."
                if derived_seeds else "RNG seed passed to every runner."
            ),
        })
        shared_param_refs.append({"@id": "#param-seed"})

    run_action_refs: List[dict] = []
    output_refs: List[dict] = []
    for task in tasks:
        task_suffix = f"-{task.task_id}" if task.task_id else ""
        circuit_ref = {"@id": _circuit_path(task)} if task.input_qasm else None
        circuit_phrase = "the input circuit" if not task.task_id else f"'{task.label}'"
        dispatched_by_sim = {f["sim"]: f["path"] for f in dispatched[id(task)]}

        for raw in task.raw_results:
            runner = raw.get("simulator")
            if not runner:
                continue
            runner_id = _canonical_sim_id(runner)
            frag = _entity_ref_id(runner) + task_suffix

            obj_refs = ([circuit_ref] if circuit_ref else []) + list(shared_param_refs)
            opt_level = raw.get("optimization_level")
            if opt_level is not None:
                opt_param_id = f"#param-optlevel-{frag}"
                graph.append({
                    "@id": opt_param_id,
                    "@type": "PropertyValue",
                    "name": "optimization_level",
                    "value": opt_level,
                    "description": f"Effective optimization level executed by the {runner} adapter.",
                })
                obj_refs.append({"@id": opt_param_id})
            if raw.get("runner_seed") is not None:
                seed_param_id = f"#param-runner-seed-{frag}"
                graph.append({
                    "@id": seed_param_id,
                    "@type": "PropertyValue",
                    "name": "runner_seed",
                    "value": raw["runner_seed"],
                    "description": (
                        f"Seed passed to the {runner} runner."
                        + ("" if raw.get("seed_honoured", True) else
                           " This backend does not honour the seed; its counts are not reproducible.")
                    ),
                })
                obj_refs.append({"@id": seed_param_id})
            if runner in dispatched_by_sim:
                obj_refs.append({"@id": dispatched_by_sim[runner]})

            output_id = f"#output-{frag}"
            graph.append({
                "@id": output_id,
                "@type": "CreativeWork",
                "name": f"{runner} {ctx.mode} output" + (f" ({task.label})" if task.task_id else ""),
                "description": (
                    f"Raw {ctx.mode} output and per-runner metrics produced by {runner}; "
                    "values preserved in results.json under raw_results."
                ),
                "isPartOf": {"@id": "results.json"},
            })
            output_refs.append({"@id": output_id})

            failed = bool(raw.get("error"))
            action = {
                "@id": f"#run-{frag}",
                "@type": "CreateAction",
                "name": f"Execution of {circuit_phrase} on {runner}",
                "description": f"Dispatch of {circuit_phrase} to the {runner} backend adapter for {ctx.mode} execution.",
                "instrument": {"@id": f"#{runner_id}"},
                "object": obj_refs,
                "result": {"@id": output_id},
                "actionStatus": _ACTION_STATUS_FAILED if failed else _ACTION_STATUS_COMPLETED,
            }
            if raw.get("dispatched_at"):
                action["startTime"] = raw["dispatched_at"]
            if raw.get("completed_at"):
                action["endTime"] = raw["completed_at"]
            if agent_ref:
                action["agent"] = agent_ref
            if failed:
                action["error"] = str(raw.get("error"))
            graph.append(action)
            run_action_refs.append({"@id": f"#run-{frag}"})

    artifact_refs: List[dict] = []
    for path in artifact_paths:
        kind = "figure" if path.startswith("figures/") else "table"
        graph.append({
            "@id": path,
            "@type": "File",
            "name": path.split("/", 1)[-1],
            "description": (
                f"Publication-ready {kind} derived deterministically from the analysis reports. "
                + artifact_descriptions.get(path, "")
            ).strip(),
            "encodingFormat": _artifact_encoding_format(path),
        })
        artifact_refs.append({"@id": path})
        root_entity["hasPart"].append({"@id": path})

    if output_refs:
        analysis_results = [{"@id": "results.json"}] + artifact_refs
        analysis = {
            "@id": "#agreement-analysis",
            "@type": "CreateAction",
            "name": "Cross-simulator agreement analysis",
            "description": (
                "QRosetta comparator computed pairwise agreement evidence over the "
                "registered-transform lattice and, for measured mode, the shot-noise "
                "statistical test, from the backend outputs. Publication figures and "
                "tables, when requested, are derived from these reports."
            ),
            "instrument": {"@id": "#quantum-rosetta"},
            "object": output_refs,
            "result": analysis_results if len(analysis_results) > 1 else {"@id": "results.json"},
            **({"agent": agent_ref} if agent_ref else {}),
        }
        finished_at = _shared_scalar(ctx, "finished_at")
        if finished_at:
            analysis["endTime"] = finished_at
        graph.append(analysis)
        run_action_refs.append({"@id": "#agreement-analysis"})

    root_entity["mentions"] = run_action_refs + root_entity["mentions"]

    seen_runner_ids = set()
    for runner in _extract_runners_used(ctx):
        runner_id = _canonical_sim_id(runner)
        if runner_id in seen_runner_ids:
            continue
        seen_runner_ids.add(runner_id)
        executed_versions = _extract_sdk_versions(ctx, runner)
        if executed_versions:
            version = ", ".join(f"{pkg} {ver}" for pkg, ver in sorted(executed_versions.items()))
        else:
            version = _get_runner_version(runner_id)
        svc = ctx.runner_services.get(runner_id, {})
        dir_name = _runner_dir_name(svc)
        node = {
            "@id": f"#{runner_id}",
            "@type": "SoftwareApplication",
            "name": f"{runner_id} Simulator Adapter",
            "softwareVersion": version,
            "description": f"Quantum execution environment provided by the {runner_id} backend adapter.",
            "url": _source_url(ctx, f"runners/{dir_name}" if dir_name else ""),
        }
        requirements: List[Any] = [
            f"{pkg}=={ver}" for pkg, ver in sorted(executed_versions.items())
        ]
        lock_path = f"runners/{dir_name}/requirements.lock"
        if lock_path in lock_paths:
            requirements.append({"@id": lock_path})
            graph.append({
                "@id": lock_path,
                "@type": "File",
                "name": "requirements.lock",
                "description": (
                    f"Full pinned Python environment (pip freeze) of the {runner_id} runner "
                    "image, as committed in the exporting server's source tree."
                ),
                "encodingFormat": "text/plain",
            })
            root_entity["hasPart"].append({"@id": lock_path})
        if requirements:
            node["softwareRequirements"] = requirements
        graph.append(node)

    return {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": graph,
    }


# --- public API ------------------------------------------------------------------------

def _fingerprint(report: dict) -> None:
    """Replace each statevector in ``report['raw_results']`` with statevector_sha256 and
    statevector_length (statevector_len is kept alongside it)."""
    fingerprint_statevectors(report, _json_sha256)
    for r in report.get("raw_results", []) or []:
        if isinstance(r, dict) and "statevector_len" in r:
            r.setdefault("statevector_length", r["statevector_len"])


def _results_json_data(ctx: ExportContext) -> dict:
    """results.json content: statevectors per ``include_statevectors`` (else a sha256 and
    length per result), display placeholders nulled and flagged, and circuit texts written
    as separate files removed."""
    data = copy.deepcopy(ctx.results)
    if not ctx.include_statevectors:
        _fingerprint(data)
        for task_result in data.get("benchmark_summary", []) or []:
            if isinstance(task_result, dict):
                _fingerprint(task_result)
        data = remove_statevectors(data)

    def clean(report: dict) -> None:
        for r in report.get("raw_results", []) or []:
            if not isinstance(r, dict):
                continue
            r.pop("transpiled_qasm", None)
            if "statevector" in r and is_display_placeholder(r):
                r["statevector"] = None
                r[OMITTED_FOR_DISPLAY] = True
        for record in report.get("dispatched_circuits", []) or []:
            if isinstance(record, dict):
                record.pop("qasm", None)
        strip_compiled_text(report)

    clean(data)
    for task_result in data.get("benchmark_summary", []) or []:
        if isinstance(task_result, dict):
            clean(task_result)
    return data


def _add_compiled_metrics_table(ctx: ExportContext, files: dict, descriptions: dict) -> None:
    """tables/compiled_circuits.csv when any task has compile records."""
    tasks = list(_iter_tasks(ctx))
    reports = [(t.task_id, t.report) for t in tasks]
    if not compile_provenance(reports):
        return
    paths = {(t.task_id, f["record"].get("compiler")): f["path"]
             for t in tasks for f in _compiled_files(t) if f["record"] is not None}
    files[COMPILED_METRICS_PATH] = compiled_metrics_csv(reports, paths).encode()
    descriptions[COMPILED_METRICS_PATH] = (
        "One row per compile-only record: status, gate_count (top-level statements), "
        "multi_qubit_gate_count, circuit_depth, gate_counts per gate name and the output file. "
        "Compilers write different gate sets, so gate_count is not comparable across them.")


def build_ro_crate(ctx: ExportContext) -> bytes:
    """Build the RO-Crate 1.1 ZIP bundle for ``ctx`` and return its bytes."""
    ts_slug = ctx.timestamp.replace(":", "-").replace("+", "p")
    dir_name = f"rosetta-export-{ts_slug}"

    results_data = _results_json_data(ctx)
    provenance_data = _build_provenance(ctx)
    publication_files, artifact_descriptions = _generate_publication_artifacts(ctx)
    _add_compiled_metrics_table(ctx, publication_files, artifact_descriptions)
    compiler_files = compiler_build_files([t.report for t in _iter_tasks(ctx)], settings.get_compiler_services(),
                                          trusted=ctx.report_source == "server_job")
    lock_files = {**_runner_lock_files(ctx), **{p: data for p, (data, _) in compiler_files.items()}}
    metadata = _build_ro_crate_metadata(ctx, sorted(publication_files), artifact_descriptions,
                                        sorted(_runner_lock_files(ctx)), compiler_files)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{dir_name}/ro-crate-metadata.json",
            json.dumps(metadata, indent=2, ensure_ascii=False),
        )
        for rel_path, data in publication_files.items():
            zf.writestr(_member(dir_name, rel_path), data)
        for rel_path, data in lock_files.items():
            zf.writestr(_member(dir_name, rel_path), data)
        for task in _iter_tasks(ctx):
            if task.input_qasm:
                zf.writestr(_member(dir_name, _circuit_path(task)), task.input_qasm)
        zf.writestr(
            f"{dir_name}/results.json",
            json.dumps(results_data, indent=2, ensure_ascii=False),
        )
        zf.writestr(
            f"{dir_name}/provenance.json",
            json.dumps(provenance_data, indent=2, ensure_ascii=False),
        )
        for task in _iter_tasks(ctx):
            for f in _dispatched_circuit_files(task) + _transpiled_circuit_files(task) + _compiled_files(task):
                zf.writestr(_member(dir_name, f["path"]), f["qasm"])

    logger.info(f"Built RO-Crate ZIP: {dir_name} ({buf.tell()} bytes)")
    return buf.getvalue()
