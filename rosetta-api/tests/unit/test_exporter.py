# Unit tests for the FAIR data export engine (services/exporter.py).

import json
import zipfile
import io
import pytest
from services.exporter import ExportContext, ExportFormat, build_ro_crate, _strip_statevectors


# --- Fixtures ---

SAMPLE_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
"""

SAMPLE_RESULTS_SV = {
    "input_qasm": SAMPLE_QASM,
    "divergence_report": {
        "simulators": ["qiskit", "cirq"],
        "fidelity_matrix": [[1.0, 1.0], [1.0, 1.0]],
        "divergences_found": [],
    },
    "performance_report": {
        "summary": "Execution time in seconds (fastest first).",
        "ranking": [
            {"simulator": "qiskit", "status": "success", "execution_time_sec": 0.05},
            {"simulator": "cirq", "status": "success", "execution_time_sec": 0.08},
        ],
    },
    "resource_report": {
        "summary": "Memory usage delta in MiB (lowest first).",
        "ranking": [],
    },
    "raw_results": [
        {
            "simulator": "qiskit",
            "statevector": [1.0, 0.0, 0.0, 0.0],
            "execution_time_sec": 0.05,
            "compilation_time_sec": 0.01,
            "simulation_time_sec": 0.04,
            "memory_usage_mb": 12.5,
            "process_peak_mb": 120.0,
            "qubit_ordering": "lsb",
        },
        {
            "simulator": "cirq",
            "statevector": [1.0, 0.0, 0.0, 0.0],
            "execution_time_sec": 0.08,
            "compilation_time_sec": 0.02,
            "simulation_time_sec": 0.06,
            "memory_usage_mb": 10.0,
            "process_peak_mb": 100.0,
            "qubit_ordering": "lsb",
        },
    ],
}

SAMPLE_RUNNER_SERVICES = {
    "qiskit": {
        "enabled": True,
        "capabilities": ["statevector", "measured_native"],
        "optimization_levels": {0: "No optimization"},
    },
    "cirq": {
        "enabled": True,
        "capabilities": ["statevector", "measured_native"],
        "optimization_levels": {0: "No optimization"},
    },
}


def _make_ctx(**overrides):
    """Build a test ExportContext with sensible defaults."""
    defaults = dict(
        qasm_string=SAMPLE_QASM,
        results=SAMPLE_RESULTS_SV,
        mode="statevector",
        runner_services=SAMPLE_RUNNER_SERVICES,
        include_statevectors=False,
    )
    defaults.update(overrides)
    return ExportContext(**defaults)


# --- Tests ---

class TestStripStatevectors:
    def test_removes_statevector_keys(self):
        data = {"simulator": "qiskit", "statevector": [1, 0, 0, 0], "time": 0.1}
        result = _strip_statevectors(data)
        assert "statevector" not in result
        assert result["simulator"] == "qiskit"
        assert result["time"] == 0.1

    def test_strips_nested_statevectors(self):
        data = {
            "raw_results": [
                {"simulator": "a", "statevector": [1, 0]},
                {"simulator": "b", "statevector": [0, 1]},
            ]
        }
        result = _strip_statevectors(data)
        for item in result["raw_results"]:
            assert "statevector" not in item

    def test_preserves_non_statevector_data(self):
        data = {"counts": {"00": 512, "11": 512}, "simulator": "qiskit"}
        result = _strip_statevectors(data)
        assert result == data


class TestExportFormat:
    def test_ro_crate_value(self):
        assert ExportFormat.RO_CRATE.value == "ro-crate"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            ExportFormat("invalid")


class TestExportContext:
    def test_defaults(self):
        ctx = _make_ctx()
        assert ctx.include_statevectors is False
        assert ctx.author_name is None
        assert ctx.author_affiliation is None
        assert ctx.circuit_features is None
        assert ctx.suite_source is None
        assert ctx.hardware_anchor is None
        assert ctx.timestamp  # auto-generated

    def test_future_extension_fields_are_none(self):
        """Future feature extension points must default to None without crashing."""
        ctx = _make_ctx()
        assert ctx.circuit_features is None
        assert ctx.suite_source is None
        assert ctx.hardware_anchor is None


class TestBuildRoCrate:
    def test_returns_valid_zip(self):
        ctx = _make_ctx()
        zip_bytes = build_ro_crate(ctx)
        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0

        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
        names = zf.namelist()
        # Should have exactly 4 files inside a directory
        assert len(names) == 4

    def test_contains_expected_files(self):
        ctx = _make_ctx()
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
        names = zf.namelist()

        basenames = [n.split("/", 1)[1] for n in names]
        assert "ro-crate-metadata.json" in basenames
        assert "circuit.qasm" in basenames
        assert "results.json" in basenames
        assert "provenance.json" in basenames

    def test_circuit_qasm_content(self):
        ctx = _make_ctx()
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        qasm_path = [n for n in zf.namelist() if n.endswith("circuit.qasm")][0]
        content = zf.read(qasm_path).decode("utf-8")
        assert "OPENQASM 2.0" in content
        assert "qreg q[3]" in content

    def test_statevectors_excluded_by_default(self):
        ctx = _make_ctx(include_statevectors=False)
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        results_path = [n for n in zf.namelist() if n.endswith("results.json")][0]
        results = json.loads(zf.read(results_path))

        for r in results.get("raw_results", []):
            assert "statevector" not in r

    def test_statevectors_included_when_requested(self):
        ctx = _make_ctx(include_statevectors=True)
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        results_path = [n for n in zf.namelist() if n.endswith("results.json")][0]
        results = json.loads(zf.read(results_path))

        has_sv = any("statevector" in r for r in results.get("raw_results", []))
        assert has_sv

    def test_metadata_is_valid_jsonld(self):
        ctx = _make_ctx()
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        meta_path = [n for n in zf.namelist() if n.endswith("ro-crate-metadata.json")][0]
        meta = json.loads(zf.read(meta_path))

        assert meta["@context"] == "https://w3id.org/ro/crate/1.1/context"
        assert "@graph" in meta
        assert isinstance(meta["@graph"], list)

        # Find root entity
        root = next((e for e in meta["@graph"] if e.get("@id") == "./"), None)
        assert root is not None
        assert root["@type"] == "Dataset"
        assert "datePublished" in root

    def test_metadata_has_no_author_when_not_provided(self):
        ctx = _make_ctx(author_name=None)
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        meta_path = [n for n in zf.namelist() if n.endswith("ro-crate-metadata.json")][0]
        meta = json.loads(zf.read(meta_path))

        root = next((e for e in meta["@graph"] if e.get("@id") == "./"), None)
        assert "author" not in root

    def test_metadata_includes_author_when_provided(self):
        ctx = _make_ctx(author_name="Jane Doe", author_affiliation="University of Testing")
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        meta_path = [n for n in zf.namelist() if n.endswith("ro-crate-metadata.json")][0]
        meta = json.loads(zf.read(meta_path))

        root = next((e for e in meta["@graph"] if e.get("@id") == "./"), None)
        assert "author" in root

        author = next((e for e in meta["@graph"] if e.get("@id") == "#author"), None)
        assert author is not None
        assert author["name"] == "Jane Doe"

        org = next((e for e in meta["@graph"] if e.get("@id") == "#affiliation"), None)
        assert org is not None
        assert org["name"] == "University of Testing"

    def test_provenance_contains_runners(self):
        ctx = _make_ctx()
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        prov_path = [n for n in zf.namelist() if n.endswith("provenance.json")][0]
        prov = json.loads(zf.read(prov_path))

        assert prov["platform"] == "Quantum Rosetta"
        assert "qiskit" in prov["runners_used"]
        assert "cirq" in prov["runners_used"]
        assert prov["canonical_input_format"] == "OpenQASM 2.0"
        assert "runner_configurations" in prov

    def test_provenance_includes_suite_source_when_set(self):
        ctx = _make_ctx(suite_source="MQT Bench")
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        prov_path = [n for n in zf.namelist() if n.endswith("provenance.json")][0]
        prov = json.loads(zf.read(prov_path))

        assert prov["suite_source"] == "MQT Bench"
