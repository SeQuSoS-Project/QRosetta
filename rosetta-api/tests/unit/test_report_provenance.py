"""Report provenance: resolved runners, bypass_limits, batch task requests, experiment
effective config, sampled-group preprocessing, and the request fixes that go with them."""
import asyncio
import json

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

pytest.importorskip("pytket")

import services.dispatcher_http as dispatcher_http  # noqa: E402
import services.job_manager as job_manager  # noqa: E402
from config import settings  # noqa: E402
from schemas import AgreementThresholds, BatchPayload, BenchmarkTask, MeasuredQasmPayload  # noqa: E402
from services.circuit_resolver import prepare_measured_dispatch  # noqa: E402
from services.validator import validate_request  # noqa: E402

H = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
CUSTOM_GATE = H + ("gate mygate a,b { h a; cx a,b; }\nqreg q[2];\ncreg c[2];\nmygate q[0],q[1];\n"
                   "barrier q;\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n")


def test_preprocessing_round_trips_the_sampled_group_too():
    dispatch = prepare_measured_dispatch(CUSTOM_GATE, apply_preprocessing=True)
    sampled = dispatch["measured_sampled"]
    assert "gate mygate" not in sampled["qasm"] and "barrier" not in sampled["qasm"]
    assert any("pytket" in note for note in sampled["api_preprocessing_applied"])
    assert sampled["qasm"] == dispatch["measured_native"]["qasm"]


def test_no_preprocessing_leaves_the_sampled_group_verbatim():
    sampled = prepare_measured_dispatch(CUSTOM_GATE, apply_preprocessing=False)["measured_sampled"]
    assert sampled == {"qasm": CUSTOM_GATE, "api_preprocessing_applied": []}


def test_round_trip_accepts_classical_registers_wider_than_32_bits():
    qasm = H + "qreg q[2];\ncreg a[22];\ncreg b[22];\ncreg w[40];\nh q[0];\nmeasure q[0] -> w[39];\n"
    sampled = prepare_measured_dispatch(qasm, apply_preprocessing=True)["measured_sampled"]
    assert "creg w[40];" in sampled["qasm"]
    assert sampled["qasm"].index("creg a[22]") < sampled["qasm"].index("creg w[40]")


@pytest.mark.parametrize("qasm, line", [
    ("OPENQASM 2.0;\nqreg q[2]\n", 2),
    (H + "qreg q[2];\nh q[0]\n", 4),
])
def test_a_final_statement_without_semicolon_is_a_syntax_error(qasm, line):
    with pytest.raises(HTTPException) as exc:
        validate_request(qasm, "measured")
    assert exc.value.status_code == 400
    assert f"line {line}" in exc.value.detail and "semicolon" in exc.value.detail


def test_qubits_is_optional_for_qasmbench_and_literal_tasks():
    assert BenchmarkTask(algorithm="adder_n4", source="qasmbench").qubits is None
    assert BenchmarkTask(algorithm="x", qasm_string=H + "qreg q[1];\n").qubits is None
    for source in (None, "preset", "mqt"):
        with pytest.raises(ValidationError, match="qubits is required"):
            BenchmarkTask(algorithm="ghz", source=source)


def test_default_shots_can_reach_the_consistent_verdict():
    assert MeasuredQasmPayload(qasm_string=H).n_shots == settings.DEFAULT_SHOTS == 8192
    description = MeasuredQasmPayload.model_fields["n_shots"].description
    assert "Benjamini-Yekutieli" in description and "recommended_shots_per_backend" in description


def _fake_fleet(monkeypatch):
    async def fake_safe_request(client, url, payload, sim_name, timeout_s, http_timeout=None):
        return {"counts": {"00": 1}, "preprocessing_applied": []}
    monkeypatch.setattr(dispatcher_http, "safe_request", fake_safe_request)
    import services.dispatcher as dispatcher
    monkeypatch.setattr(dispatcher, "EXECUTION_MODE", "local")

    async def fake_reports(*args, **kwargs):
        return {}, {}, {}
    monkeypatch.setattr(job_manager, "compile_measurement_reports", fake_reports)


def test_measured_report_records_resolved_runners_and_bypass(monkeypatch):
    _fake_fleet(monkeypatch)
    report = asyncio.run(job_manager.run_single_circuit_measurement(
        CUSTOM_GATE, 16, target_simulators=["qiskit", "quest"], seed=1, timeout_seconds=5,
        bypass_limits=True))
    assert report["bypass_limits"] is True
    assert report["resolved_runners"] == {
        "requested": ["qiskit", "quest"], "dispatched": ["qiskit", "quest"], "skipped": []}


def test_batch_tasks_record_their_request(monkeypatch):
    _fake_fleet(monkeypatch)
    payload = BatchPayload(mode="measured", n_shots=16, target_simulators=["qiskit"],
                           tasks=[BenchmarkTask(algorithm="mine", qasm_string=CUSTOM_GATE),
                                  BenchmarkTask(algorithm="no-such-preset", qubits=3)])
    summary, _ = asyncio.run(job_manager.run_batch_tasks(payload, {}))
    assert summary[0]["task_request"] == {
        "source": "qasm", "algorithm": "mine", "qubits": None, "literal_qasm": True}
    assert summary[1]["task_request"] == {
        "source": "preset", "algorithm": "no-such-preset", "qubits": 3, "literal_qasm": False}
    assert "error" in summary[1]


def test_experiment_manifest_records_the_effective_config(monkeypatch):
    pytest.importorskip("kubernetes")
    import services.experiment as exp
    from schemas import ExperimentCircuit, ExperimentPayload

    async def fake_run_batch_tasks(payload, runner_statuses, progress=None, batch_seed=None,
                                   task_offset=0):
        thresholds = job_manager.effective_thresholds(payload.thresholds)
        return [{"seed": batch_seed, "agreement_thresholds": thresholds,
                 "resolved_runners": {"requested": [], "dispatched": ["qiskit", "quest"],
                                      "skipped": [{"id": "cuquantum", "reason": "no GPU"}]},
                 "raw_results": []} for _ in payload.tasks], batch_seed
    monkeypatch.setattr(exp, "run_batch_tasks", fake_run_batch_tasks)

    payload = ExperimentPayload(circuits=[ExperimentCircuit(source="qasm", qasm_string=CUSTOM_GATE)],
                                preprocessing_modes=[True, False])
    job_manager.ACTIVE_JOBS["exp-prov"] = {"status": "pending", "target": "local"}
    try:
        asyncio.run(exp.worker_experiment("exp-prov", payload))
        job = job_manager.ACTIVE_JOBS["exp-prov"]
        manifest = json.loads(job["bundle_files"]["manifest.json"])
        result = json.loads(job["bundle_files"]["results/measured_preprocOn/000_circuit-0.json"])
    finally:
        del job_manager.ACTIVE_JOBS["exp-prov"]

    effective = manifest["effective_config"]
    assert manifest["config"]["seed"] is None and isinstance(effective["seed"], int)
    assert manifest["config"]["thresholds"] is None
    assert effective["thresholds"] == AgreementThresholds().model_dump()
    assert effective["target_simulators"] == ["qiskit", "quest"]
    assert manifest["effective_config_sha256"] != manifest["config_sha256"]
    assert set(manifest["effective_thresholds_per_axis"]) == {
        "measured_preprocOn", "measured_preprocOff"}
    assert manifest["resolved_runners_per_axis"]["measured_preprocOn"]["skipped"] == [
        {"id": "cuquantum", "reason": "no GPU"}]
    assert result["task_request"] == {"source": "qasm", "algorithm": None, "qubits": 0,
                                      "literal_qasm": True}
