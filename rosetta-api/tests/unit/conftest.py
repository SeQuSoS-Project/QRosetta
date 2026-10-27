"""Unit-test setup: each test process (each xdist worker, and the controller) has its own job
spill directory and SQLite database in a temporary directory, not the server's or ./data, with
the schema at head; every test starts with empty rate-limit counters, and runs are not refused
for the free space left on the disk that holds the spill directory. X-Forwarded-For is trusted from
any peer (TestClient's peer is "testclient"), so tests choose a client address with it;
test_v5_06_trusted_proxies.py checks the list itself."""
import os
import sys
import tempfile

import pytest


def _own_per_process(name: str, make) -> None:
    """Set ``name`` unless the caller set it. xdist workers inherit the controller's environment,
    so a value this conftest set in another process (recorded under ``_QROSETTA_TEST_<name>``)
    is replaced, not kept: every worker gets its own."""
    marker = f"_QROSETTA_TEST_{name}"
    if name in os.environ and os.environ.get(marker) != os.environ[name]:
        return
    os.environ[name] = os.environ[marker] = make()


os.environ["QROSETTA_TRUSTED_PROXIES"] = "*"
_own_per_process("QROSETTA_JOB_SPILL_DIR", lambda: tempfile.mkdtemp(prefix="qrosetta-test-jobs-"))
_own_per_process("DATABASE_URL", lambda: "sqlite:///" + os.path.join(
    tempfile.mkdtemp(prefix="qrosetta-test-db-"), "qa_rosetta.db"))


@pytest.fixture(scope="session", autouse=True)
def _database_at_head():
    from db.database import engine
    from db.migrate import upgrade_database
    upgrade_database(engine)
    yield


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    security = sys.modules.get("services.security")
    if security is not None:
        security.limiter.reset()
    yield


@pytest.fixture(autouse=True)
def _no_free_disk_floor(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "JOB_SPILL_MIN_FREE_MIB", 0)
