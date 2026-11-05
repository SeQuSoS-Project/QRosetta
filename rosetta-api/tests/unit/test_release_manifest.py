"""scripts/release/make_manifest.py: the release's services come from docker-compose.yml and
config.py's registries; myQLM, cuQuantum and BQSKit are never distributable and never get a digest; the
compose file installed mode generates from the manifest differs from the repository's only in
`build` (removed) and `image` (by digest)."""

import importlib.util
import json
import re

import pytest
import yaml

from config import settings
from tests.unit._qrosetta_fake import REPO

from qrosetta_cli import manifest as mf  # noqa: E402
from qrosetta_cli.stack import installed  # noqa: E402

_spec = importlib.util.spec_from_file_location("make_manifest", REPO / "scripts" / "release" / "make_manifest.py")
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)

NEVER_PUBLISHED = {"myqlm", "cuquantum", "bqskit"}


def _digest(i):
    return "sha256:" + f"{i:064x}"


@pytest.fixture(scope="module")
def records():
    return mm.services()


def _all_digests(records):
    return {r["id"]: _digest(i) for i, r in enumerate(records) if r["distributable"]}


def test_services_come_from_compose_and_the_enabled_registry(records):
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text())["services"]
    enabled = {sid for reg in (settings.get_runner_services(), settings.get_compiler_services())
               for sid, entry in reg.items() if entry.get("enabled", True)}
    assert {r["id"] for r in records} == enabled | {"api", "nginx"}
    for r in records:
        labels = compose[r["compose_service"]]["labels"]
        assert (labels["org.qrosetta.id"], labels["org.qrosetta.kind"]) == (r["id"], r["kind"])
        assert r["infra_host"] == compose[r["compose_service"]]["container_name"]


def test_non_distributable_images_are_never_built(records):
    assert {r["id"] for r in records if not r["distributable"]} == NEVER_PUBLISHED == set(mm.NOT_DISTRIBUTABLE)
    built = mm.release_images(records)
    assert not {i["id"] for i in built} & NEVER_PUBLISHED
    assert not any(name in i["dockerfile"] for name in ("myqlm", "cuquantum", "bqskit") for i in built)
    assert len(built) == len(records) - len(NEVER_PUBLISHED)


@pytest.mark.parametrize("sid", sorted(NEVER_PUBLISHED))
def test_a_digest_for_a_non_distributable_image_is_refused(records, sid):
    digests = dict(_all_digests(records), **{sid: _digest(999)})
    with pytest.raises(mm.ManifestError, match=f"refusing to emit a digest for {sid}"):
        mm.build_manifest("1.0.0", "abc", digests=digests, records=records)


@pytest.mark.parametrize("change,message", [
    (lambda d: d.pop("qiskit"), "no digest for qiskit"),
    (lambda d: d.update(qiskit="sha256:abc"), "is not a sha256 digest"),
    (lambda d: d.update(nosuch=_digest(5)), "not a service of this release"),
])
def test_digests_must_cover_every_distributable_image_exactly(records, change, message):
    digests = _all_digests(records)
    change(digests)
    with pytest.raises(mm.ManifestError, match=message):
        mm.build_manifest("1.0.0", "abc", digests=digests, records=records)


def test_a_manifest_without_digests_names_no_published_image(records):
    manifest = mm.build_manifest("1.0.0", "abc", records=records)
    assert manifest["images_published"] is False and not mf.published_refs(manifest)
    assert not mf.images_published(manifest)


def test_a_published_manifest_names_every_distributable_image_by_digest(records):
    digests = _all_digests(records)
    manifest = mm.build_manifest("1.0.0", "abc", "ghcr.io/sequsos-project", digests, records)
    assert manifest["schema"] == mf.SCHEMA and manifest["platform_version"] == "1.0.0"
    assert mf.images_published(manifest)
    for sid, entry in manifest["services"].items():
        if sid in NEVER_PUBLISHED:
            assert entry["ref"] is None and entry["repository"] is None and entry["not_distributable_reason"]
        else:
            assert entry["ref"] == f"ghcr.io/sequsos-project/qrosetta-{entry['infra_host']}@{digests[sid]}"
            assert mf.DIGEST_REF.match(entry["ref"])
    assert manifest["services"]["cuquantum"]["requires_gpu"] is True


def test_generated_compose_equals_the_repository_compose_but_for_build_and_image(records):
    repo = yaml.safe_load((REPO / "docker-compose.yml").read_text())
    manifest = mm.build_manifest("1.0.0", "abc", digests=_all_digests(records), records=records)
    doc = installed.compose_document(json.loads(json.dumps(manifest)))
    assert doc["name"] == repo["name"] == "${QROSETTA_PROJECT:-qsimulators}"
    for key in ("networks", "volumes"):
        assert doc[key] == repo[key]
    assert doc.get("secrets") == repo.get("secrets")
    assert doc["networks"]["isolated_net"]["internal"] is True
    published = {r["compose_service"] for r in records if r["distributable"]}
    assert set(doc["services"]) == published
    for name, svc in doc["services"].items():
        expected = {k: v for k, v in repo["services"][name].items() if k != "build"}
        assert {k: v for k, v in svc.items() if k != "image"} == expected
        assert mf.DIGEST_REF.match(svc["image"])
        assert svc["labels"]["org.qrosetta.project"] == "${QROSETTA_PROJECT:-qsimulators}"
        assert "ports" not in svc or name == "nginx"
        for volume in svc.get("volumes", []):
            assert not str(volume).startswith(("/", ".", "~")), f"{name} has a bind mount {volume}"


def test_installed_compose_keeps_the_api_job_storage_budget(records):
    manifest = mm.build_manifest("1.0.0", "abc", digests=_all_digests(records), records=records)
    doc = installed.compose_document(json.loads(json.dumps(manifest)))
    env = doc["services"]["api"]["environment"]
    assert "QROSETTA_JOB_SPILL_MAX_MIB=${QROSETTA_JOB_SPILL_MAX_MIB:-4096}" in env
    assert "QROSETTA_JOB_TTL_SEC=${QROSETTA_JOB_TTL_SEC:-86400}" in env


def test_sdk_versions_come_from_each_image_lock_file(records):
    by_id = {r["id"]: r for r in records}
    lock = (REPO / "runners" / "pytket-qiskit-runner" / "requirements.lock").read_text()
    qiskit = re.search(r"^qiskit==([^\s\\]+)", lock, re.M).group(1)
    assert by_id["qiskit"]["sdk_versions"]["qiskit"] == qiskit
    assert set(by_id["qiskit"]["sdk_versions"]) == {"pytket", "pytket-qiskit", "qiskit", "qiskit-aer"}
    assert by_id["api"]["sdk_versions"] == {}


def test_locked_versions_read_a_hash_pinned_lock(tmp_path):
    lock = tmp_path / "requirements.lock"
    lock.write_text("# header\nqiskit==1.2.4 \\\n    --hash=sha256:" + "0" * 64 + " \\\n    --hash=sha256:" + "1" * 64
                    + "\n    # via -r requirements.in\nPyJWT==2.15.1 ; python_version >= '3.9'\nnumpy==1.26.4\n")
    assert mm.locked_versions(lock) == {"qiskit": "1.2.4", "pyjwt": "2.15.1", "numpy": "1.26.4"}


def test_image_labels_resolve_the_default_project(records):
    for r in records:
        assert r["image_labels"] == {"org.qrosetta.image.project": "qsimulators",
                                     "org.qrosetta.service": r["compose_service"]}


def test_main_writes_the_manifest_and_refuses_another_version(tmp_path, capsys):
    out = tmp_path / "manifest.json"
    assert mm.main(["--git-sha", "abc", "--out", str(out)]) == 0
    assert mf.load(str(out))["git_sha"] == "abc"
    assert mm.main(["--git-sha", "abc", "--version", "0.0.1", "--out", str(out)]) == 1
    assert "differs from qrosetta_cli.__version__" in capsys.readouterr().err
    digests = tmp_path / "digests"
    digests.mkdir()
    (digests / "myqlm.json").write_text(json.dumps({"myqlm": _digest(1)}))
    assert mm.main(["--git-sha", "abc", "--digests-dir", str(digests), "--out", str(out)]) == 1
    assert "refusing to emit a digest for myqlm" in capsys.readouterr().err
    assert mm.main(["--list-images"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert not {i["id"] for i in listed} & NEVER_PUBLISHED


def test_image_ids_and_the_signer_are_recorded_for_published_images(records, tmp_path):
    digests = _all_digests(records)
    ids = {sid: _digest(1000 + i) for i, sid in enumerate(digests)}
    manifest = mm.build_manifest("1.0.0", "abc", digests=digests, records=records, image_ids=ids,
                                 signer_repository="SeQuSoS-Project/QRosetta")
    for sid, entry in manifest["services"].items():
        assert entry["image_id"] == (ids[sid] if sid not in NEVER_PUBLISHED else None)
        if sid not in NEVER_PUBLISHED:
            assert mf.release_ids(manifest, sid) == {ids[sid], digests[sid]}
    assert manifest["signing"] == {
        "issuer": "https://token.actions.githubusercontent.com",
        "identity": "https://github.com/SeQuSoS-Project/QRosetta/.github/workflows/release-images.yml@refs/tags/v1.0.0"}
    assert mf.signer(manifest) == (manifest["signing"]["identity"], manifest["signing"]["issuer"])
    assert "signing" not in mm.build_manifest("1.0.0", "abc", records=records, signer_repository="o/r")
    with pytest.raises(mm.ManifestError, match="not a sha256 digest"):
        mm.build_manifest("1.0.0", "abc", digests=digests, records=records, image_ids={"qiskit": "abc"})
    with pytest.raises(mm.ManifestError, match="which has no digest"):
        mm.build_manifest("1.0.0", "abc", digests=digests, records=records, image_ids={"myqlm": _digest(1)})
    with pytest.raises(mm.ManifestError, match="is not OWNER/REPOSITORY"):
        mm.build_manifest("1.0.0", "abc", digests=digests, records=records, signer_repository="QRosetta")
    pushed = tmp_path / "digests"
    pushed.mkdir()
    (pushed / "qiskit.json").write_text(json.dumps({"qiskit": {"digest": _digest(7), "image_id": _digest(8)}}))
    (pushed / "api.json").write_text(json.dumps({"api": _digest(9)}))
    assert mm.read_pushed(str(pushed)) == ({"qiskit": _digest(7), "api": _digest(9)}, {"qiskit": _digest(8)})
