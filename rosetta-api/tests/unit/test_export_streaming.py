"""Job crate export from disk: results.json written in chunks equals json.dumps, a spilled
batch exports the same crate as the in-memory report, memory stays near one task, and a job
that expires during the export is 404."""
import base64
import io
import json
import math
import os
import tracemalloc
import zipfile
from datetime import datetime, timezone

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import schemas
import services.exporter as exporter
from routers import export as export_router
from services import job_manager, job_store
from services.export_results import ENCODER, results_data, results_json_source
from services.job_store import JOB_NOT_FOUND

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
FIXED = datetime(2026, 10, 21, 12, 0, 0, 123000, tzinfo=timezone.utc)


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED


@pytest.fixture(autouse=True)
def spill_dir(tmp_path, monkeypatch):
    path = tmp_path / "spill"
    monkeypatch.setattr(job_store, "SPILL_DIR", str(path))
    monkeypatch.setattr(exporter, "datetime", _FixedDatetime)
    yield path
    for job_id in [j for j in job_manager.ACTIVE_JOBS if str(j).startswith("xs-")]:
        job_manager.ACTIVE_JOBS.pop(job_id, None)


@pytest.fixture
def client(monkeypatch):
    from services.security import limiter
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(export_router.router)
    return TestClient(app)


def _statevector(n_amplitudes, seed):
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(n_amplitudes) + 1j * rng.standard_normal(n_amplitudes)
    return base64.b64encode(v.astype(np.complex128).tobytes()).decode()


def _task(i, n_amplitudes=4, backends=("qiskit", "cirq")):
    raw = [{"simulator": b, "statevector": _statevector(n_amplitudes, 10 * i + k),
            "transpiled_qasm": QASM + f"// {b}\n", "optimization_level": 0,
            "sdk_versions": {b: "1.0"}, "preprocessing_applied": ["API: round-trip"]}
           for k, b in enumerate(backends)]
    raw.append({"simulator": "qibo", "error": "TypeError: gate", "dispatch_status": "error"})
    if i % 2:
        raw[0] = {**raw[0], "statevector": "<Statevector too large to display>",
                  "statevector_omitted_for_display": True}
    return {"task_name": "bell (2q)" if i < 2 else f"task {i}", "input_qasm": QASM,
            "raw_results": raw, "report_source": "server_job",
            "dispatched_circuits": [{"group": "statevector", "qasm": QASM, "runners": list(backends),
                                     "api_preprocessing_applied": []}],
            "divergence_report": {"pairwise_agreement": [
                {"simulators": list(backends[:2]), "mode": "statevector",
                 "agreement": "agree_directly", "metrics": {"direct_fidelity": 1.0}}]}}


def _spilled_job(job_id, tasks, **top):
    refs = [job_store.spill_task_report(job_id, i, t) for i, t in enumerate(tasks)]
    report = {"mode": "statevector", "benchmark_summary": refs, **top}
    job_manager.ACTIVE_JOBS[job_id] = job_manager._completed_job("t", report, {})
    return {"mode": "statevector", "benchmark_summary": tasks, **top}


def _members(zip_bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return [(i.filename, i.compress_type, i.external_attr, zf.read(i)) for i in zf.infolist()]


@pytest.mark.parametrize("value", [
    {"a": [1, 2.5, None, True, {"é": "∑", 3: "int key", 1.5: "float key"}], "b": {}, "c": []},
    {"nan": math.nan, "inf": [math.inf, -math.inf], "nested": [[[]], [{}], "line\nbreak"]},
])
def test_iterencode_gives_the_text_of_json_dumps(value):
    assert "".join(ENCODER.iterencode(value)) == json.dumps(value, indent=2, ensure_ascii=False)


@pytest.mark.parametrize("include", [False, True])
@pytest.mark.parametrize("summary", [
    [_task(0), _task(1), "not a task", {}, [{"statevector": "AAAA"}]],
    [],
    [_task(2)],
])
def test_batch_text_read_task_by_task_equals_the_whole_report(include, summary):
    results = {"run_name": "r", 7: "int key", "benchmark_summary": summary, "report_source": "x",
               "raw_results": [{"simulator": "qiskit", "statevector": _statevector(4, 1)}],
               "statevector": "AAAA", "saved_from": "server_job"}
    whole = json.dumps(results_data(results, include, "server_job"), indent=2, ensure_ascii=False)
    loaded = []
    chunks = results_json_source(results, include, "server_job",
                                 lambda i: loaded.append(i) or summary[i])
    assert "".join(chunks()) == whole
    assert "".join(chunks()) == whole
    assert loaded == list(range(len(summary))) * 2


@pytest.mark.parametrize("options", [
    {}, {"include_statevectors": True},
    {"author_name": "Ada", "author_affiliation": "JYU", "name": "Run ü"},
    {"publication_artifacts": {"items": [{"view": "agreement", "formats": ["csv", "latex"]},
                                         {"view": "fidelity_heatmap", "formats": ["svg", "csv"]}]}},
])
def test_spilled_batch_crate_equals_the_crate_of_the_report_in_memory(client, options):
    tasks = [_task(i) for i in range(4)]
    report = _spilled_job("xs-batch", tasks, seed=5, started_at="2026-10-21T10:00:00+00:00")
    r = client.post("/jobs/xs-batch/export", json=options)
    assert r.status_code == 200
    payload = schemas.ExportPayload(**options)
    reference = exporter.build_ro_crate(exporter.build_export_context(report, payload, "server_job"))
    assert _members(r.content) == _members(reference)
    assert r.headers["content-disposition"].endswith('.zip"')


def test_single_circuit_job_crate_equals_the_crate_of_the_report_in_memory(client):
    report = {**_task(0), "mode": "statevector"}
    job_manager.ACTIVE_JOBS["xs-one"] = job_manager._completed_job("t", report, {})
    r = client.post("/jobs/xs-one/export", json={"include_statevectors": True})
    reference = exporter.build_ro_crate(exporter.build_export_context(
        report, schemas.ExportPayload(include_statevectors=True), "server_job"))
    assert r.status_code == 200 and _members(r.content) == _members(reference)


def _traced_peak(fn):
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        start = tracemalloc.get_traced_memory()[0]
        out = fn()
        return out, tracemalloc.get_traced_memory()[1] - start
    finally:
        tracemalloc.stop()


@pytest.mark.parametrize("include", [False, True])
def test_export_of_a_spilled_batch_holds_about_one_task(include):
    backends = tuple(f"b{k}" for k in range(6))
    task_chars = 6 * len(_statevector(1 << 14, 0))
    payload = schemas.ExportPayload(include_statevectors=include)
    peaks = {}
    for n in (1, 8):
        _spilled_job(f"xs-mem{n}", [_task(i, 1 << 14, backends) for i in range(n)])
        (ctx, fh), peaks[n] = _traced_peak(lambda: export_router._job_crate_file(f"xs-mem{n}", payload))
        with fh:
            names = zipfile.ZipFile(fh).namelist()
        assert sum("/circuits/" in name for name in names) == n
    assert peaks[8] < 4 * task_chars, f"peak {peaks[8]} bytes for 8 tasks of {task_chars} characters"
    assert peaks[8] < 1.3 * peaks[1], peaks


def test_a_job_whose_task_files_are_removed_during_the_export_is_404(client, monkeypatch):
    _spilled_job("xs-gone", [_task(i) for i in range(3)])
    real = export_router.build_export_context

    def expire_then_build(*args, **kwargs):
        job_store.remove_job_files("xs-gone")
        return real(*args, **kwargs)
    monkeypatch.setattr(export_router, "build_export_context", expire_then_build)
    r = client.post("/jobs/xs-gone/export", json={})
    assert r.status_code == 404 and r.json()["detail"] == JOB_NOT_FOUND
    os.makedirs(job_store.SPILL_DIR, exist_ok=True)
    assert os.listdir(job_store.SPILL_DIR) == []
