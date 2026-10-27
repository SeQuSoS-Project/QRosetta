"""V1-07: `qrosetta show circuits` reads a saved crate within member-count and size caps and
names a crate it cannot read instead of failing with an internal error."""
import json
import time
import zipfile

import pytest

from tests.unit.test_qrosetta_views import _playlist_crate

from qrosetta_cli.client import circuits  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];\n'


def _refused(path):
    with pytest.raises(CliError) as err:
        circuits.crate_texts(str(path))
    assert err.value.code == Exit.INCOMPATIBLE and err.value.reason == "crate_unreadable"
    return err.value.message


def _zeros(zf, name, n_bytes):
    info = zipfile.ZipInfo(name)
    info.compress_type = zipfile.ZIP_DEFLATED
    with zf.open(info, "w", force_zip64=True) as fh:
        block = b"\0" * (1 << 20)
        for _ in range(n_bytes >> 20):
            fh.write(block)


def test_v1_07_a_compressed_metadata_bomb_is_refused_before_it_is_inflated(tmp_path):
    path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        _zeros(zf, "top/ro-crate-metadata.json", circuits.MAX_CRATE_METADATA_BYTES + (1 << 20))
    assert path.stat().st_size < 2 << 20
    started = time.monotonic()
    assert "larger than" in _refused(path)
    assert time.monotonic() - started < 1


def test_v1_07_circuit_texts_over_the_total_cap_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(circuits, "MAX_CRATE_TEXT_BYTES", 2 << 20)
    path = tmp_path / "texts.zip"
    parts = [f"circuits/c{i}.qasm" for i in range(3)]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("top/ro-crate-metadata.json", json.dumps({"@graph": [{"@id": "./", "hasPart": [{"@id": p} for p in parts]}]}))
        for p in parts:
            _zeros(zf, f"top/{p}", 1 << 20)
    assert "circuit files hold more than" in _refused(path)


def test_v1_07_too_many_members_are_refused_from_the_end_record(tmp_path, monkeypatch):
    monkeypatch.setattr(circuits, "MAX_CRATE_MEMBERS", 50)
    path = tmp_path / "many.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for i in range(60):
            zf.writestr(f"top/f{i}", "")
    monkeypatch.setattr(zipfile, "ZipFile", lambda *a, **k: pytest.fail("the file list was read"))
    assert "declares more than" in _refused(path)


def test_v1_07_missing_metadata_and_non_zip_files_are_named(tmp_path):
    path = tmp_path / "nometa.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("top/circuit.qasm", QASM)
    assert "no ro-crate-metadata.json" in _refused(path)
    other = tmp_path / "not.zip"
    other.write_bytes(b"not a zip file at all")
    assert "not a ZIP file" in _refused(other)
    broken = tmp_path / "meta.zip"
    with zipfile.ZipFile(broken, "w") as zf:
        zf.writestr("top/ro-crate-metadata.json", "{not json")
    assert "JSONDecodeError" in _refused(broken)


def test_v1_07_a_normal_crate_still_reads(tmp_path):
    path = tmp_path / "c.zip"
    _playlist_crate(path)
    assert [c["task_name"] for c in circuits.crate_texts(str(path))["circuits"]] == ["bell", "ghz"]
