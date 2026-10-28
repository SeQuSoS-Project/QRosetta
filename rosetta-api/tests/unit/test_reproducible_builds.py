"""Reproducible image builds: every Debian stage of every Dockerfile points apt at snapshot.debian.org
through ARG DEBIAN_SNAPSHOT, whose default equals release/debian-snapshot.conf, before any apt-get; every
pip install is hash-checked (--require-hashes) or installs a local path without the index or
dependencies. Dockerfiles in EXPECTED_FAIL are strict expected failures awaiting requalification.
Stdlib and pytest only."""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("eol_guard", REPO / "scripts" / "release" / "eol.py")
eol = sys.modules.get(_spec.name) or importlib.util.module_from_spec(_spec)
if _spec.name not in sys.modules:
    sys.modules[_spec.name] = eol
    _spec.loader.exec_module(eol)

SNAPSHOT_FILE = REPO / "release" / "debian-snapshot.conf"
TABLE = eol.load_table()

_B3 = "base image and lock not yet requalified (Wave B3)"
_NGINX = "Alpine: no repository pinning rule yet (Wave B4, nginx)"
REQUALIFIED = {
    "runners/pytket-qiskit-runner/Dockerfile",
    "runners/pytket-quest-runner/Dockerfile",
    "runners/pytket-qulacs-runner/Dockerfile",
    "runners/qsim-cirq-runner/Dockerfile",
}
EXPECTED_FAIL = {
    **{p.relative_to(REPO).as_posix(): _B3
       for d in ("runners", "compilers") for p in sorted((REPO / d).glob("*/Dockerfile"))
       if p.relative_to(REPO).as_posix() not in REQUALIFIED},
    "nginx/Dockerfile": _NGINX,
    "infra/Dockerfile.frontend": _NGINX,
}

_PIP = re.compile(r"(?:^|\s)(?:python3?\s+-m\s+)?pip3?\s+install\b(.*)")
_SNAPSHOT_REF = r"snapshot\.debian\.org/archive/{archive}/\$\{{?DEBIAN_SNAPSHOT\}}?"


def snapshot_default():
    values = dict(line.split("=", 1) for line in SNAPSHOT_FILE.read_text().splitlines()
                  if line.strip() and not line.startswith("#"))
    return values["DEBIAN_SNAPSHOT"].strip()


def stages(text):
    """[(stage, [(keyword, rest)])] with the global ARG defaults under the key None."""
    global_args, found = {}, []
    for line in eol._instructions(text):
        keyword, _, rest = line.partition(" ")
        keyword, rest = keyword.upper(), rest.strip()
        if keyword == "FROM":
            found.append([rest, []])
        elif found:
            found[-1][1].append((keyword, rest))
        elif keyword == "ARG":
            name, default = eol._arg_value(rest)
            global_args[name] = default
    return global_args, found


def pip_problems(run_text):
    problems = []
    for command in re.split(r"&&|\|\||;|\||\n", run_text):
        match = _PIP.search(command)
        if not match:
            continue
        args = match.group(1).split()
        if "--require-hashes" in args:
            continue
        if {"--no-index", "--no-deps"} <= set(args):
            continue
        problems.append(f"pip install without --require-hashes: {command.strip()}")
    return problems


def problems_of(path, expected_snapshot):
    global_args, parsed = stages(path.read_text())
    ordered = eol.parse_dockerfile(path.read_text())
    problems = []
    for (from_rest, instructions), stage in zip(parsed, ordered):
        run_text = "\n".join(rest for keyword, rest in instructions if keyword == "RUN")
        problems += pip_problems(run_text)
        if stage.parent is not None:
            continue
        family = eol.classify(stage, TABLE).os_family
        if family != "debian":
            problems.append(f"{from_rest}: no repository pinning rule for OS {family!r}")
            continue
        default = None
        for keyword, rest in instructions:
            if keyword == "ARG":
                name, value = eol._arg_value(rest)
                if name == "DEBIAN_SNAPSHOT":
                    default = value if "=" in rest else global_args.get(name)
        if default != expected_snapshot:
            problems.append(f"{from_rest}: ARG DEBIAN_SNAPSHOT default {default!r}, "
                            f"release/debian-snapshot.conf has {expected_snapshot!r}")
        runs = [rest for keyword, rest in instructions if keyword == "RUN"]
        source = next((i for i, rest in enumerate(runs)
                       if re.search(_SNAPSHOT_REF.format(archive="debian"), rest)
                       and re.search(_SNAPSHOT_REF.format(archive="debian-security"), rest)), None)
        if source is None:
            problems.append(f"{from_rest}: no RUN points apt at snapshot.debian.org/archive/debian and "
                            "debian-security with ${DEBIAN_SNAPSHOT}")
        elif any("apt-get" in rest or re.search(r"\bapt\s", rest) for rest in runs[:source]):
            problems.append(f"{from_rest}: apt runs before the snapshot source is set")
    return problems


def _dockerfiles():
    for path in eol.find_dockerfiles(REPO):
        rel = path.relative_to(REPO).as_posix()
        marks = [pytest.mark.xfail(strict=True, reason=EXPECTED_FAIL[rel])] if rel in EXPECTED_FAIL else []
        yield pytest.param(path, id=rel, marks=marks)


def test_snapshot_timestamp_is_one_valid_value():
    assert re.fullmatch(r"\d{8}T\d{6}Z", snapshot_default())


@pytest.mark.parametrize("path", list(_dockerfiles()))
def test_dockerfile_uses_the_apt_snapshot_and_hash_checked_pip(path):
    problems = problems_of(path, snapshot_default())
    assert not problems, f"{path.relative_to(REPO)}: " + "; ".join(problems)


def test_expected_failures_name_existing_dockerfiles():
    paths = {p.relative_to(REPO).as_posix() for p in eol.find_dockerfiles(REPO)}
    assert set(EXPECTED_FAIL) <= paths, sorted(set(EXPECTED_FAIL) - paths)


def test_build_scripts_pass_the_snapshot_from_the_one_file():
    for script in ("scripts/safe_boot.sh", "scripts/release/image.sh"):
        text = (REPO / script).read_text()
        assert "release/debian-snapshot.conf" in text, script
        assert "DEBIAN_SNAPSHOT=" in text, script


def test_api_lock_is_fully_hash_pinned():
    lock = (REPO / "rosetta-api" / "requirements.lock").read_text()
    entries = re.split(r"\n(?=[A-Za-z0-9])", "\n".join(
        line for line in lock.splitlines() if line.strip() and not line.lstrip().startswith("#")))
    assert entries
    for entry in entries:
        assert re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*==\S+ \\$", entry.splitlines()[0]), entry.splitlines()[0]
        assert re.search(r"--hash=sha256:[0-9a-f]{64}", entry), entry.splitlines()[0]


_DEBIAN_OK = """FROM python:3.12-slim@sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f
ARG DEBIAN_SNAPSHOT=20260101T000000Z
RUN sed -i -e "s|x|https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \\
      -e "s|y|https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" f
RUN apt-get update && apt-get install -y --no-install-recommends gcc
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
RUN pip install --no-cache-dir --no-deps --no-build-isolation --no-index /tmp/shared-src && rm -rf /tmp/shared-src
"""


def _write(tmp_path, text):
    path = tmp_path / "Dockerfile"
    path.write_text(text)
    return path


@pytest.mark.parametrize("text, expected", [
    (_DEBIAN_OK, []),
    (_DEBIAN_OK.replace("--require-hashes ", ""), ["pip install without --require-hashes"]),
    (_DEBIAN_OK.replace("--no-index ", ""), ["pip install without --require-hashes"]),
    (_DEBIAN_OK + "RUN python -m pip install --upgrade pip\n", ["pip install without --require-hashes"]),
    (_DEBIAN_OK.replace("20260101T000000Z", "20250101T000000Z"), ["ARG DEBIAN_SNAPSHOT default"]),
    (_DEBIAN_OK.replace("debian-security/", "debian-sec/"), ["no RUN points apt at snapshot"]),
    ("\n".join(_DEBIAN_OK.splitlines()[:2] + [_DEBIAN_OK.splitlines()[4]] + _DEBIAN_OK.splitlines()[2:4]) + "\n",
     ["apt runs before the snapshot source is set"]),
    ("ARG DEBIAN_SNAPSHOT=20260101T000000Z\n" + _DEBIAN_OK.replace(
        "ARG DEBIAN_SNAPSHOT=20260101T000000Z", "ARG DEBIAN_SNAPSHOT"), []),
    ("FROM nginx:alpine@sha256:8b1e78743a03dbb2c95171cc58639fef29abc8816598e27fb910ed2e621e589a\n",
     ["no repository pinning rule for OS 'alpine'"]),
], ids=["compliant", "no-hashes", "local-with-index", "pip-upgrade", "other-snapshot", "no-security-archive",
        "apt-before-snapshot", "global-arg-default", "alpine"])
def test_rules(tmp_path, text, expected):
    problems = problems_of(_write(tmp_path, text), "20260101T000000Z")
    assert len(problems) == len(expected), problems
    for problem, fragment in zip(problems, expected):
        assert fragment in problem


def test_a_stage_built_on_an_earlier_stage_inherits_its_sources(tmp_path):
    text = _DEBIAN_OK.replace("\nARG", " AS base\nARG", 1) + "FROM base\nRUN apt-get install -y curl\n"
    assert problems_of(_write(tmp_path, text), "20260101T000000Z") == []
