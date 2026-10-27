"""Job table for ACTIVE_JOBS: each job's untruncated report (``full_results``) is kept in a
file on local disk rather than in the worker's memory (in memory when the write fails), and
deleted with the job. A batch writes each task's report to the job's directory as the task
finishes (``spill_task_report``), so the batch report holds references that ``full_report``,
``report_with_task_loader`` and ``write_report_json`` read back one task at a time.

The directory has a budget (``settings.JOB_SPILL_MAX_MIB``) and a free-disk floor
(``settings.JOB_SPILL_MIN_FREE_MIB``): ``storage_problem`` says when either is crossed, and
``spill_task_report`` raises ``JobStorageFull`` then instead of writing. A single-circuit
report is always written, so the budget can be exceeded by the reports of jobs already
running."""

import asyncio
import json
import os
import pickle
import shutil
import tempfile
import uuid

from config import settings
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-job-store")

SPILL_DIR = os.getenv("QROSETTA_JOB_SPILL_DIR", os.path.join(tempfile.gettempdir(), "qrosetta-jobs"))

def retention_text(seconds: int) -> str:
    """A retention time in words: '30 minutes', '24 hours', '1 hour', '90 seconds'."""
    seconds = int(seconds)
    for unit, size in (("hour", 3600), ("minute", 60)):
        if seconds >= size and seconds % size == 0:
            n = seconds // size
            return f"{n} {unit}{'' if n == 1 else 's'}"
    return f"{seconds} second{'' if seconds == 1 else 's'}"


JOB_NOT_FOUND = (f"Job not found. Jobs are kept for {retention_text(settings.JOB_TTL_SEC)} after "
                 f"they finish and are lost if the server restarts; submit the run again.")

_JSON_OPTIONS = {"ensure_ascii": False, "allow_nan": False, "indent": None, "separators": (",", ":")}


_MIB = 1024 * 1024


class JobStorageFull(RuntimeError):
    """The spill directory is over its budget or its disk is below the free-space floor."""


def spill_usage_bytes() -> int:
    """Bytes held by the files under SPILL_DIR (0 when it does not exist)."""
    total = 0
    for root, _dirs, files in os.walk(SPILL_DIR):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def storage_problem():
    """Why no new job report may be written to SPILL_DIR, or None: the files there hold
    JOB_SPILL_MAX_MIB or more, or the disk holding it has less than JOB_SPILL_MIN_FREE_MIB
    free."""
    used = spill_usage_bytes()
    budget = settings.JOB_SPILL_MAX_MIB
    if used >= budget * _MIB:
        return (f"The server's storage for job results is full: it holds {used / _MIB:,.0f} MiB "
                f"and its limit is {budget:,} MiB (limits.job_storage_max_mib in GET /config). "
                f"Finished jobs are deleted {retention_text(settings.JOB_TTL_SEC)} after they "
                f"finish, and while the storage is full from "
                f"{retention_text(settings.JOB_EVICTABLE_AFTER_SEC)} after they finish, oldest "
                f"first; submit again later.")
    try:
        os.makedirs(SPILL_DIR, exist_ok=True)
        free = shutil.disk_usage(SPILL_DIR).free
    except OSError:
        return None
    floor = settings.JOB_SPILL_MIN_FREE_MIB
    if free < floor * _MIB:
        return (f"The server is low on disk space for job results: {free / _MIB:,.0f} MiB free, "
                f"and it keeps at least {floor:,} MiB free (limits.job_storage_min_free_mib in "
                f"GET /config). Submit again later.")
    return None


def require_storage() -> None:
    """Raise JobStorageFull with ``storage_problem``'s reason, if any."""
    problem = storage_problem()
    if problem:
        raise JobStorageFull(problem)


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
    report itself when the write fails. Raises JobStorageFull (``require_storage``) without
    writing."""
    require_storage()
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


def report_or_task(job: dict, task):
    """``(report, n_tasks)``. For a single-circuit job: its untruncated report (None when
    ``task`` is set) and None. For a batch: the report of task ``task`` alone, the other
    tasks not read (None when ``task`` is None or out of range), and the batch length.
    Raises FileNotFoundError when the job's files were removed (the job expired)."""
    report = _loaded(job.get("full_results"))
    tasks = report.get("benchmark_summary") if isinstance(report, dict) else None
    if not isinstance(tasks, list):
        return (report if task is None else None), None
    if task is None or not 0 <= task < len(tasks):
        return None, len(tasks)
    return _loaded(tasks[task]), len(tasks)


def report_with_task_loader(job: dict, each_task):
    """``(report, load)``: the job's untruncated report with each batch task's report passed
    through ``each_task`` (read one at a time), and ``load(i)``, which reads task i's report
    again; ``load`` is None when the report is not a batch. Raises FileNotFoundError when the
    job's files were removed (the job expired), from ``load`` too."""
    report = _loaded(job.get("full_results"))
    if not (isinstance(report, dict) and isinstance(report.get("benchmark_summary"), list)):
        return report, None
    refs = list(report["benchmark_summary"])
    tasks = [each_task(_loaded(task)) for task in refs]
    return {**report, "benchmark_summary": tasks}, lambda i: _loaded(refs[i])


def written_file(write):
    """An unnamed temporary file in SPILL_DIR holding what ``write(fh)`` wrote, positioned at
    its start; closed (and so removed) when ``write`` raises."""
    os.makedirs(SPILL_DIR, exist_ok=True)
    fh = tempfile.TemporaryFile(dir=SPILL_DIR)
    try:
        write(fh)
        fh.seek(0)
        return fh
    except BaseException:
        fh.close()
        raise


def report_json_file(job: dict):
    """The job's full report as JSON (``write_report_json``) in an unnamed temporary file in
    SPILL_DIR, positioned at its start. Raises FileNotFoundError when the job's files were
    removed (the job expired)."""
    return written_file(lambda fh: write_report_json(job, fh))


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
