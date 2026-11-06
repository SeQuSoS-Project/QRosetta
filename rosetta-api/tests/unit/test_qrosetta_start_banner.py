"""Where Quantum Rosetta runs, as `qrosetta start` (detached and foreground) ends and `qrosetta
status` begins: the URL and who can reach it, the manual and API docs, the URLs for other
computers when every interface is published, marks or words, colour, and the JSON unchanged."""

import io
import json
import socket

import pytest

from tests.unit._qrosetta_fake import FakeEngine, FakeProcess, FakeServer, Unreachable

from qrosetta_cli import output  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.stack import serve  # noqa: E402
from qrosetta_cli.stack import project as st  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402

URL = "http://localhost:8080"


class Stream(io.StringIO):
    def __init__(self, tty, encoding):
        super().__init__()
        self._tty, self._encoding = tty, encoding

    def isatty(self):
        return self._tty

    @property
    def encoding(self):
        return self._encoding


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
def quiet(monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    monkeypatch.setattr(socket, "gethostname", lambda: "lab-pc")
    monkeypatch.setattr(serve, "route_address", lambda: "192.0.2.10")
    yield
    output.configure()


def stopped():
    fake = FakeEngine().standard()
    for c in fake.containers.values():
        c["State"]["Running"] = False
    return fake


def cli(fake, project, env, argv, server=None):
    return main(argv, checkout=str(project), env=env, tty=False,
                engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env),
                transport_factory=server or Unreachable())


def test_start_detach_ends_with_where_it_runs_then_the_next_step(project, env, capsys):
    assert cli(stopped(), project, env, ["start", "-d"], FakeServer(fresh=True)) == 0
    out, err = capsys.readouterr()
    assert out.splitlines()[-5:] == [
        "Quantum Rosetta is running at http://localhost:8080  (this computer only)",
        "    Manual    http://localhost:8080/docs.html",
        "    API docs  http://localhost:8080/docs",
        "",
        "Next step:  open http://localhost:8080 in a browser, or run `qrosetta selftest`",
    ]
    tail = err.splitlines()
    assert tail[-1] == "" and tail[-2] == "`qrosetta stop` puts it on standby; `qrosetta remove` removes it."
    assert tail[-3].startswith("Finished jobs: ")
    assert tail[-4] == "Published on 127.0.0.1:8080; `qrosetta start --bind ADDRESS:PORT` changes it."
    assert "running at" not in err and "this machine" not in out + err


def test_every_interface_lists_this_hosts_name_and_address_for_other_computers(project, env, capsys):
    fake = stopped()
    fake.port = "0.0.0.0:9000"
    assert cli(fake, project, env, ["start", "-d", "--bind", "0.0.0.0:9000"], FakeServer(fresh=True)) == 0
    out, err = capsys.readouterr()
    assert out.splitlines()[-7:-2] == [
        "Quantum Rosetta is running at http://localhost:9000  (reachable from other computers)",
        "    Network   http://lab-pc:9000",
        "              http://192.0.2.10:9000",
        "    Manual    http://localhost:9000/docs.html",
        "    API docs  http://localhost:9000/docs",
    ]
    assert "0.0.0.0:9000 is reachable from other computers, over plain HTTP without TLS." in err
    assert "Published on 0.0.0.0:9000; `qrosetta start --bind ADDRESS:PORT` changes it." in err


def test_one_non_loopback_address_is_its_own_url(monkeypatch):
    lines = serve.running_lines("http://192.168.1.5:8080", "192.168.1.5:8080", Stream(False, "utf-8"))
    assert lines[0] == "Quantum Rosetta is running at http://192.168.1.5:8080  (reachable from other computers)"
    assert not any("Network" in line for line in lines)
    assert serve.running_lines(URL, "127.0.0.2:8080", Stream(False, "utf-8"))[0].endswith("(this computer only)")
    assert serve.running_lines(URL, "[::1]:8080", Stream(False, "utf-8"))[0].endswith("(this computer only)")


def test_other_hosts_skip_localhost_names_and_a_missing_route(monkeypatch):
    assert serve.other_hosts() == ["lab-pc", "192.0.2.10"]
    monkeypatch.setattr(socket, "gethostname", lambda: "localhost.localdomain")
    monkeypatch.setattr(serve, "route_address", lambda: None)
    assert serve.other_hosts() == []
    lines = serve.running_lines(URL, "[::]:8080", Stream(False, "utf-8"), hosts=lambda: ["fe80::1"])
    assert "    Network   http://[fe80::1]:8080" in lines


def test_route_address_selects_a_route_without_sending(monkeypatch):
    calls = []

    class Sock:
        def __init__(self, family, kind):
            calls.append((family, kind))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def connect(self, address):
            calls.append(address)

        def getsockname(self):
            return ("198.51.100.7", 40000)

        def send(self, data):
            raise AssertionError("sent a packet")

    monkeypatch.undo()
    monkeypatch.setattr(socket, "socket", Sock)
    assert serve.route_address() == "198.51.100.7"
    assert calls[0] == (socket.AF_INET, socket.SOCK_DGRAM)

    def unreachable(*args):
        raise OSError("Network is unreachable")

    monkeypatch.setattr(socket, "socket", unreachable)
    assert serve.route_address() is None


def test_no_published_port_says_only_that_it_runs(project, env, capsys):
    fake = stopped()
    fake.port = ""
    assert cli(fake, project, env, ["start", "-d"], FakeServer(fresh=True)) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[-3:] == ["Quantum Rosetta is running.", "", "Next step:  qrosetta selftest"]
    assert "Manual" not in out and "docs.html" not in out


def test_json_is_unchanged(project, env, capsys):
    assert cli(stopped(), project, env, ["start", "-d", "--json"], FakeServer(fresh=True)) == 0
    out, err = capsys.readouterr()
    doc = json.loads(out)
    assert doc["data"]["url"] == URL and set(doc["data"]) == {
        "url", "started", "recreated", "recreations", "not_started", "ready", "cpu_quota", "finished_jobs"}
    assert "running at" not in err


def test_foreground_start_ends_with_where_it_runs_then_ctrl_c(project, env, capsys):
    fake = stopped()
    engine = Engine(fake.engine, str(project), run=fake, popen=lambda cmd, **kw: FakeProcess(), env=env)
    server = serve.Server(engine, st.load_stack(engine), "standby", ["api"], {}, jobs_line="Finished jobs: x")
    server._up()
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        "Quantum Rosetta is running at http://localhost:8080  (this computer only)",
        "    Manual    http://localhost:8080/docs.html",
        "    API docs  http://localhost:8080/docs",
        "",
        "Press Ctrl-C to stop it.",
    ]
    assert err.splitlines()[-3:] == [
        "Published on 127.0.0.1:8080; `qrosetta start --bind ADDRESS:PORT` changes it.", "Finished jobs: x", ""]


def test_status_starts_with_the_same_lines(project, env, capsys):
    server = FakeServer(block={"platform_version": "2.0.0", "api_levels": [1, 1], "features": {}})
    assert cli(FakeEngine().standard(), project, env, ["status"], server) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[:6] == [
        "Quantum Rosetta is running at http://localhost:8080  (this computer only)",
        "    Server    platform 2.0.0, API levels 1-1",
        "    Manual    http://localhost:8080/docs.html",
        "    API docs  http://localhost:8080/docs",
        "",
        out.splitlines()[5],
    ]
    assert out.splitlines()[5].startswith("Project qr, engine podman")


def test_status_without_a_published_port_says_only_that_it_runs(project, env, capsys):
    fake = FakeEngine().standard()
    fake.port = ""
    assert cli(fake, project, env, ["status"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "Quantum Rosetta is running."


@pytest.mark.parametrize("stream,first,indent", [
    (Stream(True, "utf-8"), "✓  Quantum Rosetta is running at http://localhost:8080  (this computer only)", 5),
    (Stream(True, "ascii"), "Quantum Rosetta is running at http://localhost:8080  (this computer only)", 4),
    (Stream(False, "utf-8"), "Quantum Rosetta is running at http://localhost:8080  (this computer only)", 4),
])
def test_a_mark_on_a_utf8_terminal_and_none_otherwise_without_colour_under_no_color(stream, first, indent):
    output.configure(env={"NO_COLOR": "1"})
    lines = serve.running_lines(URL, "127.0.0.1:8080", stream)
    assert lines == [first, " " * indent + "Manual    http://localhost:8080/docs.html",
                     " " * indent + "API docs  http://localhost:8080/docs"]


def test_colour_on_the_mark_only_and_the_indent_unchanged():
    output.configure(env={"CLICOLOR_FORCE": "1"})
    lines = serve.running_lines(URL, "127.0.0.1:8080", Stream(True, "utf-8"))
    assert lines[0] == "\033[32m✓\033[0m  Quantum Rosetta is running at http://localhost:8080  (this computer only)"
    assert lines[1] == "     Manual    http://localhost:8080/docs.html"
