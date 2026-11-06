"""Who holds the address `start` publishes on: this project's web server (its own), the web
server of another Quantum Rosetta project on this computer (refused: one project runs at a
time), or a Quantum Rosetta no container of this user publishes (another program, so the port
moves when no address was chosen)."""


import pytest

from tests.unit._qrosetta_fake import REPO, FakeEngine, FakeServer, Unreachable
from tests.unit.test_qrosetta_port_fallback import Ports, _config, _port_row, _stopped, _up_env

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from qrosetta_cli.stack import doctor, ownership as own, serve  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402


@pytest.fixture
def env(tmp_path):
    return {"QROSETTA_PROJECT": "qr", "PATH": "/usr/bin", "HOME": str(tmp_path / "home"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"), "XDG_CACHE_HOME": str(tmp_path / "cache")}


@pytest.fixture
def project(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)


class EngineHost(Ports):
    """A host whose engine reads (`ps`, `container inspect`) go to a fake engine."""

    def __init__(self, env, fake, **kwargs):
        super().__init__(env, **kwargs)
        self.fake = fake

    def run(self, cmd, **kwargs):
        if cmd[1:2] in (["ps"], ["container"]):
            return self.fake(cmd, **kwargs)
        return super().run(cmd, **kwargs)


def other_web_server(fake, project="other", working_dir="", host_ip="127.0.0.1", port="8080", running=True,
                     qr_label=True):
    labels = {own.PROJECT_LABEL: project, own.SERVICE_LABEL: "nginx", "org.qrosetta.id": "nginx",
              doctor.WORKING_DIR_LABEL: working_dir}
    if qr_label:
        labels[own.QR_LABEL] = project
    cid = fake.add(f"{project}-web", labels, running=running)
    fake.containers[cid]["NetworkSettings"] = {"Ports": {"8080/tcp": [{"HostIp": host_ip, "HostPort": port}]}}
    return cid


def _start(fake, project, env, host, answering=None, argv=("start", "-d")):
    """`answering`: a Quantum Rosetta that answers at every address before and after compose."""
    def transport(srv, token=None, timeout=None):
        if answering is not None:
            return answering(srv, token, timeout)
        if _up_env(fake):
            return FakeServer(fresh=True)(srv, token, timeout)
        return Unreachable()(srv, token, timeout)

    return main(list(argv), checkout=str(project), env=env, tty=False,
                engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env),
                transport_factory=transport, host_factory=lambda e: host)


def test_web_publishers_reads_running_labelled_web_servers_of_every_project(env):
    fake = FakeEngine()
    other_web_server(fake, "one", "/w/one")
    other_web_server(fake, "two", host_ip="", port="8085")
    other_web_server(fake, "stopped", running=False)
    other_web_server(fake, "unlabelled", qr_label=False)
    found = EngineHost(env, fake).web_publishers("podman")
    assert sorted(found) == [("127.0.0.1:8080", "one", "/w/one"), (":8085", "two", "")]
    assert doctor.other_project(EngineHost(env, fake), "podman", env, "127.0.0.1:8085") == ("two", "")
    assert doctor.other_project(EngineHost(env, fake), None, env, "127.0.0.1:8080") is None
    assert EngineHost(env, FakeEngine()).web_publishers("podman") == []


def test_stop_command_names_the_project_and_its_checkout():
    assert doctor.stop_other_command("other", "") == "QROSETTA_PROJECT=other qrosetta stop"
    assert doctor.stop_other_command("other", "/no/such/dir") == "QROSETTA_PROJECT=other qrosetta stop"
    assert doctor.stop_other_command("my proj", str(REPO)) == (
        f"QROSETTA_PROJECT='my proj' qrosetta --project-dir {REPO} stop")


@pytest.mark.parametrize("argv", [("start", "-d"), ("start", "-d", "--bind", "127.0.0.1:8080")])
def test_start_refuses_when_another_project_publishes_the_address(project, env, capsys, argv):
    fake = _stopped()
    other_web_server(fake, "other", str(REPO))
    host = EngineHost(env, fake, taken={8080})
    assert _start(fake, project, env, host, answering=FakeServer(), argv=argv) == Exit.ENGINE
    err = capsys.readouterr().err
    assert ("127.0.0.1:8080 is used by Quantum Rosetta project 'other' on this computer. "
            "Only one project can run at a time.") in err
    assert "Stop that project:" in err
    tail = [line.strip() for line in err.strip().splitlines()[-4:]]
    assert tail == ["1. Stop that project:", f"QROSETTA_PROJECT=other qrosetta --project-dir {REPO} stop", "",
                    "Then run the same `qrosetta start` command again."]
    assert not _up_env(fake) and host.probed == [8080]


def test_start_moves_off_a_quantum_rosetta_no_container_of_this_user_publishes(project, env, capsys):
    fake = _stopped()
    host = EngineHost(env, fake, taken={8080})
    assert _start(fake, project, env, host, answering=FakeServer(fresh=True)) == 0
    err = capsys.readouterr().err
    assert "Port 8080 is used by another Quantum Rosetta (not this project); using 8081." in err.splitlines()
    assert {e["QROSETTA_HTTP_BIND"] for e in _up_env(fake)} == {"127.0.0.1:8081"}


def test_a_chosen_address_held_by_a_foreign_quantum_rosetta_is_refused(project, env, capsys):
    fake = _stopped()
    host = EngineHost(env, fake, taken={8080})
    argv = ("start", "-d", "--bind", "127.0.0.1:8080")
    assert _start(fake, project, env, host, answering=FakeServer(), argv=argv) == Exit.ENGINE
    assert "127.0.0.1:8080 is used by another Quantum Rosetta (not this project)" in capsys.readouterr().err
    assert not _up_env(fake)


def test_this_projects_own_web_server_stays_its_own(project, env, capsys):
    fake = FakeEngine().standard()
    other_web_server(fake, "qr")
    host = EngineHost(env, fake, taken={8080}, published=["127.0.0.1:8080"])
    assert _start(fake, project, env, host, answering=FakeServer(fresh=True)) == 0
    err = capsys.readouterr().err
    assert "Port 8080" not in err and "Only one project" not in err
    assert host.probed == [8080]


def test_doctor_rows(env, tmp_path):
    fake = FakeEngine()
    other_web_server(fake, "other")
    row, rep = _port_row(env, EngineHost(env, fake, taken={8080}), server=FakeServer())
    assert row.status == "FAIL" and row.message == (
        "127.0.0.1:8080 is used by Quantum Rosetta project 'other' on this computer. Only one project can run at a time.")
    assert row.fix == "QROSETTA_PROJECT=other qrosetta stop" and row.reason == "port_other_project"
    row, rep = _port_row(env, EngineHost(env, FakeEngine(), taken={8080}), server=FakeServer())
    assert (row.status, row.message) == (
        "INFO", "127.0.0.1:8080 is used by another Quantum Rosetta (not this project); "
                "`qrosetta start` will use 127.0.0.1:8081")
    assert rep.port_holder == "quantum_rosetta"
    cfg = _config(tmp_path, '[lifecycle]\nbind = "127.0.0.1:8080"\n')
    row, _ = _port_row(env, EngineHost(env, FakeEngine(), taken={8080}), cfg, server=FakeServer())
    assert (row.status, row.message) == ("FAIL", "127.0.0.1:8080 is used by another Quantum Rosetta (not this project)")
    row, _ = _port_row(env, EngineHost(env, FakeEngine(), taken={8080}, published=["127.0.0.1:8080"]),
                       server=FakeServer())
    assert row.status == "PASS" and "running Quantum Rosetta" in row.message


def test_the_engine_reads_are_read_only(env):
    fake = FakeEngine()
    other_web_server(fake, "other")
    EngineHost(env, fake).web_publishers("podman")
    assert [c[1:3] for c, _ in fake.calls] == [["ps", "-a"], ["container", "inspect"]]
