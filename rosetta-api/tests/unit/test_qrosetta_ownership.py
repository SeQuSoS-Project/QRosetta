"""qrosetta never acts on what is not this stack's: decoy containers, networks, volumes, images
and pods on a fake engine, and a static check that destructive engine calls get their targets
only from the ownership scan."""

import ast
import json

import pytest

from tests.unit._qrosetta_fake import REPO, FakeEngine, FakeServer, Unreachable, image_labels, ours, release_manifest

from qrosetta_cli import manifest as mf  # noqa: E402
from qrosetta_cli import mode as modes  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from qrosetta_cli.stack import ownership as own  # noqa: E402
from qrosetta_cli.stack import serve  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402

PROJECT_ONLY = {own.PROJECT_LABEL: "qr"}


class Lines:
    def __init__(self, text):
        self.text = text

    def readline(self):
        line, _, self.text = self.text.partition("\n")
        return line + "\n" if line else ""

    def isatty(self):
        return True


def decoyed(volume_is_foreign=False):
    """This stack plus decoys; returns (fake engine, set of decoy ids and names)."""
    f = FakeEngine()
    f.add("rosetta-api", ours("api"))
    f.add("nginx-reverse-proxy", ours("nginx"), running=False)
    f.add("braket-runner", ours("braket_runner"), pod="mixed")
    f.add_network("qr_isolated_net", {own.PROJECT_LABEL: "qr", own.QR_LABEL: "qr"})
    f.add_image("i-qiskit", ["localhost/qr-qiskit_runner:latest"], image_labels("qiskit_runner"))
    decoys = {
        f.add("qiskit-runner", {own.PROJECT_LABEL: "myapp", own.QR_LABEL: "myapp", own.SERVICE_LABEL: "qiskit_runner"}),
        f.add("intruder", {}, pod="mixed"), "mixed", "pod-mixed",
        f.add("pedantic_noyce", {}),
        f.add("api-by-hand", dict(PROJECT_ONLY, **{own.SERVICE_LABEL: "api"})),
        f.add("myapp-web", {own.PROJECT_LABEL: "myapp", own.SERVICE_LABEL: "web"}),
    }
    for name, labels in (("qr_public_net", PROJECT_ONLY), ("myapp_default", {own.PROJECT_LABEL: "myapp", own.QR_LABEL: "myapp"}),
                         ("podman", {})):
        f.add_network(name, labels)
        decoys |= {name, "n-" + name}
    if volume_is_foreign:
        f.add_volume("qr_db", {})
    else:
        f.add_volume("qr_db", {own.PROJECT_LABEL: "qr", own.VOLUME_LABEL: "db"})
    f.add_volume("myapp_db", {own.PROJECT_LABEL: "myapp", own.VOLUME_LABEL: "db"})
    decoys |= {"myapp_db"} | ({"qr_db"} if volume_is_foreign else set())
    f.add_image("i-foreign-api", ["localhost/qr-api:latest"], {})
    f.add_image("i-nginx-shared", ["localhost/qr-nginx:latest", "registry.example/team/nginx:1"], image_labels("nginx"))
    f.add_image("i-wrong-service", ["localhost/qr-braket_runner:latest"], image_labels("api"))
    f.add_image("i-postgres", ["docker.io/library/postgres:16"], {})
    f.extra_services = {"db": {"container_name": "", "image": "postgres:16"}}
    decoys |= {"i-foreign-api", "i-nginx-shared", "i-wrong-service", "i-postgres"}
    return f, decoys


def run(f, project, argv, tmp_path, server=None, answer="qr\n"):
    (project / ".env").write_text("COMPOSE_PROJECT_NAME=myapp\n")
    env = {"QROSETTA_PROJECT": "qr", "COMPOSE_PROJECT_NAME": "myapp", "COMPOSE_FILE": "evil.yml",
           "QROSETTA_TOKEN": "secret", "HOME": str(tmp_path), "XDG_RUNTIME_DIR": str(tmp_path / "run"),
           "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "config")}
    return main(argv, checkout=str(project), env=env, tty=True, stdin=Lines(answer),
                engine_factory=lambda d: Engine(f.engine, d, run=f, popen=f.popen, env=env),
                transport_factory=server or Unreachable())


def check_calls(f, decoys):
    names = {"nginx-reverse-proxy", "rosetta-api", "qiskit-runner", "braket-runner"}
    for cmd, env in f.calls:
        args = cmd[1:]
        assert "prune" not in args and "--all" not in args, args
        assert not any(k.startswith("COMPOSE_") for k in env), env
        assert "QROSETTA_TOKEN" not in env, env
        if args[0] == "compose":
            assert args[1:3] == ["-p", "qr"], args
            continue
        if "-a" in args:
            assert args[0] == "ps", args
        if args[0] == "ps":
            filters = [args[i + 1] for i, a in enumerate(args) if a == "--filter"]
            assert filters == [f"label={own.PROJECT_LABEL}=qr"] or (
                filters and all(x.startswith("name=") and x[5:] in names for x in filters)), args
        if args[:2] == ["network", "ls"]:
            assert f"label={own.PROJECT_LABEL}=qr" in args, args
    for args in f.destructive_calls():
        assert not set(args) & decoys, args


@pytest.fixture
def project(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path


BUSY = {"exclusive_running": False, "exclusive_waiting": 0, "shared_running": 3}


@pytest.mark.parametrize("argv,busy", [
    (["stop"], False), (["stop", "--force"], True), (["remove"], False), (["rm"], False),
    (["remove", "--images"], False), (["remove", "--data"], False), (["remove", "--data", "--confirm", "qr"], False),
    (["remove", "--images", "--data", "--confirm", "qr", "--force"], True), (["status"], False),
    (["status", "--json"], False)])
def test_no_decoy_is_ever_targeted(project, tmp_path, capsys, argv, busy):
    f, decoys = decoyed()
    server = FakeServer(gate=BUSY) if busy else None
    expected = Exit.ENGINE if argv[0] == "stop" else Exit.OK
    assert run(f, project, argv, tmp_path, server=server) == expected
    check_calls(f, decoys)
    present = set(f.containers) | set(f.networks) | set(f.volumes) | set(f.images) | set(f.pods)
    assert {d for d in decoys if d.startswith(("c-", "n-", "i-")) or d in ("myapp_db", "mixed")} <= present
    err = capsys.readouterr().err
    if argv[0] in ("remove", "rm"):
        assert "c-rosetta-api" not in f.containers and "c-braket-runner" not in f.containers
        assert "Pod pod-mixed also holds containers that are not this stack's (intruder)" in err
    if "--images" in argv:
        assert f.commands("rmi") == [["rmi", "i-qiskit"]]
        assert "qr-api has no qrosetta label" in err and "is also tagged registry.example/team/nginx:1" in err
        assert "postgres:16 has no qrosetta label" in err
        hint = next(line for line in err.splitlines() if "yourself" in line)
        assert sorted(hint.split("rmi ")[1].split()) == ["qr-api", "qr-braket_runner", "qr-nginx"]
    if "--data" in argv:
        assert "qr_db" not in f.volumes


@pytest.mark.parametrize("argv", [["stop"], ["remove", "--images", "--data", "--confirm", "qr"]])
def test_refusal_while_runs_are_in_flight_touches_nothing(project, tmp_path, argv):
    f, decoys = decoyed()
    assert run(f, project, argv, tmp_path, server=FakeServer(gate=BUSY)) == Exit.BUSY
    check_calls(f, decoys)
    assert not f.destructive_calls()


def test_a_wrong_confirmation_deletes_nothing(project, tmp_path):
    f, decoys = decoyed()
    assert run(f, project, ["remove", "--data"], tmp_path, answer="yes\n") == Exit.USAGE
    assert run(f, project, ["remove", "--data", "--confirm", "myapp"], tmp_path) == Exit.USAGE
    assert not f.destructive_calls() and "qr_db" in f.volumes


def test_foreign_volume_with_this_stacks_volume_name_is_never_deleted(project, tmp_path, capsys):
    f, decoys = decoyed(volume_is_foreign=True)
    assert run(f, project, ["remove", "--data", "--confirm", "qr"], tmp_path) == 0
    check_calls(f, decoys)
    assert "qr_db" in f.volumes and not f.commands("volume", "rm")
    assert "compose did not create for this project: qr_db" in capsys.readouterr().err


def test_start_refuses_and_touches_nothing_while_decoys_hold_its_names(project, tmp_path, capsys):
    f, decoys = decoyed()
    assert run(f, project, ["start", "--detach"], tmp_path) == Exit.ENGINE
    check_calls(f, decoys)
    assert not f.destructive_calls()
    err = capsys.readouterr().err
    assert "qiskit-runner (project myapp, running)" in err and "api-by-hand" in err


def stale_with_decoys(running=True):
    """This stack with every container on an image its tag no longer holds, beside containers of
    another project and an unlabelled one created from the same old images."""
    f = FakeEngine().standard()
    f.add("qiskit-runner", ours("qiskit_runner"), image="i-qiskit")
    for c in f.containers.values():
        c["State"]["Running"] = running
    decoys = {
        f.add("myapp-api", {own.PROJECT_LABEL: "myapp", own.QR_LABEL: "myapp", own.SERVICE_LABEL: "api"},
              image="i-api"),
        f.add("myapp-qiskit", {own.PROJECT_LABEL: "myapp", own.SERVICE_LABEL: "qiskit_runner"}, image="i-qiskit"),
        f.add("pedantic_noyce", {}, image="i-nginx"),
    }
    for service in ("nginx", "api", "qiskit_runner"):
        f.rebuild(service, "j-" + service)
    return f, decoys


@pytest.mark.parametrize("argv,running", [(["start", "-d", "--yes"], True), (["start", "-d"], False),
                                          (["start", "--on-exit", "standby", "--yes"], True)])
def test_start_recreates_only_this_stacks_containers(project, tmp_path, monkeypatch, argv, running):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    monkeypatch.setattr(serve.Server, "_follow", lambda self: 0)
    f, decoys = stale_with_decoys(running)
    server = FakeServer(gate=BUSY if running else None, fresh=True)
    assert run(f, project, argv, tmp_path, server=server) == Exit.OK
    check_calls(f, decoys)
    assert not f.destructive_calls()
    recreate = [c for c, _ in f.calls if "--force-recreate" in c]
    assert len(recreate) == 1 and recreate[0][-3:] == ["nginx", "api", "qiskit_runner"]
    assert sorted(f.recreated) == ["c-nginx-reverse-proxy", "c-qiskit-runner", "c-rosetta-api"]
    assert {f.containers[d]["Image"] for d in decoys} == {"i-api", "i-qiskit", "i-nginx"}
    assert all(f.containers[d]["State"]["Running"] for d in decoys)


def test_start_recreates_nothing_while_an_unlabelled_container_of_the_project_runs_an_old_image(project, tmp_path):
    f, decoys = stale_with_decoys()
    decoys.add(f.add("api-by-hand", dict(PROJECT_ONLY, **{own.SERVICE_LABEL: "api"}), image="i-api"))
    assert run(f, project, ["start", "-d", "--yes"], tmp_path, server=FakeServer(fresh=True)) == Exit.ENGINE
    check_calls(f, decoys)
    assert not f.compose_calls("up") and not f.recreated and not f.destructive_calls()


def test_start_recreates_on_a_changed_configuration_only_this_stacks_containers(project, tmp_path, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    f = FakeEngine().standard()
    f.containers.clear()
    assert run(f, project, ["start", "-d"], tmp_path, server=FakeServer(fresh=True)) == Exit.OK
    stale = {own.CONFIG_HASH_LABEL: "0" * 64}
    decoys = {
        f.add("myapp-api", {own.PROJECT_LABEL: "myapp", own.QR_LABEL: "myapp", own.SERVICE_LABEL: "api", **stale}),
        f.add("myapp-qiskit", {own.PROJECT_LABEL: "myapp", own.SERVICE_LABEL: "qiskit_runner", **stale}),
        f.add("pedantic_noyce", {own.SERVICE_LABEL: "nginx", **stale}),
    }
    f.calls.clear()
    f.recreated.clear()
    assert run(f, project, ["start", "-d", "--yes"], tmp_path, server=FakeServer(gate=BUSY, fresh=True)) == Exit.OK
    assert not f.compose_calls("up") and not f.recreated
    f.edit_config("api")
    assert run(f, project, ["start", "-d", "--yes"], tmp_path, server=FakeServer(gate=BUSY, fresh=True)) == Exit.OK
    check_calls(f, decoys)
    assert not f.destructive_calls() and f.recreated == ["c-rosetta-api"]
    assert all(f.containers[d]["Config"]["Labels"][own.CONFIG_HASH_LABEL] == "0" * 64 for d in decoys)
    decoys.add(f.add("api-by-hand", dict(PROJECT_ONLY, **{own.SERVICE_LABEL: "api"}, **stale)))
    f.edit_config("qiskit_runner")
    assert run(f, project, ["start", "-d", "--yes"], tmp_path, server=FakeServer(fresh=True)) == Exit.ENGINE
    check_calls(f, decoys)
    assert f.recreated == ["c-rosetta-api"] and not f.destructive_calls()


def test_status_compares_only_this_stacks_containers_with_their_tags(project, tmp_path, capsys):
    f, decoys = stale_with_decoys()
    assert run(f, project, ["status", "--json"], tmp_path) == Exit.OK
    check_calls(f, decoys)
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["data"]["services"]}
    assert {k: rows[k]["container_image"]["image_id"] for k in ("nginx", "api", "qiskit")} == {
        "nginx": "i-nginx", "api": "i-api", "qiskit": "i-qiskit"}
    assert {r["container"] for r in rows.values() if r["container_image"]} == {
        "nginx-reverse-proxy", "rosetta-api", "qiskit-runner"}


def test_foreground_exit_action_remove_touches_only_this_stack(project, tmp_path, monkeypatch):
    f, decoys = decoyed()
    env = {"QROSETTA_PROJECT": "qr", "HOME": str(tmp_path), "XDG_RUNTIME_DIR": str(tmp_path / "run")}
    engine = Engine(f.engine, str(project), run=f, popen=f.popen, env=env)
    from qrosetta_cli.stack import project as st
    stack = st.load_stack(engine)
    server = serve.Server(engine, stack, "remove", [], {}, tty=False)
    monkeypatch.setattr(server, "_follow", lambda: (_ for _ in ()).throw(serve.Interrupted(2)))
    assert server.run() == 0
    check_calls(f, decoys)
    assert "c-rosetta-api" not in f.containers and "c-pedantic_noyce" in f.containers


@pytest.mark.parametrize("argv", [["stop"], ["remove", "--images", "--data", "--confirm", "qr"], ["status"]])
def test_installed_mode_keeps_every_ownership_rule(project, tmp_path, monkeypatch, argv):
    monkeypatch.setattr(modes, "PACKAGE_PARENT", str(tmp_path / "site-packages"))
    monkeypatch.setattr(mf, "PATH", str(tmp_path / "manifest.json"))
    (tmp_path / "manifest.json").write_text(json.dumps(release_manifest()))
    f, decoys = decoyed()
    env = {"QROSETTA_PROJECT": "qr", "COMPOSE_PROJECT_NAME": "myapp", "COMPOSE_FILE": "evil.yml",
           "QROSETTA_TOKEN": "secret", "HOME": str(tmp_path), "XDG_RUNTIME_DIR": str(tmp_path / "run"),
           "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "config")}
    opened = []

    def factory(directory):
        opened.append(directory)
        return Engine(f.engine, directory, run=f, popen=f.popen, env=env)

    expected = Exit.ENGINE if argv[0] == "stop" else Exit.OK
    assert main(argv, checkout=None, env=env, tty=True, stdin=Lines("qr\n"), engine_factory=factory,
                transport_factory=Unreachable()) == expected
    assert opened == [str(tmp_path / "state" / "qrosetta")]
    check_calls(f, decoys)
    present = set(f.containers) | set(f.networks) | set(f.volumes) | set(f.images) | set(f.pods)
    assert {d for d in decoys if d.startswith(("c-", "n-", "i-")) or d in ("myapp_db", "mixed")} <= present


def test_act_refuses_targets_not_made_by_the_scan():
    with pytest.raises(RuntimeError):
        own.act(None, "container", "remove", [own.Target("container", "c-x", "x")])
    with pytest.raises(RuntimeError):
        own.act(None, "image", "remove", [own._target("container", "c-x", "x")])


def _source_calls():
    root = REPO / "qrosetta_cli"
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text())
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn, up = None, node
                while up in parents:
                    up = parents[up]
                    if isinstance(up, ast.FunctionDef):
                        fn = up.name
                        break
                yield path.relative_to(root).as_posix(), fn, node


def _const(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def test_destructive_engine_calls_take_targets_only_from_the_ownership_scan():
    destructive = {"stop", "kill", "rm", "rmi", "prune"}
    for module, fn, call in _source_calls():
        name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
        consts = [_const(a) for a in call.args]
        if name == "cli":
            if consts and consts[0] is not None:
                verbs = [c for c in consts[:2] if c]
                assert not set(verbs) & destructive, (module, fn, verbs)
            elif not (len(consts) > 1 and consts[1] == "inspect"):
                assert (module, fn) == ("stack/ownership.py", "act"), (module, fn)
        if name == "compose":
            assert consts and consts[0] in ("config", "port", "version"), (module, fn, consts)
        if name == "spawn":
            first = call.args[0]
            assert isinstance(first, ast.List) and _const(first.elts[0]) in ("up", "logs"), (module, fn)
        for arg in call.args:
            if isinstance(arg, ast.List):
                words = {_const(e) for e in arg.elts}
                assert not words & (destructive | {"down"}), (module, fn, words)
    engine_side = [p for p in (REPO / "qrosetta_cli").rglob("*.py") if "client" not in p.parts and p.name != "cli.py"]
    values = {_const(n) for p in engine_side for n in ast.walk(ast.parse(p.read_text()))}
    assert not {"prune", "--all", "down", "kill"} & values
    assert all("-a" not in cmd and "--all" not in cmd for cmd in own.COMMANDS.values())


def test_subprocess_is_used_only_by_the_engine_build_and_config_edit():
    allowed = {("stack/commands.py", "cmd_build"), ("commands.py", "cmd_config_edit")}
    for module, fn, call in _source_calls():
        f = call.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("subprocess", "os"):
            if f.attr in ("run", "call", "Popen", "check_call", "check_output", "system", "popen", "execv", "execvp"):
                assert (module, fn) in allowed, (module, fn, f.attr)
