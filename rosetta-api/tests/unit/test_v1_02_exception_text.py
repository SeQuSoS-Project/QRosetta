"""V1-02: exception text that can carry server paths or internals never reaches clients or
stored reports; the type is shown and the detail is logged with the job id."""
import asyncio

import pytest
from fastapi import HTTPException

pytest.importorskip("pytket")
pytest.importorskip("kubernetes")

import services.benchmark_library as benchmark_library  # noqa: E402
import services.dispatcher_http as dispatcher_http  # noqa: E402
import services.experiment as experiment  # noqa: E402
import services.job_manager as job_manager  # noqa: E402
from qrosetta_commons.compile_errors import CompileRefused  # noqa: E402
from qrosetta_commons.compile_service import compiler_error  # noqa: E402
from qrosetta_commons.helpers import runner_error  # noqa: E402
from qrosetta_commons.redact import strip_absolute_paths  # noqa: E402
from schemas import BatchPayload, BenchmarkTask, ExperimentCircuit, ExperimentPayload  # noqa: E402
from services.error_text import client_error_text  # noqa: E402

SECRET = "/home/appuser/app/data/qa_rosetta.db"
H = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
BELL = H + "qreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q -> c;\n"


def test_v1_02_absolute_paths_are_removed_and_other_text_kept():
    assert strip_absolute_paths(f"OSError: [Errno 13] Permission denied: '{SECRET}'") == \
        "OSError: [Errno 13] Permission denied: '<path>'"
    for kept in ("rz(pi/2) q[0];", "see https://example.org/a/b", "ratio 1/2/3", "a/b/c relative"):
        assert strip_absolute_paths(kept) == kept
    assert strip_absolute_paths('File "/usr/lib/python3.12/site-packages/x.py", line 3') == \
        'File "<path>", line 3'


def test_v1_02_runner_and_compiler_errors_keep_the_sdk_text_without_paths():
    error = runner_error("qiskit", ValueError(f"cannot open {SECRET}: gate 'foo' unknown"))["error"]
    assert error == "cannot open <path>: gate 'foo' unknown"
    record = compiler_error("staq", CompileRefused(f"staq wrote {SECRET}"))
    assert SECRET not in record["error"] and SECRET not in record["refusal"]
    assert record["error"].startswith("CompileRefused: staq wrote <path>")


def test_v1_02_a_job_whose_worker_raises_stores_the_type_only():
    async def boom():
        raise OSError(f"[Errno 28] No space left on device: '{SECRET}'")
    job_manager.ACTIVE_JOBS["v1-02-job"] = {"status": "pending"}
    try:
        asyncio.run(job_manager._run_single_job("v1-02-job", "local", {}, boom()))
        error = job_manager.ACTIVE_JOBS["v1-02-job"]["error"]
    finally:
        job_manager.ACTIVE_JOBS.pop("v1-02-job", None)
    assert SECRET not in error and "No space" not in error and "OSError" in error


def _fake_fleet(monkeypatch, result):
    async def fake_safe_request(client, url, payload, sim_name, timeout_s, http_timeout=None):
        return dict(result)
    monkeypatch.setattr(dispatcher_http, "safe_request", fake_safe_request)
    import services.dispatcher as dispatcher
    monkeypatch.setattr(dispatcher, "EXECUTION_MODE", "local")

    async def failing_reports(*args, **kwargs):
        raise KeyError(f"{SECRET} internal detail")
    monkeypatch.setattr(job_manager, "compile_measurement_reports", failing_reports)
    monkeypatch.setattr(job_manager, "compile_comparison_reports", failing_reports)


def test_v1_02_a_failed_analysis_records_the_type_only(monkeypatch):
    _fake_fleet(monkeypatch, {"counts": {"00": 1}, "preprocessing_applied": []})
    measured = asyncio.run(job_manager.run_single_circuit_measurement(
        BELL, 16, target_simulators=["qiskit"], seed=1, timeout_seconds=5))
    assert measured["error"] == "Analysis failed (KeyError)"
    _fake_fleet(monkeypatch, {"statevector": "AAAAAAAA8D8AAAAAAAAAAA==", "preprocessing_applied": []})
    statevector = asyncio.run(job_manager.run_single_circuit_comparison(
        H + "qreg q[1];\nh q[0];\n", target_simulators=["qiskit"], timeout_seconds=5))
    assert statevector["divergence_report"] == {"error": "Analysis failed (KeyError)"}


def test_v1_02_batch_task_and_experiment_failures_keep_request_messages_only(monkeypatch):
    def resolve(*args, **kwargs):
        raise OSError(f"cannot read {SECRET}")
    monkeypatch.setattr(job_manager, "resolve_circuit_qasm", resolve)
    payload = BatchPayload(mode="measured", n_shots=16, target_simulators=["qiskit"],
                           tasks=[BenchmarkTask(algorithm="ghz", qubits=3)])
    summary, _ = asyncio.run(job_manager.run_batch_tasks(payload, {}))
    assert summary[0]["error"] == "Failed to process task: OSError"

    monkeypatch.setattr(experiment, "resolve_circuit_qasm", resolve)
    resolved, errors = experiment.resolve_circuits(ExperimentPayload(
        circuits=[ExperimentCircuit(source="preset", algorithm="ghz", qubits=3)], mode="measured"))
    assert resolved == [] and errors[0]["error"] == "OSError"

    monkeypatch.setattr(experiment, "resolve_circuits", lambda p: (_ for _ in ()).throw(MemoryError(SECRET)))
    experiment.ACTIVE_JOBS["v1-02-exp"] = {"status": "pending"}
    try:
        asyncio.run(experiment.worker_experiment("v1-02-exp", ExperimentPayload(
            circuits=[ExperimentCircuit(source="qasm", qasm_string=BELL)], mode="measured")))
        job = experiment.ACTIVE_JOBS["v1-02-exp"]
    finally:
        experiment.ACTIVE_JOBS.pop("v1-02-exp", None)
    assert job["status"] == "failed" and job["error"] == "The experiment failed (MemoryError)"


def test_v1_02_request_errors_keep_their_message():
    assert client_error_text(HTTPException(400, detail="Qubit count 30 exceeds limit")) == \
        "Qubit count 30 exceeds limit"
    assert client_error_text(ValueError(f"Circuit uses reset; see {SECRET}")) == \
        "Circuit uses reset; see <path>"
    assert client_error_text(RuntimeError(SECRET)) == "RuntimeError"


def test_v1_02_an_unreadable_bundled_file_is_a_500_without_its_path(tmp_path):
    (tmp_path / "x.qasm").mkdir()
    with pytest.raises(HTTPException) as exc:
        benchmark_library._read_bundled_qasm(str(tmp_path), "x.qasm", "MQT")
    assert exc.value.status_code == 500
    assert str(tmp_path) not in exc.value.detail and "IsADirectoryError" in exc.value.detail
