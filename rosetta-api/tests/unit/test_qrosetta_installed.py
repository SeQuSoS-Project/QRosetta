"""qrosetta_cli installed mode (a wheel without a checkout): no repository is looked for, start and
status refuse while the release manifest names no published images, and with published images
the compose file is generated in $XDG_STATE_HOME/qrosetta and every engine call keeps the
checkout's ownership rules."""

import json
from pathlib import Path

import pytest

from tests.unit._qrosetta_fake import (CONFIG, REGISTRY, RELEASE_DIGEST as DIGEST, REPO, FakeEngine, FakeServer,
                                       Unreachable, image_labels, ours, release_manifest as release)

from qrosetta_cli import manifest as mf  # noqa: E402
from qrosetta_cli import mode as modes  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from qrosetta_cli.stack import installed, serve  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(modes, "PACKAGE_PARENT", str(tmp_path / "site-packages"))
    monkeypatch.setattr(mf, "PATH", str(tmp_path / "site-packages" / "qrosetta_cli" / "release" / "manifest.json"))
    monkeypatch.chdir(REPO)
    return {"QROSETTA_PROJECT": "qr", "PATH": "/usr/bin", "HOME": str(tmp_path / "home"),
            "COMPOSE_PROJECT_NAME": "myapp", "COMPOSE_FILE": "evil.yml",
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"), "XDG_CACHE_HOME": str(tmp_path / "cache")}


def ship(manifest):
    path = Path(mf.PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest))


def published_engine(missing=()):
    """A fake engine whose compose config is the release's: images by digest, pulled."""
    f = FakeEngine()
    f.add("rosetta-api", ours("api"), running=False)
    f.add("nginx-reverse-proxy", ours("nginx"), running=False)
    refs = mf.published_refs(release())
    for sid, service in (("nginx", "nginx"), ("api", "api"), ("qiskit", "qiskit_runner")):
        f.extra_services[service] = dict(CONFIG["services"][service], image=refs[sid])
        if sid not in missing:
            f.add_image("i-" + sid, [], image_labels(service), digests=[refs[sid]])
    return f


def run(argv, env, fake=None, server=None, opened=None):
    def factory(directory):
        if opened is not None:
            opened.append(directory)
        return Engine(fake.engine, directory, run=fake, popen=fake.popen, env=env)
    return main(argv, checkout=None, env=env, tty=False, engine_factory=factory if fake else None,
                transport_factory=server or Unreachable())


def test_installed_mode_ignores_a_checkout_in_the_working_directory(env):
    assert modes.detect(None, env, None) == modes.Mode("installed", "", "installed package")


@pytest.mark.parametrize("shipped", ["none", "unpublished", "partial", "non_distributable_digest"])
@pytest.mark.parametrize("argv", [["start", "-d"], ["status"], ["status", "--json"]])
def test_start_and_status_refuse_until_the_images_are_published(env, tmp_path, capsys, shipped, argv):
    manifest = {"none": None, "unpublished": release(published=False), "partial": release(),
                "non_distributable_digest": release()}[shipped]
    if shipped == "partial":
        manifest["services"]["qiskit"]["ref"] = None
    if shipped == "non_distributable_digest":
        manifest["services"]["myqlm"]["ref"] = f"{REGISTRY}/qrosetta-myqlm-runner@{DIGEST}"
    if manifest is not None:
        ship(manifest)
    opened = []
    assert run(argv, env, fake=FakeEngine(), opened=opened) == Exit.INCOMPATIBLE
    out, err = capsys.readouterr()
    if "--json" in argv:
        doc = json.loads(out)
        assert doc["error"]["reason"] == "images_not_published" and doc["error"]["hint"] == installed.SOURCE_ROUTE
    else:
        assert "are not published" in err and err.strip().splitlines()[-1] == installed.SOURCE_ROUTE
    for step in ("git clone https://github.com/SeQuSoS-Project/QRosetta", "./qrosetta build", "./qrosetta start"):
        assert step in installed.SOURCE_ROUTE
    assert opened == []
    assert not (tmp_path / "state" / "qrosetta" / "compose.yaml").exists()
    assert not (tmp_path / "run").exists()


def test_version_reports_the_manifest_in_installed_mode(env, capsys):
    ship(release(published=False))
    assert run(["version"], env) == 0
    out = capsys.readouterr().out
    assert "installed mode" in out and "Release manifest: release 9.9.9 (images not published)" in out
    assert run(["version", "--json"], env) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["data"]["manifest"] == {"release": "9.9.9", "index": None, "images_published": False}
    assert doc["data"]["mode"] == "installed" and doc["data"]["project_dir"] is None


def test_without_a_manifest_version_says_so(env, capsys):
    assert run(["version"], env) == 0
    assert "Release manifest: none in this package" in capsys.readouterr().out


def test_images_published_needs_every_distributable_digest_and_no_other():
    assert mf.images_published(release())
    assert not mf.images_published(None) and not mf.images_published(release(published=False))
    bad = release()
    bad["services"]["myqlm"]["ref"] = f"{REGISTRY}/qrosetta-myqlm-runner@{DIGEST}"
    assert not mf.images_published(bad)
    tag = release()
    tag["services"]["api"]["ref"] = f"{REGISTRY}/qrosetta-rosetta-api:9.9.9"
    assert not mf.images_published(tag)


def test_a_published_release_generates_the_compose_file_in_the_state_directory(env, tmp_path, capsys):
    ship(release())
    fake, opened = published_engine(), []
    assert run(["status"], env, fake=fake, opened=opened) == 0
    state = tmp_path / "state" / "qrosetta"
    assert opened == [str(state)]
    text = (state / "compose.yaml").read_text()
    assert text.startswith("# Generated by qrosetta")
    doc = json.loads(text.split("\n", 1)[1])
    refs = mf.published_refs(release())
    assert list(doc["services"]) == ["nginx", "api", "qiskit_runner"]
    for sid, svc in release()["services"].items():
        if sid in refs:
            generated = doc["services"][svc["compose_service"]]
            assert generated == dict(svc["compose"], image=refs[sid]) and "build" not in generated
    assert doc["name"] == "${QROSETTA_PROJECT:-qsimulators}" and doc["networks"]["isolated_net"]["internal"] is True
    for svc in doc["services"].values():
        for volume in svc.get("volumes", []):
            if isinstance(volume, dict):
                assert volume["source"] == "${QROSETTA_LIFECYCLE_TOKEN_PATH:-./infra/lifecycle-token.none}"
            else:
                assert not volume.startswith(("/", ".", "~")), volume
    assert (state / "infra" / "lifecycle-token.none").read_text() == ""
    for cmd, call_env in fake.calls:
        assert not any(k.startswith("COMPOSE_") for k in call_env)
        if cmd[1] == "compose":
            assert cmd[1:8] == ["compose", "-p", "qr", "--project-directory", str(state), "-f",
                                str(state / "compose.yaml")], cmd
    out = capsys.readouterr().out
    assert f"pulled 9.9.9 {'ab' * 6}" in out and "installed mode" in out


def test_published_start_names_pull_commands_for_images_not_yet_pulled(env, capsys, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    ship(release())
    refs = mf.published_refs(release())
    fake = published_engine(missing=("qiskit",))
    assert run(["start", "-d"], env, fake=fake, server=FakeServer(fresh=True)) == 0
    err = capsys.readouterr().err
    assert "`qrosetta pull qiskit braket` pulls them" in err and "qrosetta images load DIR" in err
    assert "qrosetta build" not in err and refs["qiskit"] not in err
    assert fake.compose_calls("up")[0][-2:] == ["nginx", "api"]
    fake = published_engine(missing=("api",))
    assert run(["start", "-d"], env, fake=fake, server=FakeServer(fresh=True)) == Exit.ENGINE
    assert capsys.readouterr().err.strip().splitlines()[-1] == "qrosetta pull api"


def test_installed_start_recreates_a_service_whose_generated_configuration_changed(env, tmp_path, capsys,
                                                                                    monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    ship(release())
    fake = published_engine()
    fake.containers.clear()
    assert run(["start", "-d"], env, fake=fake, server=FakeServer(fresh=True)) == 0
    fake.calls.clear()
    assert run(["start", "-d"], env, fake=fake, server=FakeServer(fresh=True)) == 0
    assert not fake.compose_calls("up") and not fake.recreated
    fake.edit_config("api")
    capsys.readouterr()
    assert run(["start", "-d", "--json"], env, fake=fake, server=FakeServer(fresh=True)) == 0
    state = tmp_path / "state" / "qrosetta"
    hashed = [c for c, _ in fake.calls if "--hash" in c]
    assert hashed and all(c[1:8] == ["compose", "-p", "qr", "--project-directory", str(state), "-f",
                                     str(state / "compose.yaml")] for c in hashed)
    assert [c[c.index("up"):] for c in fake.compose_calls("up")] == [
        ["up", "-d", "--no-build", "--force-recreate", "--no-deps", "api"]]
    assert json.loads(capsys.readouterr().out)["data"]["recreations"] == [{"id": "api", "reasons": ["config"]}]
