# FAIR Data Export engine — builds RO-Crate 1.1 ZIP bundles.

import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-exporter")


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
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    include_statevectors: bool = False

    # Optional author metadata — left blank by default for the user to fill in.
    author_name: Optional[str] = None
    author_affiliation: Optional[str] = None

    # --- Future extension points (not used in v1) ---
    circuit_features: Optional[Dict[str, Any]] = None  # Feature 2: static circuit telemetry
    suite_source: Optional[str] = None                  # Feature 1: "MQT Bench" / "QASMBench"
    hardware_anchor: Optional[Dict[str, Any]] = None    # Feature 3: QPU reference distribution


# ---------------------------------------------------------------------------
#  Internal helpers
# ---------------------------------------------------------------------------

import os

def _get_runner_version(runner_id: str) -> str:
    """Attempt to read the primary dependency version from the runner's requirements.txt."""
    runner_dir_map = {
        "qiskit": "pytket-qiskit-runner",
        "cirq": "pytket-cirq-runner",
        "qulacs": "pytket-qulacs-runner",
        "braket": "pytket-braket-runner",
        "projectq": "pytket-projectq-runner",
        "quest": "pytket-quest-runner",
        "pennylane-lightning": "pennylane-lightning-runner",
        "pennylane-default": "pennylane-default-runner",
        "qsim-cirq": "qsim-cirq-runner",
        "qibo": "qibo-runner",
        "qrisp": "qrisp-runner",
        "myqlm": "myqlm-runner",
        "pyquil": "pyquil-runner",
        "torchquantum": "torch-quantum-runner",
        "quimb": "quimb-runner",
        "cuquantum": "cuquantum-runner",
    }
    dir_name = runner_dir_map.get(runner_id)
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


def _extract_runners_used(ctx: ExportContext) -> List[str]:
    runners_used: List[str] = []
    raw_results = ctx.results.get("raw_results", [])
    if isinstance(raw_results, list):
        for r in raw_results:
            sim = r.get("simulator")
            if sim and sim not in runners_used:
                runners_used.append(sim)

    benchmark_summary = ctx.results.get("benchmark_summary", [])
    if isinstance(benchmark_summary, list):
        for task_result in benchmark_summary:
            for r in task_result.get("raw_results", []):
                sim = r.get("simulator")
                if sim and sim not in runners_used:
                    runners_used.append(sim)
    return runners_used


def _strip_statevectors(data: Any) -> Any:
    """Recursively remove 'statevector' keys from nested dicts/lists."""
    if isinstance(data, dict):
        return {k: _strip_statevectors(v) for k, v in data.items() if k != "statevector"}
    elif isinstance(data, list):
        return [_strip_statevectors(item) for item in data]
    return data


def _build_provenance(ctx: ExportContext) -> dict:
    """Build a provenance manifest capturing runner configurations and versions."""
    runners_used = _extract_runners_used(ctx)

    runner_configs = {}
    for name in runners_used:
        svc = ctx.runner_services.get(_canonical_sim_id(name), {})
        runner_configs[name] = {
            "enabled": svc.get("enabled", False),
            "capabilities": svc.get("capabilities", []),
            "optimization_levels": {
                str(k): v for k, v in svc.get("optimization_levels", {}).items()
            },
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

    # Embed future extension metadata when available
    if ctx.suite_source:
        provenance["suite_source"] = ctx.suite_source
    if ctx.circuit_features:
        provenance["circuit_features"] = ctx.circuit_features
    if ctx.hardware_anchor:
        provenance["hardware_anchor"] = ctx.hardware_anchor

    return provenance


def _build_ro_crate_metadata(ctx: ExportContext, dir_name: str) -> dict:
    """Build the RO-Crate 1.1 metadata descriptor (JSON-LD)."""
    graph: List[dict] = []

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
        "name": f"Quantum Rosetta Benchmark Export — {ctx.timestamp}",
        "description": (
            "Reproducible quantum simulator benchmark results exported from "
            "Quantum Rosetta. Contains the input OpenQASM 2.0 circuit, "
            "cross-simulator analysis reports (divergence, performance, resource), "
            "and full computational provenance."
        ),
        "datePublished": ctx.timestamp,
        "license": {"@id": "https://creativecommons.org/licenses/by/4.0/"},
        "hasPart": [
            {"@id": "circuit.qasm"},
            {"@id": "results.json"},
            {"@id": "provenance.json"},
        ],
    }

    # Author — only included if the user provided it.
    if ctx.author_name:
        author_id = "#author"
        root_entity["author"] = {"@id": author_id}
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

    # --- 3. Data Entities ---
    graph.append({
        "@id": "circuit.qasm",
        "@type": "File",
        "name": "circuit.qasm",
        "description": "Input OpenQASM 2.0 circuit used for this benchmark run.",
        "encodingFormat": "text/x-qasm",
        "programmingLanguage": {"@id": "#openqasm2"},
    })

    results_desc = (
        "Full benchmark analysis results including divergence, performance, "
        "and resource reports across all dispatched simulators."
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

    # --- 4. CreateAction (records the execution) ---
    runners_used = _extract_runners_used(ctx)
    instruments = [{"@id": "#quantum-rosetta"}]
    for runner in runners_used:
        runner_id = _canonical_sim_id(runner)
        instruments.append({"@id": f"#{runner_id}"})

    graph.append({
        "@id": "#benchmark-run",
        "@type": "CreateAction",
        "name": "Quantum Rosetta benchmark execution",
        "instrument": instruments,
        "object": {"@id": "circuit.qasm"},
        "result": {"@id": "results.json"},
        "endTime": ctx.timestamp,
    })

    graph.append({
        "@id": "#quantum-rosetta",
        "@type": "SoftwareApplication",
        "name": "Quantum Rosetta",
        "softwareVersion": "1.0.0",
        "description": (
            "Microservices platform for cross-simulator quantum circuit benchmarking "
            "using OpenQASM 2.0 as the canonical input format."
        ),
        "url": "https://github.com/SeQuSoS-Project/qrosetta",
    })

    # Add ComputerLanguage entity for OpenQASM 2.0
    graph.append({
        "@id": "#openqasm2",
        "@type": "ComputerLanguage",
        "name": "OpenQASM 2.0",
        "url": "https://arxiv.org/abs/1707.03429",
    })

    # Add SoftwareApplication entities for each runner
    for runner in runners_used:
        runner_id = _canonical_sim_id(runner)
        version = _get_runner_version(runner_id)
        graph.append({
            "@id": f"#{runner_id}",
            "@type": "SoftwareApplication",
            "name": f"{runner_id} Simulator Adapter",
            "softwareVersion": version,
            "description": f"Quantum execution environment provided by the {runner_id} backend adapter.",
        })

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

    # Prepare results — conditionally strip statevectors
    if ctx.include_statevectors:
        results_data = ctx.results
    else:
        results_data = _strip_statevectors(ctx.results)

    provenance_data = _build_provenance(ctx)
    metadata = _build_ro_crate_metadata(ctx, dir_name)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{dir_name}/ro-crate-metadata.json",
            json.dumps(metadata, indent=2, ensure_ascii=False),
        )
        zf.writestr(
            f"{dir_name}/circuit.qasm",
            ctx.qasm_string,
        )
        zf.writestr(
            f"{dir_name}/results.json",
            json.dumps(results_data, indent=2, ensure_ascii=False),
        )
        zf.writestr(
            f"{dir_name}/provenance.json",
            json.dumps(provenance_data, indent=2, ensure_ascii=False),
        )

    logger.info(f"Built RO-Crate ZIP: {dir_name} ({buf.tell()} bytes)")
    return buf.getvalue()
