"""One version number: qrosetta_cli.__version__ is the package version (pyproject.toml reads it),
and the API's PLATFORM_VERSION default and the API image's QROSETTA_VERSION default repeat it."""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
PEP440 = re.compile(r"^\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$")


def _one(pattern, path):
    found = re.findall(pattern, (REPO / path).read_text(), re.M)
    assert len(found) == 1, f"{path}: expected one match of {pattern!r}, found {found}"
    return found[0]


def cli_version():
    return _one(r'^__version__ = "([^"]+)"$', "qrosetta_cli/__init__.py")


def test_package_version_comes_from_the_cli_module():
    tomllib = pytest.importorskip("tomllib")
    project = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert "version" in project["project"]["dynamic"] and "version" not in project["project"]
    assert project["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "qrosetta_cli.__version__"}


def test_platform_version_defaults_equal_the_package_version():
    version = cli_version()
    assert PEP440.match(version), version
    config = _one(r'^\s*PLATFORM_VERSION: str = os\.getenv\("QROSETTA_VERSION", "([^"]+)"\)$', "rosetta-api/config.py")
    dockerfile = _one(r"^ARG QROSETTA_VERSION=(\S+)$", "rosetta-api/Dockerfile")
    assert config == version, f"rosetta-api/config.py PLATFORM_VERSION default {config} != {version}"
    assert dockerfile == version, f"rosetta-api/Dockerfile QROSETTA_VERSION default {dockerfile} != {version}"
