"""Unit-test setup: job reports spill to a temporary directory, not the server's, and every
test starts with empty rate-limit counters."""
import os
import sys
import tempfile

import pytest

os.environ.setdefault("QROSETTA_JOB_SPILL_DIR", tempfile.mkdtemp(prefix="qrosetta-test-jobs-"))


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    security = sys.modules.get("services.security")
    if security is not None:
        security.limiter.reset()
    yield
