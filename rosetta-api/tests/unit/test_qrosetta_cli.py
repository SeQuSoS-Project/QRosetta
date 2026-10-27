"""qrosetta_cli: argument handling, discovery by compose labels, and the engine commands each
subcommand runs, against a fake engine."""

import json
import signal
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from qrosetta_cli import actions, serve, stack as st  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.engine import CliError, Engine, detect_engine  # noqa: E402

CONFIG = {
    "name": "qr",
    "services": {
        "nginx": {"container_name": "nginx-reverse-proxy", "depends_on": {"api": {}},
                  "ports": [{"target": 80, "published": "8080"}]},
        "api": {"container_name": "rosetta-api"},
        "qiskit_runner": {"container_name": "qiskit-runner"},
        "braket_runner": {"container_name": "braket-runner"},
    },
    "volumes": {"db": {"name": "qr_db"}},
}


class FakeEngineState:
    """Answers the engine and compose commands qrosetta_cli runs, from an in-memory state."""

    def __init__(self, engine="podman"):
        self.engine = engine
        self.calls = []
        self.containers = {}
        self.networks = {"qr_isolated_net": "qr", "qr_public_net": "qr"}
        self.volumes = {"qr_db": ("qr", "db"), "old_db": ("old", "db")}
        self.images = {"qr-nginx": ("sha256:n", 100, ["localhost/qr-nginx:latest"], "abc123"),
                       "qr-api": ("sha256:a", 700, ["localhost/qr-api:latest", "registry/x/api:latest"], "abc123"),
                       "qr-qiskit_runner": ("sha256:q", 900, ["localhost/qr-qiskit_runner:latest"], "abc123")}
        self.port = "127.0.0.1:8080"

    def add(self, name, service, project="qr", running=True, pod=""):
        self.containers[name] = {"Id": "id-" + name, "Name": name, "Pod": pod,
                                 "State": {"Running": running},
                                 "Config": {"Labels": {st.PROJECT_LABEL: project, st.SERVICE_LABEL: service}}}

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        out, rc = self._answer(list(cmd[1:]))
        return subprocess.CompletedProcess(cmd, rc, out, "" if rc == 0 else "error")

    def _answer(self, a):
        if a[:2] == ["compose", "version"]:
            return "Docker Compose version v2.30.0\n", 0
        if a[0] == "compose" and "config" in a:
            return json.dumps(CONFIG), 0
        if a[0] == "compose" and "port" in a:
            return (self.port + "\n", 0) if self.port else ("", 1)
        if a[:2] == ["ps", "-a"]:
            return "\n".join(c["Id"] for c in self.containers.values()), 0
        if a[:2] == ["container", "inspect"]:
            return json.dumps([c for c in self.containers.values() if c["Id"] in a[2:]]), 0
        if a[0] == "stop":
            for name in a[1:]:
                self.containers[name]["State"]["Running"] = False
            return "", 0
        if a[:2] == ["rm", "-f"]:
            for name in a[2:]:
                self.containers.pop(name, None)
            return "", 0
        if a[:2] == ["network", "ls"]:
            project = a[3].split("=")[-1]
            return "\n".join(n for n, p in self.networks.items() if p == project), 0
        if a[:2] == ["network", "rm"]:
            for n in a[2:]:
                self.networks.pop(n, None)
            return "", 0
        if a[:2] == ["volume", "ls"]:
            key = a[-1].split("=")[-1]
            return "\n".join(v for v, (_, k) in self.volumes.items() if k == key), 0
        if a[:2] == ["volume", "inspect"]:
            return json.dumps([{"Name": v, "Labels": {st.PROJECT_LABEL: self.volumes[v][0]}} for v in a[2:]]), 0
        if a[:2] == ["volume", "rm"]:
            for v in a[2:]:
                self.volumes.pop(v, None)
            return "", 0
        if a[:2] == ["image", "inspect"]:
            items = [{"Id": i, "Size": size, "RepoTags": tags, "Config": {"Env": [f"QROSETTA_IMAGE_GIT_SHA={sha}"]}}
                     for ref, (i, size, tags, sha) in self.images.items() if ref in a[2:]]
            return json.dumps(items), 0 if len(items) == len(a) - 2 else 125
        if a[:2] == ["pod", "ps"]:
            return "", 0
        if a[:2] == ["system", "df"]:
            return ("Images space usage:\n\nREPOSITORY TAG\n\nLocal Volumes space usage:\n\n"
                    "VOLUME NAME  LINKS  SIZE\nqr_db  1  34.48MB\nold_db  0  81.92kB\n"), 0
        return "", 0

    def commands(self, verb):
        """Calls of `verb`, with the names after its flags sorted."""
        out = []
        for c in self.calls:
            if c[1:2] == [verb]:
                flags = [x for x in c[2:] if x.startswith("-")]
                out.append([verb, *flags, *sorted(x for x in c[2:] if not x.startswith("-"))])
        return out


@pytest.fixture
def fake():
    return FakeEngineState()


def make(fake, tmp_path):
    engine = Engine(fake.engine, str(tmp_path), run=fake)
    return engine, st.load_stack(engine)


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


def test_exit_action_defaults():
    assert serve.exit_action(None, {}, tty=True) == "ask"
    assert serve.exit_action(None, {}, tty=False) == "standby"
    assert serve.exit_action("ask", {}, tty=False) == "standby"
    assert serve.exit_action(None, {"QROSETTA_ON_EXIT": "remove"}, tty=True) == "remove"
    assert serve.exit_action("standby", {"QROSETTA_ON_EXIT": "remove"}, tty=True) == "standby"
    with pytest.raises(CliError):
        serve.exit_action(None, {"QROSETTA_ON_EXIT": "delete"}, tty=True)


def test_discovery_is_this_project_only_and_names_conflicts(fake, tmp_path):
    fake.add("rosetta-api", "api")
    fake.add("nginx-reverse-proxy", "nginx", project="oldcheckout", running=False)
    fake.add("qiskit-runner", "", project="")
    fake.add("someone-else", "web", project="unrelated")
    fake.add("rosetta-api-copy", "api", project="unrelated")
    engine, stack = make(fake, tmp_path)
    ours, conflicts = st.scan(engine, stack)
    assert [c.name for c in ours] == ["rosetta-api"]
    assert [(c.name, c.project) for c in conflicts] == [("nginx-reverse-proxy", "oldcheckout"),
                                                       ("qiskit-runner", "")]
    text = st.conflict_help(engine, stack, conflicts)
    assert "nginx-reverse-proxy (project oldcheckout, stopped)" in text
    assert "qiskit-runner (no compose project, running)" in text
    assert text.endswith("podman rm -f nginx-reverse-proxy qiskit-runner")
    assert stack.core_services() == ["nginx", "api"]
    assert stack.resolve_service("rosetta-api") == "api"


def test_stop_stops_only_running_and_keeps_everything(fake, tmp_path):
    fake.add("rosetta-api", "api")
    fake.add("qiskit-runner", "qiskit_runner")
    fake.add("nginx-reverse-proxy", "nginx", running=False)
    engine, stack = make(fake, tmp_path)
    assert actions.stop_stack(engine, stack) == []
    assert fake.commands("stop") == [["stop", "qiskit-runner", "rosetta-api"]]
    assert not fake.commands("rm") and not fake.commands("rmi")
    assert len(fake.containers) == 3 and "qr_db" in fake.volumes


def test_stop_stops_pods_on_podman(fake, tmp_path):
    fake.add("rosetta-api", "api", pod="pod123")
    engine, stack = make(fake, tmp_path)
    actions.stop_stack(engine, stack)
    assert ["pod", "stop", "pod123"] in [c[1:] for c in fake.calls]


def test_remove_keeps_images_and_data_by_default(fake, tmp_path):
    fake.add("rosetta-api", "api")
    fake.add("nginx-reverse-proxy", "nginx", project="oldcheckout")
    fake.networks["oldcheckout_public_net"] = "oldcheckout"
    engine, stack = make(fake, tmp_path)
    assert actions.remove_stack(engine, stack) == 0
    assert fake.commands("stop") == [["stop", "rosetta-api"]]
    assert fake.commands("rm") == [["rm", "-f", "rosetta-api"]]
    assert fake.networks == {"oldcheckout_public_net": "oldcheckout"}
    assert fake.containers["nginx-reverse-proxy"]["State"]["Running"]
    assert not fake.commands("rmi") and set(fake.volumes) == {"qr_db", "old_db"}


def test_stop_leaves_other_projects_alone_and_says_how_to_remove_them(fake, tmp_path, capsys):
    fake.add("rosetta-api", "api", project="oldcheckout")
    engine, stack = make(fake, tmp_path)
    assert actions.stop_stack(engine, stack) == []
    assert not fake.commands("stop")
    assert "podman rm -f rosetta-api" in capsys.readouterr().out


def test_remove_images_untags_shared_images(fake, tmp_path, capsys):
    engine, stack = make(fake, tmp_path)
    found, freed, kept = actions.image_plan(engine, stack)
    assert set(found) == {"qr-nginx", "qr-api", "qr-qiskit_runner"}
    assert freed == 1000 and [i.ref for i in kept] == ["qr-api"]
    assert actions.remove_stack(engine, stack, images=True) == 0
    assert fake.commands("rmi")[0][1:] == ["qr-api", "qr-nginx", "qr-qiskit_runner"]
    assert "registry/x/api:latest" in capsys.readouterr().out


def test_remove_data_needs_typed_confirmation(fake, tmp_path, capsys):
    fake.add("rosetta-api", "api")
    engine, stack = make(fake, tmp_path)
    assert actions.remove_stack(engine, stack, data=True, ask=lambda q: "yes", tty=True) == 1
    assert not fake.commands("rm") and "qr_db" in fake.volumes
    out = capsys.readouterr().out
    assert "qr_db (32.9 MiB)" in out and "old_db" not in out and "saved run reports" in out
    with pytest.raises(CliError, match="terminal"):
        actions.remove_stack(engine, stack, data=True, tty=False)
    assert not fake.commands("rm")
    assert actions.remove_stack(engine, stack, data=True, ask=lambda q: "delete", tty=True) == 0
    assert set(fake.volumes) == {"old_db"} and fake.containers == {}


def test_plan_start_requires_core_images(fake, tmp_path):
    engine, stack = make(fake, tmp_path)
    services, missing, env = serve.plan_start(engine, stack, None, env={})
    assert services == ["nginx", "api", "qiskit_runner"] and missing == ["braket_runner"]
    assert env == {"QROSETTA_GIT_SHA": "abc123"}
    assert serve.plan_start(engine, stack, None, env={"QROSETTA_GIT_SHA": "x"})[2] == {}
    with pytest.raises(CliError, match="qrosetta build braket_runner"):
        serve.plan_start(engine, stack, ["braket_runner"], env={})
    del fake.images["qr-api"]
    with pytest.raises(CliError, match="No image for api"):
        serve.plan_start(engine, stack, None, env={})


def test_start_refuses_names_held_by_another_project(fake, tmp_path):
    fake.add("rosetta-api", "api", project="oldcheckout", running=False)
    engine, stack = make(fake, tmp_path)
    with pytest.raises(CliError, match="rosetta-api \\(project oldcheckout, stopped\\).*podman rm -f rosetta-api"):
        serve.check_conflicts(engine, stack, st.scan(engine, stack)[1])
    factory = lambda d: Engine(fake.engine, d, run=fake)
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    assert main(["start", "--detach"], checkout=str(tmp_path), engine_factory=factory) == 1
    assert not fake.commands("rm") and not fake.commands("stop")


def test_announce_says_whether_other_machines_can_reach_it(fake, tmp_path, capsys):
    engine, stack = make(fake, tmp_path)
    serve.announce_running(engine, stack)
    out = capsys.readouterr().out
    assert "http://localhost:8080" in out and "Published on 127.0.0.1:8080 (this machine only)" in out
    fake.port = "0.0.0.0:8080"
    serve.announce_running(engine, stack)
    assert "reachable from other machines" in capsys.readouterr().out


def test_compose_v1_or_podman_compose_is_refused_with_install_steps(tmp_path):
    run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "podman-compose version 1.2.0\n", "")
    with pytest.raises(CliError, match="Docker Compose v2.*podman-compose version 1.2.0.*cli-plugins/docker-compose"):
        Engine("podman", str(tmp_path), run=run).check_compose()


@pytest.mark.parametrize("port,url", [("0.0.0.0:8080", "http://localhost:8080"),
                                      ("127.0.0.1:80", "http://localhost"),
                                      ("192.168.1.5:8080", "http://192.168.1.5:8080"),
                                      ("[::]:9000", "http://localhost:9000"), ("", None)])
def test_url_from_compose_port(fake, tmp_path, port, url):
    fake.port = port
    engine, stack = make(fake, tmp_path)
    assert serve.stack_url(engine, stack) == url


def test_sizes():
    assert actions.parse_size("34.48MB") == 34480000
    assert actions.parse_size("1GiB") == 1024 ** 3
    assert actions.parse_size("12.5kB") == 12500
    assert actions.parse_size("n/a") is None
    assert actions.human_bytes(21_886_452_201) == "20.4 GiB"
    assert actions.human_bytes(1024 ** 3) == "1.0 GiB"


class FakeProcess:
    def __init__(self, on_wait=None):
        self.on_wait = on_wait
        self.terminated = False

    def wait(self, timeout=None):
        if self.on_wait:
            hook, self.on_wait = self.on_wait, None
            hook()
        return 0

    def poll(self):
        return None if not self.terminated else 0

    pid = None

    def send_signal(self, signum):
        self.terminated = True


def _server(fake, tmp_path, action, signum, answer=None, tty=True):
    fake.add("rosetta-api", "api")
    fake.add("nginx-reverse-proxy", "nginx")
    spawned = []
    server = None

    def popen(cmd, **kwargs):
        spawned.append(cmd)
        if "logs" in cmd:
            return FakeProcess(lambda: server._handle(signum, None))
        return FakeProcess()

    engine = Engine(fake.engine, str(tmp_path), run=fake, popen=popen)
    stack = st.load_stack(engine)
    server = serve.Server(engine, stack, action, ["nginx", "api"], {}, tty=tty, ask=lambda q: answer)
    return server, spawned


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_foreground_signal_puts_stack_on_standby(fake, tmp_path, signum):
    server, spawned = _server(fake, tmp_path, "standby", signum)
    assert server.run() == 0
    assert spawned[0][-4:] == ["up", "-d", "--no-build", "nginx", "api"][-4:]
    assert any("logs" in c for c in spawned)
    assert fake.commands("stop") == [["stop", "nginx-reverse-proxy", "rosetta-api"]]
    assert len(fake.containers) == 2


def test_ask_on_ctrl_c_removes_when_answered_r(fake, tmp_path):
    server, _ = _server(fake, tmp_path, "ask", signal.SIGINT, answer="r\n")
    assert server.run() == 0
    assert fake.containers == {} and "qr_db" in fake.volumes


def test_ask_falls_back_to_standby_on_hangup_or_no_answer(fake, tmp_path):
    server, _ = _server(fake, tmp_path, "ask", signal.SIGHUP, answer="r\n")
    assert server.run() == 0 and len(fake.containers) == 2
    fake2 = FakeEngineState()
    server, _ = _server(fake2, tmp_path, "ask", signal.SIGINT, answer=None)
    assert server.run() == 0 and len(fake2.containers) == 2 and fake2.commands("stop")


def test_ctrl_c_during_shutdown_warns_then_abandons(fake, tmp_path):
    server, _ = _server(fake, tmp_path, "standby", signal.SIGINT)
    server.phase = "shutdown"
    server._handle(signal.SIGTERM, None)
    server._handle(signal.SIGINT, None)
    with pytest.raises(serve.Abandoned):
        server._handle(signal.SIGINT, None)


def test_main_runs_subcommands_with_injected_engine(fake, tmp_path, capsys):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    fake.add("rosetta-api", "api")
    factory = lambda d: Engine(fake.engine, d, run=fake)
    assert main(["stop"], checkout=str(tmp_path), engine_factory=factory) == 0
    assert "standby" in capsys.readouterr().out
    assert main(["status"], checkout=str(tmp_path), engine_factory=factory) == 0
    assert "stopped" in capsys.readouterr().out
    assert main(["logs", "nosuch"], checkout=str(tmp_path), engine_factory=factory) == 1
    assert "Unknown service" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["start", "--on-exit", "explode"], checkout=str(tmp_path), engine_factory=factory)


def test_safe_boot_hands_start_to_qrosetta():
    text = (_REPO / "scripts" / "safe_boot.sh").read_text()
    assert 'exec ./qrosetta start "${CORE_SERVICES[@]}" "${SUCCESSFUL_RUNNERS[@]}"' in text
    assert "docker compose logs -f" not in text
    assert (_REPO / "qrosetta").stat().st_mode & 0o111


def test_failed_up_stops_what_started(fake, tmp_path):
    fake.add("rosetta-api", "api")

    class Failing(FakeProcess):
        def wait(self, timeout=None):
            return 1

    engine = Engine(fake.engine, str(tmp_path), run=fake, popen=lambda cmd, **kw: Failing())
    server = serve.Server(engine, st.load_stack(engine), "ask", ["api"], {}, tty=True, ask=lambda q: "r")
    assert server.run() == 1
    assert fake.commands("stop") == [["stop", "rosetta-api"]] and len(fake.containers) == 1
