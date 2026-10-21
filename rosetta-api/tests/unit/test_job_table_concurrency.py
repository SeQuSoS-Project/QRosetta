"""JobTable under interleaved store, replace, pop and read: a Hypothesis state machine
whose rules run a store or a report read while the job is evicted from another thread."""
import asyncio
import os
import shutil
import tempfile
import threading

import pytest
from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from services import job_store
from services.job_store import JobTable, full_report, spill_task_report

JOB_IDS = st.sampled_from(["job-a", "job-b", "job-c"])
OWNERS = st.one_of(st.none(), st.integers(1, 3))
REPORTS = st.dictionaries(st.sampled_from(["x", "y", "raw_results"]), st.integers(0, 9),
                          min_size=1, max_size=3)
TASKS = st.lists(REPORTS, min_size=2, max_size=4)


def _completed(report):
    return {"status": "completed", "full_results": report, "finished_at": 1.0}


class JobTableMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self._saved_dir = job_store.SPILL_DIR
        job_store.SPILL_DIR = tempfile.mkdtemp(dir=os.path.dirname(self._saved_dir) or None,
                                               prefix="jobtable-machine-")
        self.table = JobTable()
        self.model = {}

    def teardown(self):
        shutil.rmtree(job_store.SPILL_DIR, ignore_errors=True)
        job_store.SPILL_DIR = self._saved_dir

    def _owner_after_replace(self, job_id):
        return self.model[job_id]["owner"] if job_id in self.model else None

    def _batch(self, job_id, tasks):
        refs = [spill_task_report(job_id, i, t) for i, t in enumerate(tasks)]
        return {"mode": "statevector", "benchmark_summary": refs}

    @rule(job_id=JOB_IDS, owner=OWNERS)
    def submit(self, job_id, owner):
        self.table[job_id] = {"status": "pending", "owner_user_id": owner}
        self.model[job_id] = {"owner": owner, "report": None}

    @rule(job_id=JOB_IDS, report=REPORTS)
    def finish_in_the_loop(self, job_id, report):
        owner = self._owner_after_replace(job_id)
        self.table[job_id] = _completed(report)
        self.model[job_id] = {"owner": owner, "report": report}

    @rule(job_id=JOB_IDS, report=REPORTS, tasks=st.one_of(st.none(), TASKS))
    def finish_with_store(self, job_id, report, tasks):
        present = job_id in self.table
        full = self._batch(job_id, tasks) if tasks else report
        stored = asyncio.run(self.table.store(job_id, _completed(full)))
        assert stored is present
        if present:
            expected = {"mode": "statevector", "benchmark_summary": tasks} if tasks else report
            self.model[job_id] = {"owner": self.model[job_id]["owner"], "report": expected}

    @rule(job_id=JOB_IDS)
    def evict(self, job_id):
        self.table.pop(job_id, None)
        self.model.pop(job_id, None)

    @rule(job_id=JOB_IDS, report=REPORTS)
    def evict_while_the_report_is_written(self, job_id, report):
        if job_id not in self.table:
            return
        previous = dict.__getitem__(self.table, job_id)
        entered, proceed = threading.Event(), threading.Event()
        write = job_store._write_pickle

        def gated_write(obj, path):
            entered.set()
            assert proceed.wait(5)
            write(obj, path)

        async def scenario():
            job_store._write_pickle = gated_write
            try:
                task = asyncio.create_task(self.table.store(job_id, _completed(report)))
                assert await asyncio.to_thread(entered.wait, 5)
                assert dict.__getitem__(self.table, job_id) is previous
                self.table.pop(job_id, None)
                proceed.set()
                return await task
            finally:
                job_store._write_pickle = write

        assert asyncio.run(scenario()) is False
        self.model.pop(job_id, None)
        assert job_id not in self.table

    @rule(job_id=JOB_IDS, tasks=TASKS, as_json=st.booleans())
    def evict_while_a_batch_report_is_read(self, job_id, tasks, as_json):
        if job_id not in self.table:
            return
        self.table[job_id] = _completed(self._batch(job_id, tasks))
        entry = self.table[job_id]
        paused, resume, outcome = threading.Event(), threading.Event(), []
        load, calls = job_store._loaded, []

        def load_then_wait(report):
            calls.append(1)
            loaded = load(report)
            if len(calls) == 2:
                paused.set()
                assert resume.wait(5)
            return loaded

        def read():
            try:
                if as_json:
                    job_store.report_json_file(entry).close()
                else:
                    full_report(entry)
                outcome.append("read")
            except FileNotFoundError:
                outcome.append("expired")

        job_store._loaded = load_then_wait
        try:
            reader = threading.Thread(target=read)
            reader.start()
            assert paused.wait(5)
            self.table.pop(job_id, None)
            resume.set()
            reader.join(5)
        finally:
            job_store._loaded = load
        assert outcome == ["expired"]
        self.model.pop(job_id, None)

    @invariant()
    def table_matches_the_model(self):
        assert set(self.table) == set(self.model)
        for job_id, expected in self.model.items():
            job = self.table[job_id]
            assert job.get("owner_user_id") == expected["owner"]
            if expected["report"] is None:
                assert "full_results" not in job
            else:
                assert full_report(job) == expected["report"]

    @invariant()
    def only_jobs_in_the_table_have_files(self):
        names = set(os.listdir(job_store.SPILL_DIR)) if os.path.isdir(job_store.SPILL_DIR) else set()
        owners = {n.split(".", 1)[0] for n in names}
        assert owners <= set(self.table), names
        assert not any(n.endswith(".tmp") for n in names), names


TestJobTableMachine = JobTableMachine.TestCase
TestJobTableMachine.settings = settings(
    max_examples=40, stateful_step_count=12, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.too_slow])


@pytest.fixture(autouse=True)
def _spill_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
