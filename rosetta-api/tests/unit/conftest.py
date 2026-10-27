"""Unit-test setup: job reports spill to a temporary directory, not the server's, and runs are
not refused for the free space left on the disk that holds it."""
import os
import tempfile

import pytest

os.environ.setdefault("QROSETTA_JOB_SPILL_DIR", tempfile.mkdtemp(prefix="qrosetta-test-jobs-"))


@pytest.fixture(autouse=True)
def _no_free_disk_floor(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "JOB_SPILL_MIN_FREE_MIB", 0)
