"""scripts/release/check_dist.py: a wheel with files outside qrosetta_cli, another version, a
dependency or no licence files is refused before publishing."""

import importlib.util
import io
import tarfile
import zipfile

import pytest

from tests.unit._qrosetta_fake import REPO

_spec = importlib.util.spec_from_file_location("check_dist", REPO / "scripts" / "release" / "check_dist.py")
cd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cd)

METADATA = ("Metadata-Version: 2.4\nName: qrosetta\nVersion: {v}\nRequires-Python: >=3.11\n"
            "License-Expression: Apache-2.0\n{extra}\n")


def wheel(path, version="1.0.0", extra="", stray=(), licences=("LICENSE", "THIRD_PARTY_NOTICES.md"), manifest=True):
    info = f"qrosetta-{version}.dist-info/"
    with zipfile.ZipFile(path, "w") as zf:
        for module in (REPO / "qrosetta_cli").rglob("*.py"):
            zf.writestr(str(module.relative_to(REPO)), "")
        for schema in (REPO / "qrosetta_cli" / "schemas").glob("*.json"):
            zf.writestr(f"qrosetta_cli/schemas/{schema.name}", "{}")
        if manifest:
            zf.writestr("qrosetta_cli/release/manifest.json", "{}")
        zf.writestr(info + "METADATA", METADATA.format(v=version, extra=extra))
        zf.writestr(info + "entry_points.txt", "[console_scripts]\nqrosetta = qrosetta_cli.cli:main\n")
        for licence in licences:
            zf.writestr(info + "licenses/" + licence, "text")
        for name in stray:
            zf.writestr(name, "")
    return path


def test_a_clean_wheel_passes(tmp_path):
    assert cd.check_wheel(wheel(tmp_path / "w.whl"), "1.0.0", require_manifest=True) == []


@pytest.mark.parametrize("kwargs,expected", [
    ({"stray": ["rosetta-api/main.py"]}, "files outside qrosetta_cli/"),
    ({"stray": ["tests/unit/test_x.py"]}, "files outside qrosetta_cli/"),
    ({"version": "1.0.1"}, "no qrosetta-1.0.0.dist-info/METADATA"),
    ({"extra": "Requires-Dist: requests"}, "dependencies declared"),
    ({"licences": ("LICENSE",)}, "THIRD_PARTY_NOTICES.md is not in"),
    ({"manifest": False}, "no qrosetta_cli/release/manifest.json"),
])
def test_a_wheel_unfit_to_publish_is_refused(tmp_path, kwargs, expected):
    problems = cd.check_wheel(wheel(tmp_path / "w.whl", **kwargs), "1.0.0", require_manifest=True)
    assert any(expected in p for p in problems), problems


def test_an_sdist_with_server_code_is_refused(tmp_path):
    path = tmp_path / "qrosetta-1.0.0.tar.gz"
    with tarfile.open(path, "w:gz") as tf:
        for name in ("qrosetta-1.0.0/pyproject.toml", "qrosetta-1.0.0/qrosetta_cli/cli.py",
                     "qrosetta-1.0.0/runners/qibo-runner/main.py"):
            info = tarfile.TarInfo(name)
            tf.addfile(info, io.BytesIO(b""))
    assert cd.check_sdist(path, "1.0.0") == ["unexpected file in the sdist: qrosetta-1.0.0/runners/qibo-runner/main.py"]
