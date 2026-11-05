"""qrosetta pull, images (list), images verify, images save and images load on the fake engine:
pulls go by the manifest's digests with TMPDIR under the cache directory, retry once on a network
error and check digests, labels and (with cosign) signatures; verify reads inspect data only and
runs no container; save writes only this stack's images and load refuses anything that is not a
qrosetta image of a known service; none of them ever acts on a decoy or deletes anything."""

import json
from pathlib import Path

import pytest

from tests.unit._qrosetta_fake import (REGISTRY, SIGNER, FakeEngine, FakeServer, Unreachable, identity_step,
                                       image_labels, ours, release_manifest, write_archive)
from tests.unit.test_qrosetta_contracts import validate_envelope

from qrosetta_cli import manifest as mf  # noqa: E402
from qrosetta_cli import mode as modes  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from qrosetta_cli.stack import archive, signatures  # noqa: E402
from qrosetta_cli.stack import ownership as own  # noqa: E402
from qrosetta_cli.stack import pull as pullmod  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402

IDS = {"nginx": "1" * 64, "api": "2" * 64, "qiskit": "3" * 64}
SERVICES = {"nginx": "nginx", "api": "api", "qiskit": "qiskit_runner"}
BUSY = {"exclusive_running": False, "exclusive_waiting": 0, "shared_running": 2}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(pullmod, "_sleep", lambda s: None)
    monkeypatch.setattr(signatures, "cosign_path", lambda env: None)
    return {"QROSETTA_PROJECT": "qr", "PATH": "/usr/bin", "HOME": str(tmp_path / "home"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"), "XDG_CACHE_HOME": str(tmp_path / "cache")}


@pytest.fixture
def installed(tmp_path, monkeypatch):
    """Installed mode with a shipped manifest; returns a function that ships another one."""
    monkeypatch.setattr(modes, "PACKAGE_PARENT", str(tmp_path / "site-packages"))
    monkeypatch.setattr(mf, "PATH", str(tmp_path / "site-packages" / "qrosetta_cli" / "release" / "manifest.json"))

    def ship(manifest):
        path = Path(mf.PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest))
        return manifest
    ship(release_manifest())
    return ship


@pytest.fixture
def project(tmp_path):
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path / "proj"


def registry_engine(labels_project="qr", sha="abc123", release="9.9.9"):
    """A fake engine whose compose configuration is the generated file, and a registry holding
    the release's images."""
    f = FakeEngine()
    f.from_file = True
    refs = mf.published_refs(release_manifest())
    for sid, service in SERVICES.items():
        f.publish(refs[sid], IDS[sid], image_labels(service, labels_project), sha=sha,
                  identity=("release", release), env=(["QROSETTA_VERSION=9.9.9"] if sid == "api" else []))
    return f


def run(argv, env, fake, checkout=None, server=None):
    return main(argv, checkout=str(checkout) if checkout else None, env=env, tty=False,
                engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env),
                transport_factory=server or Unreachable())


def calls(fake, verb):
    return [c for c, _ in fake.calls if c[1:1 + len(verb)] == list(verb)]


def assert_never_destructive(fake):
    assert not fake.destructive_calls()
    for cmd, _ in fake.calls:
        assert cmd[1] != "run" and "prune" not in cmd and "--all" not in cmd, cmd


# --- pull -------------------------------------------------------------------------------------


def test_pull_in_a_checkout_points_to_build_and_touches_no_engine(env, project, capsys):
    fake = FakeEngine().standard()
    assert run(["pull", "qiskit"], env, fake, checkout=project) == Exit.INCOMPATIBLE
    err = capsys.readouterr().err
    assert "carries no release manifest" in err and err.strip().splitlines()[-1].strip() == "qrosetta build qiskit"
    assert fake.calls == []


def test_pull_refuses_while_the_release_names_no_published_images(env, installed, capsys):
    installed(release_manifest(published=False))
    fake = registry_engine()
    assert run(["pull", "--all"], env, fake) == Exit.INCOMPATIBLE
    assert "are not published" in capsys.readouterr().err and not calls(fake, ["pull"])


def test_pull_by_digest_with_tmpdir_in_the_cache_then_status_shows_pulled(env, installed, tmp_path, capsys):
    fake = registry_engine()
    assert run(["pull", "qiskit", "--json"], env, fake) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    refs = mf.published_refs(release_manifest())
    assert [c[2:] for c in calls(fake, ["pull"])] == [[refs["qiskit"]]]
    pull_env = next(e for c, e in fake.calls if c[1] == "pull")
    assert pull_env["TMPDIR"] == str(tmp_path / "cache" / "qrosetta" / "tmp")
    assert (tmp_path / "cache" / "qrosetta" / "tmp").is_dir()
    assert doc["data"]["pulled"][0]["id"] == "qiskit" and doc["data"]["failed"] == []
    assert run(["pull", "--core"], env, fake) == 0
    assert sorted(c[2] for c in calls(fake, ["pull"])) == sorted(refs.values())
    assert run(["pull", "--all"], env, fake) == 0
    assert len(calls(fake, ["pull"])) == 3
    assert "already present" in capsys.readouterr().err
    assert run(["status", "--json"], env, fake) == 0
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["data"]["services"]}
    assert {k: rows[k]["image"]["state"] for k in IDS} == {k: "pulled" for k in IDS}
    assert run(["remove", "--images"], env, fake) == 0
    assert fake.commands("rmi") == [["rmi", IDS["nginx"], IDS["api"], IDS["qiskit"]]]


def test_pull_without_a_target_is_a_usage_error_and_myqlm_is_never_pulled(env, installed, capsys):
    fake = registry_engine()
    assert run(["pull"], env, fake) == Exit.USAGE
    assert capsys.readouterr().err.strip().splitlines()[-1].strip() == "qrosetta pull --profile minimal"
    assert run(["pull", "myqlm", "--json"], env, fake) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["data"]["not_published"][0]["id"] == "myqlm" and not calls(fake, ["pull"])


def test_pull_retries_once_after_a_network_error_and_never_after_a_missing_image(env, installed, capsys):
    fake = registry_engine()
    fake.pull_errors = ["Error: reading blob: toomanyrequests: retry later"]
    assert run(["pull", "api"], env, fake) == 0
    captured = capsys.readouterr()
    assert len(calls(fake, ["pull"])) == 2 and "retrying" in captured.err
    assert captured.out.splitlines()[-1] == "Next step:  qrosetta start -d"
    fake = registry_engine()
    fake.pull_errors = ["dial tcp: i/o timeout", "dial tcp: i/o timeout"]
    assert run(["pull", "api"], env, fake) == Exit.ENGINE
    assert len(calls(fake, ["pull"])) == 2
    err = capsys.readouterr().err.splitlines()
    head = err.index("qrosetta: 1 of 1 images were not pulled.")
    assert err[head + 2].startswith("  api: pulling ") and err[head + 2].endswith("dial tcp: i/o timeout")
    assert err[-2:] == ["Pull them again once the cause is resolved:", "  qrosetta pull api"]
    fake = registry_engine()
    fake.registry.clear()
    assert run(["pull", "api"], env, fake) == Exit.ENGINE
    err = capsys.readouterr().err
    assert len(calls(fake, ["pull"])) == 1 and "qrosetta images load DIR" in err


def test_a_pulled_image_labelled_for_another_service_fails(env, installed, capsys):
    fake = registry_engine()
    ref = mf.published_refs(release_manifest())["qiskit"]
    fake.registry[ref]["labels"] = image_labels("api")
    assert run(["pull", "qiskit"], env, fake) == Exit.ENGINE
    assert "labelled org.qrosetta.service='api', not qiskit_runner" in capsys.readouterr().err


def test_cosign_runs_before_the_pull_and_a_rejected_signature_pulls_nothing(env, installed, monkeypatch, capsys):
    installed(release_manifest(signed=True))
    monkeypatch.setattr(signatures, "cosign_path", lambda env: "/opt/bin/cosign")
    fake = registry_engine()
    assert run(["pull", "qiskit"], env, fake) == 0
    ref = mf.published_refs(release_manifest())["qiskit"]
    assert fake.cosign_calls == [["/opt/bin/cosign", "verify", "--certificate-identity", SIGNER,
                                  "--certificate-oidc-issuer", mf.OIDC_ISSUER, ref]]
    fake = registry_engine()
    fake.cosign = (10, "", "Error: no matching signatures: ...")
    assert run(["pull", "qiskit"], env, fake) == Exit.ENGINE
    assert not calls(fake, ["pull"]) and "signature not verified" in capsys.readouterr().err
    fake = registry_engine()
    fake.cosign = (1, "", "Error: Get https://ghcr.io/v2/: dial tcp: lookup ghcr.io: no such host")
    assert run(["pull", "qiskit"], env, fake) == 0
    assert "signature not checked" in capsys.readouterr().err
    assert run(["pull", "qiskit", "--require-signature"], env, fake) == 0
    assert "already present" in capsys.readouterr().err


def test_require_signature_without_cosign_or_signer_pulls_nothing(env, installed, capsys):
    installed(release_manifest(signed=True))
    fake = registry_engine()
    assert run(["pull", "api", "--require-signature"], env, fake) == Exit.ENGINE
    assert not calls(fake, ["pull"]) and "cosign is not installed" in capsys.readouterr().err
    installed(release_manifest())
    assert run(["pull", "api", "--require-signature"], env, fake) == Exit.ENGINE
    assert not calls(fake, ["pull"]) and "names no signing workflow" in capsys.readouterr().err


def test_pull_refuses_while_runs_are_in_flight_unless_yes(env, installed, capsys):
    fake = registry_engine()
    assert run(["pull", "api", "nginx"], env, fake) == 0
    fake.add("rosetta-api", ours("api"))
    fake.add("nginx-reverse-proxy", ours("nginx"))
    fake.port = "127.0.0.1:8080"
    release = release_manifest()
    release["services"]["nginx"]["compose"]["ports"] = [{"target": 80, "published": "8080"}]
    installed(release)
    assert run(["pull", "qiskit"], env, fake, server=FakeServer(gate=BUSY)) == Exit.BUSY
    assert len(calls(fake, ["pull"])) == 2
    assert run(["pull", "qiskit", "--yes"], env, fake, server=FakeServer(gate=BUSY)) == 0
    assert len(calls(fake, ["pull"])) == 3
    assert_never_destructive(fake)


# --- images list and verify ------------------------------------------------------------------


def checkout_engine():
    """This stack's images built here, with the identity step, beside decoys under its tags."""
    f = FakeEngine()
    f.add_image("i-nginx", ["localhost/qr-nginx:latest"], image_labels("nginx"))
    f.add_image("i-api", ["localhost/qr-api:latest"], image_labels("api"), size=700)
    f.add_image("i-qiskit", ["localhost/qr-qiskit_runner:latest"], image_labels("qiskit_runner"),
                identity=("built_locally", ""))
    f.add_image("i-braket", ["localhost/qr-braket_runner:latest", "registry.example/team/braket:1"],
                image_labels("braket_runner"), identity=("built_locally", ""))
    f.add_image("i-foreign", ["docker.io/library/postgres:16"], {})
    return f


def test_images_lists_states_and_ownership(env, project, capsys):
    fake = checkout_engine()
    assert run(["images", "--json"], env, fake, checkout=project) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    rows = {r["id"]: r for r in doc["data"]["images"]}
    assert rows["qiskit"]["state"] == "built" and rows["qiskit"]["owned"] is True
    assert rows["braket"]["owned"] is False
    assert run(["images", "ls"], env, fake, checkout=project) == 0
    out = capsys.readouterr().out
    assert "not this stack's: is also tagged registry.example/team/braket:1" in out
    assert_never_destructive(fake)


def test_verify_reads_inspect_data_only_and_fails_on_missing_identity_or_foreign_image(env, project, capsys):
    fake = checkout_engine()
    assert run(["images", "verify", "qiskit", "--json"], env, fake, checkout=project) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    checks = {c["check"]: c for c in doc["data"]["images"][0]["checks"]}
    assert checks["identity"]["status"] == "PASS" and "source=built_locally" in checks["identity"]["detail"]
    assert set(checks) == {"labels", "commit", "identity"}
    assert run(["images", "verify", "--json"], env, fake, checkout=project) == Exit.ENGINE
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    assert doc["data"]["failed"] == ["braket"]
    fake.images["i-qiskit"]["History"] = ["/bin/sh -c #(nop)  CMD [\"python\"]"]
    assert run(["images", "verify", "qiskit"], env, fake, checkout=project) == Exit.ENGINE
    assert "no build step wrote /usr/local/share/qrosetta-image/identity" in capsys.readouterr().out
    fake.images["i-qiskit"]["History"] = [identity_step("built_locally", "", "other1")]
    assert run(["images", "verify", "qiskit"], env, fake, checkout=project) == Exit.ENGINE
    assert "identity commit other1 differs from the baked abc123" in capsys.readouterr().out
    assert run(["images", "verify", "--require-signature"], env, fake, checkout=project) == Exit.USAGE
    assert_never_destructive(fake)
    assert not any(c[1] in ("run", "create", "start") for c, _ in fake.calls)


def test_verify_in_installed_mode_checks_digest_release_commit_and_signature(env, installed, monkeypatch, capsys):
    fake = registry_engine()
    assert run(["pull", "--all"], env, fake) == 0
    capsys.readouterr()
    assert run(["images", "verify", "--json"], env, fake) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    by_id = {e["id"]: {c["check"]: c["status"] for c in e["checks"]} for e in doc["data"]["images"]}
    assert by_id["qiskit"] == {"labels": "PASS", "commit": "PASS", "identity": "PASS", "release": "PASS",
                               "signature": "SKIP"}
    assert by_id["api"]["release"] == "PASS" and "identity" not in by_id["api"]
    assert run(["images", "verify", "--require-signature"], env, fake) == Exit.ENGINE
    installed(release_manifest(signed=True))
    monkeypatch.setattr(signatures, "cosign_path", lambda env: "/opt/bin/cosign")
    assert run(["images", "verify", "--require-signature"], env, fake) == 0
    capsys.readouterr()
    fake.images[IDS["qiskit"]]["History"] = [identity_step("release", "9.9.8", "abc123")]
    assert run(["images", "verify", "qiskit"], env, fake) == Exit.ENGINE
    assert "release 9.9.8, not 9.9.9" in capsys.readouterr().out
    fake.images[IDS["api"]]["Config"]["Env"] = ["QROSETTA_IMAGE_GIT_SHA=abc123", "QROSETTA_VERSION=1.0.0"]
    assert run(["images", "verify", "api"], env, fake) == Exit.ENGINE
    assert "QROSETTA_VERSION=1.0.0, release 9.9.9" in capsys.readouterr().out


def test_identity_is_parsed_from_podman_and_buildkit_history():
    podman = identity_step("release", "2.0.0", "0fd4435")
    buildkit = ("RUN |3 QROSETTA_GIT_SHA=0fd4435 QROSETTA_IMAGE_SOURCE=release QROSETTA_RELEASE=2.0.0 /bin/sh -c "
                "mkdir -p /usr/local/share/qrosetta-image && printf '...' > /usr/local/share/qrosetta-image/identity "
                "# buildkit")
    for step in (podman, buildkit):
        assert archive.identity_from_history(["CMD", step]) == {"source": "release", "release": "2.0.0",
                                                                 "git_sha": "0fd4435"}
    empty = identity_step("built_locally", "", "1fe3b11")
    assert archive.identity_from_history([empty]) == {"source": "built_locally", "release": None,
                                                     "git_sha": "1fe3b11"}
    assert archive.identity_from_history(["/bin/sh -c pip install x"]) is None


def test_identity_is_read_past_a_build_argument_whose_value_has_spaces():
    step = ("RUN |7 DEBIAN_SNAPSHOT=20261020T213255Z STAQ_VERSION=3.5 STAQ_SHA256=8384 "
            "STAQ_CXXFLAGS=-std=c++17 -O2 -DNDEBUG -DUSE_OPENQASM2_SPECS=false "
            "QROSETTA_GIT_SHA=ac7a091 QROSETTA_IMAGE_SOURCE=release QROSETTA_RELEASE=2.0.0rc2 /bin/sh -c "
            "mkdir -p /usr/local/share/qrosetta-image && printf 'source=%s' \"$QROSETTA_IMAGE_SOURCE\" "
            "> /usr/local/share/qrosetta-image/identity")
    assert archive.identity_from_history([step]) == {"source": "release", "release": "2.0.0rc2",
                                                     "git_sha": "ac7a091"}


# --- save and load ---------------------------------------------------------------------------


def test_save_writes_only_this_stacks_images_and_load_restores_them(env, project, tmp_path, capsys):
    fake = checkout_engine()
    fake.add_image("i-api-foreign", ["localhost/qr-api:old"], image_labels("api", "myapp"))
    out = tmp_path / "archives"
    assert run(["images", "save", "-o", str(out), "--json"], env, fake, checkout=project) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    index = json.loads((out / archive.INDEX).read_text())
    assert index["schema"] == archive.SCHEMA and index["project"] == "qr"
    assert sorted(e["service"] for e in index["images"]) == ["api", "nginx", "qiskit"]
    assert sorted(c[-1] for c in calls(fake, ["save"])) == ["i-api", "i-nginx", "i-qiskit"]
    assert [d["ref"] for d in doc["data"]["not_saved"]] == ["qr-braket_runner"]
    assert all(e["sha256"] == archive.sha256_file(out / e["file"]) for e in index["images"])
    save_env = next(e for c, e in fake.calls if c[1] == "save")
    assert save_env["TMPDIR"] == str(tmp_path / "cache" / "qrosetta" / "tmp")
    assert run(["images", "save", "-o", str(out)], env, fake, checkout=project) == Exit.USAGE

    other = FakeEngine()
    other.add_image("i-mine", ["localhost/qr-nginx:latest"], image_labels("nginx"))
    assert run(["images", "load", str(out), "--json"], env, other, checkout=project) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    assert sorted(e["id"] for e in doc["data"]["loaded"]) == ["api", "nginx", "qiskit"]
    tags = {t: i["Id"] for i in other.images.values() for t in i["RepoTags"]}
    assert set(tags) == {"qr-nginx", "qr-api", "qr-qiskit_runner"}
    assert other.images["i-mine"]["RepoTags"] == []
    assert run(["images", "verify", "qiskit"], env, other, checkout=project) == 0
    assert_never_destructive(fake)
    assert_never_destructive(other)


def _archive_dir(tmp_path, entries):
    out = tmp_path / "arch"
    out.mkdir(exist_ok=True)
    images = []
    for service, compose_service, labels, identity in entries:
        config = {"config": {"Labels": labels, "Env": ["QROSETTA_IMAGE_GIT_SHA=abc123"]},
                  "history": [{"created_by": identity_step(*identity, "abc123")}]}
        digest = write_archive(out / f"{service}.tar", config)
        images.append({"service": service, "compose_service": compose_service, "file": f"{service}.tar",
                       "image_id": "sha256:" + digest, "config_digest": "sha256:" + digest, "git_sha": "abc123",
                       "digest": None, "sha256": archive.sha256_file(out / f"{service}.tar")})
    archive.write_index(str(out), {"schema": archive.SCHEMA, "project": "qr", "images": images})
    return out, images


def test_load_refuses_unknown_services_other_projects_altered_files_and_held_tags(env, project, tmp_path, capsys):
    out, images = _archive_dir(tmp_path, [
        ("qiskit", "qiskit_runner", image_labels("qiskit_runner"), ("built_locally", "")),
        ("nosuch", "nosuch_runner", image_labels("nosuch_runner"), ("built_locally", "")),
        ("api", "api", image_labels("api", "myapp"), ("built_locally", "")),
        ("nginx", "nginx", image_labels("api"), ("built_locally", ""))])
    fake = FakeEngine()
    fake.add_image("i-foreign", ["localhost/qr-qiskit_runner:latest"], {})
    assert run(["images", "load", str(out), "--json"], env, fake, checkout=project) == Exit.ENGINE
    doc = json.loads(capsys.readouterr().out)
    reasons = {f["id"]: f["message"] for f in doc["data"]["failed"]}
    assert "not a service of this stack" in reasons["nosuch"]
    assert "labelled for compose project 'myapp', not 'qr'" in reasons["api"]
    assert "labelled org.qrosetta.service='api', not nginx" in reasons["nginx"]
    assert "qrosetta leaves it alone" in reasons["qiskit"]
    assert not calls(fake, ["load"]) and not calls(fake, ["tag"])
    assert fake.images["i-foreign"]["RepoTags"] == ["localhost/qr-qiskit_runner:latest"]
    with open(out / "qiskit.tar", "ab") as fh:
        fh.write(b"\0" * 512)
    del fake.images["i-foreign"]
    assert run(["images", "load", str(out), "qiskit"], env, fake, checkout=project) == Exit.ENGINE
    assert "does not have the sha256 its index records" in capsys.readouterr().err
    assert run(["images", "load", str(tmp_path / "nothing")], env, fake, checkout=project) == Exit.NOT_FOUND
    assert_never_destructive(fake)


def test_installed_load_checks_the_release_image_id_and_status_then_shows_loaded(env, installed, tmp_path,
                                                                                  capsys):
    out, images = _archive_dir(tmp_path, [
        ("qiskit", "qiskit_runner", image_labels("qiskit_runner"), ("release", "9.9.9")),
        ("api", "api", image_labels("api"), ("release", "9.9.9"))])
    ids = {e["service"]: e["config_digest"] for e in images}
    fake = registry_engine()
    installed(release_manifest())
    assert run(["images", "load", str(out), "qiskit"], env, fake) == Exit.ENGINE
    assert "records no image id for qiskit" in capsys.readouterr().err and not calls(fake, ["load"])
    installed(release_manifest(image_ids={"qiskit": ids["qiskit"], "api": "sha256:" + "f" * 64}))
    assert run(["images", "load", str(out), "--json"], env, fake) == Exit.ENGINE
    doc = json.loads(capsys.readouterr().out)
    assert [e["id"] for e in doc["data"]["loaded"]] == ["qiskit"]
    assert "is not the one release 9.9.9 records" in doc["data"]["failed"][0]["message"]
    assert [c[3] for c in calls(fake, ["tag"])] == ["qr-qiskit_runner:9.9.9"]
    assert run(["status", "--json"], env, fake) == 0
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["data"]["services"]}
    assert rows["qiskit"]["image"]["state"] == "loaded" and rows["qiskit"]["image"]["release"] == "9.9.9"
    assert rows["api"]["image"]["state"] == "missing"
    generated = json.loads((tmp_path / "state" / "qrosetta" / "compose.yaml").read_text().split("\n", 1)[1])
    assert generated["services"]["qiskit_runner"]["image"] == "qr-qiskit_runner:9.9.9"
    assert generated["services"]["api"]["image"] == mf.published_refs(release_manifest())["api"]
    assert run(["remove", "--images"], env, fake) == 0
    assert [c[2:] for c in calls(fake, ["rmi"])] == [[ids["qiskit"].split(":")[1]]]
    assert not [d for d in fake.destructive_calls() if d[0] != "rmi"]


def test_a_tag_on_a_foreign_image_is_never_used_as_a_loaded_release_image(env, installed, tmp_path, capsys):
    installed(release_manifest(image_ids={"qiskit": "sha256:" + "9" * 64}))
    fake = registry_engine()
    fake.add_image("i-impostor", ["localhost/qr-qiskit_runner:9.9.9"], image_labels("qiskit_runner"))
    assert run(["status", "--json"], env, fake) == 0
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["data"]["services"]}
    assert rows["qiskit"]["image"]["state"] == "missing"
    generated = json.loads((tmp_path / "state" / "qrosetta" / "compose.yaml").read_text().split("\n", 1)[1])
    assert generated["services"]["qiskit_runner"]["image"] == mf.published_refs(release_manifest())["qiskit"]


@pytest.mark.parametrize("argv", [["images"], ["images", "verify"], ["images", "save", "-o", "ARCH"],
                                  ["images", "load", "ARCH"]])
def test_image_commands_never_touch_decoys(env, project, tmp_path, argv):
    fake = checkout_engine()
    decoys = {"i-braket", "i-foreign"}
    fake.add_image("i-other-project", ["localhost/myapp-api:latest"], image_labels("api", "myapp"))
    decoys.add("i-other-project")
    if argv[1:2] == ["load"]:
        _archive_dir(tmp_path, [("qiskit", "qiskit_runner", image_labels("qiskit_runner"), ("built_locally", ""))])
        argv = ["images", "load", str(tmp_path / "arch")]
    argv = [str(tmp_path / "out") if a == "ARCH" else a for a in argv]
    run(argv, env, fake, checkout=project)
    assert_never_destructive(fake)
    for cmd, _ in fake.calls:
        if cmd[1] in ("save", "tag"):
            assert not set(cmd) & decoys, cmd
    assert {d: fake.images[d]["RepoTags"] for d in decoys} == {
        "i-braket": ["localhost/qr-braket_runner:latest", "registry.example/team/braket:1"],
        "i-foreign": ["docker.io/library/postgres:16"], "i-other-project": ["localhost/myapp-api:latest"]}


def test_pull_never_touches_decoys(env, installed):
    fake = registry_engine()
    fake.add_image("i-other", ["localhost/myapp-qiskit_runner:9.9.9"], image_labels("qiskit_runner", "myapp"))
    fake.add_image("i-stray", [], {own.QR_SERVICE: "api"}, digests=[f"{REGISTRY}/qrosetta-x@sha256:{'c' * 64}"])
    assert run(["pull", "--all"], env, fake) == 0
    assert_never_destructive(fake)
    assert all(c[2].startswith(f"{REGISTRY}/qrosetta-") and "@sha256:" in c[2] for c in calls(fake, ["pull"]))
    assert fake.images["i-other"]["RepoTags"] == ["localhost/myapp-qiskit_runner:9.9.9"] and "i-stray" in fake.images
