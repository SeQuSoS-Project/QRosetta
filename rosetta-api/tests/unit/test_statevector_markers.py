"""Statevector markers: history storage, export descriptions, and the job export route."""
import io
import json
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("kubernetes")

import services.storage as storage  # noqa: E402
from routers import benchmark, export  # noqa: E402
from services.exporter import ExportContext, build_ro_crate  # noqa: E402
from services.job_manager import ACTIVE_JOBS, _STATEVECTOR_PLACEHOLDER  # noqa: E402

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];\n'


def _crate(results, include=True):
    ctx = ExportContext(qasm_string=QASM, results=results, mode="statevector",
                        runner_services={}, include_statevectors=include)
    zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)))
    read = lambda suffix: zf.read(next(n for n in zf.namelist() if n.endswith(suffix)))
    return zf, json.loads(read("ro-crate-metadata.json")), json.loads(read("results.json"))


def _results_desc(meta):
    return next(e for e in meta["@graph"] if e["@id"] == "results.json")["description"]


def test_history_storage_marks_removed_statevectors(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MOCK_S3_DIR", str(tmp_path))
    monkeypatch.setattr(storage.settings, "STORAGE_MODE", "local")
    key = storage.save_run_report(1, "r1", {"raw_results": [{"simulator": "qiskit", "statevector": "AAAA"}]})
    stored = storage.fetch_run_report(key)
    assert stored["statevector_storage"] == storage.STATEVECTOR_STORAGE_MARKER
    assert "statevector" not in stored["raw_results"][0]
    _, meta, _ = _crate(stored)
    desc = _results_desc(meta)
    assert "Includes raw statevectors" not in desc
    assert "removed when this report was saved" in desc


def test_placeholder_is_not_exported_as_data():
    results = {"input_qasm": QASM, "raw_results": [
        {"simulator": "qiskit", "statevector": _STATEVECTOR_PLACEHOLDER,
         "statevector_omitted_for_display": True},
        {"simulator": "cirq", "statevector": "AAAAAAAAAAAAAAAAAAAAAA=="},
    ]}
    _, meta, data = _crate(results)
    desc = _results_desc(meta)
    assert "Includes raw statevectors for 1 backend result(s)." in desc
    assert "1 result(s) carry no statevector" in desc
    qiskit = next(r for r in data["raw_results"] if r["simulator"] == "qiskit")
    assert qiskit["statevector"] is None and qiskit["statevector_omitted_for_display"] is True


def test_job_export_uses_server_copy_with_dispatched_circuits():
    full = {
        "input_qasm": QASM, "apply_preprocessing": False, "timeout_seconds": 30,
        "started_at": "2026-01-01T00:00:00.000+00:00", "finished_at": "2026-01-01T00:00:05.000+00:00",
        "dispatched_circuits": [{"group": "statevector", "qasm": QASM + "// sent\n",
                                 "api_preprocessing_applied": [], "runners": ["qiskit"]}],
        "raw_results": [{"simulator": "qiskit", "statevector": "B" * 40, "optimization_level": 0,
                         "dispatched_at": "2026-01-01T00:00:01.000+00:00",
                         "completed_at": "2026-01-01T00:00:02.000+00:00"}],
    }
    ACTIVE_JOBS["job-x"] = {"status": "completed", "target": "local", "results": {},
                            "full_results": full, "finished_at": 0}
    app = FastAPI()
    app.state.limiter = export.limiter
    app.include_router(export.router)
    app.include_router(benchmark.router)
    client = TestClient(app)
    try:
        r = client.post("/jobs/job-x/export", json={"include_statevectors": True})
        assert r.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = [n.split("/", 1)[1] for n in zf.namelist()]
        assert "dispatched_circuits/qiskit.qasm" in names
        data = json.loads(zf.read(next(n for n in zf.namelist() if n.endswith("results.json"))))
        assert data["raw_results"][0]["statevector"] == "B" * 40
        assert "qasm" not in data["dispatched_circuits"][0]
        meta = json.loads(zf.read(next(n for n in zf.namelist() if n.endswith("ro-crate-metadata.json"))))
        run = next(e for e in meta["@graph"] if e["@id"] == "#run-qiskit")
        assert run["startTime"] == "2026-01-01T00:00:01.000+00:00"
        assert run["endTime"] == "2026-01-01T00:00:02.000+00:00"
        assert {"@id": "dispatched_circuits/qiskit.qasm"} in run["object"]
        prov = json.loads(zf.read(next(n for n in zf.namelist() if n.endswith("provenance.json"))))
        assert prov["run_configuration"]["timeout_seconds"] == 30
        assert prov["run_configuration"]["git_sha"] == "not recorded"

        assert client.get("/jobs/job-x/report").json()["raw_results"][0]["statevector"] == "B" * 40
        assert client.post("/jobs/missing/export", json={}).status_code == 404
        ACTIVE_JOBS["job-y"] = {"status": "processing", "target": "local"}
        assert client.post("/jobs/job-y/export", json={}).status_code == 409
    finally:
        ACTIVE_JOBS.pop("job-x", None)
        ACTIVE_JOBS.pop("job-y", None)
