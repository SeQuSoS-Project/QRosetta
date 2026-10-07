"""Job lifecycle: work kept off the event loop, batch reports spilled per task, worker
failures, eviction of stuck jobs, compile-only failure, and jobs that expire mid-request."""
import asyncio
import json
import os
import time
import tracemalloc
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("pytket")

import services.compilation as compilation  # noqa: E402
import services.job_manager as job_manager  # noqa: E402
from schemas import BatchPayload, BenchmarkTask  # noqa: E402
from services import job_store  # noqa: E402
from services.job_store import JOB_NOT_FOUND  # noqa: E402

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
_JSON_RESPONSE_OPTIONS = {"ensure_ascii": False, "allow_nan": False, "indent": None,
                          "separators": (",", ":")}


@pytest.fixture(autouse=True)
def spill_dir(tmp_path, monkeypatch):
    path = tmp_path / "spill"
    monkeypatch.setattr(job_store, "SPILL_DIR", str(path))
    yield path
    for job_id in [j for j in job_manager.ACTIVE_JOBS if str(j).startswith("lc-")]:
        job_manager.ACTIVE_JOBS.pop(job_id, None)


@pytest.fixture
def fake_dispatch(monkeypatch):
    async def dispatch(runner_urls, runner_payload=None, timeout_seconds=None, runner_statuses=None):
        if all(str(url).endswith("/compile") for url in runner_urls.values()):
            return [{"simulator": cid, "optimization_level": 1, "dispatch_status": "error",
                     "error": "compiler crashed"} for cid in runner_urls]
        return [{"simulator": name, "statevector": "AAAA", "dispatch_status": "ok"}
                for name in runner_urls]
    monkeypatch.setattr(job_manager, "dispatch_to_runners", dispatch)
    monkeypatch.setattr(compilation, "dispatch_to_runners", dispatch)


@pytest.fixture
def client(monkeypatch):
    from routers import benchmark, experiment
    from routers.errors import register_error_handlers
    from services.security import limiter
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    app.include_router(benchmark.router)
    app.include_router(experiment.router)
    return TestClient(app)


async def _max_loop_gap(coro) -> tuple:
    """Run ``coro`` beside a 5 ms ticker; return (its result, the longest gap between ticks)."""
    gaps, done = [0.0], asyncio.Event()

    async def tick():
        last = time.perf_counter()
        while not done.is_set():
            await asyncio.sleep(0.005)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    ticker = asyncio.create_task(tick())
    try:
        result = await coro
    finally:
        done.set()
        await ticker
    return result, max(gaps)


def _blocking(seconds, real):
    def prepare(*args, **kwargs):
        time.sleep(seconds)
        return real(*args, **kwargs)
    return prepare


@pytest.mark.parametrize("measured", [False, True])
def test_circuit_preparation_does_not_block_the_event_loop(monkeypatch, fake_dispatch, measured):
    monkeypatch.setattr(job_manager, "prepare_statevector_dispatch",
                        _blocking(0.4, job_manager.prepare_statevector_dispatch))
    monkeypatch.setattr(job_manager, "prepare_measured_dispatch",
                        _blocking(0.4, job_manager.prepare_measured_dispatch))
    monkeypatch.setattr(compilation, "prepare_statevector_dispatch",
                        _blocking(0.4, compilation.prepare_statevector_dispatch))
    run = (job_manager.run_single_circuit_measurement(QASM, 100, target_simulators=["qiskit"],
                                                      compilers={"pyzx": [1]})
           if measured else
           job_manager.run_single_circuit_comparison(QASM, target_simulators=["qiskit"],
                                                     compilers={"pyzx": [1]}))
    report, gap = asyncio.run(_max_loop_gap(run))
    assert report["raw_results"] and report["compile_input"]["qasm"]
    assert gap < 0.2, f"event loop blocked for {gap:.2f} s"


def test_storing_a_large_report_does_not_block_the_event_loop():
    report = {"raw_results": [{"simulator": f"s{i}", "statevector": os.urandom(8 << 20).hex()}
                              for i in range(6)]}
    job_manager.ACTIVE_JOBS["lc-big"] = job_manager.new_job()

    async def store():
        return await job_manager.ACTIVE_JOBS.store("lc-big", job_manager._completed_job("t", report, {}))
    stored, gap = asyncio.run(_max_loop_gap(store()))
    assert stored and gap < 0.2, f"event loop blocked for {gap:.2f} s"
    assert isinstance(dict.__getitem__(job_manager.ACTIVE_JOBS, "lc-big")["full_results"],
                      job_store.SpilledReport)
    assert job_store.full_report(job_manager.ACTIVE_JOBS["lc-big"]) == report


def test_store_shows_the_previous_entry_until_the_report_is_written(monkeypatch):
    table = job_store.JobTable()
    table["j"] = {"status": "processing", "owner_user_id": 7}
    seen = []
    real = job_store._write_pickle

    def slow_write(obj, path):
        seen.append(dict.__getitem__(table, "j")["status"])
        real(obj, path)
    monkeypatch.setattr(job_store, "_write_pickle", slow_write)
    asyncio.run(table.store("j", {"status": "completed", "full_results": {"x": 1}}))
    assert seen == ["processing"]
    assert table["j"]["status"] == "completed" and table["j"]["owner_user_id"] == 7
    assert job_store.full_report(table["j"]) == {"x": 1}


def test_a_job_evicted_while_its_report_is_written_is_not_added_back(spill_dir, monkeypatch):
    table = job_store.JobTable()
    table["j"] = {"status": "processing"}
    real = job_store._write_pickle

    def write_then_evict(obj, path):
        real(obj, path)
        table.pop("j")
    monkeypatch.setattr(job_store, "_write_pickle", write_then_evict)
    assert asyncio.run(table.store("j", {"status": "completed", "full_results": {"x": 1}})) is False
    assert "j" not in table and not any(spill_dir.rglob("*.pickle"))


def test_a_report_that_cannot_be_pickled_stays_in_memory():
    table = job_store.JobTable()
    report = {"raw_results": [], "fn": lambda: None}
    table["j"] = {"status": "completed", "full_results": report}
    assert table["j"]["full_results"] is report
    report_r = {"raw_results": [], "deep": None}
    node = report_r
    for _ in range(100000):
        node["deep"] = {"deep": None}
        node = node["deep"]
    table["k"] = {"status": "completed", "full_results": report_r}
    assert table["k"]["full_results"] is report_r


def _fake_task_runs(monkeypatch, sv_chars):
    async def run(qasm_string, *args, **kwargs):
        return {"input_qasm": qasm_string, "raw_results": [
            {"simulator": "qiskit", "statevector": os.urandom(sv_chars // 2).hex(), "dispatch_status": "ok"}]}
    monkeypatch.setattr(job_manager, "run_single_circuit_comparison", run)


def test_batch_reports_are_spilled_per_task_and_served_whole(monkeypatch, client, spill_dir):
    big = job_manager._MAX_DISPLAY_STATEVECTOR_B64_CHARS // 2 * 2 + 2
    _fake_task_runs(monkeypatch, big)
    payload = BatchPayload(mode="statevector",
                           tasks=[BenchmarkTask(algorithm=f"t{i}", qasm_string=QASM) for i in range(3)])
    job_manager.ACTIVE_JOBS["lc-batch"] = job_manager.new_job()
    asyncio.run(job_manager.worker_batch_suite("lc-batch", payload))

    job = job_manager.ACTIVE_JOBS["lc-batch"]
    assert job["status"] == "completed"
    tasks = sorted(p.name for p in (spill_dir / "lc-batch").iterdir())
    assert tasks == ["task-00000.pickle", "task-00001.pickle", "task-00002.pickle"]
    shown = job["results"]["benchmark_summary"]
    assert [t["raw_results"][0]["statevector_omitted_for_display"] for t in shown] == [True] * 3
    report = job_store.full_report(job)
    assert [len(t["raw_results"][0]["statevector"]) for t in report["benchmark_summary"]] == [big] * 3

    expected = json.dumps(report, **_JSON_RESPONSE_OPTIONS).encode("utf-8")
    r = client.get("/jobs/lc-batch/report")
    assert r.status_code == 200 and r.content == expected
    assert r.headers["content-type"] == "application/json"

    job_manager.ACTIVE_JOBS.pop("lc-batch")
    assert not (spill_dir / "lc-batch").exists() and not list(spill_dir.glob("lc-batch*"))


def test_batch_memory_is_one_task_not_the_whole_playlist(monkeypatch):
    task_bytes = 4 << 20
    _fake_task_runs(monkeypatch, task_bytes)
    payload = BatchPayload(mode="statevector",
                           tasks=[BenchmarkTask(algorithm=f"t{i}", qasm_string=QASM) for i in range(10)])
    job_manager.ACTIVE_JOBS["lc-mem"] = job_manager.new_job()
    tracemalloc.start()
    try:
        asyncio.run(job_manager.worker_batch_suite("lc-mem", payload))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert job_manager.ACTIVE_JOBS["lc-mem"]["status"] == "completed"
    assert peak < 4 * task_bytes, f"peak {peak / 2**20:.1f} MiB for 10 tasks of 4 MiB"


def test_a_batch_worker_that_raises_fails_the_job_without_details(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("internal detail /home/appuser/app/services/x.py")
    monkeypatch.setattr(job_manager, "run_batch_tasks", boom)
    job_manager.ACTIVE_JOBS["lc-raise"] = job_manager.new_job()
    payload = BatchPayload(mode="statevector", tasks=[BenchmarkTask(algorithm="ghz", qubits=2)])
    asyncio.run(job_manager.worker_batch_suite("lc-raise", payload))
    job = job_manager.ACTIVE_JOBS["lc-raise"]
    assert job["status"] == "failed" and "RuntimeError" in job["error"]
    assert "/home/appuser" not in job["error"] and "finished_at" in job


def test_cleanup_evicts_finished_and_orphaned_jobs_but_not_running_ones():
    jobs = job_manager.ACTIVE_JOBS
    old = time.time() - job_manager.JOB_TTL_SEC - 1

    async def scenario():
        running = asyncio.create_task(asyncio.sleep(10))
        finished = asyncio.create_task(asyncio.sleep(0))
        await finished
        jobs["lc-done"] = {"status": "completed", "finished_at": old}
        jobs["lc-recent"] = {"status": "completed", "finished_at": time.time()}
        jobs["lc-orphan"] = {"status": "processing", "submitted_at": old, "worker": finished}
        jobs["lc-never-started"] = {"status": "pending", "submitted_at": old}
        jobs["lc-running"] = {"status": "processing", "submitted_at": old, "worker": running}
        jobs["lc-young"] = {"status": "processing", "submitted_at": time.time(), "worker": finished}
        expired = {j for j in job_manager.expired_job_ids() if j.startswith("lc-")}
        running.cancel()
        return expired
    assert asyncio.run(scenario()) == {"lc-done", "lc-orphan", "lc-never-started"}


def test_start_job_records_its_worker():
    job_manager.ACTIVE_JOBS["lc-w"] = job_manager.new_job()

    async def scenario():
        job_manager.start_job("lc-w", {})
        return asyncio.current_task()
    task = asyncio.run(scenario())
    assert job_manager.ACTIVE_JOBS["lc-w"]["worker"] is task and task.done()


def test_compile_only_run_where_every_compile_failed_is_a_failed_job(fake_dispatch):
    report = {"simulated": False, "raw_results": [], "compiled_circuits": [
        {"compiler": "pyzx~opt1~run1", "dispatch_status": "error", "error": "x"},
        {"compiler": "qmap~opt0~run1", "dispatch_status": "skipped", "error": "mid-circuit"}]}
    assert job_manager.all_runners_failed(report) == "all 2 compiles failed"
    report["compiled_circuits"][0] = {"compiler": "pyzx~opt1~run1", "dispatch_status": "ok",
                                      "transpiled_qasm": QASM}
    assert job_manager.all_runners_failed(report) is None

    job_manager.ACTIVE_JOBS["lc-co"] = job_manager.new_job()
    asyncio.run(job_manager.worker_compare("lc-co", QASM, 0, {}, 30, [], "local",
                                           compilers={"pyzx": [1]}, simulate=False))
    job = job_manager.ACTIVE_JOBS["lc-co"]
    assert job["status"] == "failed" and job["error"] == "all 1 compiles failed"
    assert job_store.full_report(job)["compiled_circuits"][0]["error"] == "compiler crashed"

    payload = BatchPayload(mode="statevector", simulate=False, compilers={"pyzx": [1]},
                           tasks=[BenchmarkTask(algorithm="a", qasm_string=QASM),
                                  BenchmarkTask(algorithm="b", qasm_string=QASM)])
    job_manager.ACTIVE_JOBS["lc-cob"] = job_manager.new_job()
    asyncio.run(job_manager.worker_batch_suite("lc-cob", payload))
    job = job_manager.ACTIVE_JOBS["lc-cob"]
    assert job["status"] == "failed"
    assert job["error"] == "All 2 task(s) failed: no compile produced a circuit"
    assert [t["status"] for t in job["progress"]["tasks"]] == ["error", "error"]


def test_report_download_of_a_job_whose_files_were_removed_is_404(client):
    job_manager.ACTIVE_JOBS["lc-gone"] = job_manager._completed_job("t", {"raw_results": []}, {})
    os.remove(job_manager.ACTIVE_JOBS["lc-gone"]["full_results"].path)
    r = client.get("/jobs/lc-gone/report")
    assert r.status_code == 404 and r.json()["detail"] == JOB_NOT_FOUND
    with pytest.raises(Exception) as exc:
        job_manager.job_report_or_error("lc-gone", "export")
    assert exc.value.status_code == 404 and exc.value.detail == JOB_NOT_FOUND


def test_experiment_bundle_is_written_to_disk(monkeypatch, spill_dir):
    import services.experiment as exp
    from schemas import ExperimentCircuit, ExperimentPayload

    async def fake_batch(payload, runner_statuses, progress=None, batch_seed=None, task_offset=0,
                         store=None):
        out = []
        for i, task in enumerate(payload.tasks):
            report = {"task_name": "bell (2q)", "input_qasm": task.qasm_string, "raw_results": [
                {"simulator": "qiskit", "statevector": "AAAAAAAAAAAAAAAAAAAAAA==",
                 "counts": {"00": 5}, "runner_image": "img", "dispatch_status": "ok"}]}
            out.append(await store(i, report))
        return out, batch_seed
    monkeypatch.setattr(exp, "run_batch_tasks", fake_batch)
    payload = ExperimentPayload(circuits=[ExperimentCircuit(source="qasm", qasm_string=QASM, name="bell")],
                                mode="measured", seed=1)
    job_manager.ACTIVE_JOBS["lc-exp"] = {"status": "pending", "target": "local"}
    asyncio.run(exp.worker_experiment("lc-exp", payload))
    job = job_manager.ACTIVE_JOBS["lc-exp"]
    assert job["status"] == "completed" and "bundle_files" not in job
    assert job["bundle_path"] == str(spill_dir / "lc-exp" / "bundle.zip")
    assert sorted(p.name for p in (spill_dir / "lc-exp").iterdir()) == ["bundle.zip"]
    with zipfile.ZipFile(job["bundle_path"]) as zf:
        names = zf.namelist()
        result = json.loads(zf.read("results/measured_preprocOn/000_bell.json"))
        manifest = json.loads(zf.read("manifest.json"))
    assert names == sorted(names)
    assert result["raw_results"][0]["counts"] == {"00": 5}
    assert result["raw_results"][0]["statevector"] is None
    assert manifest["runner_images"] == {"qiskit": "img"}
    job_manager.ACTIVE_JOBS.pop("lc-exp")
    assert not (spill_dir / "lc-exp").exists()


def test_kept_experiment_record_drops_bulky_fields():
    import services.experiment as exp
    record = exp._kept_record({"task_name": "t", "input_qasm": QASM, "git_sha": "abc",
                               "raw_results": [{"simulator": "q", "statevector": "x", "counts": {"0": 1},
                                                "transpiled_qasm": QASM, "sdk_versions": {"q": "1"}}],
                               "divergence_report": {"pairwise_agreement": [{"agreement": "a"}],
                                                     "matrix": [[1]]}})
    assert record == {"task_name": "t", "git_sha": "abc",
                      "raw_results": [{"simulator": "q", "sdk_versions": {"q": "1"}}],
                      "divergence_report": {"pairwise_agreement": [{"agreement": "a"}]}}
