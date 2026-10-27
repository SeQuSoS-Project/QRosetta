"""The `integration` job of ci.yml, read statically: it builds and starts exactly nginx, the API and
the compose services of the runners its tests use, waits for those runners by their container
names, and runs the live-stack test files that exist, with the current checks required; the E2E
test's sign-out step runs when the server lists `logout` or the current checks are required."""

import importlib.util
import inspect
import re
import sys

import pytest
import yaml

from tests.unit._qrosetta_fake import REPO

CI = REPO / ".github" / "workflows" / "ci.yml"
COMPOSE = REPO / "docker-compose.yml"
INTEGRATION = REPO / "tests" / "integration"


@pytest.fixture(scope="module")
def job():
    return yaml.safe_load(CI.read_text())["jobs"]["integration"]


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE.read_text())["services"]


def _test_step(job):
    (step,) = [s for s in job["steps"] if "pytest" in s.get("run", "")]
    return step


def _runner_services(compose, ids):
    return {name: svc for name, svc in compose.items()
            if svc.get("labels", {}).get("org.qrosetta.kind") == "runner"
            and svc["labels"].get("org.qrosetta.id") in ids}


def test_the_job_builds_and_starts_the_runners_its_tests_use(job, compose):
    ids = set(_test_step(job)["env"]["QROSETTA_TEST_RUNNERS"].split(","))
    runners = _runner_services(compose, ids)
    assert len(runners) == len(ids), f"no compose runner service for {ids - set(runners)}"
    assert job["env"]["SERVICES"].split() == ["nginx", "api", *[
        name for name in job["env"]["SERVICES"].split() if name in runners]]
    assert set(job["env"]["SERVICES"].split()) == {"nginx", "api", *runners}
    assert set(job["env"]["RUNNER_HOSTS"].split()) == {svc["container_name"] for svc in runners.values()}


def test_the_test_runners_are_active_runners(job):
    ids = _test_step(job)["env"]["QROSETTA_TEST_RUNNERS"].split(",")
    contract = (INTEGRATION / "test_runner_contract_asymmetric.py").read_text()
    active = re.findall(r'"([^"]+)"', re.search(r"ACTIVE_STATEVECTOR_RUNNERS = \[(.*?)\]", contract, re.S).group(1))
    assert set(ids) <= set(active)


def test_the_job_runs_existing_test_files_and_requires_the_current_checks(job):
    step = _test_step(job)
    files = [word for word in step["run"].split() if word.startswith("tests/integration/")]
    assert files and all((REPO / f).is_file() for f in files)
    assert {"tests/integration/test_e2e_nginx.py", "tests/integration/test_e2e_cli.py",
            "tests/integration/test_runner_contract_asymmetric.py"} <= set(files)
    assert step["env"]["QROSETTA_E2E_REQUIRE_CURRENT"] == "1"
    assert "bypass" not in CI.read_text().split("  integration:", 1)[1].split("\n  actionlint:", 1)[0]


def test_the_job_installs_pinned_test_dependencies():
    lines = [line.strip() for line in (INTEGRATION / "requirements.txt").read_text().splitlines()
             if line.strip() and not line.startswith("#")]
    assert lines and all(re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][\w.]*", line) for line in lines)


@pytest.fixture
def e2e(monkeypatch):
    """tests/integration/test_e2e_nginx.py imported as a module, with live_stack on the path."""
    monkeypatch.syspath_prepend(str(INTEGRATION))
    monkeypatch.delitem(sys.modules, "live_stack", raising=False)
    spec = importlib.util.spec_from_file_location("e2e_nginx_gating", INTEGRATION / "test_e2e_nginx.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(*features):
    return {"server": {"git_sha": "abc1234", "features": {name: 1 for name in features}}}


def test_the_sign_out_check_follows_the_logout_feature(e2e, monkeypatch):
    from services.server_info import FEATURES

    assert e2e.LOGOUT_FEATURE in FEATURES and e2e.CURRENT_FEATURE in FEATURES
    monkeypatch.delenv("QROSETTA_E2E_REQUIRE_CURRENT", raising=False)
    assert e2e.server_state(_config("readiness", "logout"))["logout"] is True
    assert e2e.server_state(_config("readiness"))["logout"] is False
    assert e2e.server_state(_config("readiness"))["current"] is True
    assert e2e.server_state({"server": {}})["logout"] is False
    monkeypatch.setenv("QROSETTA_E2E_REQUIRE_CURRENT", "0")
    assert e2e.server_state(_config())["logout"] is False
    monkeypatch.setenv("QROSETTA_E2E_REQUIRE_CURRENT", "1")
    state = e2e.server_state(_config())
    assert state["logout"] is True and state["current"] is True


def test_sign_out_runs_after_the_share_link_and_before_deletion(e2e):
    tests = sorted((inspect.getsourcelines(f)[1], n) for n, f in vars(e2e).items()
                   if n.startswith("test_") and inspect.isfunction(f))
    names = [n for _, n in tests]
    assert (names.index("test_qft_save_share_revoke") < names.index("test_sign_out_ends_the_token")
            < names.index("test_account_deletion_ends_the_token_and_links"))
    source = inspect.getsource(e2e.test_sign_out_ends_the_token)
    assert 'if not server["logout"]' in source and '"/auth/logout"' in source
