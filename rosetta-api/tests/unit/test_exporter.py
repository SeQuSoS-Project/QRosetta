# Unit tests for the FAIR data export engine (services/exporter.py).

import json
import zipfile
import io
import pytest
from services.exporter import (
    ExportContext,
    ExportFormat,
    build_ro_crate,
    infer_export_mode,
    PROCESS_RUN_CRATE_PROFILE,
)
from services.report_filters import remove_statevectors


def _load_metadata(zip_bytes):
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
    meta_path = [n for n in zf.namelist() if n.endswith("ro-crate-metadata.json")][0]
    return json.loads(zf.read(meta_path))


def _by_id(meta):
    return {e["@id"]: e for e in meta["@graph"]}


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
        "pairwise_agreement": [
            {
                "simulators": ["qiskit", "cirq"],
                "mode": "statevector",
                "agreement": "agree_after_bit_reversal",
                "registered_transform": "bit_reversal",
                "metrics": {
                    "direct_fidelity": 0.0,
                    "bit_reversed_fidelity": 1.0,
                },
                "provenance": {
                    "qubit_ordering": {"qiskit": "lsb", "cirq": "msb"},
                    "seed": {"qiskit": None, "cirq": None},
                    "sdk_versions": {"qiskit": {}, "cirq": {}},
                },
            }
        ],
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
        result = remove_statevectors(data)
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
        result = remove_statevectors(data)
        for item in result["raw_results"]:
            assert "statevector" not in item

    def test_preserves_non_statevector_data(self):
        data = {"counts": {"00": 512, "11": 512}, "simulator": "qiskit"}
        result = remove_statevectors(data)
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


    def test_results_preserve_pairwise_agreement_records(self):
        ctx = _make_ctx(include_statevectors=False)
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        results_path = [n for n in zf.namelist() if n.endswith("results.json")][0]
        results = json.loads(zf.read(results_path))

        pairwise = results["divergence_report"]["pairwise_agreement"]
        assert pairwise[0]["agreement"] == "agree_after_bit_reversal"
        assert pairwise[0]["registered_transform"] == "bit_reversal"
        assert pairwise[0]["metrics"]["bit_reversed_fidelity"] == 1.0

    def test_provenance_summarizes_pairwise_agreement_evidence(self):
        ctx = _make_ctx()
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        prov_path = [n for n in zf.namelist() if n.endswith("provenance.json")][0]
        prov = json.loads(zf.read(prov_path))

        summary = prov["pairwise_agreement_evidence"]
        assert summary["record_count"] == 1
        assert summary["by_mode"] == {"statevector": 1}
        assert summary["by_agreement"] == {"statevector": {"agree_after_bit_reversal": 1}}
        assert summary["by_registered_transform"] == {"statevector": {"bit_reversal": 1}}
        assert "results.json" in summary["location"]


class TestExecutedSdkVersions:
    """Runners report the SDK versions they actually executed under (importlib.metadata).
    The exporter must surface these as ground truth, falling back to the requirements
    scrape only when absent (older reports)."""

    def _results_with_versions(self):
        results = json.loads(json.dumps(SAMPLE_RESULTS_SV))
        for r in results["raw_results"]:
            if r["simulator"] == "qiskit":
                r["sdk_versions"] = {"qiskit": "2.4.1", "qiskit-aer": "0.17.2"}
        return results

    def test_software_application_uses_executed_versions(self):
        ctx = _make_ctx(results=self._results_with_versions())
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        meta_path = [n for n in zf.namelist() if n.endswith("ro-crate-metadata.json")][0]
        meta = json.loads(zf.read(meta_path))

        qiskit_app = next((e for e in meta["@graph"] if e.get("@id") == "#qiskit"), None)
        assert qiskit_app is not None
        assert "qiskit 2.4.1" in qiskit_app["softwareVersion"]
        assert "qiskit-aer 0.17.2" in qiskit_app["softwareVersion"]
        # Structured, machine-readable pins for reproducibility.
        assert "qiskit==2.4.1" in qiskit_app["softwareRequirements"]

    def test_provenance_records_executed_versions(self):
        ctx = _make_ctx(results=self._results_with_versions())
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        prov_path = [n for n in zf.namelist() if n.endswith("provenance.json")][0]
        prov = json.loads(zf.read(prov_path))

        assert prov["runner_configurations"]["qiskit"]["sdk_versions"] == {
            "qiskit": "2.4.1",
            "qiskit-aer": "0.17.2",
        }

    def test_falls_back_when_no_executed_versions(self):
        """Reports predating sdk_versions reporting must still export without crashing."""
        ctx = _make_ctx()  # SAMPLE_RESULTS_SV has no sdk_versions
        zip_bytes = build_ro_crate(ctx)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")

        prov_path = [n for n in zf.namelist() if n.endswith("provenance.json")][0]
        prov = json.loads(zf.read(prov_path))

        assert prov["runner_configurations"]["qiskit"]["sdk_versions"] == {}


SAMPLE_RESULTS_MEASURED = {
    "input_qasm": SAMPLE_QASM,
    "n_shots": 128,
    "seed": 12345,
    "divergence_report": {
        "simulators": ["qiskit", "qibo"],
        "pairwise_agreement": [
            {
                "simulators": ["qiskit", "qibo"],
                "mode": "measured",
                "agreement": "agree_after_bit_reversal",
                "registered_transform": "bit_reversal",
                "metrics": {
                    "js_divergence": 0.69,
                    "statistical_test": {"basis": "bit_reversal", "verdict": "consistent"},
                },
                "provenance": {"qubit_ordering": {"qiskit": "lsb", "qibo": "msb"}},
            }
        ],
        "statistical_test_summary": {"family_size": 1, "verdict_counts": {"consistent": 1}},
    },
    "raw_results": [
        {"simulator": "qiskit", "counts": {"001": 128}, "optimization_level": 0,
         "seed": 12345, "qubit_ordering": "lsb", "execution_time_sec": 0.09},
        {"simulator": "qibo", "counts": {"100": 128}, "optimization_level": 0,
         "seed": 12345, "qubit_ordering": "msb", "execution_time_sec": 0.05},
    ],
}


def _measured_ctx(**overrides):
    defaults = dict(
        qasm_string=SAMPLE_QASM,
        results=SAMPLE_RESULTS_MEASURED,
        mode="measured",
        runner_services={"qiskit": {"enabled": True}, "qibo": {"enabled": True}},
    )
    defaults.update(overrides)
    return ExportContext(**defaults)


class TestProcessRunCrateProfile:
    """The crate conforms to the Process Run Crate profile: root conformsTo the profile,
    and each backend execution is its own CreateAction with a single instrument."""

    def test_root_conforms_to_rocrate_and_process_profile(self):
        meta = _load_metadata(build_ro_crate(_measured_ctx()))
        root = _by_id(meta)["./"]
        conforms = {c["@id"] for c in root["conformsTo"]}
        assert "https://w3id.org/ro/crate/1.1" in conforms
        assert PROCESS_RUN_CRATE_PROFILE in conforms

    def test_profile_entity_present(self):
        meta = _load_metadata(build_ro_crate(_measured_ctx()))
        profile = _by_id(meta).get(PROCESS_RUN_CRATE_PROFILE)
        assert profile is not None
        assert profile["@type"] == "CreativeWork"
        assert profile["version"] == "0.5"

    def test_one_create_action_per_execution_with_single_instrument(self):
        meta = _load_metadata(build_ro_crate(_measured_ctx()))
        byid = _by_id(meta)
        for sim in ("qiskit", "qibo"):
            action = byid.get(f"#run-{sim}")
            assert action is not None
            assert action["@type"] == "CreateAction"
            # profile MUST: a single instrument identifying the executed tool
            assert action["instrument"] == {"@id": f"#{sim}"}
            assert action["result"] == {"@id": f"#output-{sim}"}
            assert {"@id": "circuit.qasm"} in action["object"]

    def test_parameters_recorded_as_property_values(self):
        meta = _load_metadata(build_ro_crate(_measured_ctx()))
        byid = _by_id(meta)
        assert byid["#param-n_shots"]["value"] == 128
        assert byid["#param-seed"]["value"] == 12345
        run = byid["#run-qiskit"]
        assert {"@id": "#param-n_shots"} in run["object"]
        assert {"@id": "#param-seed"} in run["object"]

    def test_agreement_analysis_action_consumes_outputs(self):
        meta = _load_metadata(build_ro_crate(_measured_ctx()))
        action = _by_id(meta)["#agreement-analysis"]
        assert action["instrument"] == {"@id": "#quantum-rosetta"}
        assert {"@id": "#output-qiskit"} in action["object"]
        assert {"@id": "#output-qibo"} in action["object"]
        assert action["result"] == {"@id": "results.json"}

    def test_root_mentions_all_actions(self):
        meta = _load_metadata(build_ro_crate(_measured_ctx()))
        root = _by_id(meta)["./"]
        mentioned = {m["@id"] for m in root["mentions"]}
        assert mentioned == {"#run-qiskit", "#run-qibo", "#agreement-analysis"}

    def test_failed_execution_recorded_as_failed_status(self):
        results = json.loads(json.dumps(SAMPLE_RESULTS_MEASURED))
        results["raw_results"][1] = {"simulator": "qibo", "error": "backend crashed"}
        meta = _load_metadata(build_ro_crate(_measured_ctx(results=results)))
        action = _by_id(meta)["#run-qibo"]
        assert action["actionStatus"] == "http://schema.org/FailedActionStatus"
        assert action["error"] == "backend crashed"

    def test_no_duplicate_graph_ids(self):
        meta = _load_metadata(build_ro_crate(_measured_ctx()))
        ids = [e["@id"] for e in meta["@graph"]]
        assert len(ids) == len(set(ids))

    def test_software_application_deduplicated_for_virtual_keys(self):
        # Self-comparison uses virtual '~opt~run' keys that share one canonical backend;
        # each is its own execution action but a single SoftwareApplication entity.
        results = json.loads(json.dumps(SAMPLE_RESULTS_MEASURED))
        results["raw_results"] = [
            {"simulator": "qiskit~opt0~run1", "counts": {"001": 128}, "optimization_level": 0},
            {"simulator": "qiskit~opt1~run2", "counts": {"001": 128}, "optimization_level": 1},
        ]
        meta = _load_metadata(build_ro_crate(_measured_ctx(results=results)))
        byid = _by_id(meta)
        apps = [e for e in meta["@graph"]
                if e.get("@type") == "SoftwareApplication" and e["@id"] == "#qiskit"]
        assert len(apps) == 1  # deduplicated
        # but two distinct execution actions, both instrumented by #qiskit
        assert byid["#run-qiskit-opt0-run1"]["instrument"] == {"@id": "#qiskit"}
        assert byid["#run-qiskit-opt1-run2"]["instrument"] == {"@id": "#qiskit"}

    def test_provenance_summarizes_statistical_verdicts(self):
        ctx = _measured_ctx()
        zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)), "r")
        prov_path = [n for n in zf.namelist() if n.endswith("provenance.json")][0]
        prov = json.loads(zf.read(prov_path))
        summary = prov["pairwise_agreement_evidence"]
        assert summary["by_statistical_verdict"] == {"measured": {"consistent": 1}}

    def test_statevector_export_omits_statistical_verdict_key(self):
        # Statevector exports have no statistical test; the key must be absent, not empty.
        ctx = _make_ctx()
        zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)), "r")
        prov_path = [n for n in zf.namelist() if n.endswith("provenance.json")][0]
        prov = json.loads(zf.read(prov_path))
        assert "by_statistical_verdict" not in prov["pairwise_agreement_evidence"]


class TestPublicationArtifactsInCrate:
    """Opt-in publication figures/tables bundle into the crate and are registered as
    data entities; default (no selection) leaves the crate unchanged (non-breaking)."""

    def _basenames(self, zf):
        return [n.split("/", 1)[1] for n in zf.namelist()]

    def test_artifacts_absent_by_default(self):
        zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(_measured_ctx())), "r")
        names = self._basenames(zf)
        assert not any(n.startswith(("figures/", "tables/")) for n in names)
        # Core files unchanged.
        assert "ro-crate-metadata.json" in names and "results.json" in names

    def test_artifacts_bundled_and_registered_when_selected(self):
        ctx = _measured_ctx(publication_artifacts={
            "categories": ["agreement", "statistical"],
            "figure_formats": ["svg"], "table_formats": ["csv", "latex"],
        })
        zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)), "r")
        names = self._basenames(zf)
        # Files present in the ZIP.
        assert "figures/agreement_distribution.svg" in names
        assert "tables/agreement.csv" in names
        assert "tables/agreement.latex" in names
        assert "tables/statistical_test.csv" in names
        # Registered as RO-Crate File entities in hasPart + as analysis results.
        meta = _load_metadata(build_ro_crate(ctx))
        byid = _by_id(meta)
        fig = byid.get("figures/agreement_distribution.svg")
        assert fig is not None and fig["@type"] == "File"
        assert fig["encodingFormat"] == "image/svg+xml"
        root_parts = {p["@id"] for p in byid["./"]["hasPart"]}
        assert "figures/agreement_distribution.svg" in root_parts
        analysis_results = {r["@id"] for r in byid["#agreement-analysis"]["result"]}
        assert "results.json" in analysis_results
        assert "tables/agreement.csv" in analysis_results

    def test_crate_still_conforms_with_artifacts(self):
        ctx = _measured_ctx(publication_artifacts={
            "categories": ["agreement"], "figure_formats": ["svg"], "table_formats": ["csv"],
        })
        meta = _load_metadata(build_ro_crate(ctx))
        conforms = {c["@id"] for c in _by_id(meta)["./"]["conformsTo"]}
        assert "https://w3id.org/ro/crate/1.1" in conforms
        assert PROCESS_RUN_CRATE_PROFILE in conforms
        ids = [e["@id"] for e in meta["@graph"]]
        assert len(ids) == len(set(ids))  # no duplicate @ids

    def test_empty_categories_generate_nothing(self):
        ctx = _measured_ctx(publication_artifacts={
            "categories": [], "figure_formats": ["svg"], "table_formats": ["csv"],
        })
        names = self._basenames(zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)), "r"))
        assert not any(n.startswith(("figures/", "tables/")) for n in names)


# A batch result (POST /run_batch_suite) never duplicates the circuit/n_shots/seed at the
# top level — each queued circuit is its own entry in benchmark_summary. "qiskit" and "qibo"
# deliberately both appear in both tasks, to catch the exact bug this test suite is guarding
# against: treating a batch as a single task silently drops every task's data after the first
# occurrence of each runner id.
SAMPLE_RESULTS_BATCH_MEASURED = {
    "benchmark_summary": [
        {
            "task_name": "bell (2q)",
            "input_qasm": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n",
            "n_shots": 256,
            "seed": 999,
            "divergence_report": {
                "simulators": ["qiskit", "qibo"],
                "pairwise_agreement": [
                    {"simulators": ["qiskit", "qibo"], "mode": "measured",
                     "agreement": "agree_directly", "registered_transform": "none",
                     "metrics": {}, "provenance": {}}
                ],
            },
            "raw_results": [
                {"simulator": "qiskit", "counts": {"00": 128, "11": 128},
                 "optimization_level": 0, "transpiled_qasm": "// bell qiskit"},
                {"simulator": "qibo", "counts": {"00": 130, "11": 126},
                 "optimization_level": 0, "transpiled_qasm": "// bell qibo"},
            ],
        },
        {
            "task_name": "ghz (3q)",
            "input_qasm": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[3];\nh q[0];\ncx q[0],q[1];\ncx q[1],q[2];\n",
            "n_shots": 256,
            "seed": 999,
            "divergence_report": {
                "simulators": ["qiskit", "qibo"],
                "pairwise_agreement": [
                    {"simulators": ["qiskit", "qibo"], "mode": "measured",
                     "agreement": "agree_directly", "registered_transform": "none",
                     "metrics": {}, "provenance": {}}
                ],
            },
            "raw_results": [
                {"simulator": "qiskit", "counts": {"000": 130, "111": 126},
                 "optimization_level": 0, "transpiled_qasm": "// ghz qiskit"},
                {"simulator": "qibo", "error": "TIMEOUT (5s): the simulation exceeded the time budget and was terminated."},
            ],
        },
    ],
}


def _batch_ctx(**overrides):
    defaults = dict(
        qasm_string="",
        results=SAMPLE_RESULTS_BATCH_MEASURED,
        mode="measured",
        runner_services={"qiskit": {"enabled": True}, "qibo": {"enabled": True}},
    )
    defaults.update(overrides)
    return ExportContext(**defaults)


class TestInferExportMode:
    def test_single_circuit_measured(self):
        assert infer_export_mode({"n_shots": 128, "raw_results": []}) == "measured"

    def test_single_circuit_statevector(self):
        assert infer_export_mode({"raw_results": []}) == "statevector"

    def test_batch_measured_detected_from_first_task(self):
        # n_shots never appears at the top level for a batch — only inside benchmark_summary.
        assert infer_export_mode(SAMPLE_RESULTS_BATCH_MEASURED) == "measured"

    def test_batch_statevector_detected_from_first_task(self):
        results = {"benchmark_summary": [{"raw_results": []}, {"raw_results": []}]}
        assert infer_export_mode(results) == "statevector"


class TestBatchExport:
    """A batch/multi-circuit export must describe every task's circuit, and must not
    collapse repeated runner ids across tasks into a single execution."""

    def test_one_circuit_file_per_task_with_real_content(self):
        zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(_batch_ctx())), "r")
        names = [n.split("/", 1)[1] for n in zf.namelist()]
        assert "circuits/bell-2q.qasm" in names
        assert "circuits/ghz-3q.qasm" in names
        assert "circuit.qasm" not in names  # no misleading single/empty file for a batch
        bell_qasm = zf.read([n for n in zf.namelist() if n.endswith("circuits/bell-2q.qasm")][0])
        assert b"cx q[0],q[1];" in bell_qasm
        ghz_qasm = zf.read([n for n in zf.namelist() if n.endswith("circuits/ghz-3q.qasm")][0])
        assert b"cx q[1],q[2];" in ghz_qasm

    def test_root_hasPart_lists_every_task_circuit(self):
        meta = _load_metadata(build_ro_crate(_batch_ctx()))
        parts = {p["@id"] for p in _by_id(meta)["./"]["hasPart"]}
        assert "circuits/bell-2q.qasm" in parts
        assert "circuits/ghz-3q.qasm" in parts

    def test_same_runner_gets_a_distinct_action_per_task(self):
        # This is the exact bug: qiskit runs in both tasks and must not collapse to one action.
        meta = _load_metadata(build_ro_crate(_batch_ctx()))
        byid = _by_id(meta)
        bell_action = byid["#run-qiskit-bell-2q"]
        ghz_action = byid["#run-qiskit-ghz-3q"]
        assert bell_action["actionStatus"] == "http://schema.org/CompletedActionStatus"
        assert ghz_action["actionStatus"] == "http://schema.org/CompletedActionStatus"
        assert bell_action["object"] == [{"@id": "circuits/bell-2q.qasm"},
                                          {"@id": "#param-n_shots"}, {"@id": "#param-seed"},
                                          {"@id": "#param-optlevel-qiskit-bell-2q"}]
        assert ghz_action["object"][0] == {"@id": "circuits/ghz-3q.qasm"}

    def test_per_task_failure_recorded_independently(self):
        # qibo fails on the ghz task but succeeded on the bell task — both must be visible.
        meta = _load_metadata(build_ro_crate(_batch_ctx()))
        byid = _by_id(meta)
        assert byid["#run-qibo-bell-2q"]["actionStatus"] == "http://schema.org/CompletedActionStatus"
        failed = byid["#run-qibo-ghz-3q"]
        assert failed["actionStatus"] == "http://schema.org/FailedActionStatus"
        assert "TIMEOUT" in failed["error"]

    def test_transpiled_circuits_namespaced_per_task(self):
        zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(_batch_ctx())), "r")
        names = [n.split("/", 1)[1] for n in zf.namelist()]
        assert "transpiled_circuits/bell-2q/qiskit.qasm" in names
        assert "transpiled_circuits/ghz-3q/qiskit.qasm" in names
        bell = zf.read([n for n in zf.namelist() if n.endswith("transpiled_circuits/bell-2q/qiskit.qasm")][0])
        ghz = zf.read([n for n in zf.namelist() if n.endswith("transpiled_circuits/ghz-3q/qiskit.qasm")][0])
        assert bell == b"// bell qiskit"
        assert ghz == b"// ghz qiskit"

    def test_shared_n_shots_and_seed_present_once(self):
        # n_shots/seed are echoed identically into every task by /run_batch_suite; the crate
        # should record them once as shared parameters, not lose them because they are absent
        # from the (nonexistent) top level.
        meta = _load_metadata(build_ro_crate(_batch_ctx()))
        byid = _by_id(meta)
        assert byid["#param-n_shots"]["value"] == 256
        assert byid["#param-seed"]["value"] == 999

    def test_mode_inferred_measured_for_batch(self):
        ctx = _batch_ctx(mode=infer_export_mode(SAMPLE_RESULTS_BATCH_MEASURED))
        assert ctx.mode == "measured"

    def test_no_duplicate_graph_ids_in_batch(self):
        meta = _load_metadata(build_ro_crate(_batch_ctx()))
        ids = [e["@id"] for e in meta["@graph"]]
        assert len(ids) == len(set(ids))

    def test_single_circuit_path_unaffected_by_batch_support(self):
        # Guard against regressions: a plain single-circuit export must still use the
        # unscoped ids/paths from before batch support existed.
        meta = _load_metadata(build_ro_crate(_measured_ctx()))
        byid = _by_id(meta)
        assert "#run-qiskit" in byid
        assert "circuit.qasm" in {p["@id"] for p in byid["./"]["hasPart"]}


def _provenance(zip_bytes):
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
    return json.loads(zf.read([n for n in zf.namelist() if n.endswith("provenance.json")][0]))


class TestBatchPublicationArtifacts:
    def test_batch_bundles_artifacts_per_task(self):
        ctx = _batch_ctx(publication_artifacts={
            "categories": ["agreement", "statistical"],
            "figure_formats": ["svg"], "table_formats": ["csv"],
        })
        data = build_ro_crate(ctx)
        names = [n.split("/", 1)[1] for n in zipfile.ZipFile(io.BytesIO(data)).namelist()]
        for task in ("bell-2q", "ghz-3q"):
            assert f"figures/{task}/agreement_distribution.svg" in names
            assert f"tables/{task}/agreement.csv" in names
        assert "figures/bell-2q/counts_overview.svg" in names
        byid = _by_id(_load_metadata(data))
        entity = byid["tables/bell-2q/agreement.csv"]
        assert entity["name"] == "bell-2q/agreement.csv"
        assert "Task bell (2q)." in entity["description"]
        assert {"@id": "tables/ghz-3q/agreement.csv"} in byid["./"]["hasPart"]


class TestRunnerLocksAndThresholds:
    def test_runner_requirements_lock_is_bundled_and_referenced(self):
        services = {"qiskit": {"enabled": True, "base_url": "http://pytket-qiskit-runner:8000"}}
        data = build_ro_crate(_make_ctx(runner_services=services))
        zf = zipfile.ZipFile(io.BytesIO(data), "r")
        lock = [n for n in zf.namelist() if n.endswith("runners/pytket-qiskit-runner/requirements.lock")]
        assert len(lock) == 1 and b"==" in zf.read(lock[0])
        byid = _by_id(_load_metadata(data))
        path = "runners/pytket-qiskit-runner/requirements.lock"
        assert byid[path]["@type"] == "File"
        assert {"@id": path} in byid["#qiskit"]["softwareRequirements"]
        assert {"@id": path} in byid["./"]["hasPart"]

    def test_omitted_thresholds_export_the_effective_values(self):
        run_config = _provenance(build_ro_crate(_make_ctx()))["run_configuration"]
        assert run_config["agreement_thresholds"] == {
            "fidelity_tolerance": 1e-5, "phase_tolerance": 1e-6, "norm_tolerance": 1e-4}
        assert run_config["agreement_thresholds_requested"] == "none (defaults applied)"

    def test_recorded_pair_thresholds_win_over_defaults(self):
        results = json.loads(json.dumps(SAMPLE_RESULTS_MEASURED))
        results["agreement_thresholds"] = {"js_threshold": 0.02, "hellinger_threshold": None}
        for rec in results["divergence_report"]["pairwise_agreement"]:
            rec.setdefault("metrics", {})["hellinger_threshold"] = 0.2
        run_config = _provenance(build_ro_crate(_measured_ctx(results=results)))["run_configuration"]
        assert run_config["agreement_thresholds"] == {"js_threshold": 0.02, "hellinger_threshold": 0.2}

    def test_csv_artifact_description_carries_its_caption(self):
        ctx = _measured_ctx(publication_artifacts={
            "categories": ["agreement"], "figure_formats": ["svg"], "table_formats": ["csv", "latex"]})
        byid = _by_id(_load_metadata(build_ro_crate(ctx)))
        csv_desc = byid["tables/agreement.csv"]["description"]
        assert "carries no caption" in csv_desc and "registered-transform lattice" in csv_desc
        assert "carries the caption" in byid["tables/agreement.latex"]["description"]


class TestAnalysisProvenance:
    def test_single_run_records_analysis_version_bypass_and_report_thresholds(self):
        results = json.loads(json.dumps(SAMPLE_RESULTS_BATCH_MEASURED["benchmark_summary"][0]))
        results["bypass_limits"] = True
        results["divergence_report"]["analysis_version"] = "divergence-test"
        results["divergence_report"]["agreement_thresholds"] = {
            "js_threshold": 0.3, "hellinger_threshold": 0.1}
        prov = _provenance(build_ro_crate(_measured_ctx(results=results)))
        config = prov["run_configuration"]
        assert config["analysis_version"] == "divergence-test"
        assert config["bypass_limits"] is True
        assert config["agreement_thresholds"] == {"js_threshold": 0.3, "hellinger_threshold": 0.1}
        assert "exporter_analysis_version" in prov

    def test_batch_records_each_task_request_and_thresholds(self):
        results = json.loads(json.dumps(SAMPLE_RESULTS_BATCH_MEASURED))
        results["benchmark_summary"][0]["task_request"] = {"source": "preset", "algorithm": "bell",
                                                           "qubits": 2}
        prov = _provenance(build_ro_crate(_batch_ctx(results=results)))
        config = prov["run_configuration"]
        assert config["task_requests"]["bell-2q"]["request"]["algorithm"] == "bell"
        assert config["task_requests"]["ghz-3q"]["request"] == "not recorded"
        assert set(config["agreement_thresholds_by_task"]) == {"bell-2q", "ghz-3q"}
        assert config["bypass_limits"] == "not recorded"
