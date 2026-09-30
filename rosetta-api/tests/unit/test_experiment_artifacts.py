"""Unit tests for services/experiment_artifacts.py (stdlib-only bundle builders)."""
import hashlib
import json

from services import experiment_artifacts as art


def test_slug_and_sha256_stable():
    assert art.slug("Grover 5q!") == "grover-5q"
    assert art.slug("") == "circuit"
    # sha256 is order-independent over dict keys and deterministic.
    assert art.sha256({"a": 1, "b": 2}) == art.sha256({"b": 2, "a": 1})
    assert art.sha256("x") == art.sha256("x")


def test_strip_statevectors_replaces_list_keeps_metrics():
    report = {"raw_results": [
        {"simulator": "qiskit", "statevector": [0.0, 1.0], "execution_time_sec": 0.5},
        {"simulator": "none", "statevector": None},
    ]}
    out = art.strip_statevectors(report)
    r0 = out["raw_results"][0]
    assert r0["statevector"] is None
    assert r0["statevector_len"] == 2
    assert r0["statevector_digest_input"] == "json_list"
    assert len(r0["statevector_sha256"]) == 64
    assert r0["execution_time_sec"] == 0.5
    assert "statevector_sha256" not in out["raw_results"][1]


def test_strip_statevectors_hashes_base64_decoded_bytes():
    import base64
    import hashlib
    import numpy as np
    sv = np.array([1 / np.sqrt(2), 0, 0, 1 / np.sqrt(2)], dtype=np.complex128)
    encoded = base64.b64encode(sv.tobytes()).decode("utf-8")
    out = art.strip_statevectors({"raw_results": [{"simulator": "qiskit", "statevector": encoded}]})
    r0 = out["raw_results"][0]
    assert r0["statevector"] is None
    assert r0["statevector_sha256"] == hashlib.sha256(sv.tobytes()).hexdigest()
    assert r0["statevector_len"] == 4
    assert r0["statevector_digest_input"] == "base64_decoded_bytes"


def test_strip_statevectors_marks_display_placeholder_without_hash():
    from services.report_filters import DISPLAY_PLACEHOLDER_PREFIX
    report = {"raw_results": [
        {"simulator": "a", "statevector": DISPLAY_PLACEHOLDER_PREFIX + " for display.>"},
        {"simulator": "b", "statevector": "<x>", "statevector_omitted_for_display": True},
    ]}
    out = art.strip_statevectors(report)
    for r in out["raw_results"]:
        assert r["statevector"] is None
        assert r["statevector_omitted_for_display"] is True
        assert "statevector_sha256" not in r


def test_conformance_rows_success_error_and_timeout():
    summary = [{
        "task_name": "bell (2q)",
        "raw_results": [
            {"simulator": "qiskit"},                                   # success
            {"simulator": "qibo", "error": "boom: mat_dict not defined\nline2"},  # error
            {"simulator": "quest", "error": "Runner timed out after 300s"},       # timeout
        ],
    }]
    rows = art.build_conformance_rows("axisA", summary)
    by_sim = {r["simulator"]: r for r in rows}
    assert by_sim["qiskit"]["status"] == "success"
    assert by_sim["qiskit"]["triage"] == ""
    assert by_sim["qibo"]["status"] == "error"
    assert by_sim["qibo"]["error_signature"] == "boom: mat_dict not defined"  # first line only
    assert by_sim["qibo"]["triage"] == "untriaged"
    assert by_sim["quest"]["status"] == "timeout"


def test_conformance_circuit_level_error():
    summary = [{"task_name": "bv (14q)", "error": "Failed to process task: too big"}]
    rows = art.build_conformance_rows("axisA", summary)
    assert len(rows) == 1
    assert rows[0]["status"] == "circuit_error"
    assert rows[0]["simulator"] == "(circuit)"
    assert rows[0]["triage"] == "untriaged"


def test_prevalence_counts_by_class():
    summary = [
        {"divergence_report": {"pairwise_agreement": [
            {"agreement": "agree_directly"}, {"agreement": "agree_after_bit_reversal"},
            {"agreement": "agree_directly"}]}},
        {"divergence_report": {"pairwise_agreement": [{"agreement": "residual_disagreement"}]}},
        {"error": "nope"},  # no divergence_report -> contributes nothing
    ]
    rows = art.build_prevalence_rows("axisA", summary)
    counts = {r["agreement_class"]: r["pair_count"] for r in rows}
    assert counts == {"agree_directly": 2, "agree_after_bit_reversal": 1,
                      "residual_disagreement": 1}
    assert all(r["axis"] == "axisA" for r in rows)
    assert all(r["pair_scope"] == "compared" for r in rows)


def test_prevalence_counts_not_comparable_separately():
    summary = [{"divergence_report": {"pairwise_agreement": [
        {"agreement": "agree_directly"}, {"agreement": "not_comparable"},
        {"agreement": "not_comparable"}]}}]
    rows = art.build_prevalence_rows("axisA", summary)
    compared = [r for r in rows if r["pair_scope"] == "compared"]
    excluded = [r for r in rows if r["pair_scope"] == "not_comparable"]
    assert compared == [{"axis": "axisA", "count_basis": "agreement_label",
                         "agreement_class": "agree_directly", "pair_count": 1,
                         "pair_scope": "compared", "distance_labels": ""}]
    assert excluded == [{"axis": "axisA", "count_basis": "agreement_label",
                         "agreement_class": "not_comparable", "pair_count": 2,
                         "pair_scope": "not_comparable", "distance_labels": ""}]


def test_measured_prevalence_counts_by_assessment_with_distance_labels_secondary():
    summary = [{"divergence_report": {"pairwise_agreement": [
        {"mode": "measured", "agreement": "agree_after_bit_reversal",
         "measured_assessment": "distinguishable"},
        {"mode": "measured", "agreement": "distance_within_threshold",
         "measured_assessment": "distinguishable"},
        {"mode": "measured", "agreement": "agree_after_bit_reversal",
         "measured_assessment": "consistent_within_shot_noise"},
        {"mode": "measured", "agreement": "distance_exceeds_threshold",
         "metrics": {"statistical_test": {"verdict": "consistent"}}},
        {"mode": "measured", "agreement": "not_comparable", "measured_assessment": "not_comparable"},
    ]}}]
    rows = {r["agreement_class"]: r for r in art.build_prevalence_rows("m", summary)}
    assert {k: r["pair_count"] for k, r in rows.items()} == {
        "distinguishable": 2, "consistent_within_shot_noise": 2, "not_comparable": 1}
    assert all(r["count_basis"] == "measured_assessment" for r in rows.values())
    assert rows["distinguishable"]["distance_labels"] == (
        "agree_after_bit_reversal:1; distance_within_threshold:1")
    assert rows["consistent_within_shot_noise"]["distance_labels"] == (
        "agree_after_bit_reversal:1; distance_exceeds_threshold:1")
    assert rows["not_comparable"]["pair_scope"] == "not_comparable"


def test_conformance_uses_dispatch_status():
    summary = [{"task_name": "bell (2q)", "circuit_id": "000_bell", "raw_results": [
        {"simulator": "qiskit", "dispatch_status": "ok"},
        {"simulator": "qibo", "error": "UNAVAILABLE: no route", "dispatch_status": "offline"},
        {"simulator": "quest", "error": "something about a timeout", "dispatch_status": "error"},
    ]}]
    by_sim = {r["simulator"]: r for r in art.build_conformance_rows("axisA", summary)}
    assert by_sim["qiskit"]["status"] == "success"
    assert by_sim["qibo"]["status"] == "offline"
    assert by_sim["quest"]["status"] == "error"
    assert by_sim["qiskit"]["circuit_id"] == "000_bell"


def test_collect_sdk_versions_first_seen_and_accumulate():
    s1 = [{"raw_results": [{"simulator": "qiskit", "sdk_versions": {"qiskit": "2.4.1"}}]}]
    s2 = [{"raw_results": [{"simulator": "qiskit", "sdk_versions": {"qiskit": "9.9"}},
                           {"simulator": "qibo", "sdk_versions": {"qibo": "0.2"}}]}]
    acc = art.collect_sdk_versions(s1)
    art.collect_sdk_versions(s2, into=acc)          # accumulates, first-seen wins
    assert acc == {"qiskit": {"qiskit": "2.4.1"}, "qibo": {"qibo": "0.2"}}


def test_error_logs_grouped_per_simulator():
    rows = [
        {"axis": "a", "circuit": "bv (4q)", "simulator": "qibo", "error_signature": "e1"},
        {"axis": "a", "circuit": "grover (5q)", "simulator": "qibo", "error_signature": "e2"},
        {"axis": "a", "circuit": "bell (2q)", "simulator": "qiskit", "error_signature": ""},
    ]
    logs = art.build_error_logs(rows)
    assert set(logs) == {"qibo"}                    # qiskit had no signature
    assert "e1" in logs["qibo"] and "e2" in logs["qibo"]


def test_csv_string_headers_and_rows():
    csv = art.csv_string([{"axis": "a", "agreement_class": "agree_directly", "pair_count": 3}],
                         art.PREVALENCE_FIELDS)
    lines = csv.strip().splitlines()
    assert lines[0] == "axis,count_basis,agreement_class,pair_count,pair_scope,distance_labels"
    assert lines[1] == "a,,agree_directly,3,,"


def test_manifest_provenance_and_integrity_notes():
    m = art.build_manifest(
        config={"mode": "measured"}, git_sha="abc123", api_base="in-app",
        requested_seed=None, effective_seeds={"measured_preprocOn": 42},
        circuits=[{"id": "000_bell", "algorithm": "bell", "qubits": 2, "qasm": "OPENQASM 2.0;"}],
        sdk_versions={"qiskit": {"qiskit": "2.4.1"}})
    assert m["git_sha"] == "abc123"
    assert m["config_sha256"] == art.sha256({"mode": "measured"})
    assert m["circuits"][0]["qasm_sha256"] == hashlib.sha256(b"OPENQASM 2.0;").hexdigest()
    assert m["circuits"][0]["qasm_file"] == "inputs/000_bell.qasm"
    assert "qasm" not in m["circuits"][0]           # only the hash is stored, not raw QASM
    assert m["image_digests"].startswith("not recorded")
    assert m["seed_derivation"] == "not recorded"
    assert m["outputs"]["readme"] == "README.txt"
    assert "triage" in m["notes"].lower()
    # extra_notes are appended, not lost.
    m2 = art.build_manifest(config={}, git_sha="x", api_base="y", requested_seed=1,
                            effective_seeds={}, circuits=[], sdk_versions={},
                            extra_notes="Resolution errors: 2.")
    assert "Resolution errors: 2." in m2["notes"]


def test_recorded_value_skips_missing_and_unknown():
    reports = [{"git_sha": "unknown"}, {}, {"git_sha": "abc"}, {"git_sha": "def"}]
    assert art.recorded_value(reports, "git_sha") == "abc"
    assert art.recorded_value([{}], "git_sha") is None


def test_triage_readme_states_the_gate():
    r = art.TRIAGE_README
    assert "untriaged" in r
    # names the four triage buckets and the separation of the two outputs
    assert "adapter / SDK / by-design / resource" in r
    assert "separate outputs" in r


def test_manifest_json_serializable():
    m = art.build_manifest(config={"a": 1}, git_sha="g", api_base="b", requested_seed=None,
                           effective_seeds={}, circuits=[], sdk_versions={})
    json.dumps(m)  # must not raise
