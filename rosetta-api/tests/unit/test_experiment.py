"""Unit tests for services/experiment.py, with the fleet mocked at run_batch_tasks."""
import asyncio
import io
import hashlib
import json
import zipfile

import pytest

pytest.importorskip("pytket")
pytest.importorskip("kubernetes")

import services.experiment as exp  # noqa: E402
from services.job_manager import ACTIVE_JOBS  # noqa: E402
from schemas import ExperimentPayload, ExperimentCircuit  # noqa: E402

BELL_QASM = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n"


def _fake_summary(batch_seed):
    return [{
        "task_name": "bell (2q)",
        "seed": batch_seed,
        "git_sha": "feedface",
        "seed_derivation": "recorded derivation",
        "raw_results": [
            {"simulator": "qiskit", "statevector": [0.0, 0.707, 0.0, 0.707],
             "sdk_versions": {"qiskit": "2.4.1"}},
            {"simulator": "qibo", "error": "boom: mat_dict not defined"},
        ],
        "divergence_report": {"pairwise_agreement": [{"agreement": "agree_after_bit_reversal"}]},
    }]


def _install_fake_batch(monkeypatch, seen_seeds):
    async def fake_run_batch_tasks(payload, runner_statuses, progress=None,
                                   batch_seed=None, task_offset=0):
        seen_seeds.append(batch_seed)
        if progress is not None:
            for i in range(len(payload.tasks)):
                progress["tasks"][task_offset + i]["status"] = "done"
                progress["completed"] += 1
        return _fake_summary(batch_seed), batch_seed
    monkeypatch.setattr(exp, "run_batch_tasks", fake_run_batch_tasks)


def _run_experiment(payload):
    job_id = "test-job"
    ACTIVE_JOBS[job_id] = {"status": "pending", "target": payload.execution_target}
    asyncio.run(exp.worker_experiment(job_id, payload))
    return job_id, ACTIVE_JOBS[job_id]


def test_experiment_completes_and_freezes_bundle(monkeypatch):
    seen = []
    _install_fake_batch(monkeypatch, seen)
    payload = ExperimentPayload(
        circuits=[ExperimentCircuit(source="qasm", qasm_string=BELL_QASM, name="bell", qubits=2)],
        mode="measured", preprocessing_modes=[True, False], seed=42, label="demo")
    _, job = _run_experiment(payload)

    assert job["status"] == "completed"
    files = job["bundle_files"]
    # both axes frozen, plus inputs + the two separated CSVs + manifest + README + error log
    assert "inputs/000_bell.qasm" in files
    assert "results/measured_preprocOn/000_bell.json" in files
    assert "results/measured_preprocOff/000_bell.json" in files
    assert "conformance_matrix.csv" in files
    assert "agreement_prevalence.csv" in files
    assert "manifest.json" in files
    assert "README.txt" in files
    assert "errors/qibo.log" in files

    # one shared seed across both axes (never re-generated per axis)
    assert seen == [42, 42]

    # statevector stripped in the frozen result
    report = json.loads(files["results/measured_preprocOn/000_bell.json"])
    qiskit = next(r for r in report["raw_results"] if r["simulator"] == "qiskit")
    assert qiskit["statevector"] is None and len(qiskit["statevector_sha256"]) == 64

    # UI summary: prevalence counted once per axis; conformance separate from prevalence
    summ = job["results"]["experiment_summary"]
    prev = {r["agreement_class"]: r["pair_count"] for r in summ["prevalence"]
            if r["axis"] == "measured_preprocOn"}
    assert prev == {"agree_after_bit_reversal": 1}
    assert summ["error_count"] == 2  # qibo failed in both axes
    assert summ["bundle_ready"] is True

    # manifest provenance
    manifest = json.loads(files["manifest.json"])
    assert manifest["requested_seed"] == 42
    assert manifest["effective_seeds_per_axis"]["measured_preprocOn"] == 42
    assert manifest["mode"] == "measured"
    assert manifest["git_sha"] == "feedface"
    assert manifest["seed_derivation"] == "recorded derivation"
    digest = hashlib.sha256(files["inputs/000_bell.qasm"]).hexdigest()
    assert manifest["circuits"][0]["qasm_sha256"] == digest


def test_bundle_zip_is_valid_archive(monkeypatch):
    _install_fake_batch(monkeypatch, [])
    payload = ExperimentPayload(
        circuits=[ExperimentCircuit(source="qasm", qasm_string=BELL_QASM, name="bell", qubits=2)],
        mode="measured", preprocessing_modes=[True], seed=1)
    _, job = _run_experiment(payload)
    data = exp.build_bundle_zip(job["bundle_files"])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.testzip() is None
        names = set(zf.namelist())
        assert "manifest.json" in names and "README.txt" in names
        assert "untriaged" in zf.read("README.txt").decode("utf-8")


def test_resolution_error_recorded_not_fatal(monkeypatch):
    _install_fake_batch(monkeypatch, [])
    payload = ExperimentPayload(circuits=[
        ExperimentCircuit(source="qasm", qasm_string=BELL_QASM, name="ok", qubits=2),
        ExperimentCircuit(source="qasm", qasm_string=None, name="broken", qubits=2),  # bad
    ], mode="measured", preprocessing_modes=[True])
    _, job = _run_experiment(payload)
    assert job["status"] == "completed"  # one good circuit still runs
    summ = job["results"]["experiment_summary"]
    assert len(summ["resolution_errors"]) == 1
    assert summ["resolution_errors"][0]["name"] == "broken"
    # a resolution_error conformance row exists (recorded, never silently dropped)
    assert any(r["status"] == "resolution_error" for r in summ["conformance"])


def test_all_circuits_unresolvable_fails(monkeypatch):
    _install_fake_batch(monkeypatch, [])
    payload = ExperimentPayload(
        circuits=[ExperimentCircuit(source="qasm", qasm_string=None, name="broken")],
        mode="measured")
    _, job = _run_experiment(payload)
    assert job["status"] == "failed"
    assert "No circuits could be resolved" in job["error"]


def test_fanout_cap_enforced(monkeypatch):
    _install_fake_batch(monkeypatch, [])
    monkeypatch.setattr(exp, "MAX_EXPERIMENT_CELLS", 1)
    payload = ExperimentPayload(circuits=[
        ExperimentCircuit(source="qasm", qasm_string=BELL_QASM, name="a", qubits=2),
        ExperimentCircuit(source="qasm", qasm_string=BELL_QASM, name="b", qubits=2),
    ], mode="measured", preprocessing_modes=[True])
    _, job = _run_experiment(payload)
    assert job["status"] == "failed"
    assert "too large" in job["error"]


def test_fanout_cap_bypassable(monkeypatch):
    _install_fake_batch(monkeypatch, [])
    monkeypatch.setattr(exp, "MAX_EXPERIMENT_CELLS", 1)
    payload = ExperimentPayload(circuits=[
        ExperimentCircuit(source="qasm", qasm_string=BELL_QASM, name="a", qubits=2),
        ExperimentCircuit(source="qasm", qasm_string=BELL_QASM, name="b", qubits=2),
    ], mode="measured", preprocessing_modes=[True], bypass_limits=True)
    _, job = _run_experiment(payload)
    assert job["status"] == "completed"


def test_resolve_circuits_benchmark_sources():
    # Benchmark refs resolve server-side to the bundled QASM (no client fetch); a bad ref is
    # recorded as a resolution error, not raised.
    from schemas import ExperimentPayload as EP, ExperimentCircuit as EC
    payload = EP(circuits=[
        EC(source="qasmbench", algorithm="adder_n4", qubits=4),
        EC(source="mqt", algorithm="dj", qubits=10),
        EC(source="qasmbench", algorithm="does_not_exist_n9", qubits=9),
    ], mode="measured")
    resolved, errors = exp.resolve_circuits(payload)
    got = {r["algorithm"]: r for r in resolved}
    assert set(got) == {"adder_n4", "dj"}
    assert got["adder_n4"]["source"] == "qasmbench" and "OPENQASM" in got["adder_n4"]["qasm"]
    assert got["dj"]["source"] == "mqt" and "OPENQASM" in got["dj"]["qasm"]
    assert len(errors) == 1 and errors[0]["name"].startswith("does_not_exist_n9")


def test_statevector_mode_is_seedless(monkeypatch):
    seen = []
    _install_fake_batch(monkeypatch, seen)
    payload = ExperimentPayload(
        circuits=[ExperimentCircuit(source="qasm", qasm_string=BELL_QASM, name="bell", qubits=2)],
        mode="statevector", preprocessing_modes=[True])
    _, job = _run_experiment(payload)
    assert job["status"] == "completed"
    assert seen == [None]  # statevector is exact/seedless — no seed forced across axes


def test_result_files_named_by_circuit_id_do_not_collide(monkeypatch):
    async def fake_run_batch_tasks(payload, runner_statuses, progress=None,
                                   batch_seed=None, task_offset=0):
        summary = []
        for i, task in enumerate(payload.tasks):
            summary.append({
                "task_name": f"{task.algorithm} ({task.qubits}q)",
                "input_qasm": task.qasm_string,
                "raw_results": [{"simulator": "qiskit", "counts": {"00": 1}, "dispatch_status": "ok"}],
            })
            if progress is not None:
                progress["tasks"][task_offset + i]["status"] = "done"
                progress["completed"] += 1
        return summary, batch_seed
    monkeypatch.setattr(exp, "run_batch_tasks", fake_run_batch_tasks)

    other = BELL_QASM.replace("h q[0];", "x q[0];")
    payload = ExperimentPayload(circuits=[
        ExperimentCircuit(source="qasm", qasm_string=BELL_QASM, algorithm="bell", qubits=2),
        ExperimentCircuit(source="qasm", qasm_string=other, algorithm="bell", qubits=2),
    ], mode="measured", preprocessing_modes=[True], seed=3)
    _, job = _run_experiment(payload)
    files = job["bundle_files"]
    results = sorted(k for k in files if k.startswith("results/"))
    assert results == ["results/measured_preprocOn/000_bell-2q.json",
                       "results/measured_preprocOn/001_bell-2q.json"]
    first = json.loads(files[results[0]])
    second = json.loads(files[results[1]])
    assert first["input_qasm"] == BELL_QASM and second["input_qasm"] == other
    assert {r["circuit_id"] for r in job["results"]["experiment_summary"]["conformance"]} == {
        "000_bell-2q", "001_bell-2q"}
