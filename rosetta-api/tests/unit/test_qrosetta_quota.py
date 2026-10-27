"""qrosetta start --no-cpu-quota / --cpu-quota: the refusal on a host that does not delegate the
cgroup cpu controller, the generated compose override, the recorded stack setting, status and
doctor, against a fake engine and server."""

import hashlib
import json
import os

import pytest

from tests.unit._qrosetta_fake import CONFIG, FakeEngine, FakeServer

from qrosetta_cli import localstack  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.config import Config  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402
from qrosetta_cli.stack import doctor, quota, serve  # noqa: E402
from qrosetta_cli.stack import project as st  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402

ROOTLESS = {"version": {"Version": "5.8.2"}, "host": {"security": {"rootless": True}}}
LIMITS = {"resources": {"limits": {"cpus": 1, "memory": "1073741824"}}}


@pytest.fixture
def env(tmp_path):
    return {"QROSETTA_PROJECT": "qr", "PATH": "/usr/bin", "HOME": str(tmp_path / "home"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"), "XDG_CACHE_HOME": str(tmp_path / "cache")}


@pytest.fixture
def project(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path


@pytest.fixture
def fake():
    engine = FakeEngine().standard()
    for c in engine.containers.values():
        c["State"]["Running"] = False
    engine.extra_services = {name: dict(CONFIG["services"][name], deploy=LIMITS)
                             for name in ("api", "qiskit_runner")}
    return engine


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)


def host(monkeypatch, controllers):
    """A rootless host on cgroup v2 whose user instance has `controllers` delegated."""
    monkeypatch.setattr(quota, "_read", lambda path: controllers if path.endswith("cgroup.controllers") else None)
    monkeypatch.setattr(quota, "_exists", lambda path: path == "/sys/fs/cgroup/cgroup.controllers")


def cli(fake, project, env, argv, server=None):
    return main(argv, checkout=str(project), env=env, tty=False,
                engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env, info=ROOTLESS),
                transport_factory=server or FakeServer(fresh=True))


def up_files(fake):
    cmd = fake.compose_calls("up")[-1]
    return [cmd[i + 1] for i, a in enumerate(cmd) if a == "-f"]


def test_start_on_a_host_without_the_cpu_controller_fails_with_the_fix_and_the_flag(fake, project, env, capsys,
                                                                                    monkeypatch):
    host(monkeypatch, "memory pids\n")
    assert cli(fake, project, env, ["start", "-d"]) == Exit.ENGINE
    err = capsys.readouterr().err
    assert "cpu controller is not delegated" in err and "Delegate=cpu memory pids" in err
    assert "qrosetta start -d --no-cpu-quota" in err
    assert not fake.compose_calls("up") and not fake.destructive_calls()
    assert not os.path.exists(localstack.settings_path(env))
    assert not os.path.exists(quota.override_path(env))


def test_start_without_the_memory_controller_fails_whatever_the_quota(fake, project, env, capsys, monkeypatch):
    host(monkeypatch, "cpu pids\n")
    assert cli(fake, project, env, ["start", "-d", "--no-cpu-quota"]) == Exit.ENGINE
    assert "memory controller is not delegated" in capsys.readouterr().err
    assert not fake.compose_calls("up")


def test_no_cpu_quota_starts_through_the_generated_override(fake, project, env, capsys, monkeypatch):
    host(monkeypatch, "memory pids\n")
    compose_file = (project / "docker-compose.yml").read_text()
    assert cli(fake, project, env, ["start", "-d", "--no-cpu-quota", "--json"]) == 0
    out, err = capsys.readouterr()
    path = quota.override_path(env)
    assert path == os.path.join(env["XDG_STATE_HOME"], "qrosetta", "compose.no-cpu-quota.yaml")
    assert up_files(fake)[-1] == path and up_files(fake)[0] == str(project / "docker-compose.yml")
    text = open(path).read()
    assert text.count("cpus: !reset null") == 2 and '"api":' in text and '"qiskit_runner":' in text
    assert '"nginx":' not in text and "memory:" not in text
    assert (project / "docker-compose.yml").read_text() == compose_file
    assert "CPU quota off since" in err and "cpu_quota_cores null" in err
    data = json.loads(out)["data"]["cpu_quota"]
    assert data["enabled"] is False and data["override"] == path and data["since"]
    assert data["override_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    setting = localstack.stack_settings(env, "qr")
    assert setting["cpu_quota"] is False and setting["since"] == data["since"]
    assert all(not p.startswith("/tmp") for p in (path, localstack.settings_path(env)))


def test_the_setting_is_kept_until_cpu_quota_restores_it(fake, project, env, capsys, monkeypatch):
    host(monkeypatch, "memory pids\n")
    assert cli(fake, project, env, ["start", "-d", "--no-cpu-quota"]) == 0
    since = localstack.stack_settings(env, "qr")["since"]
    assert cli(fake, project, env, ["stop", "--force"]) == 0
    assert cli(fake, project, env, ["start", "-d"]) == 0
    assert up_files(fake)[-1] == quota.override_path(env)
    assert localstack.stack_settings(env, "qr")["since"] == since
    capsys.readouterr()
    assert cli(fake, project, env, ["status", "--json"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["data"]["cpu_quota"]["enabled"] is False
    config_calls = [c for c in fake.compose_calls("config")]
    assert config_calls and quota.override_path(env) in config_calls[-1]
    assert cli(fake, project, env, ["start", "-d", "--cpu-quota"]) == Exit.ENGINE
    assert localstack.stack_settings(env, "qr")["cpu_quota"] is False
    host(monkeypatch, "cpu memory pids\n")
    assert cli(fake, project, env, ["stop", "--force"]) == 0
    assert cli(fake, project, env, ["start", "-d", "--cpu-quota"]) == 0
    assert quota.override_path(env) not in up_files(fake)
    assert localstack.stack_settings(env, "qr") == {"cpu_quota": True, "since": localstack.stack_settings(
        env, "qr")["since"], "override": None, "override_sha256": None}
    capsys.readouterr()
    assert cli(fake, project, env, ["status"]) == 0
    assert "CPU quota off" not in capsys.readouterr().out


def test_status_prints_the_setting_on_a_stack_without_the_quota(fake, project, env, capsys, monkeypatch):
    host(monkeypatch, "memory pids\n")
    assert cli(fake, project, env, ["start", "-d", "--no-cpu-quota"]) == 0
    capsys.readouterr()
    assert cli(fake, project, env, ["status"]) == 0
    out = capsys.readouterr().out
    assert "CPU quota off since" in out and "`qrosetta start -d --cpu-quota` restores it" in out


def test_config_cpu_quota_false_is_applied_and_recorded(fake, project, env, capsys, monkeypatch):
    host(monkeypatch, "memory pids\n")
    cfg = os.path.join(env["XDG_CONFIG_HOME"], "qrosetta")
    os.makedirs(cfg)
    with open(os.path.join(cfg, "config.toml"), "w") as fh:
        fh.write("[lifecycle]\ncpu_quota = false\n")
    assert cli(fake, project, env, ["start", "-d"]) == 0
    assert up_files(fake)[-1] == quota.override_path(env)
    assert "not applied by this version" not in capsys.readouterr().err
    assert localstack.stack_settings(env, "qr")["cpu_quota"] is False


def test_a_delegating_host_starts_with_the_quota_and_records_nothing(fake, project, env, monkeypatch):
    host(monkeypatch, "cpu io memory pids\n")
    assert cli(fake, project, env, ["start", "-d"]) == 0
    assert up_files(fake) == [str(project / "docker-compose.yml")]
    assert not os.path.exists(localstack.settings_path(env))


def test_the_override_needs_compose_with_reset(fake, project, env):
    engine = Engine(fake.engine, str(project), run=fake, popen=fake.popen, env=env)
    stack = st.load_stack(engine)
    engine.compose_version = (2, 23)
    with pytest.raises(CliError) as err:
        quota.apply(engine, stack, False, env)
    assert err.value.reason == "compose_too_old" and "2.24" in err.value.message
    engine.compose_version = (2, 24)
    assert quota.apply(engine, stack, False, env) and engine.files[-1] == quota.override_path(env)
    quota.apply(engine, stack, False, env)
    assert engine.files.count(quota.override_path(env)) == 1


def test_override_text_resets_only_cpus():
    text = quota.override_text("qr", ["b_runner", "a"])
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    assert lines == ["services:", '  "a":', "    deploy:", "      resources:", "        limits:",
                     "          cpus: !reset null", '  "b_runner":', "    deploy:", "      resources:",
                     "        limits:", "          cpus: !reset null"]
    assert "services: {}" in quota.override_text("qr", [])


def test_the_cpu_controller_engine_error_names_both_remedies():
    from qrosetta_cli.stack import explain
    err = explain.engine_error("Error: crun: the requested cgroup controller `cpu` is not available", "up failed")
    assert "Delegate=cpu memory pids" in err.message and err.hint == "qrosetta start -d --no-cpu-quota"


class _Host(doctor.Host):
    def __init__(self, env, controllers):
        super().__init__(env)
        self.controllers = controllers

    def uid(self):
        return 1000

    def read(self, path):
        return self.controllers if path.endswith("user@1000.service/cgroup.controllers") else None

    def exists(self, path):
        return path == "/sys/fs/cgroup/cgroup.controllers"


def _cgroup_check(env, controllers):
    from qrosetta_cli.stack.engine import Choice
    rep = doctor.Report()
    on = localstack.cpu_quota(env, Config(path="", explicit=False))[0]
    doctor.check_controllers(_Host(env, controllers), rep, Choice("podman", "", ROOTLESS), on)
    return rep.checks[0]


def test_doctor_names_the_flag_for_a_missing_cpu_controller_and_warns_once_it_is_used(env):
    check = _cgroup_check(env, "memory pids\n")
    assert check.status == "FAIL" and "qrosetta start -d --no-cpu-quota" in check.fix
    assert "Delegate=cpu memory pids" in check.fix
    check = _cgroup_check(env, "cpu pids\n")
    assert check.status == "FAIL" and "--no-cpu-quota" not in check.fix
    localstack.write_stack_settings(env, "qr", {"cpu_quota": False, "since": "2026-10-27T10:00:00Z"})
    check = _cgroup_check(env, "memory pids\n")
    assert check.status == "WARN" and "without the CPU quota" in check.message
    assert _cgroup_check(env, "cpu memory pids\n").status == "PASS"


def test_doctor_probes_services_with_the_lifecycle_token(env, capsys):
    from qrosetta_cli.stack import hostload
    token = hostload.ensure_token(env)
    server = FakeServer(fresh=True, block={"platform_version": "2.0.0", "api_levels": [1, 1], "features": {}})
    rep = doctor.Report()
    doctor.check_live(rep, {"server": server.block}, server, env)
    fresh = [h for p, q, h in server.headers if p == "/runners" and q == {"fresh": "true"}]
    assert fresh and fresh[0]["Authorization"] == f"Bearer {token}"
    assert any(c.id == "runners" and "probed now" in c.message for c in rep.checks)
    server = FakeServer(fresh="unauthorised")
    rep = doctor.Report()
    doctor.check_live(rep, {"server": None}, server, env)
    assert any(c.id == "runners" and "cached availability: the server did not take the lifecycle token" in c.message
               for c in rep.checks)
