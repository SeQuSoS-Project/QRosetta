"""Compile-only services in a run: validated requests, dispatch after the simulators, a
recorded compile input, compiled records kept apart from raw_results, and their crate files."""
import asyncio
import io
import json
import zipfile

import pytest
from fastapi import HTTPException

import services.compilation as compilation
import services.job_manager as job_manager
from schemas import ExportPayload
from services.circuit_texts import circuit_texts
from services.run_registry import EXCLUSIVE
from services.exporter import build_export_context, build_ro_crate, invalid_runner_keys

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q -> c;\n'


def test_unknown_compilers_and_levels_are_rejected():
    compilation.validate_compilers({"pyzx": [1, 2], "qmap": [0]})
    with pytest.raises(HTTPException) as unknown:
        compilation.validate_compilers({"qiskit": [0]})
    assert unknown.value.status_code == 400 and "qiskit" in unknown.value.detail
    with pytest.raises(HTTPException) as level:
        compilation.validate_compilers({"bqskit": [0]})
    assert "no optimization level 0" in level.value.detail


def test_compile_request_shapes_are_rejected_by_the_schema(client):
    for bad in ({"pyzx": []}, {"pyzx": [1, 1]}, {"pyzx": [True]}, {"pyzx": "1"}):
        r = client.post("/compare", json={"qasm_string": QASM, "compilers": bad})
        assert r.status_code == 422, bad
    r = client.post("/compare", json={"qasm_string": QASM, "compilers": {"nope": [0]}})
    assert r.status_code == 400 and "nope" in r.json()["detail"]


def _runner_result(name):
    return {"simulator": name, "transpiled_qasm": "h q[0];", "dispatch_status": "ok"}


def _compile_result(key, level):
    return {"simulator": key, "optimization_level": level, "transpiled_qasm": "OPENQASM 2.0;\nqreg q[2];\nh q[0];\n",
            "passes_applied": ["pass A"], "gate_count": 1, "circuit_depth": 1,
            "gate_metrics_basis": "basis", "sdk_versions": {"pyzx": "0.10.6"}, "dispatch_status": "ok",
            "runner_code_sha256": "abc", "timing_samples": 1, "timing_statistic": "median",
            "device": "CPU", "exclusive": False, "simulation_time_sec": None}


@pytest.fixture
def fake_dispatch(monkeypatch):
    calls = []

    async def dispatch(runner_urls, runner_payload=None, timeout_seconds=None, runner_statuses=None):
        calls.append((dict(runner_urls), dict(runner_payload or {})))
        if all(url.endswith("/compile") for url in runner_urls.values()):
            config = runner_payload["runner_config"]
            calls[-1][1]["exclusive_during_dispatch"] = EXCLUSIVE.get()
            return [_compile_result(cid if len(levels) == 1 else f"{cid}~opt{lvl}~run1", lvl)
                    for cid, levels in config.items() for lvl in levels]
        return [_runner_result(name) for name in runner_urls]

    monkeypatch.setattr(job_manager, "dispatch_to_runners", dispatch)
    monkeypatch.setattr(compilation, "dispatch_to_runners", dispatch)
    return calls


def test_compilers_run_after_the_simulators_and_are_recorded_apart(fake_dispatch):
    pytest.importorskip("pytket")
    report = asyncio.run(job_manager.run_single_circuit_comparison(
        QASM, target_simulators=["qiskit"], compilers={"pyzx": [1, 2]}))
    (runner_urls, _), (compile_urls, compile_payload) = fake_dispatch
    assert list(runner_urls) == ["qiskit"]
    assert compile_urls == {"pyzx": "http://pyzx-compiler:8000/compile"}
    assert compile_payload["runner_config"] == {"pyzx": [1, 2]}
    assert compile_payload["circuit_data"] == report["compile_input"]["qasm"]
    assert "measure" not in report["compile_input"]["qasm"]
    assert report["compile_input"]["qasm"] == report["dispatched_circuits"][0]["qasm"]
    assert [r["simulator"] for r in report["raw_results"]] == ["qiskit"]
    keys = [c["compiler"] for c in report["compiled_circuits"]]
    assert keys == ["pyzx~opt1~run1", "pyzx~opt2~run1"]
    record = report["compiled_circuits"][0]
    assert record["compiler_id"] == "pyzx" and record["compiler_name"] == "PyZX"
    assert record["compiler_code_sha256"] == "abc"
    for absent in ("timing_samples", "timing_statistic", "device", "exclusive", "simulation_time_sec", "simulator"):
        assert absent not in record


def test_no_compilers_means_no_compile_fields(fake_dispatch):
    pytest.importorskip("pytket")
    report = asyncio.run(job_manager.run_single_circuit_comparison(QASM, target_simulators=["qiskit"]))
    assert len(fake_dispatch) == 1
    assert "compile_input" not in report and "compiled_circuits" not in report


def test_measured_circuit_with_mid_circuit_measurement_is_not_compiled(fake_dispatch):
    pytest.importorskip("pytket")
    mid = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];\n'
           'h q[0];\nmeasure q[0] -> c[0];\n')
    report = asyncio.run(job_manager.run_single_circuit_measurement(
        mid, 100, target_simulators=["qiskit"], compilers={"qmap": [0]}))
    assert report["compile_input"] is None
    (record,) = report["compiled_circuits"]
    assert record["dispatch_status"] == "skipped" and record["compiler"] == "qmap~opt0~run1"
    assert "mid-circuit measurement" in record["error"] and "measured mode instead" not in record["error"]
    assert all(not url.endswith("/compile") for urls, _ in fake_dispatch for url in urls.values())


def test_crate_holds_compile_input_and_outputs_but_results_json_does_not(fake_dispatch):
    pytest.importorskip("pytket")
    report = asyncio.run(job_manager.run_single_circuit_comparison(
        QASM, target_simulators=["qiskit"], compilers={"pyzx": [1]}))
    zip_bytes = build_ro_crate(build_export_context(report, ExportPayload()))
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = {n.split("/", 1)[1]: n for n in zf.namelist()}
        assert zf.read(names["compile_input.qasm"]).decode() == report["compile_input"]["qasm"]
        assert zf.read(names["compiled_circuits/pyzx~opt1~run1.qasm"]).decode() == report["compiled_circuits"][0]["transpiled_qasm"]
        results = json.loads(zf.read(names["results.json"]))
        zf_lock = zf.read(names["compilers/pyzx-compiler/requirements.lock"]).decode()
        zf_provenance = zf.read(names["provenance.json"])
        metadata = json.loads(zf.read(names["ro-crate-metadata.json"]))
    assert "qasm" not in results["compile_input"]
    assert "transpiled_qasm" not in results["compiled_circuits"][0]
    ids = {entity["@id"] for entity in metadata["@graph"]}
    action = next(e for e in metadata["@graph"] if e["@id"] == "#compile-pyzx~opt1~run1")
    assert action["object"] == {"@id": "compile_input.qasm"}
    assert action["result"] == {"@id": "compiled_circuits/pyzx~opt1~run1.qasm"}
    assert action["instrument"] == {"@id": "#compiler-pyzx"} and "#compiler-pyzx" in ids
    root = next(e for e in metadata["@graph"] if e["@id"] == "./")
    assert {"@id": "#compile-pyzx~opt1~run1"} in root["mentions"]
    provenance = json.loads(zf_provenance)
    assert provenance["compile_only_services"][0]["compiler"] == "pyzx~opt1~run1"
    assert {"compile_input.qasm", "compiled_circuits/pyzx~opt1~run1.qasm",
            "compilers/pyzx-compiler/requirements.lock"} <= ids
    assert "pyzx==0.10.6" in zf_lock


def test_share_texts_carry_compile_records_without_extra_fields(fake_dispatch):
    pytest.importorskip("pytket")
    report = asyncio.run(job_manager.run_single_circuit_comparison(
        QASM, target_simulators=["qiskit"], compilers={"pyzx": [1]}))
    texts = circuit_texts(report)
    assert texts["compile_input"]["qasm"] == report["compile_input"]["qasm"]
    (record,) = texts["compiled_circuits"]
    assert set(record) == {"compiler", "compiler_id", "compiler_name", "transpiled_qasm", "gate_metrics_basis",
                           "dispatch_status", "optimization_level", "gate_count", "circuit_depth",
                           "passes_applied", "sdk_versions"}


def test_client_report_with_a_bad_compiler_key_is_rejected():
    assert invalid_runner_keys({"raw_results": [], "compiled_circuits": [{"compiler": "../x"}]}) == ["../x"]


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_a_single_level_key_still_names_the_level(fake_dispatch):
    pytest.importorskip("pytket")
    report = asyncio.run(job_manager.run_single_circuit_comparison(
        QASM, target_simulators=["qiskit"], compilers={"bqskit": [2]}))
    assert [c["compiler"] for c in report["compiled_circuits"]] == ["bqskit~opt2~run1"]


def test_compiles_of_an_exclusive_job_take_the_shared_gate(fake_dispatch):
    pytest.importorskip("pytket")
    token = EXCLUSIVE.set(True)
    try:
        asyncio.run(job_manager.run_single_circuit_comparison(
            QASM, target_simulators=["qiskit"], compilers={"pyzx": [1]}))
    finally:
        EXCLUSIVE.reset(token)
    compile_payload = fake_dispatch[-1][1]
    assert compile_payload["exclusive_during_dispatch"] is False


def test_a_failing_compile_dispatch_keeps_the_simulator_results(monkeypatch):
    pytest.importorskip("pytket")

    async def dispatch(runner_urls, runner_payload=None, timeout_seconds=None, runner_statuses=None):
        if all(url.endswith("/compile") for url in runner_urls.values()):
            raise TimeoutError("gate wait expired")
        return [_runner_result(name) for name in runner_urls]

    monkeypatch.setattr(job_manager, "dispatch_to_runners", dispatch)
    monkeypatch.setattr(compilation, "dispatch_to_runners", dispatch)
    report = asyncio.run(job_manager.run_single_circuit_comparison(
        QASM, target_simulators=["qiskit", "cirq"], compilers={"pyzx": [1, 2]}))
    assert [r["simulator"] for r in report["raw_results"]] == ["qiskit", "cirq"]
    assert [(c["compiler"], c["dispatch_status"]) for c in report["compiled_circuits"]] == [
        ("pyzx~opt1~run1", "error"), ("pyzx~opt2~run1", "error")]
    assert "TimeoutError" in report["compiled_circuits"][0]["error"]


def test_lock_is_left_out_when_it_does_not_match_the_recorded_versions(fake_dispatch):
    pytest.importorskip("pytket")
    report = asyncio.run(job_manager.run_single_circuit_comparison(
        QASM, target_simulators=["qiskit"], compilers={"pyzx": [1]}))
    report["compiled_circuits"][0]["sdk_versions"] = {"pyzx": "0.8.0"}
    with zipfile.ZipFile(io.BytesIO(build_ro_crate(build_export_context(report, ExportPayload())))) as zf:
        assert not any(n.endswith("compilers/pyzx-compiler/requirements.lock") for n in zf.namelist())
    report["compiled_circuits"][0].update(sdk_versions={"pyzx": "0.10.6"}, dispatch_status="error")
    with zipfile.ZipFile(io.BytesIO(build_ro_crate(build_export_context(report, ExportPayload())))) as zf:
        assert not any(n.endswith("requirements.lock") and "compilers/" in n for n in zf.namelist())


def test_client_report_with_repeated_compiler_keys_is_rejected():
    from services.report_validation import report_problems
    record = {"compiler": "pyzx~opt1~run1", "transpiled_qasm": "h q[0];"}
    assert report_problems({"raw_results": [], "compiled_circuits": [record, dict(record)]})
    assert report_problems({"raw_results": [], "compiled_circuits": [record]}) == []


def test_block_comments_survive_preprocessing_without_a_measurement():
    pytest.importorskip("pytket")
    from services.circuit_resolver import prepare_statevector_dispatch
    text = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\ncreg c[1];\n/* note */ h q[0];\n'
    prepared = prepare_statevector_dispatch(text, True)
    assert "h q[0];" in prepared["qasm"] and "note" not in prepared["qasm"]


@pytest.mark.parametrize("name", ["‮detaler", "zero​width", "bom﻿"])
def test_names_with_invisible_formatting_characters_are_rejected(name):
    from services.report_validation import report_problems
    assert report_problems({"raw_results": [], "run_name": name})
    assert report_problems({"benchmark_summary": [{"task_name": name, "raw_results": []}]})


def test_reports_nested_too_deep_are_rejected_without_recursion():
    from services.report_validation import MAX_REPORT_DEPTH, report_problems
    deep = leaf = {}
    for _ in range(5000):
        leaf["x"] = {}
        leaf = leaf["x"]
    problems = report_problems({"raw_results": [], "extra": deep})
    assert any(f"at most {MAX_REPORT_DEPTH}" in p for p in problems)


def _crate_json(report, route, name):
    zip_bytes = build_ro_crate(build_export_context(report, ExportPayload(), route))
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        member = next(n for n in zf.namelist() if n.endswith("/" + name))
        return json.loads(zf.read(member))


def test_crate_records_how_the_exporter_obtained_the_report():
    forged = {"raw_results": [], "input_qasm": QASM, "saved_from": "server_job", "git_sha": "deadbeef"}
    client = _crate_json(forged, "client_request", "provenance.json")
    assert client["report_source"] == "client_supplied"
    assert "did not produce or check" in client["report_source_meaning"]
    assert "saved_from" not in _crate_json(forged, "client_request", "results.json")
    metadata = _crate_json(forged, "client_request", "ro-crate-metadata.json")
    root = next(e for e in metadata["@graph"] if e["@id"] == "./")
    assert "supplied in the export request" in root["description"]
    assert _crate_json({**forged, "saved_from": "upload"}, "saved_run", "provenance.json")["report_source"] == "upload"
    assert _crate_json({"raw_results": []}, "saved_run", "provenance.json")["report_source"] == "not_recorded"
    assert _crate_json({"raw_results": []}, "server_job", "provenance.json")["report_source"] == "server_job"


def test_malformed_compile_records_do_not_break_exports():
    from services.report_validation import report_problems
    record = {"compiler": "pyzx~opt1~run1", "compiler_id": "pyzx", "transpiled_qasm": "h q[0];",
              "dispatch_status": "ok", "sdk_versions": "pyzx 0.10.6"}
    report = {"raw_results": [], "compiled_circuits": [record]}
    assert report_problems(report) == []
    zip_bytes = build_ro_crate(build_export_context(report, ExportPayload()))
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert not any("compilers/" in n and n.endswith("requirements.lock") for n in zf.namelist())
    assert report_problems({"raw_results": [], "compiled_circuits": [{"transpiled_qasm": "x"}, {"transpiled_qasm": "y"}]})


def test_compile_requests_are_recorded_and_queued_under_dispatch_keys(fake_dispatch):
    pytest.importorskip("pytket")
    statuses = {}
    compilation.queue_compile_statuses(statuses, {"pyzx": [1, 2], "bqskit": [1]})
    assert statuses == {"pyzx~opt1~run1": "queued", "pyzx~opt2~run1": "queued", "bqskit": "queued"}
    report = asyncio.run(job_manager.run_single_circuit_comparison(
        QASM, target_simulators=["qiskit"], compilers={"pyzx": [1]}))
    assert report["compilers_requested"] == {"pyzx": [1]}
