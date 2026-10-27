"""The `integration` job of ci.yml, read statically: it builds and starts exactly nginx, the API and
the compose services of the runners its tests use, waits for those runners by their container
names, and runs the live-stack test files that exist, with the current checks required."""

import re

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
