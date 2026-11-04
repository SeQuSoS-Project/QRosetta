"""Unit-test setup: each test process (each xdist worker, and the controller) has its own job
spill directory and SQLite database in a temporary directory, not the server's or ./data, with
the schema at head; every test starts with the rate limiter on and its counters empty, and with
the CLI's output settings at their defaults (a `main([..., "--json"])` call leaves --json mode on
for every later test in the process that prints through qrosetta_cli.output directly), and fails
if it leaves the limiter or logging switched off; runs are not refused for the free space left on the disk that
holds the spill directory. X-Forwarded-For is trusted from
any peer (TestClient's peer is "testclient"), so tests choose a client address with it;
test_v5_06_trusted_proxies.py checks the list itself. Below Python 3.11 the files that import the
CLI (which requires 3.11) are not collected; the CLI job runs them on 3.11 and later."""
import logging
import os
import re
import sys
import tempfile

import pytest

_CLI_IMPORT = re.compile(r"^\s*(from|import) qrosetta_cli\b", re.MULTILINE)


def pytest_ignore_collect(collection_path, config):
    if sys.version_info >= (3, 11) or collection_path.suffix != ".py":
        return None
    try:
        return bool(_CLI_IMPORT.search(collection_path.read_text(encoding="utf-8"))) or None
    except OSError:
        return None


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
        security.limiter.enabled = True
    yield
    security = sys.modules.get("services.security")
    if security is not None and not security.limiter.enabled:
        security.limiter.enabled = True
        pytest.fail("the test left the rate limiter switched off for the tests after it; "
                    "switch it off with monkeypatch.setattr(limiter, 'enabled', False)")


@pytest.fixture(autouse=True)
def _fresh_cli_output():
    output = sys.modules.get("qrosetta_cli.output")
    if output is not None:
        output.configure()
    yield


@pytest.fixture(autouse=True)
def _logging_left_on():
    yield
    if logging.root.manager.disable:
        logging.disable(logging.NOTSET)
        pytest.fail("the test left logging.disable() on for the tests after it; "
                    "restore logging.root.manager.disable when it ends")


@pytest.fixture(autouse=True)
def _no_free_disk_floor(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "JOB_SPILL_MIN_FREE_MIB", 0)
