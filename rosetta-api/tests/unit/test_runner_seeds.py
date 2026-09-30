"""Per-runner seed derivation, result annotation, and the job's full vs display copies."""
import asyncio

import pytest

pytest.importorskip("kubernetes")

from config import settings  # noqa: E402
import services.dispatcher_http as dispatcher_http  # noqa: E402
import services.job_manager as job_manager  # noqa: E402
from qrosetta_commons.seeds import derive_runner_seed  # noqa: E402
from services.dispatcher import (  # noqa: E402
    RUNNER_SERVICES, annotate_result, build_runner_payload, expand_runner_jobs,
)

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


def test_each_runner_key_gets_its_own_seed():
    urls = {"qiskit": "http://x/run_measured", "qibo": "http://y/run_measured"}
    payload = {"seed": 42, "runner_config": {"qiskit": [0, 0]}, "optimization_level": 0}
    specs = expand_runner_jobs(urls, payload)
    seeds = {s["key"]: build_runner_payload(payload, s)["seed"] for s in specs}
    assert set(seeds) == {"qiskit~opt0~run1", "qiskit~opt0~run2", "qibo"}
    assert len(set(seeds.values())) == 3
    assert seeds["qibo"] == derive_runner_seed(42, "qibo")
    assert "runner_config" not in build_runner_payload(payload, specs[0])


def test_statevector_payload_stays_seedless():
    spec = {"key": "qiskit", "sim_name": "qiskit", "opt_level": 0}
    assert "seed" not in build_runner_payload({"circuit_data": QASM}, spec)


def test_annotate_records_runner_seed_and_honoured_flag():
    assert RUNNER_SERVICES["braket"]["honours_seed"] is False
    spec = {"key": "braket", "sim_name": "braket", "opt_level": 0}
    r = annotate_result({"counts": {"00": 1}}, spec, {"seed": 7}, "t0")
    assert r["runner_seed"] == 7 and r["seed"] == 7
    assert r["seed_honoured"] is False
    assert r["dispatch_status"] == "ok"
    assert r["timing_samples"] == 1
    spec = {"key": "qiskit", "sim_name": "qiskit", "opt_level": 0}
    r = annotate_result({"error": "TIMEOUT (5s): killed"}, spec, {"seed": 7}, "t0")
    assert r["seed_honoured"] is None
    assert r["dispatch_status"] == "timeout"


def _fake_runner(monkeypatch):
    async def fake_safe_request(client, url, payload, sim_name, timeout_s, http_timeout=None):
        return {"counts": {"00": 1}, "received_seed": payload.get("seed"),
                "received_qasm": payload["circuit_data"],
                "preprocessing_applied": ["runner pass"]}
    monkeypatch.setattr(dispatcher_http, "safe_request", fake_safe_request)
    import services.dispatcher as dispatcher
    monkeypatch.setattr(dispatcher, "EXECUTION_MODE", "local")

    async def fake_reports(*args, **kwargs):
        return {}, {}, {}
    monkeypatch.setattr(job_manager, "compile_measurement_reports", fake_reports)


def test_measured_run_records_master_and_runner_seeds(monkeypatch):
    _fake_runner(monkeypatch)
    report = asyncio.run(job_manager.run_single_circuit_measurement(
        QASM, 16, target_simulators=["qiskit", "qibo", "quest"], seed=99, timeout_seconds=5))
    assert report["seed"] == 99
    assert "sha256" in report["seed_derivation"]
    by_sim = {r["simulator"]: r for r in report["raw_results"]}
    assert set(by_sim) == {"qiskit", "qibo", "quest"}
    for key, r in by_sim.items():
        assert r["runner_seed"] == derive_runner_seed(99, key) == r["received_seed"]
    assert len({r["runner_seed"] for r in by_sim.values()}) == 3

    native = by_sim["qiskit"]
    assert native["dispatch_group"] == "measured_native"
    assert native["preprocessing_applied"][-1] == "runner pass"
    assert native["preprocessing_applied"][0].startswith("API: ")
    groups = {g["group"]: g for g in report["dispatched_circuits"]}
    assert groups["measured_native"]["qasm"] == native["received_qasm"]
    assert groups["measured_sampled"]["qasm"] == by_sim["quest"]["received_qasm"]
    assert report["api_preprocessing_applied"]
    assert report["started_at"] <= report["finished_at"]
    assert report["timeout_scope"]
    assert report["queue_max_wait_sec"] == settings.RUNNER_QUEUE_MAX_WAIT_SEC
    assert report["skipped_runners"] == []
    assert report["runner_registry"]["qiskit"]["enabled"] is True


def test_job_keeps_full_copy_and_serves_display_copy():
    big = "A" * (job_manager._MAX_DISPLAY_STATEVECTOR_B64_CHARS + 1)
    report = {"raw_results": [{"simulator": "qiskit", "statevector": big}]}
    job = job_manager._completed_job("t", report, {})
    assert job["full_results"]["raw_results"][0]["statevector"] == big
    shown = job["results"]["raw_results"][0]
    assert shown["statevector"] == job_manager._STATEVECTOR_PLACEHOLDER
    assert shown["statevector_omitted_for_display"] is True
    batch = job_manager.display_report({"benchmark_summary": [report]})
    assert batch["benchmark_summary"][0]["raw_results"][0]["statevector_omitted_for_display"]
