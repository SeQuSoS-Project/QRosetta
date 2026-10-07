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
    zip_bytes = build_ro_crate(build_export_context(report, ExportPayload(), route="server_job"))
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
    with zipfile.ZipFile(io.BytesIO(build_ro_crate(build_export_context(report, ExportPayload(), route="server_job")))) as zf:
        assert not any(n.endswith("compilers/pyzx-compiler/requirements.lock") for n in zf.namelist())
    report["compiled_circuits"][0]["sdk_versions"] = {"pyzx": "0.10.6", "not-a-package": "9.9"}
    with zipfile.ZipFile(io.BytesIO(build_ro_crate(build_export_context(report, ExportPayload(), route="server_job")))) as zf:
        assert not any(n.endswith("compilers/pyzx-compiler/requirements.lock") for n in zf.namelist())
    report["compiled_circuits"][0].update(sdk_versions={"pyzx": "0.10.6"}, dispatch_status="error")
    with zipfile.ZipFile(io.BytesIO(build_ro_crate(build_export_context(report, ExportPayload(), route="server_job")))) as zf:
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


def _crate_names_and_graph(report, route="server_job"):
    with zipfile.ZipFile(io.BytesIO(build_ro_crate(build_export_context(report, ExportPayload(), route=route)))) as zf:
        names = zf.namelist()
        meta = next(n for n in names if n.endswith("ro-crate-metadata.json"))
        return names, json.loads(zf.read(meta))["@graph"]


def test_build_files_are_included_only_when_their_hash_matches_the_image(fake_dispatch):
    import hashlib
    from pathlib import Path
    pytest.importorskip("pytket")
    report = asyncio.run(job_manager.run_single_circuit_comparison(
        QASM, target_simulators=["qiskit"], compilers={"quartz": [0]}))
    source = Path(__file__).resolve().parents[3] / "compilers" / "quartz-compiler"
    sha = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
           for name in ("Dockerfile", "shift10-normalise.patch", "Nam_complete_ECC_set.json")}
    record = report["compiled_circuits"][0]
    main_sha = hashlib.sha256((source / "main.py").read_bytes()).hexdigest()
    record.update(dispatch_status="ok", transpiled_qasm=QASM, build_files={**sha, "Dockerfile": "0" * 64, "main.py": main_sha},
                  native_components=[{"name": "quartz", "version": "0.3.2", "source_url": "https://x/q.tar.gz",
                                      "source_sha256": "ab" * 32, "patches": ["shift10-normalise.patch"]}],
                  sdk_versions={"qiskit": "2.5.2", "quartz": "0.3.2"})
    names, graph = _crate_names_and_graph(report)
    assert any(n.endswith("compilers/quartz-compiler/shift10-normalise.patch") for n in names)
    assert any(n.endswith("compilers/quartz-compiler/Nam_complete_ECC_set.json") for n in names)
    assert not any(n.endswith("compilers/quartz-compiler/Dockerfile") for n in names)
    assert not any(n.endswith("compilers/quartz-compiler/main.py") for n in names)
    patch = next(e for e in graph if e["@id"] == "compilers/quartz-compiler/shift10-normalise.patch")
    assert patch["sha256"] == sha["shift10-normalise.patch"]
    app = next(e for e in graph if e["@id"] == "#compiler-quartz")
    assert {"@id": "compilers/quartz-compiler/shift10-normalise.patch"} in app["hasPart"]
    assert "qiskit==2.5.2" in app["softwareRequirements"]
    assert not any(isinstance(r, str) and r.startswith("quartz==") for r in app["softwareRequirements"])
    native = next(e for e in graph if e["@id"] == "#native-quartz-0.3.2")
    assert native["softwareVersion"] == "0.3.2" and native["identifier"] == "sha256:" + "ab" * 32
    assert {"@id": "#native-quartz-0.3.2"} in app["softwareRequirements"]
    names, graph = _crate_names_and_graph(report, route="client_request")
    assert not any("/compilers/" in n for n in names)
    native = next(e for e in graph if e["@id"] == "#native-quartz-0.3.2")
    assert "as the supplied report states" in native["description"]


def test_a_refusal_reaches_the_share_texts_but_other_errors_do_not():
    from services.circuit_texts import single_circuit_texts
    report = {"compiled_circuits": [
        {"compiler": "staq~opt1~run1", "compiler_id": "staq", "dispatch_status": "error",
         "error": "CompileRefused: r names a gate", "refusal": "r names a gate", "refusal_kind": "input"},
        {"compiler": "staq~opt2~run1", "compiler_id": "staq", "dispatch_status": "error",
         "error": "ValueError: staq exited with status 1: /tmp/x"}]}
    refused, failed = single_circuit_texts(report)["compiled_circuits"]
    assert refused["refusal"] == "r names a gate" and refused["refusal_kind"] == "input"
    assert "error" not in refused and "error" not in failed and "refusal" not in failed


def test_compile_only_run_dispatches_no_simulator_and_exports(fake_dispatch):
    pytest.importorskip("pytket")
    report = asyncio.run(job_manager.run_compile_only(QASM, compilers={"pyzx": [1]}))
    assert len(fake_dispatch) == 1
    (compile_urls, _), = fake_dispatch
    assert all(url.endswith("/compile") for url in compile_urls.values())
    assert report["simulated"] is False and report["raw_results"] == []
    assert [c["compiler"] for c in report["compiled_circuits"]] == ["pyzx~opt1~run1"]
    assert report["compile_input"]["qasm"]
    assert job_manager.all_runners_failed(report) is None
    assert not job_manager.report_failed_before_dispatch(report)
    zip_bytes = build_ro_crate(build_export_context(report, ExportPayload(), route="server_job"))
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert any(n.endswith("compile_input.qasm") for n in zf.namelist())


def test_compile_only_requests_need_compilers_and_no_simulator_settings(client):
    r = client.post("/compare", json={"qasm_string": QASM, "simulate": False})
    assert r.status_code == 422 and "compilers" in r.text
    r = client.post("/compare", json={"qasm_string": QASM, "simulate": False, "compilers": {"pyzx": [1]},
                                      "target_simulators": ["qiskit"]})
    assert r.status_code == 422 and "target_simulators" in r.text
    r = client.post("/run_batch_suite", json={"tasks": [{"algorithm": "ghz", "qubits": 2}], "mode": "statevector",
                                              "simulate": False, "runner_config": {"qiskit": 0}, "compilers": {"pyzx": [1]}})
    assert r.status_code == 422 and "runner_config" in r.text


def test_compile_only_batch_runs_each_task_without_simulators(fake_dispatch):
    pytest.importorskip("pytket")
    from schemas import BatchPayload, BenchmarkTask
    payload = BatchPayload(mode="statevector", simulate=False, compilers={"pyzx": [1]},
                           tasks=[BenchmarkTask(algorithm="mine", qasm_string=QASM)])
    summary, _ = asyncio.run(job_manager.run_batch_tasks(payload, {}))
    assert summary[0]["simulated"] is False and summary[0]["raw_results"] == []
    assert all(url.endswith("/compile") for urls, _ in fake_dispatch for url in urls.values())


def _wide(n):
    return f'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[{n}];\nh q[0];\n'


def test_compile_only_runs_have_their_own_qubit_limit(client):
    from fastapi import HTTPException
    from services.validator import validate_request
    from config import settings
    assert settings.max_qubits_for_mode("compile") == settings.MAX_QUBITS_COMPILE == 24
    validate_request(_wide(20), mode="compile")
    with pytest.raises(HTTPException) as exc:
        validate_request(_wide(20), mode="statevector")
    assert "18 qubits for statevector mode" in exc.value.detail
    r = client.post("/compare", json={"qasm_string": _wide(25), "simulate": False, "compilers": {"pyzx": [1]}})
    assert r.status_code == 400 and "24 qubits for a compile-only run" in r.text
    r = client.post("/run_batch_suite", json={"tasks": [{"qasm_string": _wide(25)}], "mode": "statevector",
                                              "simulate": False, "compilers": {"pyzx": [1]}})
    assert r.status_code == 400 and "24 qubits for a compile-only run" in r.text
    assert client.get("/config").json()["limits"]["max_qubits_compile"] == 24


def test_undeployed_compilers_are_rejected(monkeypatch):
    monkeypatch.setattr(compilation.settings, "NOT_DEPLOYED", frozenset({"qsynth"}))
    with pytest.raises(HTTPException) as exc:
        compilation.validate_compilers({"qsynth": [0]})
    assert exc.value.status_code == 400 and "not deployed" in exc.value.detail
    compilation.validate_compilers({"pyzx": [1]})
