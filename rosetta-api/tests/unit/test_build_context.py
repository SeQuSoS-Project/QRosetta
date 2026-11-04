"""The image build context (the repository root, per docker-compose.yml and
scripts/release/image.sh) leaves out npm's node_modules (the nginx and API images copy
rosetta-api/static, and whatever it holds is served as files), host databases and data
directories, environment files, caches and test artefacts (V1-10), and keeps every file the
images copy."""
import os
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
ROOT = _ROOT


def test_node_modules_are_outside_the_build_context():
    patterns = [line.strip() for line in (_ROOT / ".dockerignore").read_text().splitlines()]
    assert "**/node_modules" in patterns


def _patterns():
    rules = []
    for line in (ROOT / ".dockerignore").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        pattern = os.path.normpath(line.lstrip("!").strip("/"))
        regex = ""
        i = 0
        while i < len(pattern):
            if pattern.startswith("**/", i):
                regex += "(?:.*/)?"
                i += 3
            elif pattern.startswith("**", i):
                regex += ".*"
                i += 2
            elif pattern[i] == "*":
                regex += "[^/]*"
                i += 1
            elif pattern[i] == "?":
                regex += "[^/]"
                i += 1
            else:
                regex += re.escape(pattern[i])
                i += 1
        rules.append((re.compile(regex + r"(?:/.*)?$"), negate))
    return rules


def excluded(path: str) -> bool:
    """Whether the build context leaves ``path`` (relative to the root) out, as the
    .dockerignore rules read: the last matching rule wins; a rule for a directory covers
    everything below it."""
    result = False
    for regex, negate in _patterns():
        if regex.match(path):
            result = not negate
    return result


@pytest.mark.parametrize("path", [
    "rosetta-api/data/qa_rosetta.db", "rosetta-api/data/s3_storage_mock/reports/u1/r1.json",
    "rosetta-api/qa_rosetta.db", "runners/qiskit/data/x", "rosetta-api/app.db", "rosetta-api/x.sqlite3",
    "rosetta-api/app.db-journal", ".env", ".env.local", "rosetta-api/.env", "rosetta-api/.env.production",
    "compilers/staq-compiler/prod.env", "rosetta-api/__pycache__/main.cpython-312.pyc",
    "rosetta-api/tests/unit/__pycache__/x.pyc", "rosetta-api/.pytest_cache/v/cache/nodeids",
    "rosetta-api/.coverage", "rosetta-api/.coverage.host.123", "rosetta-api/htmlcov/index.html",
    "rosetta-api/coverage.xml", "rosetta-api/node_modules/x/index.js", "shared/build/lib/x.py",
    "shared/qrosetta_commons.egg-info/PKG-INFO", ".venv/bin/python", "rosetta-api/.venv/bin/python",
    "rosetta-api/.mypy_cache/x", "CLAUDE.md", "rosetta-api/CLAUDE.md", "rosetta-api/export/x.zip",
    "rosetta-api/experiments/run1/bundle.zip", "qrosetta-results/20261104-142938Z-selftest/plan.json",
    "rosetta-api/static/tailwind.config.js",
    "rosetta-api/static/tsconfig.json"])
def test_v1_10_host_files_are_left_out_of_the_build_context(path):
    assert excluded(path), path


def test_v1_10_every_file_the_images_copy_stays_in_the_context():
    for path in ("rosetta-api/main.py", "rosetta-api/requirements.lock", "rosetta-api/static/index.html",
                 "rosetta-api/circuits/selftest/expected.json", "rosetta-api/benchmarks/preparation_peaks.json",
                 "shared/qrosetta_commons/helpers.py", "shared/setup.py", "nginx/nginx.conf",
                 "runners/pytket-qiskit-runner/main.py", "compilers/staq-compiler/main.py"):
        assert (ROOT / path).exists(), path
        assert not excluded(path), path


def test_v1_10_the_api_context_of_this_checkout_holds_none_of_them():
    forbidden = re.compile(r"(^|/)(data|__pycache__|\.pytest_cache|htmlcov|node_modules)(/|$)|\.(db|sqlite3?)$"
                           r"|(^|/)\.env|\.coverage")
    kept = []
    for top in ("rosetta-api", "shared", "runners", "compilers", "nginx"):
        for dirpath, dirnames, filenames in os.walk(ROOT / top):
            rel_dir = Path(dirpath).relative_to(ROOT).as_posix()
            dirnames[:] = [d for d in dirnames if not excluded(f"{rel_dir}/{d}")]
            kept += [f"{rel_dir}/{f}" for f in filenames if not excluded(f"{rel_dir}/{f}")]
    assert kept and not [p for p in kept if forbidden.search(p)]


def test_cli_results_directory_is_not_tracked_by_git():
    """`qrosetta run`/`selftest` write to ./qrosetta-results by default, which is the checkout
    when started there."""
    patterns = [line.strip() for line in (ROOT / ".gitignore").read_text().splitlines()]
    assert "qrosetta-results/" in patterns
