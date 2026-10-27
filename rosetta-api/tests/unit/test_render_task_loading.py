"""Rendering one circuit of a playlist job reads that task's spilled report only."""

import pytest
from fastapi import HTTPException

import routers.publication as publication
from services import job_store


@pytest.fixture
def batch_job(tmp_path, monkeypatch):
    loads = []
    real = job_store.SpilledReport.load

    def counting_load(self):
        loads.append(self.path)
        return real(self)
    monkeypatch.setattr(job_store.SpilledReport, "load", counting_load)
    refs = []
    for i in range(4):
        path = tmp_path / f"task-{i}.pickle"
        job_store._write_pickle({"task_name": f"t{i}", "raw_results": []}, str(path))
        refs.append(job_store.SpilledReport(str(path)))
    job = {"status": "completed", "full_results": {"mode": "statevector", "benchmark_summary": refs}}
    monkeypatch.setattr(publication, "finished_job_or_error", lambda job_id, action: job)
    return loads, refs


def test_one_task_is_read(batch_job):
    loads, refs = batch_job
    assert publication._job_circuit_report("j", 2) == {"task_name": "t2", "raw_results": []}
    assert loads == [refs[2].path]


def test_playlist_without_task_is_400_and_reads_no_task(batch_job):
    loads, _ = batch_job
    with pytest.raises(HTTPException) as exc:
        publication._job_circuit_report("j", None)
    assert exc.value.status_code == 400 and loads == []


def test_task_out_of_range_is_404(batch_job):
    loads, _ = batch_job
    with pytest.raises(HTTPException) as exc:
        publication._job_circuit_report("j", 9)
    assert exc.value.status_code == 404 and loads == []


def test_expired_task_file_is_404(batch_job):
    _, refs = batch_job
    import os
    os.remove(refs[1].path)
    with pytest.raises(HTTPException) as exc:
        publication._job_circuit_report("j", 1)
    assert exc.value.status_code == 404
