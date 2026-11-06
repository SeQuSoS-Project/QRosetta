"""The build kit (scripts/release/make_buildkit.py) and `qrosetta build` in installed mode: the kit
is reproducible, carries every file the images' Dockerfiles copy and no test file or secret, and
fits the wheel; an installed qrosetta verifies and unpacks it, builds through safe_boot.sh with
the release identity under its own tags, and every stack command then treats those images as the
project's local builds of the release."""

import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from tests.unit._qrosetta_fake import (REGISTRY, FakeEngine, FakeServer, Unreachable, image_labels,
                                       release_manifest)
from tests.unit.test_qrosetta_contracts import validate_envelope

from qrosetta_cli import __version__  # noqa: E402
from qrosetta_cli import manifest as mf  # noqa: E402
from qrosetta_cli import mode as modes  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from qrosetta_cli.stack import buildkit, signatures  # noqa: E402
from qrosetta_cli.stack import pull as pullmod  # noqa: E402
from qrosetta_cli.stack import serve  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
COMMIT = "c" * 40
KIT_TAG = f"{__version__}-buildkit"


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / "release" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_buildkit():
    pytest.importorskip("yaml")
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("needs a git checkout")
    return _load_script("make_buildkit")


# --- the kit itself ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def kit():
    mk = _make_buildkit()
    data, meta = mk.build(REPO, "HEAD")
    return mk, data, meta


def _names(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        return [m.name for m in tar.getmembers()], tar.getmembers()


def test_the_kit_of_one_commit_is_the_same_bytes_every_time(kit):
    mk, data, meta = kit
    again, meta2 = mk.build(REPO, "HEAD")
    assert again == data and meta2 == meta
    assert meta["sha256"] == hashlib.sha256(data).hexdigest() and meta["size"] == len(data)
    names, members = _names(data)
    assert names == sorted(names) and meta["files"] == len(names)
    assert {(m.uid, m.gid, m.uname, m.gname, m.mtime) for m in members} == {(0, 0, "", "", meta["commit_time"])}
    assert data[4:8] == meta["commit_time"].to_bytes(4, "little")


def test_the_kit_carries_every_file_the_dockerfiles_copy_and_the_build_tooling(kit):
    mk, data, meta = kit
    names = set(_names(data)[0])
    import yaml
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text())
    tracked = set(subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True,
                                 check=True).stdout.split())
    for svc in compose["services"].values():
        build = svc["build"]
        dockerfile = str(Path(build["dockerfile"]).as_posix()).lstrip("./")
        assert build["context"] == "." and dockerfile in names
        for src in mk.copy_sources((REPO / dockerfile).read_text(), dockerfile):
            src = src.rstrip("/")
            hits = [n for n in names if n == src or n.startswith(src + "/")]
            assert hits, (dockerfile, src)
            expected = {p for p in tracked if (p == src or p.startswith(src + "/")) and "/tests/" not in f"/{p}"}
            patterns = mk.dockerignore_patterns((REPO / ".dockerignore").read_text())
            assert {p for p in expected if not mk.ignored(p, patterns)} == set(hits), (dockerfile, src)
    for path in mk.BASE_FILES + ("infra/lifecycle-token.none",):
        assert path in names
    assert meta["version"] == __version__ and 1_000_000 < meta["size"] < mk.MAX_BYTES


def test_the_kit_carries_no_test_file_and_nothing_dockerignore_excludes(kit, tmp_path):
    mk, data, _ = kit
    names, members = _names(data)
    assert not [n for n in names if "/tests/" in f"/{n}" or n.startswith("tests/")]
    assert not [n for n in names if n.endswith((".env", ".pem", ".key", ".db", ".sqlite", "CLAUDE.md"))]
    assert not [n for n in names if n.split("/")[0] in ("docs", "latex", ".github", ".git", "experiments")]
    assert {m.mode for m in members} <= {0o644, 0o755}
    gitleaks = shutil.which("gitleaks") or (str(Path.home() / ".local/bin/gitleaks")
                                            if (Path.home() / ".local/bin/gitleaks").exists() else None)
    if gitleaks is None:
        pytest.skip("gitleaks is not installed")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar.getmembers():
            dest = tmp_path / "kit" / m.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(tar.extractfile(m).read())
    out = subprocess.run([gitleaks, "dir", str(tmp_path / "kit"), "--config", str(REPO / ".gitleaks.toml"),
                          "--no-banner", "--exit-code", "3"], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def _repo(tmp_path, dockerfile, extra=()):
    repo = tmp_path / "repo"
    (repo / "svc").mkdir(parents=True)
    (repo / "scripts" / "release").mkdir(parents=True)
    (repo / "release").mkdir()
    (repo / "qrosetta_cli").mkdir()
    files = {"docker-compose.yml": "services:\n  svc:\n    build:\n      context: .\n      dockerfile: ./svc/Dockerfile\n",
             ".dockerignore": "**/secrets\n", "scripts/safe_boot.sh": "", "scripts/release/oci_labels.py": "",
             "release/debian-snapshot.conf": "DEBIAN_SNAPSHOT=1\n", "qrosetta_cli/__init__.py": '__version__ = "1.0"\n',
             "svc/Dockerfile": dockerfile, "svc/main.py": "", "svc/tests/test_x.py": "", "svc/secrets/k": ""}
    files.update(dict(extra))
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@e"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "x"], check=True, env={"GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
                                                                         "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
                                                                         "PATH": "/usr/bin:/bin"})
    return repo


def test_a_copy_source_that_names_no_file_stops_the_kit(tmp_path):
    mk = _make_buildkit()
    repo = _repo(tmp_path, "FROM x\nCOPY svc/missing.py .\n")
    with pytest.raises(mk.KitError, match="COPY source svc/missing.py matches no tracked file"):
        mk.build(repo, "HEAD")


def test_a_directory_copy_leaves_out_tests_and_dockerignored_paths(tmp_path):
    mk = _make_buildkit()
    repo = _repo(tmp_path, "FROM x\nCOPY --chmod=0755 svc/ \\\n  /app/\nCOPY --from=b /x /y\n")
    data, meta = mk.build(repo, "HEAD")
    names = _names(data)[0]
    assert "svc/main.py" in names and "svc/Dockerfile" in names
    assert "svc/tests/test_x.py" not in names and "svc/secrets/k" not in names
    assert meta["version"] == "1.0" and meta["files"] == len(names) == 8


def test_a_kit_over_the_size_limit_is_refused(tmp_path, monkeypatch):
    mk = _make_buildkit()
    repo = _repo(tmp_path, "FROM x\nCOPY svc/main.py .\n")
    monkeypatch.setattr(mk, "MAX_BYTES", 100)
    with pytest.raises(mk.KitError, match="over the 100-byte limit"):
        mk.build(repo, "HEAD")


# --- packaging ----------------------------------------------------------------------------------


def test_the_wheel_ships_the_kit_and_check_dist_requires_a_matching_one(tmp_path):
    import tomllib
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    shipped = data["tool"]["setuptools"]["package-data"]["qrosetta_cli"]
    assert "release/buildkit.tar.gz" in shipped and "release/buildkit.json" in shipped
    ignored = (REPO / ".gitignore").read_text().splitlines()
    assert "qrosetta_cli/release/buildkit.tar.gz" in ignored and "qrosetta_cli/release/buildkit.json" in ignored
    cd = _load_script("check_dist")
    kit_bytes = b"kit"
    good = {"sha256": hashlib.sha256(kit_bytes).hexdigest(), "size": 3}
    for meta, expect in ((good, []), (dict(good, size=4), ["does not match"]), (None, ["no qrosetta_cli/release"])):
        path = tmp_path / "w.zip"
        with zipfile.ZipFile(path, "w") as zf:
            if meta is not None:
                zf.writestr("qrosetta_cli/release/buildkit.tar.gz", kit_bytes)
                zf.writestr("qrosetta_cli/release/buildkit.json", json.dumps(meta))
        with zipfile.ZipFile(path) as zf:
            problems = cd.check_buildkit(zf, zf.namelist())
        assert all(any(e in p for p in problems) for e in expect) and bool(problems) == bool(expect)


def test_the_release_workflow_builds_the_kit_before_the_wheel_and_checks_it():
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "release-images.yml").read_text())
    names = [s.get("name") for s in wf["jobs"]["wheel"]["steps"]]
    runs = {s.get("name"): s.get("run", "") for s in wf["jobs"]["wheel"]["steps"]}
    assert names.index("Build kit") < names.index("Build")
    assert runs["Build kit"].strip() == "python scripts/release/make_buildkit.py"
    assert "--require-buildkit" in runs["Check the distributions"]


# --- installed build --------------------------------------------------------------------------


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(pullmod, "_sleep", lambda s: None)
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    monkeypatch.setattr(signatures, "cosign_path", lambda env: None)
    monkeypatch.setattr(modes, "PACKAGE_PARENT", str(tmp_path / "site-packages"))
    monkeypatch.setattr(mf, "PATH", str(tmp_path / "site-packages" / "qrosetta_cli" / "release" / "manifest.json"))
    return {"QROSETTA_PROJECT": "qr", "PATH": "/usr/bin", "HOME": str(tmp_path / "home"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"), "XDG_CACHE_HOME": str(tmp_path / "cache")}


def ship(manifest=None, with_kit=True, published=True):
    release = Path(mf.PATH).parent
    release.mkdir(parents=True, exist_ok=True)
    manifest = manifest or release_manifest(published=published)
    manifest["services"]["myqlm"]["requires_gpu"] = False
    (release / "manifest.json").write_text(json.dumps(manifest))
    if with_kit:
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w:gz") as tar:
            for name, text, mode in (("docker-compose.yml", "services: {}\n", 0o644),
                                     ("scripts/safe_boot.sh", "#!/bin/bash\n", 0o755)):
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(text), mode
                tar.addfile(info, io.BytesIO(text.encode()))
        data = raw.getvalue()
        (release / "buildkit.tar.gz").write_bytes(data)
        (release / "buildkit.json").write_text(json.dumps({
            "schema": buildkit.SCHEMA, "file": "buildkit.tar.gz", "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data), "files": 2, "commit": COMMIT, "commit_time": 0, "version": __version__}))
    return manifest


def engine_with_release(pulled=("nginx", "api", "qiskit")):
    f = FakeEngine()
    f.from_file = True
    refs = mf.published_refs(release_manifest())
    for sid, service in (("nginx", "nginx"), ("api", "api"), ("qiskit", "qiskit_runner")):
        if sid in pulled:
            f.add_image("i-" + sid, [], image_labels(service), digests=[refs[sid]], identity=("release", "9.9.9"),
                        env=(["QROSETTA_VERSION=9.9.9"] if sid == "api" else []))
        f.publish(refs[sid], "i-" + sid, image_labels(service), identity=("release", "9.9.9"))
    return f


def builder(fake, seen, code=0, sha=None):
    """subprocess.call of safe_boot.sh: records the call and adds each requested image as the kit
    build would tag and label it."""
    def call(cmd, env, cwd, **kwargs):
        seen.append({"cmd": cmd, "env": env, "cwd": cwd})
        for service in env["QR_BUILD_SERVICES"].split():
            fake.add_image(f"k-{service}", [f"localhost/qr-{service}:{env['QR_IMAGE_TAG']}"],
                           image_labels(service), sha=sha or env["QR_GIT_SHA"],
                           identity=(env["QROSETTA_IMAGE_SOURCE"], env["QROSETTA_RELEASE"]),
                           env=([f"QROSETTA_VERSION={env['QROSETTA_RELEASE']}"] if service == "api" else []))
        return code
    return call


def run(argv, env, fake, server=None):
    return main(argv, checkout=None, env=env, tty=False,
                engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env),
                transport_factory=server or Unreachable())


def test_build_without_a_kit_names_the_kit_and_the_checkout_route(env, capsys):
    ship(with_kit=False)
    assert run(["build", "myqlm"], env, FakeEngine()) == Exit.INCOMPATIBLE
    err = capsys.readouterr().err
    assert "carries no build kit" in err and err.strip().splitlines()[-1].strip().endswith("./qrosetta build")


def test_installed_build_runs_safe_boot_in_the_unpacked_kit_with_the_release_identity(env, tmp_path, monkeypatch,
                                                                                      capsys):
    ship()
    fake, seen = engine_with_release(), []
    monkeypatch.setattr(subprocess, "call", builder(fake, seen))
    assert run(["build", "myqlm", "qiskit", "--json"], env, fake) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    assert doc["data"]["built"] == ["myqlm", "qiskit"] and doc["data"]["commit"] == COMMIT + "+buildkit"
    kit_dir = tmp_path / "cache" / "qrosetta" / "buildkit" / f"{__version__}-{doc_sha()[:12]}"
    (call,) = seen
    assert call["cmd"] == ["bash", str(kit_dir / "scripts" / "safe_boot.sh")] and call["cwd"] == str(kit_dir)
    e = call["env"]
    assert e["QR_BUILD_ONLY"] == "1" and e["QR_BUILD_SERVICES"] == "myqlm_runner qiskit_runner"
    assert e["QR_GIT_SHA"] == COMMIT + "+buildkit" and e["QR_IMAGE_TAG"] == KIT_TAG
    assert e["QROSETTA_IMAGE_SOURCE"] == "built_locally" and e["QROSETTA_RELEASE"] == __version__
    assert e["TMPDIR"] == str(tmp_path / "cache" / "qrosetta" / "tmp")
    assert e["COMPOSE_FILE"] == str(kit_dir / "docker-compose.yml") and e["COMPOSE_PROJECT_NAME"] == "qr"
    assert e["QROSETTA_PROJECT"] == "qr" and e["QR_BUILD_LOG_DIR"].startswith(str(tmp_path / "cache"))
    settings = json.loads((tmp_path / "state" / "qrosetta" / "stack-settings.json").read_text())
    assert settings["projects"]["qr"]["built_locally"] == {"myqlm": f"qr-myqlm_runner:{KIT_TAG}",
                                                          "qiskit": f"qr-qiskit_runner:{KIT_TAG}"}
    assert not fake.destructive_calls()


def doc_sha():
    return json.loads((Path(mf.PATH).parent / "buildkit.json").read_text())["sha256"]


def test_a_profile_build_adds_core_and_no_argument_builds_every_release_service(env, monkeypatch):
    manifest = release_manifest()
    manifest["services"]["qiskit"]["profiles"] = ["minimal"]
    ship(manifest)
    fake, seen = engine_with_release(), []
    monkeypatch.setattr(subprocess, "call", builder(fake, seen))
    assert run(["build", "--profile", "minimal"], env, fake) == 0
    assert run(["build"], env, fake) == 0
    assert [c["env"]["QR_BUILD_SERVICES"] for c in seen] == ["qiskit_runner nginx api",
                                                             "nginx api qiskit_runner myqlm_runner"]


def test_the_kit_is_checked_and_its_unpacked_copy_reused_until_a_file_changes(env, tmp_path, monkeypatch, capsys):
    ship()
    fake, seen = engine_with_release(), []
    monkeypatch.setattr(subprocess, "call", builder(fake, seen))
    assert run(["build", "myqlm"], env, fake) == 0
    script = Path(seen[0]["cmd"][1])
    marker = script.parents[1] / buildkit.MARKER
    stamp = marker.stat().st_mtime_ns
    assert run(["build", "myqlm"], env, fake) == 0 and marker.stat().st_mtime_ns == stamp
    script.write_text("#!/bin/bash\nevil\n")
    assert run(["build", "myqlm"], env, fake) == 0 and script.read_text() == "#!/bin/bash\n"
    (Path(mf.PATH).parent / "buildkit.tar.gz").write_bytes(b"other")
    capsys.readouterr()
    assert run(["build", "myqlm", "--json"], env, fake) == Exit.INTERNAL
    assert json.loads(capsys.readouterr().out)["error"]["reason"] == "buildkit_corrupt"
    assert len(seen) == 3


def test_a_build_that_did_not_bake_the_kit_commit_exits_16(env, monkeypatch, capsys):
    ship()
    fake, seen = engine_with_release(), []
    monkeypatch.setattr(subprocess, "call", builder(fake, seen, sha="unknown"))
    assert run(["build", "myqlm"], env, fake) == Exit.ENGINE
    assert "without the commit " + COMMIT + "+buildkit: myqlm" in capsys.readouterr().err
    assert not (Path(env["XDG_STATE_HOME"]) / "qrosetta" / "stack-settings.json").exists()


def _compose(env):
    text = (Path(env["XDG_STATE_HOME"]) / "qrosetta" / "compose.yaml").read_text()
    return json.loads(text.split("\n", 1)[1])["services"]


def test_compose_mixes_local_builds_and_published_digests_and_status_names_the_source(env, monkeypatch, capsys):
    ship()
    fake, seen = engine_with_release(), []
    refs = mf.published_refs(release_manifest())
    assert run(["status"], env, fake) == 0
    services = _compose(env)
    assert services["myqlm_runner"]["image"] == f"qr-myqlm_runner:{KIT_TAG}"
    assert services["qiskit_runner"]["image"] == refs["qiskit"]
    monkeypatch.setattr(subprocess, "call", builder(fake, seen))
    assert run(["build", "qiskit", "myqlm"], env, fake) == 0
    capsys.readouterr()
    assert run(["status", "--json"], env, fake) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    services = _compose(env)
    assert services["qiskit_runner"]["image"] == f"qr-qiskit_runner:{KIT_TAG}"
    assert services["myqlm_runner"]["image"] == f"qr-myqlm_runner:{KIT_TAG}"
    assert services["api"]["image"] == refs["api"] and services["nginx"]["image"] == refs["nginx"]
    assert run(["status"], env, fake) == 0
    out = capsys.readouterr().out
    assert f"built locally from release {__version__} (cccccccccccc+buildkit)" in out
    assert "pulled 9.9.9" in out


def test_start_names_build_for_services_the_release_does_not_publish(env, capsys):
    ship()
    fake = engine_with_release()
    assert run(["start", "-d"], env, fake, server=FakeServer(fresh=True)) == 0
    err = capsys.readouterr().err
    assert "Not started (no image): myqlm." in err
    assert "myqlm: not included in this release; build it: qrosetta build myqlm." in err


def test_images_verify_accepts_a_kit_build_with_info_for_release_and_signature(env, monkeypatch, capsys):
    ship()
    fake, seen = engine_with_release(), []
    monkeypatch.setattr(subprocess, "call", builder(fake, seen))
    assert run(["build", "myqlm", "qiskit"], env, fake) == 0
    capsys.readouterr()
    assert run(["images", "verify", "--json"], env, fake) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    by_id = {i["id"]: {c["check"]: c for c in i["checks"]} for i in doc["data"]["images"]}
    for sid in ("myqlm", "qiskit"):
        checks = by_id[sid]
        assert checks["identity"]["status"] == "PASS" and "source=built_locally" in checks["identity"]["detail"]
        assert checks["release"]["status"] == "INFO" and "build kit" in checks["release"]["detail"]
        assert checks["signature"]["status"] == "INFO" and "no signature" in checks["signature"]["detail"]
        assert "release commit" not in checks
    assert by_id["api"]["release"]["status"] == "PASS"
    assert run(["images", "verify", "qiskit", "--require-signature"], env, fake) == Exit.ENGINE


def test_pull_replaces_a_local_build_and_remove_images_removes_both(env, monkeypatch, capsys):
    ship()
    fake, seen = engine_with_release(pulled=("nginx", "api")), []
    monkeypatch.setattr(subprocess, "call", builder(fake, seen))
    assert run(["build", "qiskit", "myqlm"], env, fake) == 0
    capsys.readouterr()
    assert run(["pull", "qiskit"], env, fake) == 0
    assert "qiskit: the stack runs the release images now" in capsys.readouterr().err
    assert run(["status"], env, fake) == 0
    assert _compose(env)["qiskit_runner"]["image"] == mf.published_refs(release_manifest())["qiskit"]
    assert run(["remove", "--images"], env, fake) == 0
    removed = {a for c in fake.destructive_calls() for a in c}
    assert {"k-qiskit_runner", "k-myqlm_runner", "i-qiskit", "i-api", "i-nginx"} <= removed
    assert not fake.images
    assert buildkit.recorded(env, "qr") == {}


def test_without_published_images_the_kit_alone_makes_a_stack(env, monkeypatch, capsys):
    ship(published=False)
    fake, seen = FakeEngine(), []
    fake.from_file = True
    assert run(["pull", "qiskit"], env, fake) == Exit.INCOMPATIBLE
    assert capsys.readouterr().err.strip().splitlines()[-1].strip() == "qrosetta build --profile minimal"
    monkeypatch.setattr(subprocess, "call", builder(fake, seen))
    assert run(["build"], env, fake) == 0
    assert run(["status"], env, fake) == 0
    assert {s["image"] for s in _compose(env).values()} == {
        f"qr-{c}:{KIT_TAG}" for c in ("nginx", "api", "qiskit_runner", "myqlm_runner")}
    assert run(["start", "-d"], env, fake, server=FakeServer(fresh=True)) == 0


def test_doctor_reports_the_kit_and_suggests_build_when_nothing_is_published(env, capsys):
    from tests.unit.test_qrosetta_doctor import FakeHost
    from qrosetta_cli.stack import doctor
    ship(published=False)
    host = FakeHost(env, free=200 * doctor.GIB)
    host.images_present = lambda ctx: False
    assert main(["doctor"], env=env, host_factory=lambda e: host, transport_factory=Unreachable()) == 0
    out = capsys.readouterr().out
    assert "build kit present (" in out and "`qrosetta build NAME` builds images" in out
    assert out.strip().splitlines()[-1].endswith("qrosetta build --profile minimal")
    ship(with_kit=False)
    (Path(mf.PATH).parent / "buildkit.json").unlink()
    assert main(["doctor"], env=env, host_factory=lambda e: host, transport_factory=Unreachable()) == 0
    assert "no build kit in this package" in capsys.readouterr().out


def test_doctor_warns_when_var_tmp_is_smaller_than_the_largest_image_build(env, capsys):
    from tests.unit.test_qrosetta_doctor import FakeHost
    from qrosetta_cli.stack import doctor
    host = FakeHost(env, free=200 * doctor.GIB)
    host.free_bytes = lambda path: 1_600_000_000 if path == "/var/tmp" else 200 * doctor.GIB
    rep = doctor.run(_ctx(env), host)
    rows = [c for c in rep.checks if c.id == "disk" and "/var/tmp" in c.message]
    assert [c.status for c in rows] == ["WARN"] and "the largest image build stages" in rows[0].message
    host.free_bytes = lambda path: 200 * doctor.GIB
    rep = doctor.run(_ctx(env), host)
    assert [c.status for c in rep.checks if c.id == "disk" and "/var/tmp" in c.message] == ["INFO"]


def _ctx(env):
    from qrosetta_cli import config as cfgmod
    from qrosetta_cli.context import Context
    return Context(args=type("A", (), {})(), env=env, cfg=cfgmod.Config("/none", False),
                   transport_factory=Unreachable())


# --- the identity a kit build bakes -----------------------------------------------------------


def test_the_self_test_and_specimens_accept_a_kit_commit_as_a_local_build():
    from services import specimens
    from services.selftest import environment
    sha = COMMIT + "+buildkit"
    result = {"image_identity": {"source": "built_locally", "release": __version__, "git_sha": sha},
              "image_git_sha": sha}
    status, reason, value = environment._provenance(result, "qiskit", "statevector")
    assert status == "WARN" and sha in reason and value == {"source": "built_locally", "git_sha": sha}
    from qrosetta_cli.client import imageprobes
    row = {"versions": {"image_identity": {"source": "built_locally", "git_sha": sha}}}
    status, reason, _ = imageprobes._commit(row, sha)
    assert status == "PASS" and "built locally from " + sha in reason
    status, _, _ = imageprobes._commit(row, "abc")
    assert status == "WARN"
    assert specimens.result_specimen(result)["kind"] == "built_locally"
    assert specimens.result_specimen(result)["image_git_sha"] == sha


def test_a_registry_name_is_no_kit_tag():
    assert buildkit.tag("qr", "api") == f"qr-api:{KIT_TAG}" and "@" not in buildkit.tag("qr", "api")
    assert not buildkit.tag("qr", "api").startswith(REGISTRY)


def test_not_included_text_names_the_build_command_only_with_a_kit(env):
    manifest = release_manifest()
    manifest["services"]["cuquantum"] = dict(manifest["services"]["myqlm"], requires_gpu=True,
                                             compose_service="cuquantum_runner")
    ship(manifest, with_kit=False)
    assert mf.not_included_text(["myqlm"]) == mf.NOT_INCLUDED
    ship(manifest)
    manifest["services"]["cuquantum"]["requires_gpu"] = True
    (Path(mf.PATH)).write_text(json.dumps(manifest))
    assert mf.not_included_text(["myqlm"]) == "not included in this release; build it: qrosetta build myqlm"
    assert mf.not_included_text(["myqlm", "cuquantum"]) == (
        "not included in this release; build them: qrosetta build myqlm cuquantum "
        "(cuquantum needs an NVIDIA GPU to run)")


def test_doctor_and_compose_leave_a_kit_build_out_of_the_not_included_list(env, monkeypatch):
    from qrosetta_cli import config as cfgmod
    from qrosetta_cli.context import Context
    from qrosetta_cli.stack import doctor
    ship()
    fake, seen = engine_with_release(), []
    monkeypatch.setattr(subprocess, "call", builder(fake, seen))
    ctx = Context(args=type("A", (), {"project_dir": None})(), env=env, cfg=cfgmod.Config("/none", False),
                  engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env))
    assert doctor.not_included_ids(ctx) == {"myqlm"} and doctor.local_services(ctx)["not_included"] == {"myqlm"}
    assert run(["build", "myqlm"], env, fake) == 0
    assert doctor.not_included_ids(ctx) == set() and doctor.local_services(ctx)["not_included"] == set()
    fake.calls.clear()
    assert run(["status"], env, fake) == 0
    assert {e.get(mf.NOT_INCLUDED_VAR) for c, e in fake.calls if c[1] == "compose"} == {""}
