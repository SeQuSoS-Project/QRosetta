"""Job table for ACTIVE_JOBS: each job's untruncated report (``full_results``) is kept in a
file on local disk rather than in the worker's memory (in memory when the write fails), and
deleted with the job."""

import os
import pickle
import shutil
import tempfile
import threading

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-job-store")

SPILL_DIR = os.getenv("QROSETTA_JOB_SPILL_DIR", os.path.join(tempfile.gettempdir(), "qrosetta-jobs"))

JOB_NOT_FOUND = ("Job not found. Jobs are kept for 30 minutes after they finish and are lost "
                 "if the server restarts; submit the run again.")


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


class JobTable(dict):
    """dict of job_id -> job whose ``full_results`` dicts are written to disk on assignment."""

    _lock = threading.Lock()

    def __setitem__(self, job_id, job):
        if isinstance(job, dict) and isinstance(job.get("full_results"), dict):
            path = _path(job_id)
            tmp = f"{path}.{threading.get_ident()}.tmp"
            try:
                os.makedirs(SPILL_DIR, exist_ok=True)
                with open(tmp, "wb") as fh:
                    pickle.dump(job["full_results"], fh, protocol=pickle.HIGHEST_PROTOCOL)
                os.replace(tmp, path)
                job = {**job, "full_results": SpilledReport(path)}
            except OSError as exc:
                logger.warning(f"Keeping the report of job {job_id} in memory: {exc}")
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        super().__setitem__(job_id, job)

    def pop(self, job_id, *default):
        try:
            os.remove(_path(job_id))
        except OSError:
            pass
        return super().pop(job_id, *default)


def full_report(job: dict):
    """The job's untruncated report, or None when it has none."""
    report = job.get("full_results")
    return report.load() if isinstance(report, SpilledReport) else report
