"""scripts/lint/baseline.py: shellcheck and hadolint findings above the baseline fail, findings at or
below it pass, and the committed baselines parse."""
import importlib.util
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("lint_baseline", _REPO / "scripts" / "lint" / "baseline.py")
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)


def _shellcheck(*rows):
    return json.dumps({"comments": [{"file": f, "line": n, "code": c, "level": "warning", "message": "m"}
                                    for f, n, c in rows]})


def _hadolint(*rows):
    return json.dumps([{"file": f, "line": n, "code": c, "level": "warning", "message": "m"} for f, n, c in rows])


def test_shellcheck_codes_get_the_sc_prefix():
    rows = baseline.findings("shellcheck", _shellcheck(("a.sh", 3, 2086)))
    assert rows == [("a.sh", "SC2086", 3, "m")]


def test_a_finding_above_the_baseline_fails_and_one_at_it_passes():
    accepted = baseline.read_baseline("# comment\na.sh SC2086 1\n")
    one = baseline.findings("shellcheck", _shellcheck(("a.sh", 3, 2086)))
    two = baseline.findings("shellcheck", _shellcheck(("a.sh", 3, 2086), ("a.sh", 9, 2086)))
    assert baseline.compare(one, accepted) == ([], [])
    new, _ = baseline.compare(two, accepted)
    assert [r[2] for r in new] == [3, 9]


def test_a_new_file_or_code_fails():
    accepted = baseline.read_baseline("Dockerfile DL3008 1\n")
    rows = baseline.findings("hadolint", _hadolint(("Dockerfile", 2, "DL3008"), ("Dockerfile", 5, "DL3042"),
                                                   ("other/Dockerfile", 1, "DL3008")))
    new, _ = baseline.compare(rows, accepted)
    assert {(r[0], r[1]) for r in new} == {("Dockerfile", "DL3042"), ("other/Dockerfile", "DL3008")}


def test_fewer_findings_pass_and_are_reported():
    accepted = baseline.read_baseline("a.sh SC2046 2\nb.sh SC2034 1\n")
    rows = baseline.findings("shellcheck", _shellcheck(("a.sh", 1, 2046)))
    assert baseline.compare(rows, accepted) == ([], [("a.sh", "SC2046"), ("b.sh", "SC2034")])


def test_written_baseline_reads_back_to_the_same_counts():
    rows = baseline.findings("hadolint", _hadolint(("D", 1, "DL3008"), ("D", 4, "DL3008"), ("E", 2, "DL3066")))
    assert baseline.read_baseline(baseline.format_baseline("hadolint", rows)) == {("D", "DL3008"): 2,
                                                                                  ("E", "DL3066"): 1}


def test_pre_commit_ruff_is_the_ci_ruff():
    pins = dict(line.split("==") for line in (_REPO / "scripts" / "lint" / "requirements.txt").read_text().splitlines()
                if "==" in line and not line.startswith("#"))
    config = (_REPO / ".pre-commit-config.yaml").read_text()
    assert f"# frozen: v{pins['ruff']}" in config


@pytest.mark.parametrize("name", ["shellcheck.txt", "hadolint.txt"])
def test_committed_baselines_name_existing_files(name):
    accepted = baseline.read_baseline((_REPO / "scripts" / "lint" / name).read_text())
    assert accepted
    for path, _ in accepted:
        assert (_REPO / path).is_file(), f"{name} lists {path}, which does not exist"
