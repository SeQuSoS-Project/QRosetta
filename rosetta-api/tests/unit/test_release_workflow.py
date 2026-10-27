""".github/workflows/release-images.yml, read statically: myQLM, cuQuantum and BQSKit are never built or
pushed, every built image is scanned before anything is published, the publish jobs use the trusted
environments, only publish jobs get an OIDC token, the PyPI upload needs published images and a
final version (a pre-release tag goes to TestPyPI only), every published image gets an SBOM
attestation and its image id recorded, every image carries the labels qrosetta recognises it by,
every third-party action is pinned to a commit, and the GitHub release of a final version (never
of a pre-release, a dry run or the internal repository) is drafted with its attested files,
checked, and only then published."""

import os
import re
import subprocess

import pytest
import yaml

from tests.unit._qrosetta_fake import REPO

WORKFLOW = REPO / ".github" / "workflows" / "release-images.yml"
IMAGE_SCRIPT = REPO / "scripts" / "release" / "image.sh"
NEVER_PUBLISHED = ("myqlm", "cuquantum", "bqskit")


@pytest.fixture(scope="module")
def text():
    return WORKFLOW.read_text()


@pytest.fixture(scope="module")
def wf(text):
    return yaml.safe_load(text)


def _steps(job):
    return job.get("steps", [])


def _runs(job):
    return "\n".join(step.get("run", "") for step in _steps(job))


def test_triggers_are_version_tags_and_manual_dry_runs(wf):
    on = wf[True]
    assert set(on) == {"push", "workflow_dispatch"}
    assert on["push"] == {"tags": ["v*"]}


def test_only_publish_jobs_get_an_oidc_token(wf):
    assert wf["permissions"] == {"contents": "read"}
    with_token = {name for name, job in wf["jobs"].items() if (job.get("permissions") or {}).get("id-token") == "write"}
    assert with_token == {"publish-images", "publish-testpypi", "publish-pypi", "release-assets"}
    for name, job in wf["jobs"].items():
        if name == "scan-results":
            assert job["permissions"] == {"contents": "read", "security-events": "write", "actions": "read"}
        elif name == "release-assets":
            assert job["permissions"] == {"contents": "read", "id-token": "write", "attestations": "write"}
        elif not name.startswith("publish"):
            assert job["permissions"] == {"contents": "read"}, name
    assert wf["jobs"]["publish-testpypi"]["permissions"] == {"id-token": "write"}
    assert wf["jobs"]["publish-pypi"]["permissions"] == {"id-token": "write"}
    assert wf["jobs"]["publish-release"]["permissions"] == {"contents": "write"}
    writers = {name for name, job in wf["jobs"].items() if (job.get("permissions") or {}).get("contents") == "write"}
    assert writers == {"publish-release"}


def test_packages_write_only_where_images_are_pushed_and_only_when_enabled(wf):
    writers = {name for name, job in wf["jobs"].items() if (job.get("permissions") or {}).get("packages") == "write"}
    assert writers == {"publish-images"}
    condition = wf["jobs"]["publish-images"]["if"]
    assert "vars.QROSETTA_PUBLISH_IMAGES == 'true'" in condition
    assert "github.event_name == 'push'" in condition and "startsWith(github.ref, 'refs/tags/v')" in condition
    pushes = [name for name, job in wf["jobs"].items() if "docker push" in _runs(job) or "cosign sign" in _runs(job)]
    assert pushes == ["publish-images"]


def test_publish_jobs_use_the_trusted_environments(wf):
    test, real = wf["jobs"]["publish-testpypi"], wf["jobs"]["publish-pypi"]
    assert test["environment"]["name"] == "testpypi" and real["environment"]["name"] == "pypi"
    assert "github.event_name == 'workflow_dispatch'" in test["if"]
    uploads = {name: [s for s in _steps(job) if s.get("uses", "").startswith("pypa/gh-action-pypi-publish@")]
               for name, job in wf["jobs"].items()}
    assert {name for name, steps in uploads.items() if steps} == {"publish-testpypi", "publish-pypi"}
    assert uploads["publish-testpypi"][0]["with"] == {"repository-url": "https://test.pypi.org/legacy/"}
    assert "with" not in uploads["publish-pypi"][0]


def test_pypi_needs_a_tag_and_published_images(wf):
    job = wf["jobs"]["publish-pypi"]
    assert "publish-images" in job["needs"] and "wheel" in job["needs"]
    assert "startsWith(github.ref, 'refs/tags/v')" in job["if"]
    assert "needs.publish-images.result == 'success'" in job["if"]
    assert "images_published" in _runs(job)


def test_every_third_party_action_is_pinned_to_a_commit(text):
    uses = re.findall(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$", text, re.M)
    assert uses
    for ref, comment in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}", ref), ref
        assert re.match(r"\s*# v\d+(\.\d+)*$", comment), f"{ref} has no release comment"


def test_wheel_version_is_checked_against_the_tag(wf):
    run = _runs(wf["jobs"]["wheel"])
    assert 'expected="${GITHUB_REF_NAME#v}"' in run
    assert "check_dist.py dist --version" in run and "--require-manifest" in run
    assert 'GITHUB_REF_NAME#v}" != "$base"' in _runs(wf["jobs"]["plan"])


def test_non_distributable_images_are_never_built_or_pushed(wf, text):
    code = "\n".join(line for line in text.lower().splitlines() if not line.lstrip().startswith("#"))
    for name in NEVER_PUBLISHED:
        assert name not in code
    assert not re.search(r"docker build(?!x)", code)
    assert "--list-images" in _runs(wf["jobs"]["plan"])
    for name in ("images", "publish-images"):
        job = wf["jobs"][name]
        assert job["strategy"]["matrix"] == {"include": "${{ fromJSON(needs.plan.outputs.images) }}"}
        assert "scripts/release/image.sh build" in _runs(job)
    push = _runs(wf["jobs"]["publish-images"])
    assert re.findall(r"docker push (\S+)", push) == ['"$REPOSITORY:$VERSION"']


@pytest.mark.parametrize("sid,dockerfile", [("myqlm", "runners/myqlm-runner/Dockerfile"),
                                            ("cuquantum", "runners/cuquantum-runner/Dockerfile"),
                                            ("bqskit", "compilers/bqskit-compiler/Dockerfile"),
                                            ("qiskit", "compilers/bqskit-compiler/Dockerfile"),
                                            ("qiskit", "runners/cuquantum-runner/Dockerfile")])
@pytest.mark.parametrize("action", ["build", "self-test"])
def test_the_image_script_refuses_non_distributable_images(tmp_path, sid, dockerfile, action):
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\necho called > \"$(dirname \"$0\")/called\"\n")
    docker.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}", ID=sid, DOCKERFILE=dockerfile,
               VERSION="1.0.0", IMAGE="x", SELF_TEST="true", LABELS="", GITHUB_SHA="abc",
               GITHUB_SERVER_URL="https://github.com", GITHUB_REPOSITORY="o/r")
    proc = subprocess.run(["bash", str(IMAGE_SCRIPT), action], env=env, capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 1 and "never" in proc.stderr
    assert not (tmp_path / "called").exists()


def test_a_pre_release_tag_goes_to_testpypi_and_never_to_pypi(wf):
    plan = wf["jobs"]["plan"]
    assert plan["outputs"]["prerelease"] == "${{ steps.version.outputs.prerelease }}"
    assert 'check_dist.py --prerelease "$version"' in _runs(plan)
    test, real = wf["jobs"]["publish-testpypi"], wf["jobs"]["publish-pypi"]
    assert "plan" in test["needs"] and "plan" in real["needs"]
    assert ("(github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') && "
            "needs.plan.outputs.prerelease == 'true')") in test["if"]
    assert "needs.wheel.result == 'success'" in test["if"]
    assert "needs.plan.outputs.prerelease == 'false'" in real["if"]
    assert "prerelease == 'true'" not in real["if"]
    final = next(s for s in real["steps"] if s.get("name") == "The wheel is a final version")
    upload = next(i for i, s in enumerate(real["steps"]) if s.get("uses", "").startswith("pypa/gh-action-pypi-publish@"))
    assert real["steps"].index(final) < upload
    assert "never goes to PyPI" in final["run"] and "(a|b|rc)[0-9]+|[.]dev[0-9]+" in final["run"]


@pytest.mark.parametrize("version,expected", [("2.0.0", False), ("2.0.0.post1", False), ("2.0.0rc1", True),
                                              ("2.0.0a2", True), ("2.0.0b1.post1", True), ("2.0.0.dev3", True),
                                              ("2.0.0rc1.dev1", True)])
def test_pre_release_detection_follows_pep_440(version, expected):
    from tests.unit.test_release_dist import cd
    assert cd.is_prerelease(version) is expected
    assert cd.main(["--prerelease", version]) == 0


@pytest.mark.parametrize("version", ["2.0.0-rc1", "v2.0.0", "2.0.0RC1", "2.0", "02.0.0", ""])
def test_a_non_canonical_version_stops_the_plan(version, capsys):
    from tests.unit.test_release_dist import cd
    if version == "2.0":
        assert cd.is_prerelease(version) is False
        return
    assert cd.main(["--prerelease", version]) == 1
    assert "not a canonical PEP 440 version" in capsys.readouterr().err


def test_published_images_get_an_sbom_attestation_and_a_recorded_image_id(wf):
    steps = wf["jobs"]["publish-images"]["steps"]
    uses = [s.get("uses", "").split("@")[0] for s in steps]
    sbom = steps[uses.index("anchore/sbom-action")]
    attest = steps[uses.index("actions/attest-sbom")]
    assert uses.index("anchore/sbom-action") < uses.index("actions/attest-sbom")
    assert sbom["with"]["image"] == "${{ env.REPOSITORY }}@${{ steps.push.outputs.digest }}"
    assert sbom["with"]["format"] == "spdx-json" and re.fullmatch(r"v\d+\.\d+\.\d+", sbom["with"]["syft-version"])
    assert attest["with"]["sbom-path"] == sbom["with"]["output-file"]
    assert attest["with"]["subject-digest"] == "${{ steps.push.outputs.digest }}"
    assert attest["with"]["push-to-registry"] is True
    image_id = next(s for s in steps if s.get("id") == "image-id")
    assert "imagetools inspect --raw" in image_id["run"] and '["config"]["digest"]' in image_id["run"]
    assert '"$config" != "$local_id"' in image_id["run"]
    record = next(s for s in steps if s.get("name") == "Record the digest and image id")
    assert '"image_id"' in record["run"] and record["env"]["IMAGE_ID"] == "${{ steps.image-id.outputs.image_id }}"
    assert "--signer-repository \"$GITHUB_REPOSITORY\"" in _runs(wf["jobs"]["wheel"])


def test_the_image_script_requires_the_ownership_labels_and_adds_the_notices_label(tmp_path):
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$(dirname \"$0\")/args\"\n")
    docker.chmod(0o755)
    base = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}", ID="qiskit",
                DOCKERFILE="runners/pytket-qiskit-runner/Dockerfile", VERSION="1.0.0", IMAGE="x", GITHUB_SHA="abc",
                GITHUB_SERVER_URL="https://github.com", GITHUB_REPOSITORY="o/r")
    for labels in ("", "org.qrosetta.service=pytket_qiskit_runner", "org.qrosetta.image.project=qsimulators",
                   "org.qrosetta.image.project= org.qrosetta.service=x"):
        proc = subprocess.run(["bash", str(IMAGE_SCRIPT), "build"], env=dict(base, LABELS=labels),
                              capture_output=True, text=True, cwd=REPO)
        assert proc.returncode == 1 and "LABELS lacks" in proc.stderr, labels
        assert not (tmp_path / "args").exists()
    labels = "org.qrosetta.image.project=qsimulators org.qrosetta.service=pytket_qiskit_runner"
    proc = subprocess.run(["bash", str(IMAGE_SCRIPT), "build"], env=dict(base, LABELS=labels),
                          capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 0, proc.stderr
    args = (tmp_path / "args").read_text().splitlines()
    for label in labels.split() + ["org.qrosetta.third-party-notices=https://github.com/o/r/blob/abc/"
                                   "THIRD_PARTY_NOTICES.md"]:
        assert args[args.index(label) - 1] == "--label", label


def test_every_release_image_gets_both_ownership_labels():
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_manifest", REPO / "scripts" / "release" / "make_manifest.py")
    mm = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mm)
        records = mm.services()
    except ImportError:
        pytest.skip("make_manifest needs PyYAML and pydantic")
    for image in mm.release_images(records):
        labels = dict(item.split("=", 1) for item in image["labels"].split())
        assert labels == {"org.qrosetta.image.project": "qsimulators",
                          "org.qrosetta.service": image["compose_service"]}


def test_every_image_is_scanned_before_anything_is_published(wf):
    images = wf["jobs"]["images"]
    names = [s.get("name") for s in images["steps"]]
    assert names.index("Build") < names.index("Self-test") < names.index("Scan")
    assert next(s for s in images["steps"] if s.get("name") == "Scan")["run"] == "scripts/release/image.sh scan"
    assert "images" in wf["jobs"]["publish-images"]["needs"]
    assert "needs.images.result == 'success'" in wf["jobs"]["wheel"]["if"]
    upload = next(s for s in images["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["with"]["name"] == "trivy-${{ matrix.id }}" and "!cancelled()" in upload["if"]
    results = wf["jobs"]["scan-results"]
    assert results["strategy"]["matrix"] == {"include": "${{ fromJSON(needs.plan.outputs.images) }}"}
    sarif = next(s for s in results["steps"] if s.get("uses", "").startswith("github/codeql-action/upload-sarif@"))
    assert sarif["with"]["category"] == "trivy-${{ matrix.id }}"


PUBLIC_ONLY = "github.repository == 'SeQuSoS-Project/QRosetta'"
TAG_PUSH = "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')"


def _step(job, prefix):
    return next(s for s in _steps(job) if s.get("uses", "").startswith(prefix) or s.get("name") == prefix)


def test_a_final_tag_needs_a_dated_changelog_section_before_anything_is_built(wf):
    plan = wf["jobs"]["plan"]
    notes = next(s for s in _steps(plan) if s.get("name") == "Release notes")
    assert notes["if"] == "github.event_name == 'push' && steps.version.outputs.prerelease == 'false'"
    assert 'release_assets.py notes --version "$VERSION" --check' in notes["run"]
    assert all("plan" in (job.get("needs") or []) for name, job in wf["jobs"].items() if name != "plan")


def test_no_image_is_pushed_before_the_api_description_is_written(wf):
    job = wf["jobs"]["openapi"]
    assert job["permissions"] == {"contents": "read"} and "if" not in job
    assert "-r rosetta-api/requirements.lock" in _runs(job)
    assert 'release_assets.py openapi --out "openapi/openapi-$VERSION.json"' in _runs(job)
    assert _step(job, "actions/upload-artifact@")["with"]["name"] == "openapi"
    assert "openapi" in wf["jobs"]["publish-images"]["needs"]
    assert "needs.openapi.result == 'success'" in wf["jobs"]["wheel"]["if"]


def test_every_published_image_leaves_its_sbom_and_notice_for_the_release_page(wf):
    job = wf["jobs"]["publish-images"]
    names = {s["with"]["name"] for s in _steps(job) if s.get("uses", "").startswith("actions/upload-artifact@")}
    assert {"sbom-${{ matrix.id }}", "notice-${{ matrix.id }}", "digest-${{ matrix.id }}"} <= names
    assert 'cp sbom.spdx.json "sbom/sbom-$ID.spdx.json"' in _runs(job)
    wheel = wf["jobs"]["wheel"]
    listing = next(s for s in _steps(wheel) if s.get("name") == "Image list")
    assert listing["if"] == "needs.publish-images.result == 'success'"
    assert "release_assets.py images --manifest qrosetta_cli/release/manifest.json" in listing["run"]


def test_release_assets_are_collected_attested_and_verified_in_the_public_repository_only(wf):
    job = wf["jobs"]["release-assets"]
    for clause in (PUBLIC_ONLY, TAG_PUSH, "needs.publish-images.result == 'success'",
                   "(needs.publish-pypi.result == 'success' || needs.publish-testpypi.result == 'success')"):
        assert clause in job["if"], clause
    assert "workflow_dispatch" not in job["if"]
    downloads = [s["with"] for s in _steps(job) if s.get("uses", "").startswith("actions/download-artifact@")]
    assert {d.get("name") or d.get("pattern") for d in downloads} == {"dist", "openapi", "image-list", "sbom-*",
                                                                      "notice-*"}
    assert all(d["path"] == "assets" for d in downloads)
    assert not any(s.get("uses", "").startswith("actions/checkout@") for s in _steps(job)), \
        "the job holding an OIDC token runs no code from the checkout"
    assert "pip install" not in _runs(job)
    attest = _step(job, "actions/attest-build-provenance@")
    assert attest["with"] == {"subject-checksums": "assets/SHA256SUMS"}
    runs = _runs(job)
    assert 'cp "$BUNDLE" "assets/qrosetta-$VERSION.intoto.jsonl"' in runs
    assert "gh attestation verify" in runs and '--bundle "qrosetta-$VERSION.intoto.jsonl"' in runs
    assert "--signer-workflow" in runs
    for name in ("qrosetta-$VERSION-py3-none-any.whl", "qrosetta-$VERSION.tar.gz", "openapi-$VERSION.json",
                 "qrosetta-$VERSION-images.txt", "sbom-*.spdx.json", "NOTICE-*.txt"):
        assert name in runs, name
    assert _step(job, "actions/upload-artifact@")["with"]["name"] == "release-assets"


def test_the_github_release_is_a_draft_until_its_files_are_checked(wf):
    job = wf["jobs"]["publish-release"]
    for clause in (PUBLIC_ONLY, TAG_PUSH, "needs.plan.outputs.prerelease == 'false'",
                   "needs.publish-pypi.result == 'success'", "needs.release-assets.result == 'success'"):
        assert clause in job["if"], clause
    assert "workflow_dispatch" not in job["if"] and "prerelease == 'true'" not in job["if"]
    assert {"plan", "release-assets", "publish-pypi"} <= set(job["needs"])
    names = [s.get("name") for s in _steps(job)]
    order = [names.index(n) for n in ("A final version, and the files are the attested ones", "Release notes",
                                      "Draft", "Check the draft's files", "Publish")]
    assert order == sorted(order)
    final = _step(job, "A final version, and the files are the attested ones")["run"]
    assert 'check_dist.py --prerelease "$VERSION")" != false' in final and "sha256sum -c SHA256SUMS" in final
    draft = _step(job, "Draft")["run"]
    assert "gh release create" in draft and "--draft" in draft and "--verify-tag" in draft
    assert "--notes-file notes.md --generate-notes assets/*" in draft
    assert "already published" in draft
    check = _step(job, "Check the draft's files")["run"]
    assert "gh release download" in check and "sha256sum -c ../assets/SHA256SUMS" in check
    assert "diff <(cd assets && ls) <(cd attached && ls)" in check
    publish = _step(job, "Publish")["run"]
    assert "--draft=false" in publish
    creates = [name for name, j in wf["jobs"].items() if "gh release" in _runs(j)]
    assert creates == ["publish-release"]


def test_release_note_categories_end_with_a_catch_all():
    config = yaml.safe_load((REPO / ".github" / "release.yml").read_text())["changelog"]
    categories = config["categories"]
    assert categories[-1]["labels"] == ["*"]
    assert all(c["labels"] and c["title"] for c in categories)
    assert "skip-changelog" in config["exclude"]["labels"]
