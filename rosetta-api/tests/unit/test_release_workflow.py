""".github/workflows/release-images.yml, read statically: myQLM and cuQuantum are never built or
pushed, the publish jobs use the trusted environments, only publish jobs get an OIDC token, the
PyPI upload needs published images, and every third-party action is pinned to a commit."""

import os
import re
import subprocess

import pytest
import yaml

from tests.unit._qrosetta_fake import REPO

WORKFLOW = REPO / ".github" / "workflows" / "release-images.yml"
IMAGE_SCRIPT = REPO / "scripts" / "release" / "image.sh"
NEVER_PUBLISHED = ("myqlm", "cuquantum")


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
    assert with_token == {"publish-images", "publish-testpypi", "publish-pypi"}
    for name, job in wf["jobs"].items():
        if not name.startswith("publish"):
            assert job["permissions"] == {"contents": "read"}, name
    assert wf["jobs"]["publish-testpypi"]["permissions"] == {"id-token": "write"}
    assert wf["jobs"]["publish-pypi"]["permissions"] == {"id-token": "write"}


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
    assert test["if"] == "github.event_name == 'workflow_dispatch'"
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


def test_myqlm_and_cuquantum_are_never_built_or_pushed(wf, text):
    code = "\n".join(line for line in text.lower().splitlines() if not line.lstrip().startswith("#"))
    for name in NEVER_PUBLISHED:
        assert name not in code
    assert "docker build" not in code
    assert "--list-images" in _runs(wf["jobs"]["plan"])
    for name in ("images", "publish-images"):
        job = wf["jobs"][name]
        assert job["strategy"]["matrix"] == {"include": "${{ fromJSON(needs.plan.outputs.images) }}"}
        assert "scripts/release/image.sh build" in _runs(job)
    push = _runs(wf["jobs"]["publish-images"])
    assert re.findall(r"docker push (\S+)", push) == ['"$REPOSITORY:$VERSION"']


@pytest.mark.parametrize("sid,dockerfile", [("myqlm", "runners/myqlm-runner/Dockerfile"),
                                            ("cuquantum", "runners/cuquantum-runner/Dockerfile"),
                                            ("qiskit", "runners/cuquantum-runner/Dockerfile")])
@pytest.mark.parametrize("action", ["build", "self-test"])
def test_the_image_script_refuses_myqlm_and_cuquantum(tmp_path, sid, dockerfile, action):
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\necho called > \"$(dirname \"$0\")/called\"\n")
    docker.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}", ID=sid, DOCKERFILE=dockerfile,
               VERSION="1.0.0", IMAGE="x", SELF_TEST="true", LABELS="", GITHUB_SHA="abc",
               GITHUB_SERVER_URL="https://github.com", GITHUB_REPOSITORY="o/r")
    proc = subprocess.run(["bash", str(IMAGE_SCRIPT), action], env=env, capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 1 and "never" in proc.stderr
    assert not (tmp_path / "called").exists()
