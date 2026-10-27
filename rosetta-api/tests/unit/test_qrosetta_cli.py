"""qrosetta_cli: argument handling, project selection, and the engine commands each subcommand
runs, against a fake engine."""

import signal
import subprocess

import pytest

from tests.unit._qrosetta_fake import REPO, FakeEngine, image_labels, ours

from qrosetta_cli import actions, serve, stack as st  # noqa: E402
from qrosetta_cli import ownership as own  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.engine import CliError, Engine, detect_engine, project_name  # noqa: E402

ENV = {"QROSETTA_PROJECT": "qr", "PATH": "/usr/bin"}


@pytest.fixture
def fake():
    return FakeEngine().standard()


@pytest.fixture
def project(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path


def make(fake, project, popen=None, env=ENV):
    kwargs = {"popen": popen} if popen else {}
    engine = Engine(fake.engine, str(project), run=fake, env=env, **kwargs)
    return engine, st.load_stack(engine)


def factory(fake, env=ENV):
    return lambda d: Engine(fake.engine, d, run=fake, env=env)


def test_project_dir_precedence(tmp_path):
    for name in ("flag", "env", "checkout"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "docker-compose.yml").write_text("services: {}\n")
    env = {"QROSETTA_HOME": str(tmp_path / "env")}
    assert st.find_project_dir(str(tmp_path / "flag"), env, str(tmp_path / "checkout")) == str(tmp_path / "flag")
    assert st.find_project_dir(None, env, str(tmp_path / "checkout")) == str(tmp_path / "env")
    assert st.find_project_dir(None, {}, str(tmp_path / "checkout")) == str(tmp_path / "checkout")
    with pytest.raises(CliError, match="QROSETTA_HOME"):
        st.find_project_dir(None, {}, None)
    with pytest.raises(CliError, match="No compose file"):
        st.find_project_dir(str(tmp_path), {}, None)


def test_project_name_comes_from_qrosetta_project_only():
    assert project_name({}) == "qsimulators"
    assert project_name({"COMPOSE_PROJECT_NAME": "myapp"}) == "qsimulators"
    assert project_name({"QROSETTA_PROJECT": "dev2"}) == "dev2"
    with pytest.raises(CliError):
        project_name({"QROSETTA_PROJECT": "My App"})


def test_compose_calls_name_project_and_files_and_drop_compose_variables(fake, project):
    (project / "docker-compose.override.yml").write_text("services: {}\n")
    (project / ".env").write_text("COMPOSE_PROJECT_NAME=myapp\nCOMPOSE_FILE=other.yml\n")
    env = dict(ENV, COMPOSE_PROJECT_NAME="myapp", COMPOSE_FILE="evil.yml")
    engine, stack = make(fake, project, env=env)
    assert stack.name == "qr"
    cmd, child = next((c, e) for c, e in fake.calls if c[1] == "compose")
    assert cmd[2:6] == ["-p", "qr", "--project-directory", str(project)]
    assert cmd[6:10] == ["-f", str(project / "docker-compose.yml"), "-f", str(project / "docker-compose.override.yml")]
    assert not any(k.startswith("COMPOSE_") for k in child) and child["QROSETTA_PROJECT"] == "qr"


def test_a_different_reported_project_is_refused(fake, project):
    fake.config_name = "myapp"
    with pytest.raises(CliError, match="'myapp', not 'qr'"):
        make(fake, project)


def test_engine_detection():
    shim = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "podman version 5.8.2\n", "")
    real = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "Docker version 27.0.1\n", "")
    both = {"docker": "/usr/bin/docker", "podman": "/usr/bin/podman"}.get
    assert detect_engine({}, both, shim) == "podman"
    assert detect_engine({}, both, real) == "docker"
    assert detect_engine({}, {"podman": "/usr/bin/podman"}.get, real) == "podman"
    assert detect_engine({"QROSETTA_ENGINE": "docker"}, both, shim) == "docker"
    with pytest.raises(CliError):
        detect_engine({}, {}.get, real)
    with pytest.raises(CliError):
        detect_engine({"QROSETTA_ENGINE": "lxc"}, both, real)


def test_compose_v1_or_podman_compose_is_refused_with_install_steps(project):
    run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "podman-compose version 1.2.0\n", "")
    with pytest.raises(CliError, match="Docker Compose v2.*podman-compose version 1.2.0.*cli-plugins/docker-compose"):
        Engine("podman", str(project), run=run, env=ENV).check_compose()


def test_exit_action_defaults():
    assert serve.exit_action(None, {}, tty=True) == "ask"
    assert serve.exit_action(None, {}, tty=False) == "standby"
    assert serve.exit_action("ask", {}, tty=False) == "standby"
    assert serve.exit_action(None, {"QROSETTA_ON_EXIT": "remove"}, tty=True) == "remove"
    assert serve.exit_action("standby", {"QROSETTA_ON_EXIT": "remove"}, tty=True) == "standby"
    with pytest.raises(CliError):
        serve.exit_action(None, {"QROSETTA_ON_EXIT": "delete"}, tty=True)


def test_stop_stops_running_containers_by_id_and_keeps_everything(fake, project):
    fake.add("qiskit-runner", ours("qiskit_runner"), running=False)
    engine, stack = make(fake, project)
    assert actions.stop_stack(engine, stack) == []
    assert fake.commands("stop") == [["stop", "c-nginx-reverse-proxy", "c-rosetta-api"]]
    assert not fake.commands("rm") and not fake.commands("rmi") and len(fake.containers) == 3


def test_stop_stops_a_pod_holding_only_this_stack(fake, project):
    fake.add("qiskit-runner", ours("qiskit_runner"), pod="p1")
    engine, stack = make(fake, project)
    actions.stop_stack(engine, stack)
    assert fake.commands("pod", "stop") == [["pod", "stop", "p1"]]


def test_remove_keeps_images_and_data_by_default(fake, project):
    engine, stack = make(fake, project)
    assert actions.remove_stack(engine, stack) == 0
    assert fake.commands("rm") == [["rm", "-f", "c-nginx-reverse-proxy", "c-rosetta-api"]]
    assert fake.commands("network", "rm") == [["network", "rm", "n-qr_isolated_net"]]
    assert fake.containers == {} and fake.networks == {}
    assert not fake.commands("rmi") and "qr_db" in fake.volumes and len(fake.images) == 3


def test_remove_images_removes_labelled_images_by_id(fake, project, capsys):
    engine, stack = make(fake, project)
    assert actions.remove_stack(engine, stack, images=True) == 0
    assert fake.commands("rmi") == [["rmi", "i-api", "i-nginx", "i-qiskit"]]
    assert "Removing 3 images, 1.7 KiB" in capsys.readouterr().out


def test_remove_data_needs_typed_confirmation(fake, project, capsys):
    engine, stack = make(fake, project)
    assert actions.remove_stack(engine, stack, data=True, ask=lambda q: "yes", tty=True) == 1
    assert not fake.commands("rm") and "qr_db" in fake.volumes
    out = capsys.readouterr().out
    assert "qr_db (32.9 MiB)" in out and "saved run reports" in out
    with pytest.raises(CliError, match="terminal"):
        actions.remove_stack(engine, stack, data=True, tty=False)
    assert not fake.commands("rm")
    assert actions.remove_stack(engine, stack, data=True, ask=lambda q: "delete", tty=True) == 0
    assert fake.volumes == {} and fake.containers == {}


def test_plan_start_requires_core_images(fake, project):
    engine, stack = make(fake, project)
    services, missing, env = serve.plan_start(engine, stack, None, env={})
    assert services == ["nginx", "api", "qiskit_runner"] and missing == ["braket_runner"]
    assert env == {"QROSETTA_GIT_SHA": "abc123"}
    assert serve.plan_start(engine, stack, None, env={"QROSETTA_GIT_SHA": "x"})[2] == {}
    with pytest.raises(CliError, match="qrosetta build braket_runner"):
        serve.plan_start(engine, stack, ["braket_runner"], env={})
    del fake.images["i-api"]
    with pytest.raises(CliError, match="No image for api"):
        serve.plan_start(engine, stack, None, env={})


def test_start_refuses_while_unlabelled_or_foreign_objects_hold_its_names(fake, project, capsys):
    fake.add("braket-runner", {"com.docker.compose.project": "oldcheckout"}, running=False)
    fake.add("qiskit-runner", {"com.docker.compose.project": "qr", "com.docker.compose.service": "qiskit_runner"})
    fake.add_network("qr_public_net", {"com.docker.compose.project": "qr"})
    assert main(["start", "--detach"], checkout=str(project), engine_factory=factory(fake)) == 1
    err = capsys.readouterr().err
    assert "braket-runner (project oldcheckout, stopped)" in err and "podman rm -f braket-runner" in err
    assert "without the qrosetta label" in err and "podman rm -f qiskit-runner" in err
    assert "podman network rm qr_public_net" in err
    assert not fake.destructive_calls()
    assert not [c for c, _ in fake.calls if "up" in c]


def test_announce_says_whether_other_machines_can_reach_it(fake, project, capsys):
    engine, stack = make(fake, project)
    serve.announce_running(engine, stack)
    out = capsys.readouterr().out
    assert "http://localhost:8080" in out and "Published on 127.0.0.1:8080 (this machine only)" in out
    fake.port = "0.0.0.0:8080"
    serve.announce_running(engine, stack)
    assert "reachable from other machines" in capsys.readouterr().out


@pytest.mark.parametrize("port,url", [("0.0.0.0:8080", "http://localhost:8080"),
                                      ("127.0.0.1:80", "http://localhost"),
                                      ("192.168.1.5:8080", "http://192.168.1.5:8080"),
                                      ("[::]:9000", "http://localhost:9000"), ("", None)])
def test_url_from_compose_port(fake, project, port, url):
    fake.port = port
    engine, stack = make(fake, project)
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


def _server(fake, project, action, signum, answer=None, tty=True):
    spawned = []
    server = None

    def popen(cmd, **kwargs):
        spawned.append(cmd)
        if "logs" in cmd:
            return FakeProcess(lambda: server._handle(signum, None))
        return FakeProcess()

    engine, stack = make(fake, project, popen=popen)
    server = serve.Server(engine, stack, action, ["nginx", "api"], {}, tty=tty, ask=lambda q: answer)
    return server, spawned


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_foreground_signal_puts_stack_on_standby(fake, project, signum):
    server, spawned = _server(fake, project, "standby", signum)
    assert server.run() == 0
    assert spawned[0][-5:] == ["up", "-d", "--no-build", "nginx", "api"]
    assert any("logs" in c for c in spawned)
    assert fake.commands("stop") == [["stop", "c-nginx-reverse-proxy", "c-rosetta-api"]]
    assert len(fake.containers) == 2


def test_ask_on_ctrl_c_removes_when_answered_r(fake, project):
    server, _ = _server(fake, project, "ask", signal.SIGINT, answer="r\n")
    assert server.run() == 0
    assert fake.containers == {} and "qr_db" in fake.volumes and len(fake.images) == 3


def test_ask_falls_back_to_standby_on_hangup_or_no_answer(fake, project):
    server, _ = _server(fake, project, "ask", signal.SIGHUP, answer="r\n")
    assert server.run() == 0 and len(fake.containers) == 2
    fake2 = FakeEngine().standard()
    server, _ = _server(fake2, project, "ask", signal.SIGINT, answer=None)
    assert server.run() == 0 and len(fake2.containers) == 2 and fake2.commands("stop")


def test_ctrl_c_during_shutdown_warns_then_abandons(fake, project):
    server, _ = _server(fake, project, "standby", signal.SIGINT)
    server.phase = "shutdown"
    server._handle(signal.SIGTERM, None)
    server._handle(signal.SIGINT, None)
    with pytest.raises(serve.Abandoned):
        server._handle(signal.SIGINT, None)


def test_failed_up_stops_what_started(fake, project):
    engine, stack = make(fake, project, popen=lambda cmd, **kw: FakeProcess(code=1))
    server = serve.Server(engine, stack, "ask", ["api"], {}, tty=True, ask=lambda q: "r")
    assert server.run() == 1
    assert fake.commands("stop") == [["stop", "c-nginx-reverse-proxy", "c-rosetta-api"]]
    assert len(fake.containers) == 2


def test_main_runs_subcommands_with_injected_engine(fake, project, capsys):
    assert main(["stop"], checkout=str(project), engine_factory=factory(fake)) == 0
    assert "standby" in capsys.readouterr().out
    assert main(["status"], checkout=str(project), engine_factory=factory(fake)) == 0
    assert "stopped" in capsys.readouterr().out
    assert main(["logs", "nosuch"], checkout=str(project), engine_factory=factory(fake)) == 1
    assert "Unknown service" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["start", "--on-exit", "explode"], checkout=str(project), engine_factory=factory(fake))


def test_build_passes_this_project_to_safe_boot(fake, project, monkeypatch):
    (project / "scripts").mkdir()
    (project / "scripts" / "safe_boot.sh").write_text("")
    seen = {}
    monkeypatch.setattr(subprocess, "call", lambda cmd, env, cwd: seen.update(env) or 0)
    env = dict(ENV, COMPOSE_PROJECT_NAME="myapp")
    assert main(["build", "api"], checkout=str(project), engine_factory=factory(fake, env)) == 0
    assert seen["COMPOSE_PROJECT_NAME"] == "qr" and seen["QROSETTA_PROJECT"] == "qr"
    assert seen["QR_BUILD_SERVICES"] == "api" and seen["COMPOSE_FILE"] == str(project / "docker-compose.yml")


def test_safe_boot_hands_start_to_qrosetta_and_labels_its_builds():
    text = (REPO / "scripts" / "safe_boot.sh").read_text()
    assert 'exec ./qrosetta start "${CORE_SERVICES[@]}" "${SUCCESSFUL_RUNNERS[@]}"' in text
    assert 'export COMPOSE_PROJECT_NAME="$QROSETTA_PROJECT"' in text
    assert '" --label "' in text
    assert (REPO / "qrosetta").stat().st_mode & 0o111


def test_image_labels_match_the_ownership_check():
    assert image_labels("api") == {own.QR_IMAGE_PROJECT: "qr", own.QR_SERVICE: "api"}
