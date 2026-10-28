"""End-of-life guard (scripts/release/eol.py, release/eol.json): every Dockerfile's final stage fails
from 12 months before its Python or base OS reaches end of life, judged on today's date. Images in
EXPECTED_FAIL are strict expected failures: one that becomes compliant fails until it is removed from
the list. Also checks the Dockerfile parser and the table itself. Stdlib and pytest only."""

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("eol_guard", REPO / "scripts" / "release" / "eol.py")
eol = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = eol
_spec.loader.exec_module(eol)

TABLE = eol.load_table()
TODAY = dt.date.today()
IMAGES = eol.load_images(REPO, TABLE)

_PY310 = "Python 3.10 reached end of life on 2026-10-01; requalify on 3.12 or 3.13 (Wave B3)"
_PY311 = "Python 3.11 reaches end of life in 2027-10; requalify on 3.12 or 3.13 (Wave B3)"
EXPECTED_FAIL = {
    "compilers/bqskit-compiler/Dockerfile": _PY310,
    "runners/myqlm-runner/Dockerfile": _PY310,
    "runners/pennylane-default-runner/Dockerfile": _PY310,
    "runners/pytket-cirq-runner/Dockerfile": _PY310,
    "runners/pytket-projectq-runner/Dockerfile": _PY310 + "; disabled runner",
    "runners/qrisp-runner/Dockerfile": _PY310,
    "runners/quimb-runner/Dockerfile": _PY311,
}


def _image_params():
    for image in IMAGES:
        marks = []
        if image.path in EXPECTED_FAIL:
            marks.append(pytest.mark.xfail(strict=True, reason=EXPECTED_FAIL[image.path]))
        yield pytest.param(image, id=image.path, marks=marks)


@pytest.mark.parametrize("image", list(_image_params()))
def test_image_python_and_base_os_are_outside_the_end_of_life_window(image):
    problems = eol.violations(image.final, TABLE, TODAY)
    assert not problems, f"{image.path} ({image.final.ref}): " + "; ".join(problems)


def test_expected_failures_name_existing_dockerfiles():
    paths = {image.path for image in IMAGES}
    assert set(EXPECTED_FAIL) <= paths, sorted(set(EXPECTED_FAIL) - paths)


def test_every_service_dockerfile_is_judged():
    paths = {image.path for image in IMAGES}
    expected = {p.relative_to(REPO).as_posix() for d in ("runners", "compilers")
                for p in (REPO / d).glob("*/Dockerfile")}
    expected |= {"rosetta-api/Dockerfile", "nginx/Dockerfile", "infra/Dockerfile.frontend"}
    assert expected <= paths, sorted(expected - paths)


def test_every_base_image_has_a_known_python_and_os():
    for image in IMAGES:
        for base in [image.final] + [b for _, b in image.build_stages]:
            assert base.os_family is not None, f"{image.path}: {base.ref} has no OS in release/eol.json"
            if base.repository == "python":
                assert base.python in TABLE["python"]["branches"], (image.path, base.python)
            known = TABLE["base_images"].get(base.digest or "")
            if known and known.get("python") and base.python:
                assert known["python"].startswith(base.python + "."), (image.path, base.ref, known["python"])


def test_every_lock_is_read_and_tracked_series_are_in_the_table():
    for d in ("runners", "compilers"):
        for lock in (REPO / d).glob("*/requirements.lock"):
            assert eol.read_lock(lock), lock
    for image in IMAGES:
        for note in eol.sdk_notes(image, TABLE, TODAY):
            assert "not in release/eol.json" not in note, f"{image.path}: {note}"


def test_table_entries_name_their_source_and_parse():
    for section in [TABLE["python"]] + list(TABLE["os"].values()) + list(TABLE["packages"].values()):
        assert section["source"].startswith("https://") and section["fetched"]
    for entry in TABLE["python"]["branches"].values():
        eol.parse_date(entry["eol"])
    for family in TABLE["os"].values():
        for entry in family["releases"].values():
            eol.parse_date(entry["eol"])
    for digest, entry in TABLE["base_images"].items():
        assert digest.startswith("sha256:") and len(digest) == 71, digest
        assert entry["os"]["release"] in TABLE["os"][entry["os"]["family"]]["releases"], digest
        assert entry["verified"]


def test_month_only_dates_are_the_first_day_and_the_window_is_twelve_months():
    assert eol.parse_date("2027-10") == dt.date(2027, 10, 1)
    assert eol.minus_months(dt.date(2027, 10, 1), 12) == dt.date(2026, 10, 1)
    assert eol.minus_months(dt.date(2028, 2, 29), 12) == dt.date(2027, 2, 28)
    assert eol.minus_months(dt.date(2027, 1, 31), 13) == dt.date(2025, 12, 31)


def _base(text, table=TABLE):
    stages = eol.parse_dockerfile(text)
    return eol.classify(stages[-1], table)


def test_window_boundary():
    base = _base("FROM python:3.12-slim-trixie\n")
    assert eol.violations(base, TABLE, dt.date(2027, 9, 30)) == []
    assert "Python 3.12" in eol.violations(base, TABLE, dt.date(2027, 10, 1))[0]
    assert "reached end of life" in eol.violations(base, TABLE, dt.date(2028, 10, 1))[0]


def test_multi_stage_build_judges_the_final_stage():
    text = (
        "# syntax=docker/dockerfile:1\n"
        "FROM --platform=linux/amd64 python:3.10-slim-bookworm AS build\n"
        "RUN make \\\n    && make install\n"
        "FROM python:3.13-slim-trixie\n"
        "COPY --from=build /out /out\n"
    )
    stages = eol.parse_dockerfile(text)
    assert [s.name for s in stages] == ["build", None]
    final = eol.classify(stages[-1], TABLE)
    assert (final.python, final.os_family, final.os_release) == ("3.13", "debian", "13")
    build = eol.classify(stages[0], TABLE)
    assert (build.python, build.os_release) == ("3.10", "12")


def test_stage_built_from_an_earlier_stage_inherits_its_base():
    text = "FROM python:3.11-slim-trixie AS base\nRUN true\nFROM base AS final\nRUN true\n"
    final = eol.classify(eol.parse_dockerfile(text)[-1], TABLE)
    assert (final.repository, final.python) == ("python", "3.11")


def test_arg_defaulted_base_image_and_digest():
    digest = "sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634"
    text = f'ARG PY=3.11\nARG BASE="python:${{PY}}-slim@{digest}"\nFROM $BASE\nARG LATER=x\n'
    base = _base(text)
    assert (base.repository, base.tag, base.digest) == ("python", "3.11-slim", digest)
    assert (base.os_family, base.os_release, base.os_basis) == ("debian", "13", "release/eol.json base_images (digest)")
    assert eol.split_ref("docker.io/library/nginx:alpine@sha256:ab") == ("nginx", "alpine", "sha256:ab")
    assert eol.split_ref("localhost:5000/team/img") == ("team/img", None, None)
    assert _base("ARG T\nFROM python:${T:-3.12}-slim-bookworm\n").python == "3.12"


def test_python_installed_on_a_non_python_base():
    text = ("FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04\n"
            "RUN apt-get update && apt-get install -y --no-install-recommends python3.11 python3.11-venv\n")
    base = _base(text)
    assert (base.python, base.python_basis) == ("3.11", "installed by the Dockerfile")
    assert base.os_family is None
    assert any("unknown" in v for v in eol.violations(base, TABLE, dt.date(2026, 1, 1)))


def test_image_without_python_is_judged_by_its_os():
    base = _base("FROM nginx:alpine@sha256:8b1e78743a03dbb2c95171cc58639fef29abc8816598e27fb910ed2e621e589a\n")
    assert (base.python, base.os_family, base.os_release) == (None, "alpine", "3.23")
    assert eol.violations(base, TABLE, dt.date(2026, 10, 31)) == []
    assert "alpine 3.23" in eol.violations(base, TABLE, dt.date(2026, 11, 1))[0]


def test_unknown_digest_and_unlisted_python_cannot_pass():
    base = _base("FROM python:3.9-slim@sha256:" + "0" * 64 + "\n")
    problems = eol.violations(base, TABLE, dt.date(2020, 1, 1))
    assert any("base OS" in p and "unknown" in p for p in problems)
    base = _base("FROM python:3.99-slim-trixie\n")
    assert any("Python 3.99: not in release/eol.json" in p for p in eol.violations(base, TABLE, dt.date(2020, 1, 1)))
