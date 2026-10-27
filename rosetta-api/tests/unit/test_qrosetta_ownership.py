"""qrosetta never acts on what is not this stack's: decoy containers, networks, volumes, images
and pods on a fake engine, and a static check that destructive engine calls get their targets
only from the ownership scan."""

import ast
import sys

import pytest

from tests.unit._qrosetta_fake import REPO, FakeEngine, image_labels, ours

from qrosetta_cli import ownership as own  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.engine import Engine  # noqa: E402

PROJECT_ONLY = {own.PROJECT_LABEL: "qr"}
ENV = {"QROSETTA_PROJECT": "qr", "COMPOSE_PROJECT_NAME": "myapp", "COMPOSE_FILE": "evil.yml"}


class Tty:
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


def run(f, project, argv, monkeypatch, answer="delete"):
    (project / ".env").write_text("COMPOSE_PROJECT_NAME=myapp\n")
    monkeypatch.setattr("builtins.input", lambda q: answer)
    monkeypatch.setattr(sys, "stdin", Tty())
    return main(argv, checkout=str(project), engine_factory=lambda d: Engine(f.engine, d, run=f, env=ENV))


def check_calls(f, decoys):
    names = {"nginx-reverse-proxy", "rosetta-api", "qiskit-runner", "braket-runner"}
    for cmd, env in f.calls:
        args = cmd[1:]
        assert "prune" not in args and "--all" not in args, args
        assert not any(k.startswith("COMPOSE_") for k in env), env
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


@pytest.mark.parametrize("argv", [["stop"], ["remove"], ["remove", "--images"], ["remove", "--data"],
                                  ["remove", "--images", "--data"], ["status"]])
def test_no_decoy_is_ever_targeted(project, monkeypatch, capsys, argv):
    f, decoys = decoyed()
    run(f, project, argv, monkeypatch)
    check_calls(f, decoys)
    present = set(f.containers) | set(f.networks) | set(f.volumes) | set(f.images) | set(f.pods)
    assert {d for d in decoys if d.startswith(("c-", "n-", "i-")) or d in ("myapp_db", "mixed")} <= present
    out = capsys.readouterr().out
    if argv[0] == "remove":
        assert "c-rosetta-api" not in f.containers and "c-braket-runner" not in f.containers
        assert "Pod pod-mixed also holds containers that are not this stack's (intruder)" in out
    if "--images" in argv:
        assert f.commands("rmi") == [["rmi", "i-qiskit"]]
        assert "qr-api has no qrosetta label" in out and "is also tagged registry.example/team/nginx:1" in out
        assert "postgres:16 has no qrosetta label" in out
        hint = next(line for line in out.splitlines() if "yourself" in line)
        assert sorted(hint.split("rmi ")[1].split()) == ["qr-api", "qr-braket_runner", "qr-nginx"]
    if "--data" in argv:
        assert "qr_db" not in f.volumes


def test_foreign_volume_with_this_stacks_volume_name_is_never_deleted(project, monkeypatch, capsys):
    f, decoys = decoyed(volume_is_foreign=True)
    assert run(f, project, ["remove", "--data"], monkeypatch) == 0
    check_calls(f, decoys)
    assert "qr_db" in f.volumes and not f.commands("volume", "rm")
    assert "compose did not create for this project: qr_db" in capsys.readouterr().out


def test_start_refuses_and_touches_nothing_while_decoys_hold_its_names(project, monkeypatch, capsys):
    f, decoys = decoyed()
    assert run(f, project, ["start", "--detach"], monkeypatch) == 1
    check_calls(f, decoys)
    assert not f.destructive_calls()
    err = capsys.readouterr().err
    assert "qiskit-runner (project myapp, running)" in err and "api-by-hand" in err


def test_act_refuses_targets_not_made_by_the_scan():
    with pytest.raises(RuntimeError):
        own.act(None, "container", "remove", [own.Target("container", "c-x", "x")])
    with pytest.raises(RuntimeError):
        own.act(None, "image", "remove", [own._target("container", "c-x", "x")])


def _source_calls():
    for path in sorted((REPO / "qrosetta_cli").glob("*.py")):
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
                yield path.name, fn, node


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
                assert (module, fn) == ("ownership.py", "act"), (module, fn)
        if name == "compose":
            assert consts and consts[0] in ("config", "port", "version"), (module, fn, consts)
        if name == "spawn":
            first = call.args[0]
            assert isinstance(first, ast.List) and _const(first.elts[0]) in ("up", "logs"), (module, fn)
    values = {_const(n) for p in (REPO / "qrosetta_cli").glob("*.py") for n in ast.walk(ast.parse(p.read_text()))}
    assert not {"prune", "--all", "down", "kill"} & values
    assert set(own.COMMANDS.values().__iter__().__next__()) and all(
        "-a" not in cmd and "--all" not in cmd for cmd in own.COMMANDS.values())


def test_subprocess_is_used_only_by_the_engine_and_build():
    for module, fn, call in _source_calls():
        f = call.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("subprocess", "os"):
            if f.attr in ("run", "call", "Popen", "check_call", "check_output", "system", "popen", "execv", "execvp"):
                assert (module, fn) == ("cli.py", "cmd_build"), (module, fn, f.attr)
