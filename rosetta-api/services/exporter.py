# FAIR Data Export engine — builds RO-Crate 1.1 ZIP bundles.

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
from services.report_filters import remove_statevectors

logger = get_logger("rosetta-exporter")

# Process Run Crate profile (Workflow Run RO-Crate family; Leo et al., PLOS ONE 2024).
# QRosetta orchestrates each backend via its dispatcher rather than a workflow-language
# file, so the crate records one CreateAction per tool execution without a
# ComputationalWorkflow main entity.
PROCESS_RUN_CRATE_PROFILE = "https://w3id.org/ro/wfrun/process/0.5"
_ACTION_STATUS_COMPLETED = "http://schema.org/CompletedActionStatus"
_ACTION_STATUS_FAILED = "http://schema.org/FailedActionStatus"


def _entity_ref_id(key: str) -> str:
    """Sanitize a (possibly virtual '~opt~run') runner key into a safe @id fragment."""
    return (key or "unknown").replace("~", "-").replace(" ", "_")


_ARTIFACT_ENCODING = {
    "svg": "image/svg+xml", "png": "image/png", "pdf": "application/pdf",
    "csv": "text/csv", "latex": "application/x-latex", "html": "text/html",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _artifact_encoding_format(path: str) -> str:
    return _ARTIFACT_ENCODING.get(path.rsplit(".", 1)[-1], "application/octet-stream")


def _generate_publication_artifacts(ctx: "ExportContext") -> Dict[str, bytes]:
    """Generate opt-in publication figures/tables, or {} when not requested.

    Lazy-imports the publication engine (and matplotlib) only when artifacts are
    actually requested, so ordinary exports and API startup stay light.
    """
    sel = ctx.publication_artifacts
    if not sel or not sel.get("categories"):
        return {}
    from services.publication import build_publication_artifacts  # lazy (pulls matplotlib)
    return build_publication_artifacts(
        ctx.results,
        ctx.mode,
        tuple(sel.get("categories", [])),
        tuple(sel.get("figure_formats", ["svg"])),
        tuple(sel.get("table_formats", ["csv"])),
    )


@dataclass
class _TaskView:
    """One circuit within the export.

    A single-circuit run (POST /compare, /compare_measured) yields exactly one _TaskView
    with task_id=None: file paths and entity @ids stay exactly as they were before batch
    support existed (circuit.qasm at the crate root, #run-<runner> action ids), so ordinary
    exports are byte-for-byte unaffected by this.

    A batch run (POST /run_batch_suite; results shaped as {"benchmark_summary": [...]})
    yields one _TaskView per queued circuit, each with its own input_qasm and raw_results —
    batch results never duplicate the circuit/n_shots/seed at the top level, so treating a
    batch as "one task" silently loses every circuit but the first.
    """
    task_id: Optional[str]
    label: Optional[str]
    input_qasm: str
    raw_results: List[dict]


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
            ))
        return tasks
    # Single-circuit path, unchanged from every export before batch support existed.
    return [_TaskView(
        task_id=None,
        label=None,
        input_qasm=ctx.qasm_string,
        raw_results=[r for r in ctx.results.get("raw_results", []) if isinstance(r, dict)],
    )]


def _circuit_path(task: _TaskView) -> str:
    return "circuit.qasm" if task.task_id is None else f"circuits/{task.task_id}.qasm"


def _shared_scalar(ctx: "ExportContext", key: str):
    """A value that's uniform across an entire export: present at the top level for a
    single-circuit run, or (for n_shots/seed specifically) echoed identically into every
    task of a batch run, per the /run_batch_suite contract — read the first task's copy."""
    if key in ctx.results:
        return ctx.results.get(key)
    benchmark_summary = ctx.results.get("benchmark_summary")
    if isinstance(benchmark_summary, list) and benchmark_summary:
        first = benchmark_summary[0]
        if isinstance(first, dict):
            return first.get(key)
    return None


def infer_export_mode(results: dict) -> str:
    """"measured" or "statevector", from either a single-circuit result (checks the top
    level) or a batch result (checks the first task inside benchmark_summary, since batch
    results never duplicate n_shots at the top level)."""
    if "n_shots" in results:
        return "measured"
    benchmark_summary = results.get("benchmark_summary")
    if isinstance(benchmark_summary, list) and benchmark_summary:
        first = benchmark_summary[0]
        if isinstance(first, dict) and "n_shots" in first:
            return "measured"
    return "statevector"


def _canonical_sim_id(simulator: str) -> str:
    """Self-comparison results carry virtual keys like 'qiskit~opt1~run2' (built by the
    dispatcher). Strip the '~opt~run' suffix back to the canonical runner id so provenance
    lookups in runner_services resolve. Plain canonical ids pass through unchanged."""
    return (simulator or "").split("~", 1)[0]


class ExportFormat(str, Enum):
    """Supported export formats. Extensible for future additions (BagIt, DataCite, etc.)."""
    RO_CRATE = "ro-crate"


@dataclass
class ExportContext:
    """
    Unified container for all data needed by any export format.

    Future features extend this class with additional fields
    rather than modifying the export pipeline itself:
      - Feature 1 (Suite Connectors):  suite_source
      - Feature 2 (Circuit Heuristics): circuit_features
      - Feature 3 (QPU Anchor):        hardware_anchor
    """
    qasm_string: str
    results: dict
    mode: str                                          # "statevector" or "measured"
    runner_services: Dict[str, Any]                    # config.get_runner_services()
    # Millisecond precision (not Python's default microseconds) matches the ISO 8601
    # format the Process Run Crate profile expects for Action endTime/startTime.
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    )
    include_statevectors: bool = False

    # Optional author metadata — left blank by default for the user to fill in.
    author_name: Optional[str] = None
    author_affiliation: Optional[str] = None

    # Opt-in publication artifacts: {"categories": [...], "figure_formats": [...],
    # "table_formats": [...]}. None/empty categories => none generated (non-breaking).
    publication_artifacts: Optional[Dict[str, Any]] = None

    # --- Future extension points (not used in v1) ---
    circuit_features: Optional[Dict[str, Any]] = None  # Feature 2: static circuit telemetry
    suite_source: Optional[str] = None                  # Feature 1: "MQT Bench" / "QASMBench"
    hardware_anchor: Optional[Dict[str, Any]] = None    # Feature 3: QPU reference distribution


# ---------------------------------------------------------------------------
#  Internal helpers
# ---------------------------------------------------------------------------

def _get_runner_version(runner_id: str) -> str:
    """Attempt to read the primary dependency version from the runner's requirements.txt."""
    svc = settings.get_runner_services().get(runner_id)
    if not svc:
        return "unknown"
    # The runner's directory name is its service hostname, encoded in the registry
    # base_url (http://<hostname>:8000). Deriving it here keeps config.py the single
    # source for the runner-to-directory mapping.
    dir_name = svc.get("base_url", "").split("://", 1)[-1].split(":", 1)[0].split("/", 1)[0]
    if not dir_name:
        return "unknown"

    base_paths = [
        os.path.join(os.getcwd(), "runners", dir_name),
        os.path.join(os.getcwd(), "..", "runners", dir_name),
    ]
    
    versions = []
    for base in base_paths:
        req_path = os.path.join(base, "requirements.txt")
        if os.path.exists(req_path):
            try:
                with open(req_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if "==" in line:
                            pkg_name, pkg_version = line.split("==", 1)
                            # Collect all quantum-related packages
                            keywords = ["qiskit", "cirq", "qulacs", "pennylane", "qibo", "pytket", "cuquantum", "torch", "quimb", "myqlm", "qrisp", "pyquil"]
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
            
    if versions:
        return ", ".join(versions)
    return "unknown"


def _iter_raw_results(ctx: ExportContext):
    """Yield every per-runner raw result across single runs and batch summaries."""
    for task in _iter_tasks(ctx):
        yield from task.raw_results


def _extract_sdk_versions(ctx: ExportContext, runner_name: str) -> dict:
    """Return the executed SDK versions a runner reported in its result, if any.

    This is the ground-truth version coordinate (importlib.metadata, captured inside
    the runner at execution time). Falls back to {} when absent — e.g. reports
    produced before runners emitted sdk_versions."""
    for r in _iter_raw_results(ctx):
        if r.get("simulator") == runner_name:
            versions = r.get("sdk_versions")
            if isinstance(versions, dict) and versions:
                return versions
    return {}


def _raw_result_for(ctx: ExportContext, runner_name: str) -> dict:
    """Return the raw per-runner result dict for a given execution key, or {}."""
    for r in _iter_raw_results(ctx):
        if r.get("simulator") == runner_name:
            return r
    return {}


def _extract_runners_used(ctx: ExportContext) -> List[str]:
    runners_used: List[str] = []
    for r in _iter_raw_results(ctx):
        sim = r.get("simulator")
        if sim and sim not in runners_used:
            runners_used.append(sim)
    return runners_used


def _iter_pairwise_agreement_records(ctx: ExportContext):
    divergence_report = ctx.results.get("divergence_report")
    if isinstance(divergence_report, dict):
        pairwise = divergence_report.get("pairwise_agreement", [])
        if isinstance(pairwise, list):
            for record in pairwise:
                if isinstance(record, dict):
                    yield record

    benchmark_summary = ctx.results.get("benchmark_summary", [])
    if isinstance(benchmark_summary, list):
        for task_result in benchmark_summary:
            divergence_report = task_result.get("divergence_report")
            if isinstance(divergence_report, dict):
                pairwise = divergence_report.get("pairwise_agreement", [])
                if isinstance(pairwise, list):
                    for record in pairwise:
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
        "description": (
            "Counts of agreement labels, registered transforms, and (for measured "
            "mode) shot-noise statistical verdicts. The full per-pair metrics and "
            "provenance records are preserved in results.json."
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

    # Measured mode only — drop the key entirely when no statistical verdicts exist
    # (e.g. statevector exports) rather than emitting an empty object.
    if not summary["by_statistical_verdict"]:
        del summary["by_statistical_verdict"]
    return summary



def _build_provenance(ctx: ExportContext) -> dict:
    """Build a provenance manifest capturing runner configurations and versions."""
    runners_used = _extract_runners_used(ctx)

    runner_configs = {}
    for name in runners_used:
        svc = ctx.runner_services.get(_canonical_sim_id(name), {})
        preprocessing_applied = _raw_result_for(ctx, name).get("preprocessing_applied", [])

        runner_configs[name] = {
            "enabled": svc.get("enabled", False),
            "capabilities": svc.get("capabilities", []),
            "optimization_levels": {
                str(k): v for k, v in svc.get("optimization_levels", {}).items()
            },
            "preprocessing_applied": preprocessing_applied,
            "sdk_versions": _extract_sdk_versions(ctx, name),
        }

    provenance = {
        "platform": "Quantum Rosetta",
        "platform_version": "1.0.0",
        "export_timestamp": ctx.timestamp,
        "execution_mode": ctx.mode,
        "canonical_input_format": "OpenQASM 2.0",
        "runners_used": runners_used,
        "runner_configurations": runner_configs,
    }

    pairwise_summary = _build_pairwise_agreement_summary(ctx)
    if pairwise_summary:
        provenance["pairwise_agreement_evidence"] = pairwise_summary

    # Embed future extension metadata when available
    if ctx.suite_source:
        provenance["suite_source"] = ctx.suite_source
    if ctx.circuit_features:
        provenance["circuit_features"] = ctx.circuit_features
    if ctx.hardware_anchor:
        provenance["hardware_anchor"] = ctx.hardware_anchor

    return provenance


def _build_ro_crate_metadata(ctx: ExportContext,
                             artifact_paths: Optional[List[str]] = None) -> dict:
    """Build the RO-Crate 1.1 metadata descriptor (JSON-LD)."""
    graph: List[dict] = []
    artifact_paths = artifact_paths or []
    # Set below, in the author block, when the user supplied one. Referenced later as the
    # `agent` of every CreateAction (the Person who ran the export), when available.
    agent_ref: Optional[dict] = None

    tasks = _iter_tasks(ctx)
    is_batch = any(t.task_id is not None for t in tasks)

    # --- 1. Metadata descriptor entity (describes this file itself) ---
    graph.append({
        "@type": "CreativeWork",
        "@id": "ro-crate-metadata.json",
        "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
        "about": {"@id": "./"}
    })

    # --- 2. Root Data Entity ---
    root_entity: dict = {
        "@id": "./",
        "@type": "Dataset",
        "conformsTo": [
            {"@id": "https://w3id.org/ro/crate/1.1"},
            {"@id": PROCESS_RUN_CRATE_PROFILE},
        ],
        "name": f"Quantum Rosetta Benchmark Export — {ctx.timestamp}",
        "description": (
            "Reproducible quantum simulator benchmark results exported from "
            "Quantum Rosetta. Contains the input OpenQASM 2.0 circuit"
            + ("s" if is_batch else "") + ", "
            "cross-simulator analysis reports (including pairwise agreement evidence "
            "records when available), performance and resource reports, and full "
            "computational provenance. Each backend execution is recorded as a "
            "CreateAction per the Process Run Crate profile."
        ),
        "datePublished": ctx.timestamp,
        "license": {"@id": "#license"},
        "hasPart": [{"@id": _circuit_path(t)} for t in tasks] + [
            {"@id": "results.json"},
            {"@id": "provenance.json"},
        ],
        "mentions": [],  # populated with the run + analysis CreateActions below
    }

    # Author — only included if the user provided it.
    if ctx.author_name:
        author_id = "#author"
        root_entity["author"] = {"@id": author_id}
        agent_ref = {"@id": author_id}
        author_entity: dict = {
            "@id": author_id,
            "@type": "Person",
            "name": ctx.author_name,
        }
        if ctx.author_affiliation:
            org_id = "#affiliation"
            author_entity["affiliation"] = {"@id": org_id}
            graph.append({
                "@id": org_id,
                "@type": "Organization",
                "name": ctx.author_affiliation,
            })
        graph.append(author_entity)

    graph.append(root_entity)

    graph.append({
        "@id": "#license",
        "@type": "CreativeWork",
        "name": "CC BY 4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
    })

    # --- 3. Data Entities ---
    for task in tasks:
        graph.append({
            "@id": _circuit_path(task),
            "@type": "File",
            "name": f"{task.task_id}.qasm" if task.task_id else "circuit.qasm",
            "description": (
                f"Input OpenQASM 2.0 circuit for '{task.label}'."
                if task.task_id else
                "Input OpenQASM 2.0 circuit used for this benchmark run."
            ),
            "encodingFormat": "text/x-qasm",
            "programmingLanguage": {"@id": "#openqasm2"},
        })

    results_desc = (
        "Full benchmark analysis results including divergence, pairwise agreement "
        "evidence records when available, performance, and resource reports across "
        "all dispatched simulators."
    )
    if ctx.include_statevectors:
        results_desc += " Includes raw statevector data."
    else:
        results_desc += " Raw statevectors excluded to reduce file size."

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
            "Computational provenance: runner configurations, capabilities, "
            "optimization level descriptions, and platform metadata."
        ),
        "encodingFormat": "application/json",
    })

    # Transpiled circuit entities, per task (deduplicated within each task, preserving
    # first-seen order — the same backend can transpile differently across tasks, so a
    # single-run's transpiled_circuits/<sim>.qasm path is only reused when there is one task).
    for task in tasks:
        seen_sims: List[str] = []
        for r in task.raw_results:
            sim = r.get("simulator")
            if r.get("transpiled_qasm") and sim and sim not in seen_sims:
                seen_sims.append(sim)
        for sim in seen_sims:
            path = (
                f"transpiled_circuits/{sim}.qasm" if task.task_id is None
                else f"transpiled_circuits/{task.task_id}/{sim}.qasm"
            )
            graph.append({
                "@id": path,
                "@type": "File",
                "name": f"{sim}.qasm",
                "description": (
                    f"The exact transpiled and preprocessed QASM 2.0 code that was executed "
                    f"by the {sim} backend adapter"
                    + (f" for '{task.label}'." if task.task_id else ".")
                ),
                "encodingFormat": "text/x-qasm",
                "programmingLanguage": {"@id": "#openqasm2"},
            })
            root_entity["hasPart"].append({"@id": path})

    # --- 4. Profile + orchestrating engine + language ---
    # Both entries in the root entity's conformsTo (RO-Crate 1.1 itself and the Process
    # Run Crate profile) need their own described CreativeWork entity in the graph, since
    # the Process Run Crate profile requires every conformsTo target to be typed.
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
        "softwareVersion": "1.0.0",
        "description": (
            "Microservices platform for cross-simulator quantum circuit benchmarking "
            "using OpenQASM 2.0 as the canonical input format. Orchestrates each backend "
            "execution and computes cross-simulator agreement evidence."
        ),
        "url": "https://github.com/SeQuSoS-Project/QRosetta",
    })

    # Add ComputerLanguage entity for OpenQASM 2.0
    graph.append({
        "@id": "#openqasm2",
        "@type": "ComputerLanguage",
        "name": "OpenQASM 2.0",
        "url": "https://arxiv.org/abs/1707.03429",
    })

    # --- 5. Shared parameter entities (PropertyValue), referenced by run actions ---
    n_shots = _shared_scalar(ctx, "n_shots")
    seed = _shared_scalar(ctx, "seed")
    shared_param_refs: List[dict] = []
    if ctx.mode == "measured" and n_shots is not None:
        graph.append({
            "@id": "#param-n_shots",
            "@type": "PropertyValue",
            "name": "n_shots",
            "value": n_shots,
        })
        shared_param_refs.append({"@id": "#param-n_shots"})
    if seed is not None:
        graph.append({
            "@id": "#param-seed",
            "@type": "PropertyValue",
            "name": "seed",
            "value": seed,
            "description": "RNG seed for reproducible sampling.",
        })
        shared_param_refs.append({"@id": "#param-seed"})

    # --- 6. Per-execution CreateActions (Process Run Crate core) ---
    # One CreateAction per (task, runner) pair, not per runner: the same backend runs once
    # per queued circuit in a batch, with its own circuit, output, and success/failure.
    run_action_refs: List[dict] = []
    output_refs: List[dict] = []
    for task in tasks:
        task_suffix = f"-{task.task_id}" if task.task_id else ""
        circuit_ref = {"@id": _circuit_path(task)}
        circuit_phrase = "the input circuit" if not task.task_id else f"'{task.label}'"

        for raw in task.raw_results:
            runner = raw.get("simulator")
            if not runner:
                continue
            runner_id = _canonical_sim_id(runner)
            frag = _entity_ref_id(runner) + task_suffix

            # Per-runner optimization level as its own PropertyValue (may differ per backend).
            obj_refs = [circuit_ref] + list(shared_param_refs)
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

            # Contextual output entity: the runner's raw output lives inside results.json.
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
                "endTime": ctx.timestamp,
                "actionStatus": _ACTION_STATUS_FAILED if failed else _ACTION_STATUS_COMPLETED,
            }
            if agent_ref:
                action["agent"] = agent_ref
            if failed:
                action["error"] = str(raw.get("error"))
            graph.append(action)
            run_action_refs.append({"@id": f"#run-{frag}"})

    # --- 7. Publication artifact data entities (opt-in; derived analysis outputs) ---
    artifact_refs: List[dict] = []
    for path in artifact_paths:
        kind = "figure" if path.startswith("figures/") else "table"
        graph.append({
            "@id": path,
            "@type": "File",
            "name": path.rsplit("/", 1)[-1],
            "description": (
                f"Publication-ready {kind} derived deterministically from the analysis "
                "reports. Raw metrics vs transformed analysis evidence are distinguished "
                "in the figure/table caption."
            ),
            "encodingFormat": _artifact_encoding_format(path),
        })
        artifact_refs.append({"@id": path})
        root_entity["hasPart"].append({"@id": path})

    # --- 8. Agreement-analysis CreateAction (QRosetta consumes outputs -> reports) ---
    if output_refs:
        analysis_results = [{"@id": "results.json"}] + artifact_refs
        graph.append({
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
            "endTime": ctx.timestamp,
            **({"agent": agent_ref} if agent_ref else {}),
        })
        run_action_refs.append({"@id": "#agreement-analysis"})

    root_entity["mentions"] = run_action_refs

    # --- 9. SoftwareApplication entity per backend (deduplicated by canonical id) ---
    # Prefer the versions the runner actually executed under (reported in its result
    # via importlib.metadata — ground truth). Fall back to the declared requirements.txt
    # pin only for older reports that predate sdk_versions reporting.
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
        dir_name = svc.get("base_url", "").split("://", 1)[-1].split(":", 1)[0].split("/", 1)[0]
        node = {
            "@id": f"#{runner_id}",
            "@type": "SoftwareApplication",
            "name": f"{runner_id} Simulator Adapter",
            "softwareVersion": version,
            "description": f"Quantum execution environment provided by the {runner_id} backend adapter.",
            "url": (
                f"https://github.com/SeQuSoS-Project/QRosetta/tree/main/runners/{dir_name}"
                if dir_name else "https://github.com/SeQuSoS-Project/QRosetta"
            ),
        }
        if executed_versions:
            # Structured, machine-readable form of the executed stack for reproducibility.
            node["softwareRequirements"] = [
                f"{pkg}=={ver}" for pkg, ver in sorted(executed_versions.items())
            ]
        graph.append(node)

    return {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": graph,
    }


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def build_ro_crate(ctx: ExportContext) -> bytes:
    """
    Build a complete RO-Crate 1.1 ZIP bundle from the given ExportContext.

    Returns raw ZIP bytes suitable for streaming as an HTTP response.
    """
    ts_slug = ctx.timestamp.replace(":", "-").replace("+", "p")
    dir_name = f"rosetta-export-{ts_slug}"

    # Prepare results — conditionally strip statevectors. results_data must be a
    # distinct object from ctx.results: below we pop transpiled_qasm out of it (to
    # keep results.json small) but still read transpiled_qasm from ctx.results when
    # writing the transpiled_circuits/ files. _strip_statevectors already returns a
    # fresh structure; deepcopy the keep-statevectors branch so the pop can't erase
    # the transpiled circuits before they are written.
    if ctx.include_statevectors:
        results_data = copy.deepcopy(ctx.results)
    else:
        results_data = remove_statevectors(ctx.results)

    provenance_data = _build_provenance(ctx)
    # Opt-in publication artifacts (figures/tables). Generated before metadata so each
    # file can be registered as an RO-Crate data entity.
    publication_files = _generate_publication_artifacts(ctx)
    metadata = _build_ro_crate_metadata(ctx, sorted(publication_files))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{dir_name}/ro-crate-metadata.json",
            json.dumps(metadata, indent=2, ensure_ascii=False),
        )
        for rel_path, data in publication_files.items():
            zf.writestr(f"{dir_name}/{rel_path}", data)
        for task in _iter_tasks(ctx):
            zf.writestr(f"{dir_name}/{_circuit_path(task)}", task.input_qasm)
        # Strip transpiled_qasm from results_data to save space, since we dump them separately
        if isinstance(results_data.get("raw_results"), list):
            for r in results_data["raw_results"]:
                r.pop("transpiled_qasm", None)
        
        benchmark_summary = results_data.get("benchmark_summary", [])
        if isinstance(benchmark_summary, list):
            for task_result in benchmark_summary:
                if isinstance(task_result.get("raw_results"), list):
                    for r in task_result["raw_results"]:
                        r.pop("transpiled_qasm", None)

        zf.writestr(
            f"{dir_name}/results.json",
            json.dumps(results_data, indent=2, ensure_ascii=False),
        )
        zf.writestr(
            f"{dir_name}/provenance.json",
            json.dumps(provenance_data, indent=2, ensure_ascii=False),
        )

        # Write transpiled circuits, one subtree per task so the same backend's transpiled
        # QASM from different circuits in a batch never overwrites another task's copy.
        for task in _iter_tasks(ctx):
            written_sims = set()
            for r in task.raw_results:
                tq = r.get("transpiled_qasm")
                sim = r.get("simulator")
                if tq and sim and sim not in written_sims:
                    written_sims.add(sim)
                    path = (
                        f"transpiled_circuits/{sim}.qasm" if task.task_id is None
                        else f"transpiled_circuits/{task.task_id}/{sim}.qasm"
                    )
                    zf.writestr(f"{dir_name}/{path}", tq)

    logger.info(f"Built RO-Crate ZIP: {dir_name} ({buf.tell()} bytes)")
    return buf.getvalue()
