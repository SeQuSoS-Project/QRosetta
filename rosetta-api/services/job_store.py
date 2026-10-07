"""Job table for ACTIVE_JOBS: each job's untruncated report (``full_results``) is kept in a
file on local disk rather than in the worker's memory (in memory when the write fails), and
deleted with the job. A batch writes each task's report to the job's directory as the task
finishes (``spill_task_report``), so the batch report holds references that ``full_report``
and ``write_report_json`` read back one task at a time."""

import asyncio
import json
import os
import pickle
import shutil
import tempfile
import uuid

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-job-store")

SPILL_DIR = os.getenv("QROSETTA_JOB_SPILL_DIR", os.path.join(tempfile.gettempdir(), "qrosetta-jobs"))

JOB_NOT_FOUND = ("Job not found. Jobs are kept for 30 minutes after they finish and are lost "
                 "if the server restarts; submit the run again.")

_JSON_OPTIONS = {"ensure_ascii": False, "allow_nan": False, "indent": None, "separators": (",", ":")}


class SpilledReport:
    """Reference to a report pickled at ``path``."""

    __slots__ = ("path",)

    def __init__(self, path):
        self.path = path

    def load(self) -> dict:
        with open(self.path, "rb") as fh:
            return pickle.load(fh)


def reset_spill_dir() -> None:
    """Remove reports left by a previous server process and recreate the directory."""
    shutil.rmtree(SPILL_DIR, ignore_errors=True)
    os.makedirs(SPILL_DIR, exist_ok=True)


def _path(job_id) -> str:
    return os.path.join(SPILL_DIR, f"{os.path.basename(str(job_id))}.pickle")


def job_dir(job_id) -> str:
    """Directory for the job's other files (batch task reports, experiment bundle)."""
    return os.path.join(SPILL_DIR, os.path.basename(str(job_id)))


def remove_job_files(job_id) -> None:
    try:
        os.remove(_path(job_id))
    except OSError:
        pass
    shutil.rmtree(job_dir(job_id), ignore_errors=True)


def _write_pickle(obj, path: str) -> None:
    """Pickle ``obj`` to ``path`` through a temporary file, so ``path`` is never partial."""
    tmp = f"{path}.{uuid.uuid4().hex}.tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "wb") as fh:
            pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def spill_task_report(job_id, index: int, report: dict):
    """Write one batch task's report to the job's directory and return its reference; the
    report itself when the write fails."""
    path = os.path.join(job_dir(job_id), f"task-{int(index):05d}.pickle")
    try:
        _write_pickle(report, path)
        return SpilledReport(path)
    except Exception as exc:
        logger.warning(f"Keeping task {index} of job {job_id} in memory: {type(exc).__name__}: {exc}")
        return report


class JobTable(dict):
    """dict of job_id -> job whose ``full_results`` dicts are written to disk on assignment.
    A job's ``owner_user_id`` survives every later assignment that does not set it.
    ``store`` is the assignment for the event loop: it writes the report in a thread."""

    def _with_owner(self, job_id, job):
        previous = dict.get(self, job_id)
        if (isinstance(job, dict) and isinstance(previous, dict) and "owner_user_id" in previous
                and "owner_user_id" not in job):
            job = {**job, "owner_user_id": previous["owner_user_id"]}
        return job

    @staticmethod
    def _spilled(job_id, job):
        if isinstance(job, dict) and isinstance(job.get("full_results"), dict):
            path = _path(job_id)
            try:
                _write_pickle(job["full_results"], path)
                job = {**job, "full_results": SpilledReport(path)}
            except Exception as exc:
                logger.warning(f"Keeping the report of job {job_id} in memory: "
                               f"{type(exc).__name__}: {exc}")
        return job

    def __setitem__(self, job_id, job):
        super().__setitem__(job_id, self._spilled(job_id, self._with_owner(job_id, job)))

    async def store(self, job_id, job) -> bool:
        """Assign ``job`` once its report is written, writing it in a worker thread; readers
        see the previous entry until then. A job evicted meanwhile is not added back and its
        files are removed. Returns whether the job was stored."""
        spilled = await asyncio.to_thread(self._spilled, job_id, job)
        if not dict.__contains__(self, job_id):
            await asyncio.to_thread(remove_job_files, job_id)
            return False
        super().__setitem__(job_id, self._with_owner(job_id, spilled))
        return True

    def pop(self, job_id, *default):
        remove_job_files(job_id)
        return super().pop(job_id, *default)

    def __delitem__(self, job_id):
        remove_job_files(job_id)
        super().__delitem__(job_id)


def _loaded(report):
    return report.load() if isinstance(report, SpilledReport) else report


def full_report(job: dict, each_task=None):
    """The job's untruncated report, or None when it has none. A batch's task reports are
    read one at a time and passed through ``each_task`` when given. Raises
    FileNotFoundError when the job's files were removed (the job expired)."""
    report = _loaded(job.get("full_results"))
    if isinstance(report, dict) and isinstance(report.get("benchmark_summary"), list):
        tasks = []
        for task in report["benchmark_summary"]:
            task = _loaded(task)
            tasks.append(each_task(task) if each_task else task)
        report = {**report, "benchmark_summary": tasks}
    return report


def report_json_file(job: dict):
    """The job's full report as JSON (``write_report_json``) in an unnamed temporary file in
    SPILL_DIR, positioned at its start. Raises FileNotFoundError when the job's files were
    removed (the job expired)."""
    os.makedirs(SPILL_DIR, exist_ok=True)
    fh = tempfile.TemporaryFile(dir=SPILL_DIR)
    try:
        write_report_json(job, fh)
        fh.seek(0)
        return fh
    except BaseException:
        fh.close()
        raise


def file_chunks(fh, size: int = 1 << 20):
    """Read the binary file ``fh`` in chunks for a StreamingResponse, closing it at the end.
    An open file stays readable after the job's files are removed."""
    try:
        while chunk := fh.read(size):
            yield chunk
    finally:
        fh.close()


def write_report_json(job: dict, fh) -> None:
    """Write the job's full report to the binary file ``fh`` as the JSON a JSONResponse of
    ``full_report(job)`` sends, holding one batch task's report in memory at a time."""
    report = _loaded(job.get("full_results"))
    if not (isinstance(report, dict) and isinstance(report.get("benchmark_summary"), list)):
        fh.write(json.dumps(report, **_JSON_OPTIONS).encode("utf-8"))
        return
    fh.write(b"{")
    for i, (key, value) in enumerate(report.items()):
        if i:
            fh.write(b",")
        fh.write(json.dumps(key, **_JSON_OPTIONS).encode("utf-8") + b":")
        if key != "benchmark_summary":
            fh.write(json.dumps(value, **_JSON_OPTIONS).encode("utf-8"))
            continue
        fh.write(b"[")
        for j, task in enumerate(value):
            if j:
                fh.write(b",")
            fh.write(json.dumps(_loaded(task), **_JSON_OPTIONS).encode("utf-8"))
        fh.write(b"]")
    fh.write(b"}")
