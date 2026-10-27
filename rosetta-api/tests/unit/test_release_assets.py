"""scripts/release/release_assets.py: the OpenAPI document comes from the checked-out API and names
its version, the image list names every published image by digest with its cosign and
`gh attestation` commands, and the release notes are the version's dated CHANGELOG.md section."""

import importlib.util
import json
import subprocess
import sys

import pytest

from tests.unit._qrosetta_fake import REPO

SCRIPT = REPO / "scripts" / "release" / "release_assets.py"
spec = importlib.util.spec_from_file_location("release_assets", SCRIPT)
ra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ra)

D1, D2, D3, D4 = (f"sha256:{c * 64}" for c in "abcd")
IDENTITY = "https://github.com/SeQuSoS-Project/QRosetta/.github/workflows/release-images.yml@refs/tags/v2.0.0"
ISSUER = "https://token.actions.githubusercontent.com"


def manifest(**over):
    m = {
        "schema": "qrosetta.release-manifest@1", "platform_version": "2.0.0", "git_sha": "0" * 40,
        "images_published": True, "signing": {"identity": IDENTITY, "issuer": ISSUER},
        "services": {
            "api": {"distributable": True, "profiles": [], "ref": f"ghcr.io/o/qrosetta-rosetta-api@{D1}",
                    "image_id": D2},
            "qiskit": {"distributable": True, "profiles": ["minimal", "cpu"],
                       "ref": f"ghcr.io/o/qrosetta-pytket-qiskit-runner@{D3}", "image_id": D4},
            "withheld": {"distributable": False, "ref": None, "image_id": None,
                         "not_distributable_reason": "its licence"},
        },
    }
    m.update(over)
    return m


def test_the_openapi_document_is_written_from_the_checkout(tmp_path):
    out = tmp_path / "openapi.json"
    proc = subprocess.run([sys.executable, str(SCRIPT), "openapi", "--out", str(out)], capture_output=True,
                          text=True, cwd=tmp_path, timeout=300)
    assert proc.returncode == 0, proc.stderr
    doc = json.loads(out.read_text())
    assert doc["info"]["version"] == ra.cli_version()
    assert {"/config", "/runners", "/compare", "/jobs/{job_id}/report"} <= set(doc["paths"])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["openapi.json"]
    assert not (REPO / "rosetta-api" / "data" / "openapi.db").exists()


def test_the_openapi_document_must_name_the_expected_version(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT), "openapi", "--out", str(tmp_path / "o.json"),
                           "--version", "0.0.1"], capture_output=True, text=True, cwd=tmp_path, timeout=300)
    assert proc.returncode == 1 and "not 0.0.1" in proc.stderr
    assert not (tmp_path / "o.json").exists()


def test_the_image_list_names_every_published_image_with_its_verify_commands():
    text = ra.images_text(manifest())
    for ref in (f"ghcr.io/o/qrosetta-rosetta-api@{D1}", f"ghcr.io/o/qrosetta-pytket-qiskit-runner@{D3}"):
        assert (f"cosign verify --certificate-identity '{IDENTITY}' --certificate-oidc-issuer '{ISSUER}' {ref}"
                in text)
        assert f"gh attestation verify oci://{ref} -R SeQuSoS-Project/QRosetta\n" in text
        assert (f"gh attestation verify oci://{ref} -R SeQuSoS-Project/QRosetta --predicate-type "
                "https://spdx.dev/Document/v2.3") in text
    assert f"image id {D2}" in text and f"image id {D4}" in text
    assert "withheld: its licence" in text
    assert "minimal,cpu" in text and text.count("# ") == 2


@pytest.mark.parametrize("change,message", [
    ({"images_published": False}, "no published images"),
    ({"signing": None}, "no signing workflow"),
    ({"platform_version": "2.0.1"}, "names v2.0.0, the manifest 2.0.1"),
])
def test_the_image_list_refuses_a_manifest_without_signed_published_images(change, message):
    with pytest.raises(ra.AssetError, match=message):
        ra.images_text(manifest(**change))


def test_the_image_list_refuses_a_reference_by_tag():
    m = manifest()
    m["services"]["api"]["ref"] = "ghcr.io/o/qrosetta-rosetta-api:2.0.0"
    with pytest.raises(ra.AssetError, match="not a reference by digest"):
        ra.images_text(m)


CHANGELOG = """# Changelog

## [Unreleased]

### Added
- next

## [2.0.0] - 2026-11-02

### Added
- the thing

## [1.0.0] - 2026-06-17

- first

[Unreleased]: https://example.org/compare/v2.0.0...HEAD
[2.0.0]: https://example.org/compare/v1.0.0...v2.0.0
"""


def test_release_notes_are_the_dated_section_of_the_version():
    assert ra.changelog_section("2.0.0", CHANGELOG) == "### Added\n- the thing"
    assert ra.changelog_section("1.0.0", CHANGELOG) == "- first"
    notes = ra.notes_text("2.0.0", CHANGELOG, "o/r")
    assert notes.startswith("### Added\n- the thing\n\n## Files")
    assert "--bundle qrosetta-2.0.0.intoto.jsonl -R o/r" in notes


@pytest.mark.parametrize("version,message", [("2.0.1", "no section"), ("Unreleased", "no date")])
def test_release_notes_refuse_a_missing_or_undated_section(version, message):
    with pytest.raises(ra.AssetError, match=message):
        ra.changelog_section(version, CHANGELOG)


def test_notes_check_reads_the_real_changelog(capsys):
    assert ra.main(["notes", "--version", "1.0.0", "--check"]) == 0
    assert capsys.readouterr().out == ""
    assert ra.main(["notes", "--version", "0.0.1", "--check"]) == 1
    assert "no section [0.0.1]" in capsys.readouterr().err
