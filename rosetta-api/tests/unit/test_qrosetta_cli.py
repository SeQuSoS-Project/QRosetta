"""qrosetta_cli lifecycle commands: argument handling, project selection, the engine commands
each subcommand runs, the stdout/stderr split and exit codes, against a fake engine and server."""

import json
import platform
import signal
import subprocess
from pathlib import Path

import pytest

from tests.unit._qrosetta_fake import REPO, FakeEngine, FakeServer, Unreachable, image_labels, ours

from qrosetta_cli import mode as modes  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402
from qrosetta_cli.stack import actions, serve  # noqa: E402
from qrosetta_cli.stack import ownership as own  # noqa: E402
from qrosetta_cli.stack import project as st  # noqa: E402
from qrosetta_cli.stack.engine import Engine, choose_engine, detect_engine, project_name  # noqa: E402


@pytest.fixture
def env(tmp_path):
    return {"QROSETTA_PROJECT": "qr", "PATH": "/usr/bin", "HOME": str(tmp_path / "home"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"), "XDG_CACHE_HOME": str(tmp_path / "cache")}


@pytest.fixture
def fake():
    return FakeEngine().standard()


@pytest.fixture
def project(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path


def make(fake, project, env, popen=None):
    engine = Engine(fake.engine, str(project), run=fake, popen=popen or fake.popen, env=env)
    return engine, st.load_stack(engine)


def cli(fake, project, env, argv, server=None, tty=False, stdin=None):
    return main(argv, checkout=str(project), env=env, tty=tty, stdin=stdin,
                engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env),
                transport_factory=server or Unreachable())


def test_project_dir_precedence(tmp_path, capsys):
    for name in ("flag", "env", "old", "checkout"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "docker-compose.yml").write_text("services: {}\n")
    env = {"QROSETTA_PROJECT_DIR": str(tmp_path / "env"), "QROSETTA_HOME": str(tmp_path / "old")}
    checkout = str(tmp_path / "checkout")
    assert modes.detect(str(tmp_path / "flag"), env, checkout).project_dir == str(tmp_path / "flag")
    assert modes.detect(None, env, checkout).project_dir == str(tmp_path / "env")
    found = modes.detect(None, {"QROSETTA_HOME": str(tmp_path / "old")}, checkout)
    assert found.project_dir == str(tmp_path / "old") and "QROSETTA_HOME is deprecated" in capsys.readouterr().err
    assert modes.detect(None, {}, checkout) == modes.Mode("checkout", checkout, "this checkout")
    with pytest.raises(CliError) as err:
        modes.detect(str(tmp_path), {}, None)
    assert err.value.code == Exit.USAGE and "No compose file" in err.value.message


def test_project_name_comes_from_qrosetta_project_only():
    assert project_name({}) == "qsimulators"
    assert project_name({"COMPOSE_PROJECT_NAME": "myapp"}) == "qsimulators"
    assert project_name({"QROSETTA_PROJECT": "dev2"}) == "dev2"
    with pytest.raises(CliError):
        project_name({"QROSETTA_PROJECT": "My App"})


def test_compose_calls_name_project_and_files_and_drop_compose_and_cli_variables(fake, project, env):
    (project / "docker-compose.override.yml").write_text("services: {}\n")
    (project / ".env").write_text("COMPOSE_PROJECT_NAME=myapp\nCOMPOSE_FILE=other.yml\n")
    env = dict(env, COMPOSE_PROJECT_NAME="myapp", COMPOSE_FILE="evil.yml", QROSETTA_TOKEN="secret-token",
               QROSETTA_SERVER="https://x", QROSETTA_ENGINE="podman")
    engine, stack = make(fake, project, env)
    assert stack.name == "qr"
    cmd, child = next((c, e) for c, e in fake.calls if c[1] == "compose")
    assert cmd[2:6] == ["-p", "qr", "--project-directory", str(project)]
    assert cmd[6:10] == ["-f", str(project / "docker-compose.yml"), "-f", str(project / "docker-compose.override.yml")]
    assert not any(k.startswith("COMPOSE_") for k in child) and child["QROSETTA_PROJECT"] == "qr"
    assert not {"QROSETTA_TOKEN", "QROSETTA_SERVER", "QROSETTA_ENGINE"} & set(child)


def test_a_different_reported_project_is_refused(fake, project, env):
    fake.config_name = "myapp"
    with pytest.raises(CliError, match="'myapp', not 'qr'"):
        make(fake, project, env)


def _engine_run(docker_info=0, podman_info=0, docker_is_podman=False):
    def run(cmd, **kw):
        if cmd[1:] == ["--version"]:
            text = "podman version 5.8.2\n" if docker_is_podman else "Docker version 27.0.1\n"
            return subprocess.CompletedProcess(cmd, 0, text, "")
        rc = docker_info if cmd[0].endswith("docker") else podman_info
        err = "permission denied while trying to connect to the Docker daemon socket" if rc else ""
        return subprocess.CompletedProcess(cmd, rc, "{}" if rc == 0 else "", err)
    return run


def test_engine_choice_is_the_first_whose_info_answers():
    both = {"docker": "/usr/bin/docker", "podman": "/usr/bin/podman"}.get
    assert detect_engine({}, both, _engine_run(docker_is_podman=True)) == "podman"
    assert detect_engine({}, both, _engine_run()) == "docker"
    choice = choose_engine({}, None, both, _engine_run(docker_info=1))
    assert choice.name == "podman" and choice.reason == "using podman (docker: permission denied for this user)"
    assert detect_engine({}, {"podman": "/usr/bin/podman"}.get, _engine_run()) == "podman"
    assert detect_engine({"QROSETTA_ENGINE": "docker"}, both, _engine_run(docker_is_podman=True)) == "docker"
    assert detect_engine({}, both, _engine_run(), configured="podman") == "podman"
    assert detect_engine({"QROSETTA_ENGINE": "docker"}, both, _engine_run(), configured="podman") == "docker"
    for kwargs in ({"which": {}.get}, {"which": {"docker": "/usr/bin/docker"}.get, "run": _engine_run(docker_info=1)}):
        with pytest.raises(CliError) as err:
            choose_engine({}, None, kwargs["which"], kwargs.get("run", _engine_run()))
        assert err.value.code == Exit.ENGINE and err.value.hint == "qrosetta doctor"
    with pytest.raises(CliError) as err:
        detect_engine({"QROSETTA_ENGINE": "lxc"}, both, _engine_run())
    assert err.value.code == Exit.USAGE


def test_compose_v1_or_podman_compose_is_refused_with_install_steps(project, env):
    run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "podman-compose version 1.2.0\n", "")
    ubuntu = lambda: "ID=ubuntu\nID_LIKE=debian\n"
    with pytest.raises(CliError, match="Docker Compose v2.*podman-compose version 1.2.0.*docker-compose-v2") as err:
        Engine("podman", str(project), run=run, env=env, os_release=ubuntu).check_compose()
    assert err.value.code == Exit.ENGINE


def test_exit_action_defaults():
    assert serve.exit_action(None, {}, tty=True) == "ask"
    assert serve.exit_action(None, {}, tty=False) == "standby"
    assert serve.exit_action("ask", {}, tty=False) == "standby"
    assert serve.exit_action(None, {"QROSETTA_ON_EXIT": "remove"}, tty=True) == "remove"
    assert serve.exit_action(None, {}, tty=True, configured="remove") == "remove"
    assert serve.exit_action(None, {"QROSETTA_ON_EXIT": "standby"}, tty=True, configured="remove") == "standby"
    assert serve.exit_action("standby", {"QROSETTA_ON_EXIT": "remove"}, tty=True) == "standby"
    with pytest.raises(CliError) as err:
        serve.exit_action(None, {"QROSETTA_ON_EXIT": "delete"}, tty=True)
    assert err.value.code == Exit.USAGE


def test_stop_stops_running_containers_by_id_and_keeps_everything(fake, project, env, capsys):
    fake.add("qiskit-runner", ours("qiskit_runner"), running=False)
    assert cli(fake, project, env, ["stop"]) == 0
    assert fake.commands("stop") == [["stop", "c-nginx-reverse-proxy", "c-rosetta-api"]]
    assert not fake.commands("rm") and not fake.commands("rmi") and len(fake.containers) == 3
    out, err = capsys.readouterr()
    assert "On standby" in out and "Stopping 2 containers" in err


def test_stop_stops_a_pod_holding_only_this_stack(fake, project, env):
    fake.add("qiskit-runner", ours("qiskit_runner"), pod="p1")
    engine, stack = make(fake, project, env)
    actions.stop_stack(engine, stack)
    assert fake.commands("pod", "stop") == [["pod", "stop", "p1"]]


def test_stop_refuses_while_runs_are_in_flight_unless_forced(fake, project, env, capsys):
    busy = FakeServer(gate={"exclusive_running": False, "shared_running": 2})
    assert cli(fake, project, env, ["stop"], server=busy) == Exit.BUSY
    err = capsys.readouterr().err
    assert "2 dispatches are in flight" in err and err.strip().splitlines()[-1].strip() == "qrosetta stop --force"
    assert not fake.destructive_calls()
    assert cli(fake, project, env, ["stop", "--force"], server=busy) == 0
    assert fake.commands("stop") and "continuing because of --force" in capsys.readouterr().err


def test_stop_continues_with_a_warning_when_the_server_cannot_report_the_gate(fake, project, env, capsys):
    server = FakeServer(gate={})
    assert cli(fake, project, env, ["stop"], server=server) == 0
    assert "does not report runs in flight" in capsys.readouterr().err and fake.commands("stop")


def test_stop_exits_16_while_containers_still_run(fake, project, env, capsys):
    fake.add("old-runner", {own.PROJECT_LABEL: "qr", own.SERVICE_LABEL: "braket_runner"})
    assert cli(fake, project, env, ["stop"]) == Exit.ENGINE
    assert "Still running: old-runner" in capsys.readouterr().err


def test_remove_keeps_images_and_data_by_default(fake, project, env, capsys):
    assert cli(fake, project, env, ["rm"]) == 0
    assert fake.commands("rm") == [["rm", "-f", "c-nginx-reverse-proxy", "c-rosetta-api"]]
    assert fake.commands("network", "rm") == [["network", "rm", "n-qr_isolated_net"]]
    assert fake.containers == {} and fake.networks == {}
    assert not fake.commands("rmi") and "qr_db" in fake.volumes and len(fake.images) == 3
    assert "kept images and data" in capsys.readouterr().out


def test_remove_images_removes_labelled_images_by_id(fake, project, env, capsys):
    assert cli(fake, project, env, ["remove", "--images"]) == 0
    assert fake.commands("rmi") == [["rmi", "i-api", "i-nginx", "i-qiskit"]]
    assert "Removing 3 images, 1.7 KiB" in capsys.readouterr().err


def test_remove_data_needs_the_project_name(fake, project, env, capsys):
    assert cli(fake, project, env, ["remove", "--data"]) == Exit.USAGE
    err = capsys.readouterr().err
    assert "qr_db (32.9 MiB)" in err and "saved run reports" in err and "compose project `qr`" in err
    assert err.strip().splitlines()[-1].strip() == "qrosetta remove --data --confirm qr"
    assert cli(fake, project, env, ["remove", "--data", "--confirm", "delete"]) == Exit.USAGE
    assert cli(fake, project, env, ["remove", "--data"], tty=True, stdin=_Lines("yes\n")) == Exit.USAGE
    assert not fake.commands("rm") and "qr_db" in fake.volumes
    assert cli(fake, project, env, ["remove", "--data"], tty=True, stdin=_Lines("qr\n")) == 0
    assert fake.volumes == {} and fake.containers == {}


def test_remove_data_with_confirm_flag_needs_no_terminal(fake, project, env):
    assert cli(fake, project, env, ["remove", "--data", "--confirm", "qr"]) == 0
    assert fake.volumes == {}


class _Lines:
    def __init__(self, text):
        self.text = text

    def readline(self):
        line, _, self.text = self.text.partition("\n")
        return line + "\n" if line else ""

    def isatty(self):
        return True


def test_plan_start_requires_core_images(fake, project, env):
    engine, stack = make(fake, project, env)
    services, missing, extra = serve.plan_start(engine, stack, None, env={})
    assert services == ["nginx", "api", "qiskit_runner"] and missing == ["braket_runner"]
    assert extra == {"QROSETTA_GIT_SHA": "abc123"}
    assert serve.plan_start(engine, stack, None, env={"QROSETTA_GIT_SHA": "x"})[2] == {}
    with pytest.raises(CliError) as err:
        serve.plan_start(engine, stack, ["braket_runner"], env={})
    assert err.value.hint == "qrosetta build braket" and err.value.code == Exit.ENGINE
    del fake.images["i-api"]
    with pytest.raises(CliError, match="No image for api"):
        serve.plan_start(engine, stack, None, env={})


def test_service_keys_resolve_with_compose_and_container_names_as_aliases(fake, project, env):
    _, stack = make(fake, project, env)
    assert {stack.resolve_service(n) for n in ("qiskit", "qiskit_runner", "qiskit-runner")} == {"qiskit_runner"}
    with pytest.raises(CliError) as err:
        stack.resolve_service("qiskti")
    assert err.value.code == Exit.USAGE and err.value.hint == "did you mean qiskit?"
    assert stack.kind_of("api") == "core" and stack.services["qiskit_runner"].profiles == ["minimal", "cpu", "full"]


def test_start_refuses_while_unlabelled_or_foreign_objects_hold_its_names(fake, project, env, capsys):
    fake.add("braket-runner", {"com.docker.compose.project": "oldcheckout"}, running=False)
    fake.add("qiskit-runner", {"com.docker.compose.project": "qr", "com.docker.compose.service": "qiskit_runner"})
    fake.add_network("qr_public_net", {"com.docker.compose.project": "qr"})
    assert cli(fake, project, env, ["start", "--detach"]) == Exit.ENGINE
    err = capsys.readouterr().err
    assert "braket-runner (project oldcheckout, stopped)" in err and "podman rm -f braket-runner" in err
    assert "without the qrosetta label" in err and "podman rm -f qiskit-runner" in err
    assert "podman network rm qr_public_net" in err
    assert not fake.destructive_calls()
    assert not fake.compose_calls("up")


def _stopped(fake):
    for c in fake.containers.values():
        c["State"]["Running"] = False
    return fake


def test_start_detach_waits_for_fresh_probes(fake, project, env, capsys, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    server = FakeServer(fresh=True)
    assert cli(_stopped(fake), project, env, ["start", "-d"], server=server) == 0
    up = fake.compose_calls("up")[0]
    assert up[-6:] == ["up", "-d", "--no-build", "nginx", "api", "qiskit_runner"]
    up_env = next(e for c, e in fake.calls if c[1:2] == ["compose"] and "up" in c)
    assert up_env["QROSETTA_HOST_OS"] == platform.system()
    assert up_env["QROSETTA_HOST_ARCH"] == platform.machine()
    assert any(q == {"fresh": "true"} for _, p, q, _ in server.requests if p == "/runners")
    out, err = capsys.readouterr()
    assert "qiskit ready" in err and out.strip().splitlines()[0] == "Quantum Rosetta is running at http://localhost:8080"
    assert "no on-demand probes" not in err


def test_start_detach_without_fresh_probes_uses_the_cache_and_says_so(fake, project, env, capsys, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    assert cli(_stopped(fake), project, env, ["start", "-d"], server=FakeServer()) == 0
    assert "no on-demand probes" in capsys.readouterr().err
    assert cli(_stopped(fake), project, env, ["start", "-d"], server=FakeServer(fresh="unauthorised")) == 0
    assert "fresh probes need" in capsys.readouterr().err


def test_start_detach_names_runners_that_never_became_ready(fake, project, env, capsys, monkeypatch):
    clock = iter(range(0, 10000, 50))
    monkeypatch.setattr(serve, "_clock", lambda: next(clock))
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    server = FakeServer(fresh=True, runners=[{"id": "qiskit", "enabled": True, "available": False,
                                               "error_kind": "dns"}])
    assert cli(_stopped(fake), project, env, ["start", "-d"], server=server) == Exit.ENGINE
    err = capsys.readouterr().err
    assert "cannot resolve qiskit on the internal network" in err and err.strip().splitlines()[-1].strip() == "qrosetta doctor"


READY_BLOCK = {"platform_version": "2.0.0", "api_levels": [1, 1], "features": {"readiness": 1}}


def test_start_detach_waits_for_the_api_to_be_ready(fake, project, env, capsys, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    answers = iter([(503, {"detail": "Not ready: the database does not answer."}),
                    (200, {"status": "ready", "checks": {}})])

    class Settling(FakeServer):
        def request(self, method, path, query=None, body=None, headers=None, timeout=None):
            if path == "/ready":
                self.status["/ready"] = next(answers)
            return super().request(method, path, query, body, headers, timeout)

    server = Settling(fresh=True, block=READY_BLOCK)
    assert cli(_stopped(fake), project, env, ["start", "-d"], server=server) == 0
    assert [p for _, p, _, _ in server.requests].count("/ready") == 2
    assert "qiskit ready" in capsys.readouterr().err


def test_start_detach_names_the_reason_the_api_never_became_ready(fake, project, env, capsys, monkeypatch):
    clock = iter(range(0, 10000, 50))
    monkeypatch.setattr(serve, "_clock", lambda: next(clock))
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    server = FakeServer(fresh=True, block=READY_BLOCK,
                        status={"/ready": (503, {"detail": "Not ready: the job storage directory does not "
                                                           "accept new files."})})
    assert cli(_stopped(fake), project, env, ["start", "-d"], server=server) == Exit.ENGINE
    err = capsys.readouterr().err
    assert "was not ready within" in err and "job storage directory does not accept new files" in err
    assert not any(p == "/runners" for _, p, _, _ in server.requests)


def test_start_detach_skips_readiness_on_a_server_without_it(fake, project, env, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    server = FakeServer(fresh=True, block={**READY_BLOCK, "features": {}})
    assert cli(_stopped(fake), project, env, ["start", "-d"], server=server) == 0
    assert "/ready" not in [p for _, p, _, _ in server.requests]


def test_start_adds_only_missing_services_and_respects_runs_in_flight(fake, project, env, capsys, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    busy = FakeServer(gate={"exclusive_running": True, "shared_running": 0}, fresh=True)
    assert cli(fake, project, env, ["start", "-d", "qiskit"], server=busy) == Exit.BUSY
    assert not fake.compose_calls("up")
    assert capsys.readouterr().err.strip().splitlines()[-1].strip() == "qrosetta start --yes"
    assert cli(fake, project, env, ["start", "-d", "qiskit", "--yes"], server=busy) == 0
    up = fake.compose_calls("up")[0]
    assert up[-5:] == ["up", "-d", "--no-build", "--no-deps", "qiskit_runner"]


def _rebuilt(fake, *services):
    """`qrosetta build` while the stack runs: each service's tag moves to a new image."""
    fake.add("qiskit-runner", ours("qiskit_runner"), image="i-qiskit")
    for service in services:
        fake.rebuild(service, "j-" + service.split("_")[0])
    return fake


def test_start_recreates_running_containers_built_from_an_older_image(fake, project, env, capsys, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    _rebuilt(fake, "api", "qiskit_runner")
    assert cli(fake, project, env, ["start", "-d", "--json"], server=FakeServer(fresh=True)) == 0
    ups = fake.compose_calls("up")
    assert [c[c.index("up"):] for c in ups] == [
        ["up", "-d", "--no-build", "--force-recreate", "--no-deps", "api", "qiskit_runner"]]
    assert fake.recreated == ["c-rosetta-api", "c-qiskit-runner"]
    assert fake.containers["c-rosetta-api"]["Image"] == "j-api"
    assert fake.containers["c-qiskit-runner"]["Image"] == "j-qiskit"
    assert fake.containers["c-nginx-reverse-proxy"]["Image"] == "i-nginx"
    assert not fake.destructive_calls()
    out, err = capsys.readouterr()
    assert "Recreating 2 services" in err
    assert "api (running): image rebuilt, built from abc123 (image i-api) -> built from new456 (image j-api)" in err
    assert "already running" not in err
    assert json.loads(out)["data"]["recreated"] == ["api", "qiskit"]


def test_start_does_not_recreate_containers_on_the_image_under_their_tag(fake, project, env, capsys, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    _rebuilt(fake)
    fake.containers["c-rosetta-api"]["Image"] = "sha256:i-api"
    assert st.image_key("sha256:i-api") == st.image_key("i-api") == "i-api"
    assert cli(fake, project, env, ["start", "-d"], server=FakeServer(fresh=True)) == 0
    assert not fake.compose_calls("up") and not fake.recreated
    assert "Every requested service is already running" in capsys.readouterr().err


def test_recreating_running_containers_is_refused_while_runs_are_in_flight(fake, project, env, capsys, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    _rebuilt(fake, "qiskit_runner")
    busy = FakeServer(gate={"exclusive_running": False, "shared_running": 1}, fresh=True)
    assert cli(fake, project, env, ["start", "-d"], server=busy) == Exit.BUSY
    err = capsys.readouterr().err
    assert "recreating the containers of qiskit on new images stops them" in err
    assert err.strip().splitlines()[-1].strip() == "qrosetta start --yes"
    assert not fake.compose_calls("up") and fake.containers["c-qiskit-runner"]["Image"] == "i-qiskit"
    assert cli(fake, project, env, ["start", "-d", "--yes"], server=busy) == 0
    assert fake.recreated == ["c-qiskit-runner"]


def test_start_from_standby_recreates_stopped_containers_built_from_an_older_image(fake, project, env, capsys,
                                                                                    monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    _stopped(_rebuilt(fake, "api"))
    assert cli(fake, project, env, ["start", "-d"], server=FakeServer(fresh=True)) == 0
    ups = [c[c.index("up"):] for c in fake.compose_calls("up")]
    assert ups == [["up", "-d", "--no-build", "--force-recreate", "api"],
                   ["up", "-d", "--no-build", "nginx", "qiskit_runner"]]
    assert fake.recreated == ["c-rosetta-api"] and fake.containers["c-rosetta-api"]["Image"] == "j-api"
    assert all(c["State"]["Running"] for c in fake.containers.values())
    assert "api (stopped): image rebuilt, built from abc123" in capsys.readouterr().err


def test_foreground_start_recreates_like_detach(fake, project, env, capsys, monkeypatch):
    monkeypatch.setattr(serve.Server, "_follow", lambda self: 0)
    _rebuilt(fake, "nginx")
    assert cli(fake, project, env, ["start", "--on-exit", "standby"], server=FakeServer()) == 0
    ups = [c[c.index("up"):] for c in fake.compose_calls("up")]
    assert ups == [["up", "-d", "--no-build", "--force-recreate", "--no-deps", "nginx"]]
    assert fake.recreated == ["c-nginx-reverse-proxy"]
    assert "nginx (running): image rebuilt, built from abc123" in capsys.readouterr().err


def test_foreground_start_from_standby_recreates_then_starts_the_rest(project, env, monkeypatch):
    monkeypatch.setattr(serve.Server, "_follow", lambda self: 0)
    fake = _stopped(_rebuilt(FakeEngine().standard(), "qiskit_runner"))
    assert cli(fake, project, env, ["start", "--on-exit", "standby"], server=FakeServer()) == 0
    ups = [c[c.index("up"):] for c in fake.compose_calls("up")]
    assert ups == [["up", "-d", "--no-build", "--force-recreate", "qiskit_runner"],
                   ["up", "-d", "--no-build", "nginx", "api"]]
    assert fake.containers["c-qiskit-runner"]["Image"] == "j-qiskit"


def _created(project, env, monkeypatch):
    """The stack as `start -d` created it: every container carries its service's config hash."""
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    monkeypatch.setattr(serve.Server, "_follow", lambda self: 0)
    fake = FakeEngine().standard()
    fake.containers.clear()
    assert cli(fake, project, env, ["start", "-d"], server=FakeServer(fresh=True)) == 0
    assert all(c["Config"]["Labels"].get(own.CONFIG_HASH_LABEL) for c in fake.containers.values())
    fake.calls.clear()
    fake.recreated.clear()
    return fake


def _ups(fake):
    return [c[c.index("up"):] for c in fake.compose_calls("up")]


def test_start_leaves_a_stack_whose_compose_configuration_is_unchanged_alone(project, env, capsys, monkeypatch):
    fake = _created(project, env, monkeypatch)
    capsys.readouterr()
    assert cli(fake, project, env, ["start", "-d", "--json"], server=FakeServer(fresh=True)) == 0
    assert not fake.compose_calls("up") and not fake.recreated
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["recreated"] == [] and data["recreations"] == []
    hashed = [e for c, e in fake.calls if "--hash" in c]
    up_env = {k: hashed[0].get(k) for k in ("QROSETTA_HOST_OS", "QROSETTA_HOST_ARCH", "QROSETTA_GIT_SHA",
                                            "QROSETTA_LIFECYCLE_TOKEN_PATH")}
    assert up_env == {"QROSETTA_HOST_OS": platform.system(), "QROSETTA_HOST_ARCH": platform.machine(),
                      "QROSETTA_GIT_SHA": "abc123",
                      "QROSETTA_LIFECYCLE_TOKEN_PATH": env["XDG_RUNTIME_DIR"] + "/qrosetta/lifecycle.token"}
    assert cli(fake, project, env, ["start", "--on-exit", "standby"], server=FakeServer()) == 0
    assert not fake.compose_calls("up") and not fake.recreated
    assert cli(_stopped(fake), project, env, ["start", "-d"], server=FakeServer(fresh=True)) == 0
    assert _ups(fake) == [["up", "-d", "--no-build", "nginx", "api", "qiskit_runner"]] and not fake.recreated
    assert "Recreating" not in capsys.readouterr().err


def test_start_recreates_only_the_service_whose_compose_configuration_changed(project, env, capsys, monkeypatch):
    fake = _created(project, env, monkeypatch)
    fake.edit_config("api")
    capsys.readouterr()
    assert cli(fake, project, env, ["start", "-d", "--json"], server=FakeServer(fresh=True)) == 0
    assert _ups(fake) == [["up", "-d", "--no-build", "--force-recreate", "--no-deps", "api"]]
    assert fake.recreated == ["c-rosetta-api"] and not fake.destructive_calls()
    out, err = capsys.readouterr()
    assert ("Recreating 1 service whose container was created from another compose configuration than the "
            "compose file now gives:\n  api (running): compose configuration changed\n") in err
    data = json.loads(out)["data"]
    assert data["recreated"] == ["api"] and data["recreations"] == [{"id": "api", "reasons": ["config"]}]
    assert cli(fake, project, env, ["start", "-d"], server=FakeServer(fresh=True)) == 0
    assert fake.recreated == ["c-rosetta-api"]


def test_start_names_both_reasons_when_image_and_configuration_changed(project, env, capsys, monkeypatch):
    fake = _created(project, env, monkeypatch)
    fake.edit_config("api")
    fake.rebuild("api", "j-api", sha="abc123")
    fake.rebuild("qiskit_runner", "j-qiskit")
    capsys.readouterr()
    assert cli(fake, project, env, ["start", "-d", "--json"], server=FakeServer(fresh=True)) == 0
    assert _ups(fake) == [["up", "-d", "--no-build", "--force-recreate", "--no-deps", "api", "qiskit_runner"]]
    out, err = capsys.readouterr()
    assert ("Recreating 2 services whose containers were created from other images or compose configurations "
            "than the current ones:") in err
    assert ("  api (running): image rebuilt, built from abc123 (image i-api) -> built from abc123 (image j-api); "
            "compose configuration changed\n  qiskit (running): image rebuilt, built from abc123 (image i-qiskit) "
            "-> built from new456 (image j-qiskit)\n") in err
    assert json.loads(out)["data"]["recreations"] == [{"id": "api", "reasons": ["image", "config"]},
                                                      {"id": "qiskit", "reasons": ["image"]}]


def test_rebuilding_the_web_server_alone_does_not_change_the_apis_configuration(project, env, capsys, monkeypatch):
    fake = _created(project, env, monkeypatch)
    fake.rebuild("nginx", "j-nginx")
    capsys.readouterr()
    assert cli(fake, project, env, ["start", "-d", "--json"], server=FakeServer(fresh=True)) == 0
    assert json.loads(capsys.readouterr().out)["data"]["recreations"] == [{"id": "nginx", "reasons": ["image"]}]
    assert fake.recreated == ["c-nginx-reverse-proxy"]


def test_recreating_on_a_changed_configuration_is_refused_while_runs_are_in_flight(project, env, capsys, monkeypatch):
    fake = _created(project, env, monkeypatch)
    fake.edit_config("qiskit_runner")
    busy = FakeServer(gate={"exclusive_running": False, "shared_running": 1}, fresh=True)
    capsys.readouterr()
    assert cli(fake, project, env, ["start", "-d"], server=busy) == Exit.BUSY
    err = capsys.readouterr().err
    assert "recreating the containers of qiskit with their new compose configuration stops them" in err
    assert not fake.compose_calls("up") and not fake.recreated
    assert cli(fake, project, env, ["start", "-d", "--yes"], server=busy) == 0
    assert fake.recreated == ["c-qiskit-runner"]


def test_start_from_standby_recreates_a_changed_configuration_first(project, env, capsys, monkeypatch):
    fake = _stopped(_created(project, env, monkeypatch))
    fake.edit_config("qiskit_runner")
    capsys.readouterr()
    assert cli(fake, project, env, ["start", "-d"], server=FakeServer(fresh=True)) == 0
    assert _ups(fake) == [["up", "-d", "--no-build", "--force-recreate", "qiskit_runner"],
                          ["up", "-d", "--no-build", "nginx", "api"]]
    assert fake.recreated == ["c-qiskit-runner"]
    assert "  qiskit (stopped): compose configuration changed" in capsys.readouterr().err


def test_foreground_start_recreates_a_changed_configuration(project, env, capsys, monkeypatch):
    fake = _created(project, env, monkeypatch)
    fake.edit_config("nginx")
    capsys.readouterr()
    assert cli(fake, project, env, ["start", "--on-exit", "standby"], server=FakeServer()) == 0
    assert _ups(fake) == [["up", "-d", "--no-build", "--force-recreate", "--no-deps", "nginx"]]
    assert fake.recreated == ["c-nginx-reverse-proxy"]
    assert "  nginx (running): compose configuration changed" in capsys.readouterr().err


def test_bind_given_to_start_is_part_of_the_web_servers_configuration(project, env, capsys, monkeypatch):
    fake = _created(project, env, monkeypatch)
    assert cli(fake, project, env, ["start", "-d", "--bind", "0.0.0.0:9000"], server=FakeServer(fresh=True)) == 0
    assert fake.recreated == ["c-nginx-reverse-proxy"]
    assert cli(fake, project, env, ["start", "-d", "--bind", "0.0.0.0:9000"], server=FakeServer(fresh=True)) == 0
    assert fake.recreated == ["c-nginx-reverse-proxy"]
    assert cli(fake, project, env, ["start", "-d"], server=FakeServer(fresh=True)) == 0
    assert fake.recreated == ["c-nginx-reverse-proxy"] * 2


def test_without_config_hashes_start_compares_images_only(project, env, capsys, monkeypatch):
    fake = _created(project, env, monkeypatch)
    fake.edit_config("api")
    fake.hash_supported = False
    capsys.readouterr()
    assert cli(fake, project, env, ["start", "-d"], server=FakeServer(fresh=True)) == 0
    assert not fake.compose_calls("up") and not fake.recreated
    assert "config --hash` failed" in capsys.readouterr().err


def test_status_names_a_changed_compose_configuration(project, env, capsys, monkeypatch):
    from tests.unit.test_qrosetta_contracts import validate_envelope
    fake = _created(project, env, monkeypatch)
    token = Path(env["XDG_RUNTIME_DIR"]) / "qrosetta" / "lifecycle.token"
    assert token.is_file()
    token.unlink()
    capsys.readouterr()
    assert cli(fake, project, env, ["status", "--json"]) == 0
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["data"]["services"]}
    assert {k: r["config_current"] for k, r in rows.items()} == {
        "nginx": True, "api": True, "qiskit": True, "braket": None}
    fake.edit_config("api")
    assert cli(fake, project, env, ["status"]) == 0
    out = capsys.readouterr().out
    assert next(line for line in out.splitlines() if line.startswith("api ")).endswith(
        "built from abc123; compose configuration changed")
    assert ("1 container was created from another compose configuration than the compose file now gives; "
            "`qrosetta start -d api` recreates it with the current one.") in out
    fake.rebuild("qiskit_runner", "j-qiskit")
    assert cli(fake, project, env, ["status", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    rows = {r["id"]: r for r in doc["data"]["services"]}
    assert rows["api"]["config_current"] is False and rows["qiskit"]["config_current"] is True
    assert cli(fake, project, env, ["status"]) == 0
    assert ("2 containers were created from other images or compose configurations than the current ones "
            "(IMAGE column); `qrosetta start -d api qiskit` recreates them.") in capsys.readouterr().out


def test_start_profile_from_compose_labels(fake, project, env, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    assert cli(_stopped(fake), project, env, ["start", "-d", "--profile", "minimal"], server=FakeServer(fresh=True)) == 0
    assert fake.compose_calls("up")[0][-3:] == ["qiskit_runner", "nginx", "api"]
    assert cli(fake, project, env, ["start", "-d", "--profile", "nosuch"], server=FakeServer()) == Exit.USAGE


def test_start_explains_engine_failures(fake, project, env, capsys):
    fake.up_error = "Error: rootlessport listen tcp 127.0.0.1:8080: bind: address already in use\n"
    assert cli(_stopped(fake), project, env, ["start", "-d"]) == Exit.ENGINE
    err = capsys.readouterr().err
    assert "127.0.0.1:8080 is in use" in err and err.strip().splitlines()[-1].strip() == "qrosetta start -d --bind 127.0.0.1:8090"


def _unhealthy_api(fake):
    _stopped(fake)
    fake.up_error = ("Container rosetta-api  Error dependency api failed to start\n"
                     "dependency failed to start: container rosetta-api is unhealthy\n")
    fake.containers["c-rosetta-api"]["State"].update(Running=True, Health={"Status": "unhealthy", "Log": [
        {"ExitCode": 1, "Output": "first check"},
        {"ExitCode": 1, "Output": "Traceback (most recent call last):\nConnectionRefusedError: [Errno 111]\n"}]})
    fake.logs["c-rosetta-api"] = ("2026-11-04T12:10:25Z GET /config 200\n",
                                  "2026-11-04T12:10:20Z [INFO] Booting worker with pid: 3\n"
                                  "2026-11-04T12:10:30Z [ERROR] Worker (pid:3) was sent SIGKILL!\n")
    return fake


def test_start_unhealthy_api_prints_its_last_health_check_and_log(fake, project, env, capsys):
    foreign = fake.add("rosetta-api-copy", {"com.docker.compose.project": "other",
                                            "com.docker.compose.service": "api"})
    assert cli(_unhealthy_api(fake), project, env, ["start", "-d"]) == Exit.ENGINE
    err = capsys.readouterr().err
    assert "failed its health check (GET /health inside the container)" in err and "page cache" not in err
    assert "Last health check of rosetta-api: exit code 1" in err and "ConnectionRefusedError" in err
    assert "first check" not in err
    lines = err.splitlines()
    start = lines.index("  Last 3 lines of its log:")
    assert [x.split()[0] for x in lines[start + 1:start + 4]] == [
        "2026-11-04T12:10:20Z", "2026-11-04T12:10:25Z", "2026-11-04T12:10:30Z"]
    assert lines[-2:] == ["Read the API's log:", "  qrosetta logs api --tail 50"]
    logs = [c for c, _ in fake.calls if c[1:2] == ["logs"]]
    assert logs == [["podman", "logs", "--timestamps", "--tail", "20", "c-rosetta-api"]]
    assert foreign not in json.dumps(logs) and not fake.destructive_calls()


def test_start_unhealthy_api_without_its_container_keeps_the_engine_message(fake, project, env, capsys):
    del _unhealthy_api(fake).containers["c-rosetta-api"]
    assert cli(fake, project, env, ["start", "-d"]) == Exit.ENGINE
    err = capsys.readouterr().err
    assert "failed its health check" in err and "Last health check" not in err
    assert not [c for c, _ in fake.calls if c[1:2] == ["logs"]]


def test_start_bind_reaches_compose_and_warns_off_loopback(fake, project, env, capsys, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    assert cli(_stopped(fake), project, env, ["start", "-d", "--bind", "0.0.0.0:9000"], server=FakeServer()) == 0
    up_env = next(e for c, e in fake.calls if c[1:2] == ["compose"] and "up" in c)
    assert up_env["QROSETTA_HTTP_BIND"] == "0.0.0.0:9000" and "without TLS" in capsys.readouterr().err
    assert cli(fake, project, env, ["start", "-d", "--bind", "nonsense"]) == Exit.USAGE


def test_announce_says_whether_other_machines_can_reach_it(fake, project, env, capsys):
    engine, stack = make(fake, project, env)
    serve.announce_running(engine, stack)
    out, err = capsys.readouterr()
    assert "http://localhost:8080" in out and "Published on 127.0.0.1:8080 (this machine only)" in err
    fake.port = "0.0.0.0:8080"
    serve.announce_running(engine, stack)
    assert "reachable from other machines" in capsys.readouterr().err


@pytest.mark.parametrize("port,url", [("0.0.0.0:8080", "http://localhost:8080"),
                                      ("127.0.0.1:80", "http://localhost"),
                                      ("192.168.1.5:8080", "http://192.168.1.5:8080"),
                                      ("[::]:9000", "http://localhost:9000"), ("", None)])
def test_url_from_compose_port(fake, project, env, port, url):
    fake.port = port
    engine, stack = make(fake, project, env)
    assert serve.stack_url(engine, stack) == url


def test_sizes():
    assert actions.parse_size("34.48MB") == 34480000
    assert actions.parse_size("1GiB") == 1024 ** 3
    assert actions.parse_size("12.5kB") == 12500
    assert actions.parse_size("n/a") is None
    assert actions.human_bytes(21_886_452_201) == "20.4 GiB"
    assert actions.human_bytes(1024 ** 3) == "1.0 GiB"


class FakeProcess:
    pid = None

    def __init__(self, on_wait=None, code=0):
        self.on_wait = on_wait
        self.code = code
        self.terminated = False

    def wait(self, timeout=None):
        if self.on_wait:
            hook, self.on_wait = self.on_wait, None
            hook()
        return self.code

    def poll(self):
        return None if not self.terminated else 0

    def send_signal(self, signum):
        self.terminated = True


def _server(fake, project, env, action, signum, answer=None, tty=True):
    spawned = []
    server = None

    def popen(cmd, **kwargs):
        spawned.append(cmd)
        if "logs" in cmd:
            return FakeProcess(lambda: server._handle(signum, None))
        return FakeProcess()

    engine, stack = make(fake, project, env, popen=popen)
    server = serve.Server(engine, stack, action, ["nginx", "api"], {}, tty=tty, ask=lambda q: answer)
    return server, spawned


@pytest.mark.parametrize("signame", ["SIGINT", "SIGTERM", "SIGHUP"])
def test_foreground_signal_puts_stack_on_standby(fake, project, env, signame):
    if not hasattr(signal, signame):
        pytest.skip(f"{signame} does not exist here")
    server, spawned = _server(fake, project, env, "standby", getattr(signal, signame))
    assert server.run() == 0
    assert spawned[0][-5:] == ["up", "-d", "--no-build", "nginx", "api"]
    assert any("logs" in c for c in spawned)
    assert fake.commands("stop") == [["stop", "c-nginx-reverse-proxy", "c-rosetta-api"]]
    assert len(fake.containers) == 2


def test_ask_on_ctrl_c_removes_when_answered_r(fake, project, env):
    server, _ = _server(fake, project, env, "ask", signal.SIGINT, answer="r\n")
    assert server.run() == 0
    assert fake.containers == {} and "qr_db" in fake.volumes and len(fake.images) == 3


def test_ask_falls_back_to_standby_on_hangup_or_no_answer(fake, project, env):
    server, _ = _server(fake, project, env, "ask", signal.SIGTERM, answer="r\n")
    assert server.run() == 0 and len(fake.containers) == 2
    fake2 = FakeEngine().standard()
    server, _ = _server(fake2, project, env, "ask", signal.SIGINT, answer=None)
    assert server.run() == 0 and len(fake2.containers) == 2 and fake2.commands("stop")


def test_ctrl_c_during_shutdown_warns_then_abandons(fake, project, env):
    server, _ = _server(fake, project, env, "standby", signal.SIGINT)
    server.phase = "shutdown"
    server._handle(signal.SIGTERM, None)
    server._handle(signal.SIGINT, None)
    with pytest.raises(serve.Abandoned):
        server._handle(signal.SIGINT, None)


def test_failed_up_stops_what_started_and_exits_16(fake, project, env):
    engine, stack = make(fake, project, env, popen=lambda cmd, **kw: FakeProcess(code=1))
    server = serve.Server(engine, stack, "ask", ["api"], {}, tty=True, ask=lambda q: "r")
    with pytest.raises(CliError) as err:
        server.run()
    assert err.value.code == Exit.ENGINE
    assert fake.commands("stop") == [["stop", "c-nginx-reverse-proxy", "c-rosetta-api"]]
    assert len(fake.containers) == 2


def test_status_prints_the_table_on_stdout_and_exits_0(fake, project, env, capsys):
    fake.add("old", {own.PROJECT_LABEL: "qr", own.SERVICE_LABEL: "braket_runner"}, running=False)
    server = FakeServer(block={"platform_version": "2.0.0", "api_levels": [1, 1], "features": {}})
    assert cli(fake, project, env, ["status"], server=server) == 0
    out, err = capsys.readouterr()
    assert "running at http://localhost:8080 (platform 2.0.0, API levels 1-1)" in out
    assert "SERVICE" in out and "qiskit" in out and "built from abc123" in out and "braket" in out
    assert "missing" in out and "podman rm -f old" in err


def test_status_json_validates_and_carries_the_server_block(fake, project, env, capsys):
    from tests.unit.test_qrosetta_contracts import validate_envelope
    server = FakeServer(block={"platform_version": "2.0.0", "api_levels": [1, 1], "features": {}})
    assert cli(fake, project, env, ["status", "--json"], server=server) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    assert doc["schema"] == "qrosetta.cli/status@1" and doc["server"]["platform_version"] == "2.0.0"
    rows = {r["id"]: r for r in doc["data"]["services"]}
    assert rows["qiskit"]["image"]["state"] == "built" and rows["braket"]["image"]["state"] == "missing"
    assert rows["api"]["kind"] == "core" and rows["api"]["state"] == "running"


def test_status_names_the_image_a_container_runs_when_its_tag_moved(fake, project, env, capsys):
    from tests.unit.test_qrosetta_contracts import validate_envelope
    _rebuilt(fake, "qiskit_runner")
    assert cli(fake, project, env, ["status"]) == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.startswith("qiskit "))
    assert row.endswith("built from abc123; newer image built from new456")
    assert next(line for line in out.splitlines() if line.startswith("api ")).endswith("built from abc123")
    assert ("1 container was created from an image other than the one now under its tag; "
            "`qrosetta start -d qiskit` recreates it on that image.") in out
    assert cli(fake, project, env, ["status", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    rows = {r["id"]: r for r in doc["data"]["services"]}
    assert rows["qiskit"]["image"]["image_id"] == "j-qiskit" and rows["qiskit"]["image"]["git_sha"] == "new456"
    assert rows["qiskit"]["container_image"] == {"state": "built", "ref": "qr-qiskit_runner", "digest": None,
                                                 "image_id": "i-qiskit", "git_sha": "abc123", "release": None,
                                                 "current": False}
    assert rows["api"]["container_image"]["current"] is True and rows["braket"]["container_image"] is None


def test_status_of_a_container_whose_image_is_gone_or_unreported(fake, project, env, capsys):
    _rebuilt(fake, "qiskit_runner")
    del fake.images["i-qiskit"]
    fake.containers["c-rosetta-api"]["Image"] = ""
    assert cli(fake, project, env, ["status"]) == 0
    out = capsys.readouterr().out
    assert next(line for line in out.splitlines() if line.startswith("qiskit ")).endswith(
        "image i-qiskit (removed); newer image built from new456")
    assert next(line for line in out.splitlines() if line.startswith("api ")).endswith("built from abc123")
    assert "`qrosetta start -d qiskit`" in out


def test_main_runs_subcommands_with_injected_engine(fake, project, env, capsys):
    assert cli(fake, project, env, ["stop"]) == 0
    assert "standby" in capsys.readouterr().out
    assert cli(fake, project, env, ["status"]) == 0
    assert "stopped" in capsys.readouterr().out
    assert cli(fake, project, env, ["logs", "nosuch"]) == Exit.USAGE
    assert "Unknown service" in capsys.readouterr().err
    assert cli(fake, project, env, ["logs", "--json"]) == Exit.USAGE
    assert cli(fake, project, env, ["start", "--on-exit", "explode"]) == Exit.USAGE


def test_logs_pass_through_with_service_keys(fake, project, env):
    assert cli(fake, project, env, ["logs", "qiskit", "--no-follow", "--tail", "5"]) == 0
    logs = fake.compose_calls("logs")[0]
    assert logs[-3:] == ["--tail", "5", "qiskit_runner"]


def _safe_boot(project):
    (project / "scripts").mkdir(exist_ok=True)
    (project / "scripts" / "safe_boot.sh").write_text("")


def test_build_passes_this_project_to_safe_boot(fake, project, env, monkeypatch):
    _safe_boot(project)
    seen = {}
    monkeypatch.setattr(subprocess, "call", lambda cmd, env, cwd, **kw: seen.update(env) or 0)
    assert cli(fake, project, dict(env, COMPOSE_PROJECT_NAME="myapp"), ["build", "api"]) == 0
    assert seen["COMPOSE_PROJECT_NAME"] == "qr" and seen["QROSETTA_PROJECT"] == "qr"
    assert seen["QR_BUILD_SERVICES"] == "api" and seen["COMPOSE_FILE"] == str(project / "docker-compose.yml")
    assert cli(fake, project, env, ["build", "--profile", "minimal"]) == 0
    assert seen["QR_BUILD_SERVICES"] == "qiskit_runner nginx api"


def test_build_exits_16_when_the_baked_commit_is_unknown(fake, project, env, monkeypatch, capsys):
    _safe_boot(project)
    fake.add_image("i-api", ["localhost/qr-api:latest"], image_labels("api"), sha="unknown")
    monkeypatch.setattr(subprocess, "call", lambda cmd, env, cwd, **kw: 0)
    assert cli(fake, project, env, ["build", "api"]) == Exit.ENGINE
    err = capsys.readouterr().err
    assert "without a baked commit: api" in err and err.strip().splitlines()[-1].strip().endswith("qrosetta build api")
    monkeypatch.setattr(subprocess, "call", lambda cmd, env, cwd, **kw: 2)
    assert cli(fake, project, env, ["build", "api"]) == Exit.ENGINE


def test_build_refuses_while_runs_are_in_flight(fake, project, env, monkeypatch):
    _safe_boot(project)
    called = []
    monkeypatch.setattr(subprocess, "call", lambda cmd, env, cwd, **kw: called.append(cmd) or 0)
    busy = FakeServer(gate={"exclusive_running": False, "shared_running": 1})
    assert cli(fake, project, env, ["build", "api"], server=busy) == Exit.BUSY and not called
    assert cli(fake, project, env, ["build", "api", "--yes"], server=busy) == 0 and called


def test_engine_lock_refuses_a_second_stack_change(fake, project, env, capsys):
    from qrosetta_cli.stack import guard
    with guard.engine_lock(env, "test holder"):
        assert cli(fake, project, env, ["stop"]) == Exit.BUSY
    assert "Another qrosetta command is changing the stack" in capsys.readouterr().err
    assert not fake.commands("stop")
    assert cli(fake, project, env, ["stop"]) == 0


def test_profiles_lists_built_in_and_user_profiles(fake, project, env, capsys):
    pytest.importorskip("tomllib")
    cfg = project / "c.toml"
    cfg.write_text('[profiles.mine]\nextends = "minimal"\nservices = ["braket"]\n')
    assert cli(fake, project, env, ["profiles", "--config", str(cfg), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    rows = {r["name"]: r for r in doc["data"]["profiles"]}
    assert rows["minimal"]["services"] == ["qiskit"] and rows["mine"]["services"] == ["braket", "qiskit"]
    assert rows["mine"]["experimental"] is True


def test_profiles_from_a_server_need_its_profiles_field(project, env, capsys):
    server = FakeServer(runners=[{"id": "qiskit", "profiles": ["minimal", "cpu"]}],
                        compilers=[{"id": "staq", "profiles": ["compilers"]}])
    assert main(["profiles", "--server", "http://localhost:8080", "--json"], env=env, transport_factory=server) == 0
    rows = {r["name"]: r["services"] for r in json.loads(capsys.readouterr().out)["data"]["profiles"]}
    assert rows == {"minimal": ["qiskit"], "cpu": ["qiskit"], "compilers": ["staq"]}
    assert main(["profiles", "--server", "http://localhost:8080"], env=env, transport_factory=FakeServer()) == Exit.INCOMPATIBLE


def test_safe_boot_hands_start_to_qrosetta_and_labels_its_builds():
    text = (REPO / "scripts" / "safe_boot.sh").read_text()
    assert 'exec ./qrosetta start "${CORE_SERVICES[@]}" "${SUCCESSFUL_RUNNERS[@]}"' in text
    assert 'export COMPOSE_PROJECT_NAME="$QROSETTA_PROJECT"' in text
    assert '" --label "' in text
    assert (REPO / "qrosetta").stat().st_mode & 0o111


def test_start_refuses_other_hosts_unless_emulation_is_allowed(capsys):
    from qrosetta_cli.stack.commands import check_host
    check_host(False, "Linux", "x86_64")
    with pytest.raises(CliError) as err:
        check_host(False, "Darwin", "arm64")
    assert err.value.code == Exit.ENGINE and err.value.hint == "qrosetta start --allow-emulation"
    check_host(True, "Darwin", "arm64")
    assert "under emulation" in capsys.readouterr().err


def test_start_passes_the_native_host_os_and_machine_to_compose():
    from qrosetta_cli.stack.commands import host_compose_env

    def sysctl(answer):
        def run(cmd, **_kw):
            assert cmd == ["sysctl", "-n", "sysctl.proc_translated"]
            return subprocess.CompletedProcess(cmd, 0, stdout=answer, stderr="")
        return run

    def no_call(*_a, **_kw):
        raise AssertionError("sysctl is read only for an x86_64 Python on macOS")

    assert host_compose_env("Linux", "x86_64", run=no_call) == {
        "QROSETTA_HOST_OS": "Linux", "QROSETTA_HOST_ARCH": "x86_64"}
    assert host_compose_env("Darwin", "arm64", run=no_call)["QROSETTA_HOST_ARCH"] == "arm64"
    assert host_compose_env("Darwin", "x86_64", run=sysctl("1\n"))["QROSETTA_HOST_ARCH"] == "arm64"
    assert host_compose_env("Darwin", "x86_64", run=sysctl("0\n"))["QROSETTA_HOST_ARCH"] == "x86_64"
    assert host_compose_env("Darwin", "x86_64", run=sysctl(""))["QROSETTA_HOST_ARCH"] == "x86_64"


def test_image_labels_match_the_ownership_check():
    assert image_labels("api") == {own.QR_IMAGE_PROJECT: "qr", own.QR_SERVICE: "api"}
