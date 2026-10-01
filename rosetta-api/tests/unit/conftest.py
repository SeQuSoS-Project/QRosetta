"""Unit-test setup: job reports spill to a temporary directory, not the server's."""
import os
import tempfile

os.environ.setdefault("QROSETTA_JOB_SPILL_DIR", tempfile.mkdtemp(prefix="qrosetta-test-jobs-"))
