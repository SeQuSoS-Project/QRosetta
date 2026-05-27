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

def _strip_statevectors(data: Any) -> Any:
    """Recursively remove 'statevector' keys from nested dicts/lists."""
    if isinstance(data, dict):
        return {k: _strip_statevectors(v) for k, v in data.items() if k != "statevector"}
    elif isinstance(data, list):
        return [_strip_statevectors(item) for item in data]
    return data


def _build_provenance(ctx: ExportContext) -> dict:
    """Build a provenance manifest capturing runner configurations and versions."""
    runners_used: List[str] = []

    raw_results = ctx.results.get("raw_results", [])
    if isinstance(raw_results, list):
        for r in raw_results:
            sim = r.get("simulator")
            if sim:
                runners_used.append(sim)

    # Also check batch results
    benchmark_summary = ctx.results.get("benchmark_summary", [])
    if isinstance(benchmark_summary, list):
        for task_result in benchmark_summary:
            for r in task_result.get("raw_results", []):
                sim = r.get("simulator")
                if sim and sim not in runners_used:
                    runners_used.append(sim)

    runner_configs = {}
    for name in runners_used:
        svc = ctx.runner_services.get(name, {})
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
    graph.append({
        "@id": "#benchmark-run",
        "@type": "CreateAction",
        "name": "Quantum Rosetta benchmark execution",
        "instrument": {"@id": "#quantum-rosetta"},
        "object": {"@id": "circuit.qasm"},
        "result": {"@id": "results.json"},
        "endTime": ctx.timestamp,
    })

    graph.append({
        "@id": "#quantum-rosetta",
        "@type": "SoftwareApplication",
        "name": "Quantum Rosetta",
        "description": (
            "Microservices platform for cross-simulator quantum circuit benchmarking "
            "using OpenQASM 2.0 as the canonical input format."
        ),
        "url": "https://github.com/SeQuSoS-Project/qrosetta",
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
