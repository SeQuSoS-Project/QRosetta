"""The workflows and .github/dependabot.yml, read statically. Every action in every workflow is
pinned to a commit, one commit per action; checkouts keep no token; no workflow takes a
pull_request_target or workflow_run trigger or expands an expression inside a script; ci.yml and
the supply-chain workflows hold least-privilege tokens; the CLI matrix equals the package's
classifiers. The rebuild check builds no non-distributable image and pushes nothing; Dependabot
groups its updates and labels runner and compiler updates sealed-image. Also the Trivy scan and
the OCI labels of scripts/release/image.sh, oci_labels.py and safe_boot.sh."""

import json
import os
import re
import subprocess
import sys

import pytest
import yaml

from tests.unit._qrosetta_fake import REPO

WORKFLOWS = REPO / ".github" / "workflows"
OWNED = ("codeql.yml", "scorecard.yml", "rebuild-check.yml")
ALL = tuple(sorted(p.name for p in WORKFLOWS.glob("*.y*ml")))
IMAGE_SCRIPT = REPO / "scripts" / "release" / "image.sh"
SAFE_BOOT = REPO / "scripts" / "safe_boot.sh"
NEVER_PUBLISHED = ("myqlm", "cuquantum", "bqskit")
USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$", re.M)
PINNED = re.compile(r"[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}")

sys.path.insert(0, str(REPO / "scripts" / "release"))
import eol  # noqa: E402
import oci_labels  # noqa: E402


def _load(name):
    data = yaml.safe_load((WORKFLOWS / name).read_text())
    data["on"] = data.pop(True)
    return data


def _uses(text):
    return USES.findall(text)


@pytest.mark.parametrize("name", ALL)
def test_actions_are_pinned_to_commits_with_their_release(name):
    found = _uses((WORKFLOWS / name).read_text())
    assert found
    for ref, comment in found:
        assert PINNED.fullmatch(ref), ref
        assert re.match(r"\s*# v\d+(\.\d+)*$", comment), f"{ref} has no release comment"


def test_one_commit_per_action_across_the_workflows():
    assert {"ci.yml", "release-images.yml", *OWNED} <= set(ALL)
    refs = [ref for name in ALL for ref, _ in _uses((WORKFLOWS / name).read_text())]
    commits = {}
    for ref in refs:
        path, sha = ref.split("@")
        commits.setdefault("/".join(path.split("/")[:2]), set()).add(sha)
    for action, shas in commits.items():
        assert len(shas) == 1, (action, shas)
    assert all(PINNED.fullmatch(ref) for ref in refs)


@pytest.mark.parametrize("name", OWNED)
def test_tokens_are_read_only_unless_a_job_needs_more(name):
    wf = _load(name)
    assert wf["permissions"] == {"contents": "read"}
    for job_name, job in wf["jobs"].items():
        perms = job["permissions"]
        assert perms.get("contents") == "read", job_name
        writes = {k for k, v in perms.items() if v == "write"}
        if name == "scorecard.yml":
            assert writes == {"security-events", "id-token"}
        elif job_name in ("analyze", "scan-results"):
            assert writes == {"security-events"}, job_name
        else:
            assert writes == set(), job_name
        assert "packages" not in perms and "attestations" not in perms


def test_ci_tokens_are_read_only():
    wf = _load("ci.yml")
    assert wf["permissions"] == {"contents": "read"}
    for job_name, job in wf["jobs"].items():
        assert job["permissions"] == {"contents": "read"}, job_name


@pytest.mark.parametrize("name", ALL)
def test_no_untrusted_triggers_and_no_expressions_inside_scripts(name):
    wf = _load(name)
    triggers = wf["on"] if isinstance(wf["on"], (dict, list)) else [wf["on"]]
    assert not {"pull_request_target", "workflow_run"} & set(triggers)
    for job_name, job in wf["jobs"].items():
        for step in job.get("steps", []):
            assert "${{" not in step.get("run", ""), (job_name, step.get("name"))


@pytest.mark.parametrize("name", ALL)
def test_checkouts_keep_no_credentials(name):
    for job in _load(name)["jobs"].values():
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False


def test_code_scanning_runs_only_in_the_public_repository():
    public = "github.repository == 'SeQuSoS-Project/QRosetta'"
    assert _load("codeql.yml")["jobs"]["analyze"]["if"] == public
    assert _load("scorecard.yml")["jobs"]["analysis"]["if"] == public
    assert public in _load("rebuild-check.yml")["jobs"]["scan-results"]["if"]
    assert public in _load("release-images.yml")["jobs"]["scan-results"]["if"]


def test_codeql_covers_python_javascript_and_the_workflows():
    wf = _load("codeql.yml")
    assert wf["on"]["push"] == {"branches": ["main"]} and wf["on"]["pull_request"] == {"branches": ["main"]}
    assert len(wf["on"]["schedule"]) == 1
    job = wf["jobs"]["analyze"]
    assert job["strategy"]["matrix"]["language"] == ["python", "javascript-typescript", "actions"]
    init = next(s for s in job["steps"] if s.get("uses", "").startswith("github/codeql-action/init@"))
    assert init["with"] == {"languages": "${{ matrix.language }}", "build-mode": "none"}
    assert any(s.get("uses", "").startswith("github/codeql-action/analyze@") for s in job["steps"])


def test_scorecard_meets_the_publishing_restrictions():
    wf = _load("scorecard.yml")
    assert "env" not in wf and "defaults" not in wf
    assert set(wf["on"]) == {"push", "schedule", "branch_protection_rule"}
    assert list(wf["jobs"]) == ["analysis"]
    job = wf["jobs"]["analysis"]
    assert "env" not in job and "defaults" not in job and "container" not in job and "services" not in job
    allowed = ("actions/checkout@", "actions/upload-artifact@", "github/codeql-action/upload-sarif@",
               "ossf/scorecard-action@")
    for step in job["steps"]:
        assert "run" not in step and step["uses"].startswith(allowed), step
    scorecard = next(s for s in job["steps"] if s["uses"].startswith("ossf/scorecard-action@"))
    assert scorecard["with"]["publish_results"] is True and scorecard["with"]["results_format"] == "sarif"
    upload = next(s for s in job["steps"] if s["uses"].startswith("github/codeql-action/upload-sarif@"))
    assert upload["with"]["sarif_file"] == scorecard["with"]["results_file"]


def test_the_rebuild_check_builds_release_images_from_scratch_and_pushes_nothing():
    text = (WORKFLOWS / "rebuild-check.yml").read_text()
    wf = _load("rebuild-check.yml")
    minute, hour, day, month, weekday = wf["on"]["schedule"][0]["cron"].split()
    assert day.isdigit() and month == "*" and weekday == "*"
    assert "workflow_dispatch" in wf["on"]
    code = "\n".join(line for line in text.lower().splitlines() if not line.lstrip().startswith("#"))
    for name in NEVER_PUBLISHED:
        assert name not in code
    for word in ("docker push", "docker login", "cosign", "pypi", "ghcr.io"):
        assert word not in code
    assert "make_manifest.py --list-images" in "\n".join(s.get("run", "") for s in wf["jobs"]["plan"]["steps"])
    images = wf["jobs"]["images"]
    assert images["strategy"]["matrix"] == {"include": "${{ fromJSON(needs.plan.outputs.images) }}"}
    assert images["env"]["NO_CACHE"] == "1" and images["env"]["IMAGE_SOURCE"] == "built_locally"
    runs = [s.get("run") for s in images["steps"] if "run" in s]
    assert runs == ["scripts/release/image.sh build", "scripts/release/image.sh self-test",
                    "scripts/release/image.sh scan"]


RUNNER_OS = {"ubuntu-latest": "POSIX :: Linux", "macos-latest": "MacOS", "windows-latest": "Microsoft :: Windows"}


def test_the_cli_matrix_equals_the_package_classifiers():
    pyproject = (REPO / "pyproject.toml").read_text()
    pythons = re.findall(r'"Programming Language :: Python :: (3\.\d+)"', pyproject)
    systems = re.findall(r'"Operating System :: ([^"]+)"', pyproject)
    matrix = _load("ci.yml")["jobs"]["cli"]["strategy"]["matrix"]
    assert matrix["python-version"] == pythons
    assert re.search(r'^requires-python = ">=([\d.]+)"$', pyproject, re.M).group(1) == pythons[0]
    include = matrix.get("include", [])
    assert {row["python-version"] for row in include} <= set(pythons)
    assert sorted({RUNNER_OS[os_] for os_ in matrix["os"] + [row["os"] for row in include]}) == sorted(systems)


def test_licence_txt_is_a_copy_of_license_and_ci_checks_it():
    assert (REPO / "Licence.txt").read_bytes() == (REPO / "LICENSE").read_bytes()
    runs = [s.get("run") for s in _load("ci.yml")["jobs"]["static-checks"]["steps"]]
    assert "cmp LICENSE Licence.txt" in runs
    files = re.search(r"^license-files = \[(.*)\]$", (REPO / "pyproject.toml").read_text(), re.M).group(1)
    assert files == '"LICENSE", "THIRD_PARTY_NOTICES.md"'


def test_actionlint_lints_every_workflow_with_checked_binaries():
    job = _load("ci.yml")["jobs"]["actionlint"]
    assert job["permissions"] == {"contents": "read"}
    install = next(s for s in job["steps"] if s.get("name") == "Install actionlint and ShellCheck")
    assert re.fullmatch(r"[0-9a-f]{64}", install["env"]["ACTIONLINT_SHA256"])
    assert re.fullmatch(r"[0-9a-f]{64}", install["env"]["SHELLCHECK_SHA256"])
    assert install["run"].count("sha256sum -c -") == 2
    lint = next(s for s in job["steps"] if s.get("name") == "Lint the workflows")
    assert lint["run"].startswith('"$RUNNER_TEMP/actionlint"') and '-shellcheck "$RUNNER_TEMP/shellcheck"' in lint["run"]


def test_zizmor_audits_the_workflows_from_a_hash_pinned_wheel():
    steps = {s.get("name"): s for s in _load("ci.yml")["jobs"]["actionlint"]["steps"]}
    install = steps["Install zizmor"]["run"]
    assert "--require-hashes" in install and "--no-deps" in install and "--only-binary=:all:" in install
    requirements = install.split(" -r ")[1].strip()
    pins = [line for line in (REPO / requirements).read_text().splitlines() if line and not line.startswith("#")]
    assert len(pins) == 1 and re.fullmatch(r"zizmor==[\d.]+ --hash=sha256:[0-9a-f]{64}", pins[0])
    audit = steps["Audit the workflows with zizmor"]
    assert audit["run"].startswith("zizmor ") and "--offline" not in audit["run"]
    assert audit["env"] == {"GH_TOKEN": "${{ github.token }}"}


def test_semgrep_runs_in_the_lint_job_from_hash_pinned_wheels():
    steps = {s.get("name"): s for s in _load("ci.yml")["jobs"]["lint"]["steps"]}
    install = steps["Install Semgrep"]["run"]
    assert "--require-hashes" in install and "--no-deps" in install and "--only-binary=:all:" in install
    assert '-m venv "$RUNNER_TEMP/semgrep"' in install
    requirements = REPO / re.search(r"-r (\S+)", install).group(1)
    assert requirements == REPO / "scripts" / "lint" / "semgrep-requirements.txt"
    text = "\n".join(line for line in requirements.read_text().splitlines() if not line.startswith("#"))
    pins = {}
    for line in filter(None, text.replace(" \\\n", " ").splitlines()):
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==(\S+)((?: +--hash=sha256:[0-9a-f]{64})+)", line.strip())
        assert match, line
        pins[match.group(1).lower()] = match.group(2)
    assert len(pins) > 1
    baseline = (REPO / "scripts" / "lint" / "semgrep.txt").read_text()
    assert f"Semgrep {pins['semgrep']}," in baseline
    run = steps["Semgrep against its baseline"]
    assert run["run"] == "scripts/lint/check.sh semgrep"
    assert run["env"] == {"SEMGREP": "${{ runner.temp }}/semgrep/bin/semgrep"}


def _dependabot():
    return yaml.safe_load((REPO / ".github" / "dependabot.yml").read_text())


def _dirs(update):
    return update.get("directories") or [update["directory"]]


def test_dependabot_covers_every_manifest_in_a_few_grouped_weekly_updates():
    cfg = _dependabot()
    assert cfg["version"] == 2
    for update in cfg["updates"]:
        assert update["schedule"]["interval"] == "weekly"
        assert update["groups"] and all(g["patterns"] == ["*"] for g in update["groups"].values())
    by_eco = {}
    for update in cfg["updates"]:
        by_eco.setdefault(update["package-ecosystem"], []).extend(_dirs(update))
    assert by_eco["github-actions"] == ["/"]
    assert {"/", "/rosetta-api", "/rosetta-api/tests"} <= set(by_eco["pip"])
    docker_dirs = set(by_eco["docker"])
    for dockerfile in eol.find_dockerfiles():
        rel = dockerfile.parent.relative_to(REPO).as_posix()
        parent = "/" + rel.rsplit("/", 1)[0] + "/*" if "/" in rel else None
        assert "/" + rel in docker_dirs or parent in docker_dirs, rel


def test_runner_and_compiler_updates_are_labelled_sealed_and_open_no_pip_version_updates():
    for update in _dependabot()["updates"]:
        dirs = _dirs(update)
        sealed = any(d.startswith(("/runners", "/compilers")) for d in dirs)
        assert all(d.startswith(("/runners", "/compilers")) for d in dirs) or not sealed, dirs
        assert ("sealed-image" in update.get("labels", [])) is sealed, dirs
        if sealed and update["package-ecosystem"] == "pip":
            assert update["open-pull-requests-limit"] == 0
            assert all(g.get("applies-to") == "security-updates" for g in update["groups"].values())


def test_dependabot_keeps_python_minor_versions_and_boto_below_1_36():
    for update in _dependabot()["updates"]:
        if update["package-ecosystem"] == "docker":
            assert {"dependency-name": "python",
                    "update-types": ["version-update:semver-major", "version-update:semver-minor"]} in update["ignore"]
        if update["package-ecosystem"] == "pip" and "/rosetta-api" in _dirs(update):
            ignored = {i["dependency-name"]: i["versions"] for i in update["ignore"]}
            assert ignored == {"boto3": [">=1.36.0"], "botocore": [">=1.36.0"]}


def _image_script(tmp_path, action, docker_body, **env):
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\n" + docker_body)
    docker.chmod(0o755)
    base = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}", ID="qiskit",
                DOCKERFILE="runners/pytket-qiskit-runner/Dockerfile", VERSION="1.0.0", IMAGE="x:1",
                GITHUB_SHA="0123abc", GITHUB_SERVER_URL="https://github.com", GITHUB_REPOSITORY="o/r",
                LABELS="org.qrosetta.image.project=qsimulators org.qrosetta.service=pytket_qiskit_runner",
                SCAN_DIR=str(tmp_path / "out"), TRIVY_CACHE=str(tmp_path / "cache"))
    base.update(env)
    return subprocess.run(["bash", str(IMAGE_SCRIPT), action], env=base, capture_output=True, text=True, cwd=REPO)


RECORD = 'n=$(ls "$(dirname "$0")"/call.* 2>/dev/null | wc -l)\nprintf \'%s\\n\' "$@" > "$(dirname "$0")/call.$n"\n'


def test_the_build_carries_the_oci_labels(tmp_path):
    proc = _image_script(tmp_path, "build", RECORD)
    assert proc.returncode == 0, proc.stderr
    args = (tmp_path / "call.0").read_text().splitlines()
    labels = dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "--label")
    assert labels["org.opencontainers.image.revision"] == "0123abc"
    assert labels["org.opencontainers.image.version"] == "1.0.0"
    assert labels["org.opencontainers.image.source"] == "https://github.com/o/r"
    assert labels["org.opencontainers.image.licenses"] == "Apache-2.0"
    assert labels["org.opencontainers.image.title"] == "Quantum Rosetta Qiskit runner"
    assert "THIRD_PARTY_NOTICES.md" in labels["org.opencontainers.image.description"]
    assert labels["org.qrosetta.image.project"] == "qsimulators"
    assert labels["org.qrosetta.service"] == "pytket_qiskit_runner"
    assert "QROSETTA_IMAGE_SOURCE=release" in args and "--no-cache" not in args


def test_a_rebuild_check_build_uses_no_cache_and_its_own_source(tmp_path):
    proc = _image_script(tmp_path, "build", RECORD, NO_CACHE="1", IMAGE_SOURCE="built_locally")
    assert proc.returncode == 0, proc.stderr
    args = (tmp_path / "call.0").read_text().splitlines()
    assert "--no-cache" in args and "--pull" in args and "QROSETTA_IMAGE_SOURCE=built_locally" in args
    proc = _image_script(tmp_path, "build", RECORD, IMAGE_SOURCE="pushed")
    assert proc.returncode == 1 and "IMAGE_SOURCE" in proc.stderr


def test_the_scan_writes_sarif_then_checks_for_fixable_criticals(tmp_path):
    proc = _image_script(tmp_path, "scan", RECORD)
    assert proc.returncode == 0, proc.stderr
    first = (tmp_path / "call.0").read_text().splitlines()
    second = (tmp_path / "call.1").read_text().splitlines()
    trivy = re.search(r'^TRIVY_IMAGE="([^"]+)"$', IMAGE_SCRIPT.read_text(), re.M).group(1)
    assert re.fullmatch(r"ghcr\.io/aquasecurity/trivy:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}", trivy)
    assert not trivy.split("@")[0].endswith(":0.69.4")
    for call in (first, second):
        assert call[:2] == ["run", "--rm"] and trivy in call and call[-1] == "x:1"
        assert "--ignore-unfixed" in call and "/src/.trivyignore" in call
        assert call[call.index("--scanners") + 1] == "vuln"
    assert first[first.index("--severity") + 1] == "HIGH,CRITICAL"
    assert first[first.index("--format") + 1] == "sarif" and "/out/trivy.sarif" in first
    assert second[second.index("--severity") + 1] == "CRITICAL"
    assert second[second.index("--exit-code") + 1] == "1" and "--skip-db-update" in second
    assert (tmp_path / "out").is_dir() and (REPO / ".trivyignore").is_file()


def test_the_scan_fails_when_trivy_finds_a_fixable_critical(tmp_path):
    proc = _image_script(tmp_path, "scan", 'case "$*" in *--exit-code*) exit 1;; esac\n')
    assert proc.returncode == 1


@pytest.mark.parametrize("sid", NEVER_PUBLISHED)
def test_the_scan_refuses_non_distributable_images(tmp_path, sid):
    proc = _image_script(tmp_path, "scan", RECORD, ID=sid)
    assert proc.returncode == 1 and "never" in proc.stderr
    assert not list(tmp_path.glob("call.*"))


def test_every_dockerfile_has_an_oci_title_and_description():
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text())
    built = {os.path.normpath(svc["build"]["dockerfile"]) for svc in compose["services"].values()}
    assert built and built <= set(oci_labels.SERVICES)
    for path in oci_labels.SERVICES:
        assert (REPO / path).is_file(), path
    for title, description in oci_labels.SERVICES.values():
        assert title.startswith("Quantum Rosetta ")
        assert len(f"{description} {oci_labels.THIRD_PARTY}") <= 512


def test_oci_label_defaults_follow_the_repository():
    config = (REPO / "rosetta-api" / "config.py").read_text()
    assert f'"{oci_labels.PUBLIC_REPOSITORY}"' in config
    assert oci_labels.platform_version() == re.search(
        r'^__version__ = "([^"]+)"$', (REPO / "qrosetta_cli" / "__init__.py").read_text(), re.M).group(1)
    found = oci_labels.labels(REPO / "nginx" / "Dockerfile", "abc-dirty")
    assert found["org.opencontainers.image.revision"] == "abc-dirty"
    assert set(found) == {f"org.opencontainers.image.{k}" for k in
                          ("title", "description", "licenses", "source", "revision", "version")}
    assert oci_labels.main([str(REPO / "LICENSE"), "--revision", "x"]) == 1
    assert oci_labels.main([str(REPO / "nginx" / "Dockerfile"), "--revision", " "]) == 1


def test_safe_boot_builds_carry_the_oci_and_ownership_labels(tmp_path):
    compose = {"name": "qsimulators", "services": {"api": {"image": "qsimulators-api", "build": {
        "context": str(REPO), "dockerfile": "./rosetta-api/Dockerfile", "args": {"QROSETTA_GIT_SHA": "from-compose"},
        "labels": {"org.qrosetta.image.project": "qsimulators", "org.qrosetta.service": "api"}}}}}
    (tmp_path / "compose.json").write_text(json.dumps(compose))
    engine = tmp_path / "engine"
    engine.write_text('#!/bin/sh\nd="$(dirname "$0")"\n'
                      'if [ "$1" = compose ]; then cat "$d/compose.json"; exit 0; fi\n'
                      'if [ "$1" = build ]; then printf \'%s\\n\' "$@" > "$d/build.args"; exit 0; fi\n'
                      'exit 1\n')
    engine.chmod(0o755)
    env = dict(os.environ, QR_ENGINE=str(engine), QR_BUILD_ONLY="1", QR_BUILD_SERVICES="api",
               QR_BUILD_LOG_DIR=str(tmp_path / "logs"))
    proc = subprocess.run(["bash", str(SAFE_BOOT)], env=env, capture_output=True, text=True, cwd=REPO, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    args = (tmp_path / "build.args").read_text().splitlines()
    labels = dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "--label")
    assert labels["org.qrosetta.image.project"] == "qsimulators" and labels["org.qrosetta.service"] == "api"
    assert labels["org.opencontainers.image.title"] == "Quantum Rosetta API"
    sha = re.search(r"^\[INFO\] QROSETTA_GIT_SHA=(\S+)$", proc.stdout, re.M).group(1)
    assert labels["org.opencontainers.image.revision"] == sha
    assert labels["org.opencontainers.image.licenses"] == "Apache-2.0"
