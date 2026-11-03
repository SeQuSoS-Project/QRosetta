"""qrosetta doctor against a fake host, and the plain-language table of engine failures (one
recorded engine message per row)."""

import json
import stat
import subprocess

import pytest

from tests.unit._qrosetta_fake import FakeServer, Unreachable

from qrosetta_cli import config as cfgmod  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.context import Context  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402
from qrosetta_cli.stack import doctor, explain  # noqa: E402

UID = 1000
CONTROLLERS = f"/sys/fs/cgroup/user.slice/user-{UID}.slice/user@{UID}.service/cgroup.controllers"
PODMAN_INFO = {"version": {"Version": "5.4.0"}, "host": {"security": {"rootless": True}},
               "store": {"graphRoot": "/store"}}


class FakeHost(doctor.Host):
    def __init__(self, env, files=None, paths=(), docker="missing", podman="ok", system="Linux",
                 machine="x86_64", port_free=True, free=50 * doctor.GIB, compose="Docker Compose version v2.30.0",
                 modes=None, running=None):
        self.env = env
        self.running = running
        self.files = {"/etc/subuid": "u:100000:65536\n", "/etc/subgid": "u:100000:65536\n",
                      CONTROLLERS: "cpu io memory pids\n", **(files or {})}
        self.paths = {"/sys/fs/cgroup/cgroup.controllers", f"{env['XDG_RUNTIME_DIR']}/podman/podman.sock", *paths}
        self.docker, self.podman, self._system, self._machine = docker, podman, system, machine
        self._port_free, self._free, self.compose, self.modes = port_free, free, compose, modes or {}

    def running_services(self, ctx):
        return self.running

    def which(self, name):
        state = {"docker": self.docker, "podman": self.podman}.get(name, "missing")
        return None if state == "missing" else f"/usr/bin/{name}"

    def run(self, cmd, **kwargs):
        name, args = cmd[0].rsplit("/", 1)[-1], cmd[1:]
        if args == ["--version"]:
            return subprocess.CompletedProcess(cmd, 0, f"{name} version 1\n", "")
        if args[:1] == ["info"]:
            state = self.docker if name == "docker" else self.podman
            if state == "ok":
                info = PODMAN_INFO if name == "podman" else {"ServerVersion": "27.0", "SecurityOptions": [],
                                                             "DockerRootDir": "/var/lib/docker"}
                return subprocess.CompletedProcess(cmd, 0, json.dumps(info), "")
            return subprocess.CompletedProcess(cmd, 1, "", "permission denied while trying to connect to the "
                                               "Docker daemon socket at unix:///var/run/docker.sock")
        if args[:2] == ["compose", "version"]:
            return subprocess.CompletedProcess(cmd, 0, self.compose + "\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "unexpected")

    def system(self):
        return self._system

    def machine(self):
        return self._machine

    def uid(self):
        return UID

    def user(self):
        return "u"

    def read(self, path):
        return self.files.get(path)

    def exists(self, path):
        return path in self.paths or path in self.files

    def free_bytes(self, path):
        return self._free

    def port_free(self, host, port):
        return self._port_free

    def mode(self, path):
        return self.modes.get(path)


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_RUNTIME_DIR": str(tmp_path / "run"), "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CACHE_HOME": str(tmp_path / "cache")}


def _doctor(env, host, server=None):
    ctx = Context(args=type("A", (), {})(), env=env, cfg=cfgmod.Config("/none", False),
                  transport_factory=server or Unreachable())
    return doctor.run(ctx, host)


def _by_id(rep):
    out = {}
    for c in rep.checks:
        out.setdefault(c.id, []).append(c)
    return out


def test_a_healthy_rootless_podman_host_passes(env):
    rep = _doctor(env, FakeHost(env))
    assert not rep.failed
    checks = _by_id(rep)
    assert checks["engine"][0].status == "PASS" and "podman 5.4.0 (rootless)" in checks["engine"][0].message
    assert checks["cgroup"][0].status == "PASS" and checks["subuid"][0].status == "PASS"
    assert checks["server"][0].status == "INFO" and "live checks skipped" in checks["server"][0].message


def test_docker_refused_with_podman_working_is_info(env):
    rep = _doctor(env, FakeHost(env, docker="refused"))
    engine = _by_id(rep)["engine"][0]
    assert engine.status == "INFO" and "docker: permission denied for this user" in engine.message
    assert not rep.failed


def test_neither_engine_is_a_failure_with_the_docker_group_line(env):
    rep = _doctor(env, FakeHost(env, docker="refused", podman="missing"))
    engine = _by_id(rep)["engine"][0]
    assert engine.status == "FAIL" and "usermod -aG docker" in engine.fix


@pytest.mark.parametrize("kwargs,check,fix", [
    ({"system": "Darwin", "machine": "arm64"}, "os", "Linux x86_64"),
    ({"compose": "podman-compose version 1.2.0"}, "compose", "--no-install-recommends docker-compose-v2"),
    ({"files": {"/etc/subuid": ""}}, "subuid", "usermod --add-subuids"),
    ({"files": {CONTROLLERS: "memory pids\n"}}, "cgroup", "Delegate=cpu memory pids"),
    ({"port_free": False}, "port", "qrosetta start -d --bind 127.0.0.1:8090"),
])
def test_each_failure_names_its_fix(env, kwargs, check, fix):
    rep = _doctor(env, FakeHost(env, **kwargs))
    failing = [c for c in rep.failed if c.id == check]
    assert failing and fix in failing[0].fix, rep.checks


def test_missing_podman_socket_and_cgroup_v1(env, tmp_path):
    host = FakeHost(env)
    host.paths = set()
    checks = _by_id(_doctor(env, host))
    assert checks["podman_socket"][0].fix == "systemctl --user enable --now podman.socket"
    assert checks["cgroup"][0].status == "FAIL" and "cgroup v1" in checks["cgroup"][0].message


def test_low_disk_warns_and_credentials_mode_fails(env):
    creds = env["XDG_STATE_HOME"] + "/qrosetta/credentials.json"
    rep = _doctor(env, FakeHost(env, free=2 * doctor.GIB, modes={creds: stat.S_IFREG | 0o644}))
    checks = _by_id(rep)
    assert any(c.status == "WARN" for c in checks["disk"]) and any("/var/tmp" in c.message for c in checks["disk"])
    assert checks["credentials"][0].status == "FAIL" and checks["credentials"][0].fix == f"chmod 600 {creds}"


def test_live_checks_with_a_running_server(env):
    old = FakeServer(runners=[{"id": "qiskit", "enabled": True, "available": False, "unavailable_reason": "unreachable"},
                              {"id": "cirq", "enabled": True, "available": True}])
    checks = _by_id(_doctor(env, FakeHost(env, port_free=False), server=old))
    assert checks["port"][0].status == "PASS" and "running Quantum Rosetta" in checks["port"][0].message
    assert checks["server"][0].status == "WARN" and "predates" in checks["server"][0].message
    assert checks["runners"][0].status == "WARN" and "1 of 2 runners available" in checks["runners"][0].message
    new = FakeServer(block={"platform_version": "2.0.0", "api_levels": [1, 1], "features": {}},
                     runners=[{"id": "qiskit", "enabled": True, "available": False, "error_kind": "dns"}])
    checks = _by_id(_doctor(env, FakeHost(env), server=new))
    assert checks["server"][0].status == "PASS" and "cannot resolve qiskit" in checks["runners"][0].message
    assert checks["ready"][0].status == "SKIP"
    checks = _by_id(_doctor(env, FakeHost(env, running={"cirq"}), server=new))
    assert checks["runners"][0].status == "INFO" and "not started in this stack: qiskit" in checks["runners"][0].message


@pytest.mark.parametrize("answer,status,words", [
    ((200, {"status": "ready", "checks": {"database": "ok", "job_storage": "ok"}}), "PASS", "database and job storage work"),
    ((503, {"detail": "Not ready: the database does not answer.", "status": "not_ready"}), "FAIL",
     "Not ready: the database does not answer."),
    ((502, None), "FAIL", "GET /ready answered HTTP 502"),
])
def test_live_checks_read_the_servers_readiness(env, answer, status, words):
    block = {"platform_version": "2.0.0", "api_levels": [1, 1], "features": {"readiness": 1}}
    checks = _by_id(_doctor(env, FakeHost(env), server=FakeServer(block=block, status={"/ready": answer})))
    assert checks["ready"][0].status == status and words in checks["ready"][0].message
    if status == "FAIL":
        assert checks["ready"][0].fix == "qrosetta logs api --tail 50"


def test_doctor_command_exit_codes_and_envelope(env, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "Host", lambda e: FakeHost(env))
    assert main(["doctor"], env=env, transport_factory=Unreachable()) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("PASS")
    monkeypatch.setattr(doctor, "Host", lambda e: FakeHost(env, port_free=False))
    assert main(["doctor", "--json"], env=env, transport_factory=Unreachable()) == Exit.CHECKS_FAILED
    doc = json.loads(capsys.readouterr().out)
    from tests.unit.test_qrosetta_contracts import validate_envelope
    validate_envelope(doc)
    assert doc["error"]["code"] == "checks_failed" and doc["data"]["failed"] == 1
    assert doc["error"]["hint"] == "qrosetta start -d --bind 127.0.0.1:8090"


RECORDED = [
    ("Error: rootlessport listen tcp 127.0.0.1:8080: bind: address already in use", "port_in_use"),
    ("Error response from daemon: driver failed programming external connectivity on endpoint nginx-reverse-proxy: "
     "Bind for 127.0.0.1:8080 failed: port is already allocated", "port_in_use"),
    ('permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: Get '
     '"http://%2Fvar%2Frun%2Fdocker.sock/v1.24/containers/json": dial unix /var/run/docker.sock: connect: '
     'permission denied', "docker_permission"),
    ("Cannot connect to the Docker daemon at unix:///run/user/1000/podman/podman.sock. Is the docker daemon running?",
     "podman_socket"),
    ("Error: OCI runtime error: crun: the requested cgroup controller `cpu` is not available", "cpu_controller_missing"),
    ('cannot find mappings for user u: No subuid ranges found for user "u" in /etc/subuid', "subuid_missing"),
    ("potentially insufficient UIDs or GIDs available in user namespace (requested 0:42 for /etc/shadow): Check "
     "/etc/subuid and /etc/subgid", "subuid_missing"),
    ("newuidmap: write to uid_map failed: Operation not permitted", "subuid_missing"),
    ('Error: writing blob: storing blob to file "/var/tmp/storage123/1": write /var/tmp/storage123/1: no space left '
     "on device", "no_space"),
    ("Error: initializing source docker://ghcr.io/sequsos-project/qrosetta-api@sha256:00: reading manifest "
     "sha256:00 in ghcr.io/sequsos-project/qrosetta-api: manifest unknown", "image_not_in_registry"),
    ("exec /usr/local/bin/python3: exec format error", "wrong_architecture"),
    ("toomanyrequests: retry-after: 0.000000, allowed: 44000/minute", "registry_rate_limit"),
    ("dependency failed to start: container rosetta-api is unhealthy", "api_unhealthy"),
    ('Error response from daemon: Conflict. The container name "/rosetta-api" is already in use by container '
     '"abc123". You have to remove (or rename) that container to be able to reuse that name.', "name_conflict"),
    ('Error: creating container storage: the container name "rosetta-api" is already in use by 3f2a. You have to '
     "remove that container to be able to reuse that name: that name is already in use", "name_conflict"),
]


@pytest.mark.parametrize("text,reason", RECORDED)
def test_each_engine_message_gets_its_plain_language_row(text, reason):
    err = explain.engine_error(text, "`compose up` failed")
    assert err.code == Exit.ENGINE and err.reason == reason and err.hint


def test_every_row_has_a_recorded_message():
    assert {r for _, r in RECORDED} >= {explain.explain(t)[1] for t, _ in RECORDED}
    assert len({explain.explain(t)[1] for t, _ in RECORDED}) == len(explain.ROWS)


def test_specific_wording():
    msg, _, hint = explain.explain("bind: address already in use", "127.0.0.1:9999")
    assert msg == "127.0.0.1:9999 is in use." and hint == "qrosetta start -d --bind 127.0.0.1:8090"
    assert "rosetta-api" in explain.explain(RECORDED[-1][0])[0]
    assert "/var/tmp" in explain.explain(RECORDED[8][0])[0]


def test_unmatched_messages_print_the_last_line_and_doctor():
    err = explain.engine_error("line one\nError: something new\n", "`compose up` failed")
    assert err.reason == "engine_error" and err.message.endswith("Error: something new") and err.hint == "qrosetta doctor"


@pytest.mark.parametrize("kind,words", [("dns", "cannot resolve qiskit"), ("connect", "cold start"),
                                        ("timeout", "within 5 s"), ("http", "answered with an error"),
                                        ("other", "not available")])
def test_probe_kinds(kind, words):
    message, hint = explain.probe_message(kind, "qiskit")
    assert words in message and hint.startswith("qrosetta")


def test_check_error_codes_are_cli_errors():
    assert isinstance(explain.engine_error("x", "y"), CliError)
