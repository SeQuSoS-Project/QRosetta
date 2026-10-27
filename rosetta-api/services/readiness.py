"""The checks behind GET /ready: the database answers ``SELECT 1`` and the job spill directory
takes a new file. Each check runs on this module's own two threads with a time limit, so a
database that never answers cannot occupy the event loop or the default executor; a check
still running from an earlier request is awaited again instead of being started twice, and a
result less than ``REUSE_SEC`` old is served again."""

import asyncio
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from db import database
from qrosetta_commons.helpers import get_logger
from services import job_store

logger = get_logger("rosetta-readiness")

CHECK_TIMEOUT_SEC = 2.0
REUSE_SEC = 1.0

REASONS = {
    "database": "the database does not answer",
    "job_storage": "the job storage directory does not accept new files",
}


def _database() -> None:
    with database.engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _job_storage() -> None:
    """Open an unnamed file in the spill directory and close it: O_TMPFILE where the file
    system has it (no directory entry is ever made), else a file removed as it is opened, the
    same call ``job_store`` uses to build exports."""
    with tempfile.TemporaryFile(dir=job_store.SPILL_DIR):
        pass


CHECKS = {"database": _database, "job_storage": _job_storage}

_EXECUTOR = ThreadPoolExecutor(max_workers=len(CHECKS), thread_name_prefix="readiness")
_in_flight: dict = {}
_last: dict = {"at": None, "checks": None}


async def _run(name: str) -> str:
    """'ok', 'failed' or 'timeout' for one check."""
    fut = _in_flight.get(name)
    if fut is None or fut.done():
        fut = _EXECUTOR.submit(CHECKS[name])
        _in_flight[name] = fut
    waited = asyncio.wrap_future(fut)
    waited.add_done_callback(lambda f: f.cancelled() or f.exception())
    done, _ = await asyncio.wait({waited}, timeout=CHECK_TIMEOUT_SEC)
    if not done:
        logger.warning(f"Readiness check {name} did not finish within {CHECK_TIMEOUT_SEC:g} s")
        return "timeout"
    exc = waited.exception()
    if exc is not None:
        logger.warning(f"Readiness check {name} failed: {type(exc).__name__}: {exc}")
        return "failed"
    return "ok"


async def check() -> dict:
    """{check name: 'ok' | 'failed' | 'timeout'}."""
    now = time.monotonic()
    if _last["at"] is not None and now - _last["at"] < REUSE_SEC:
        return dict(_last["checks"])
    names = list(CHECKS)
    results = await asyncio.gather(*(_run(name) for name in names))
    checks = dict(zip(names, results))
    _last.update(at=time.monotonic(), checks=checks)
    return dict(checks)


def reset() -> None:
    """Forget the last result (tests)."""
    _last.update(at=None, checks=None)
