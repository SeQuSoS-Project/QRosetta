"""`qrosetta start` on another port when another program holds 127.0.0.1:8080 and the user chose
no address: the search over 8080-8089, the recorded address and who reads it, doctor's row, the
refusals that stay, and the own-stack test."""

import json
import socket

import pytest

from tests.unit._qrosetta_fake import FakeEngine, FakeServer, Unreachable
from tests.unit.test_qrosetta_doctor import FakeHost

from qrosetta_cli import config as cfgmod, localstack  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import servers  # noqa: E402
from qrosetta_cli.context import Context  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from qrosetta_cli.stack import doctor, ports, quota, serve  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402


class Ports(FakeHost):
    """A host where other programs hold the ports in `taken` (on 127.0.0.1)."""

    def __init__(self, env, taken=(), **kwargs):
        super().__init__(env, **kwargs)
        self.taken = set(taken)
        self.probed = []

    def port_free(self, host, port):
        self.probed.append(port)
        return port not in self.taken


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


def _stopped():
    fake = FakeEngine().standard()
    for c in fake.containers.values():
        c["State"]["Running"] = False
    return fake


def _cli(fake, project, env, argv, host, server=None):
    """`server` answers once compose has started the stack; before that the programs holding
    ports are not Quantum Rosetta."""
    def transport(srv, token=None, timeout=None):
        if server is None or not _up_env(fake):
            return Unreachable()(srv, token, timeout)
        return server(srv, token, timeout)

    return main(argv, checkout=str(project), env=env, tty=False,
                engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env),
                transport_factory=transport, host_factory=lambda e: host)


def _up_env(fake):
    return [e for c, e in fake.calls if c[1:2] == ["compose"] and "up" in c]


def _recorded(env):
    return localstack.stack_settings(env, "qr").get("bind")


def _config(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text)
    return cfgmod.load(str(path), {})


# --- start --------------------------------------------------------------------------------------


def test_start_moves_to_the_first_free_port_says_so_and_records_it(project, env, capsys):
    fake = _stopped()
    host = Ports(env, taken={8080, 8081})
    assert _cli(fake, project, env, ["start", "-d"], host, FakeServer(fresh=True)) == 0
    err = capsys.readouterr().err
    assert "Port 8080 is in use by another program; using 8082." in err.splitlines()
    assert err.index("Port 8080 is in use") < err.index("Starting")
    assert {e["QROSETTA_HTTP_BIND"] for e in _up_env(fake)} == {"127.0.0.1:8082"}
    assert _recorded(env) == "127.0.0.1:8082"
    assert host.probed[:3] == [8080, 8081, 8082]


def test_a_later_start_reuses_the_recorded_port_while_it_is_free(project, env, capsys):
    localstack.record_bind(env, "qr", "127.0.0.1:8083")
    fake = _stopped()
    assert _cli(fake, project, env, ["start", "-d"], Ports(env, taken={8080}), FakeServer(fresh=True)) == 0
    assert "is in use by another program" not in capsys.readouterr().err
    assert {e["QROSETTA_HTTP_BIND"] for e in _up_env(fake)} == {"127.0.0.1:8083"}
    assert _recorded(env) == "127.0.0.1:8083"


def test_a_recorded_port_taken_by_another_program_is_searched_again_from_8080(project, env, capsys):
    localstack.record_bind(env, "qr", "127.0.0.1:8083")
    fake = _stopped()
    assert _cli(fake, project, env, ["start", "-d"], Ports(env, taken={8083}), FakeServer(fresh=True)) == 0
    assert "Port 8083 is in use by another program; using 8080." in capsys.readouterr().err
    assert {e["QROSETTA_HTTP_BIND"] for e in _up_env(fake)} == {"127.0.0.1:8080"}
    assert _recorded(env) is None
    localstack.record_bind(env, "qr", "127.0.0.1:8083")
    fake = _stopped()
    assert _cli(fake, project, env, ["start", "-d"], Ports(env, taken={8080, 8083}), FakeServer(fresh=True)) == 0
    assert _recorded(env) == "127.0.0.1:8081"


def test_this_stacks_own_web_server_on_8080_is_not_another_program(project, env, capsys):
    fake = FakeEngine().standard()
    host = Ports(env, taken={8080}, published=["127.0.0.1:8080"])
    assert _cli(fake, project, env, ["start", "-d"], host, FakeServer(fresh=True)) == 0
    assert "is in use by another program" not in capsys.readouterr().err
    assert host.probed == [8080] and _recorded(env) is None
    assert all("QROSETTA_HTTP_BIND" not in e for e in _up_env(fake))


@pytest.mark.parametrize("how", ["flag", "env", "config", "dotenv"])
def test_a_chosen_address_that_is_taken_is_refused_before_compose(project, env, tmp_path, capsys, how):
    argv = ["start", "-d"]
    if how == "flag":
        argv += ["--bind", "127.0.0.1:8080"]
    elif how == "env":
        env = dict(env, QROSETTA_HTTP_BIND="127.0.0.1:8080")
    elif how == "config":
        (tmp_path / "config.toml").write_text('[lifecycle]\nbind = "127.0.0.1:8080"\n')
        env = dict(env, QROSETTA_CONFIG=str(tmp_path / "config.toml"))
    else:
        (project / ".env").write_text('SECRET_KEY=x\nQROSETTA_HTTP_BIND="127.0.0.1:8080"\n')
    fake = _stopped()
    host = Ports(env, taken={8080})
    assert _cli(fake, project, env, argv, host) == Exit.ENGINE
    err = capsys.readouterr().err
    assert "FAIL  port           127.0.0.1:8080 is in use" in err.splitlines()
    assert "using 8081" not in err and fake.calls == [] and host.probed == [8080]
    assert _recorded(env) is None


def test_all_ten_ports_taken_is_refused_with_the_numbered_fix(project, env, capsys):
    fake = _stopped()
    assert _cli(fake, project, env, ["start", "-d"], Ports(env, taken=set(range(8080, 8090)))) == Exit.ENGINE
    lines = capsys.readouterr().err.splitlines()
    assert "FAIL  port           127.0.0.1:8080 to 127.0.0.1:8089 are all in use" in lines
    assert "  1. Use port 8090 for this and every later command:" in lines
    assert fake.calls == [] and _recorded(env) is None


def test_json_start_keeps_its_keys_and_carries_the_moved_url(project, env, capsys):
    fake = _stopped()
    fake.port = "127.0.0.1:8081"
    assert _cli(fake, project, env, ["start", "-d", "--json"], Ports(env, taken={8080}), FakeServer(fresh=True)) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["data"]["url"] == "http://localhost:8081"
    assert set(doc["data"]) == {"url", "started", "recreated", "recreations", "not_started", "ready", "cpu_quota",
                                "finished_jobs"}


def test_status_gives_compose_the_recorded_address_so_nginx_stays_current(project, env, capsys):
    fake = _stopped()
    del fake.containers["c-nginx-reverse-proxy"]
    assert _cli(fake, project, env, ["start", "-d"], Ports(env, taken={8080}), FakeServer(fresh=True)) == 0
    capsys.readouterr()

    def nginx_current():
        assert _cli(fake, project, env, ["status", "--json"], Ports(env, taken={8080})) == 0
        rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["data"]["services"]}
        return rows["nginx"]["config_current"]

    assert nginx_current() is True
    localstack.forget_bind(env, "qr")
    assert nginx_current() is False


def test_remove_forgets_the_recorded_address_and_stop_keeps_it(project, env):
    fake = FakeEngine().standard()
    localstack.record_bind(env, "qr", "127.0.0.1:8081")
    quota.record(env, "qr", False, "abc")
    assert _cli(fake, project, env, ["stop"], Ports(env)) == 0
    assert _recorded(env) == "127.0.0.1:8081"
    assert _cli(fake, project, env, ["remove"], Ports(env)) == 0
    assert _recorded(env) is None and localstack.stack_settings(env, "qr")["cpu_quota"] is False


def test_the_foreground_exit_action_remove_forgets_it_too(project, env):
    fake = FakeEngine().standard()
    engine = Engine(fake.engine, str(project), run=fake, popen=fake.popen, env=env)
    from qrosetta_cli.stack import project as st

    gone = []
    server = serve.Server(engine, st.load_stack(engine), "remove", [], {}, removed=lambda: gone.append(True))
    assert server._exit("remove") == 0 and gone == [True]
    assert serve.Server(engine, st.load_stack(engine), "standby", [], {},
                        removed=lambda: gone.append(False))._exit("standby") == 0
    assert gone == [True]


# --- the stack setting --------------------------------------------------------------------------


def test_the_cpu_quota_setting_and_the_address_are_kept_side_by_side(env):
    localstack.record_bind(env, "qr", "127.0.0.1:8084")
    quota.record(env, "qr", True, None)
    assert localstack.stack_settings(env, "qr") == {"bind": "127.0.0.1:8084"}
    quota.record(env, "qr", False, "abc")
    localstack.record_bind(env, "qr", "127.0.0.1:8085")
    entry = localstack.stack_settings(env, "qr")
    assert entry["bind"] == "127.0.0.1:8085" and entry["cpu_quota"] is False
    localstack.record_bind(env, "qr", "127.0.0.1:8080")
    assert "bind" not in localstack.stack_settings(env, "qr")
    localstack.forget_bind(env, "other")
    assert list(json.load(open(localstack.settings_path(env)))["projects"]) == ["qr"]


def test_the_recorded_address_belongs_to_its_project(env):
    localstack.record_bind(env, "qr", "127.0.0.1:8086")
    cfg = cfgmod.Config("/none", False)
    assert localstack.local_bind(env, cfg) == ("127.0.0.1:8086", "stack setting")
    assert localstack.local_bind(dict(env, QROSETTA_PROJECT="other"), cfg) == ("127.0.0.1:8080", "default")


# --- who finds the local server there ---------------------------------------------------------


def test_commands_find_the_local_server_at_the_recorded_address_unless_one_is_configured(env, tmp_path):
    localstack.record_bind(env, "qr", "127.0.0.1:8081")
    none = cfgmod.Config("/none", False)
    assert servers.select(None, env, none).url == "http://localhost:8081"
    assert servers.resolve("local", "job index", none, env).url == "http://localhost:8081"
    assert servers.select(None, dict(env, QROSETTA_HTTP_BIND="127.0.0.1:9000"), none).url == "http://localhost:9000"
    cfg = _config(tmp_path, '[lifecycle]\nbind = "127.0.0.1:8095"\n')
    assert servers.select(None, env, cfg).url == "http://localhost:8095"
    cfg = _config(tmp_path, '[servers.local]\nurl = "http://localhost:7000"\n')
    assert servers.select(None, env, cfg).url == "http://localhost:7000"
    assert servers.select("http://example.org:1", env, none).url == "http://example.org:1"
    localstack.forget_bind(env, "qr")
    assert servers.select(None, env, none).url == "http://localhost:8080"


def test_config_show_names_where_the_address_comes_from(env, capsys):
    localstack.record_bind(env, "qr", "127.0.0.1:8081")
    assert main(["config", "show", "--json"], env=env) == 0
    rows = {r["key"]: r for r in json.loads(capsys.readouterr().out)["data"]["settings"]}
    assert rows["lifecycle.bind"]["source"] == "stack setting"
    assert rows["lifecycle.bind"]["value"].startswith("127.0.0.1:8081 ")
    assert rows["server"]["value"].endswith("http://localhost:8081")


# --- doctor -------------------------------------------------------------------------------------


def _port_row(env, host, cfg=None, server=None):
    ctx = Context(args=type("A", (), {})(), env=env, cfg=cfg or cfgmod.Config("/none", False),
                  transport_factory=server or Unreachable())
    rep = doctor.run(ctx, host)
    return next(c for c in rep.checks if c.id == "port"), rep


def test_doctor_says_which_port_start_will_use_instead_of_failing(env):
    row, rep = _port_row(env, Ports(env, taken={8080}))
    assert (row.status, row.message) == ("INFO", "127.0.0.1:8080 is in use; `qrosetta start` will use 127.0.0.1:8081")
    assert not rep.failed and rep.port_choice == "127.0.0.1:8081"


def test_doctor_fails_on_a_chosen_address_or_a_full_range(env, tmp_path):
    cfg = _config(tmp_path, '[lifecycle]\nbind = "127.0.0.1:8080"\n')
    row, rep = _port_row(env, Ports(env, taken={8080}), cfg)
    assert row.status == "FAIL" and row.message == "127.0.0.1:8080 is in use" and row.reason == "port_in_use"
    row, _ = _port_row(dict(env, QROSETTA_HTTP_BIND="127.0.0.1:8080"), Ports(env, taken={8080}))
    assert row.status == "FAIL"
    row, _ = _port_row(env, Ports(env, taken=set(range(8080, 8090))))
    assert row.status == "FAIL" and row.message == "127.0.0.1:8080 to 127.0.0.1:8089 are all in use"
    assert "qrosetta start -d --bind 127.0.0.1:8090" in row.fix


def test_doctor_checks_the_recorded_address_and_talks_to_the_server_there(env):
    localstack.record_bind(env, "qr", "127.0.0.1:8083")
    host = Ports(env, taken={8080})
    row, _ = _port_row(env, host)
    assert (row.status, row.message) == ("PASS", "127.0.0.1:8083 is free (`qrosetta start` chose it earlier)")
    assert host.probed == [8083]
    server = FakeServer(url="http://localhost:8083")
    seen = []

    def factory(srv, token=None, timeout=None):
        seen.append(srv.url)
        return server(srv, token, timeout)

    row, rep = _port_row(env, Ports(env, taken={8083}, published=["127.0.0.1:8083"]), server=factory)
    assert seen[0] == "http://localhost:8083"
    assert row.status == "PASS" and "running Quantum Rosetta" in row.message


def test_doctor_counts_this_stacks_own_web_server_as_its_own(env):
    row, _ = _port_row(env, Ports(env, taken={8080}, published=["127.0.0.1:8080"]))
    assert row.status == "PASS" and "running Quantum Rosetta" in row.message


# --- the search ---------------------------------------------------------------------------------


def test_the_search_skips_held_ports_and_stops_at_the_end_of_the_range(env):
    host = Ports(env, taken={8080, 8081, 8082})
    assert ports.search(host, lambda a: False) == "127.0.0.1:8083"
    assert ports.search(Ports(env, taken={8081}), lambda a: False, skip="127.0.0.1:8080") == "127.0.0.1:8082"
    assert ports.search(Ports(env, taken={8080, 8081}), lambda a: a == "127.0.0.1:8081") == "127.0.0.1:8081"
    host = Ports(env, taken=set(range(8080, 8090)))
    assert ports.search(host, lambda a: False) is None and host.probed == list(range(8080, 8090))
    assert ports.FALLBACK_PORTS == tuple(range(8080, 8090)) and ports.FALLBACK_HOST == "127.0.0.1"


def _free_block(size):
    """A start port with `size` consecutive free ports above it, in the ephemeral-free high range."""
    for start in range(47000, 60000, 37):
        socks = []
        try:
            for p in range(start, start + size):
                s = socket.socket()
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", p))
                socks.append(s)
            return start
        except OSError:
            continue
        finally:
            for s in socks:
                s.close()
    pytest.skip("no free block of ports")


def test_the_search_on_real_sockets_takes_the_first_port_nobody_listens_on(env):
    start = _free_block(4)
    held = []
    try:
        for p in (start, start + 1):
            s = socket.socket()
            s.bind(("127.0.0.1", p))
            s.listen()
            held.append(s)
        candidates = range(start, start + 4)
        assert ports.search(doctor.Host(env), lambda a: False, candidates=candidates) == f"127.0.0.1:{start + 2}"
        s = socket.socket()
        s.bind(("127.0.0.1", start + 2))
        s.listen()
        held.append(s)
        assert ports.search(doctor.Host(env), lambda a: False, candidates=candidates) == f"127.0.0.1:{start + 3}"
        assert ports.search(doctor.Host(env), lambda a: False, candidates=range(start, start + 3)) is None
    finally:
        for s in held:
            s.close()
    assert ports.search(doctor.Host(env), lambda a: False, candidates=range(start, start + 4)) == f"127.0.0.1:{start}"


def test_dotenv_bind_reads_the_value_compose_would(tmp_path):
    (tmp_path / ".env").write_text("# QROSETTA_HTTP_BIND=1.2.3.4:1\nexport QROSETTA_HTTP_BIND='0.0.0.0:9000'\n")
    assert ports.dotenv_bind(str(tmp_path)) == "0.0.0.0:9000"
    (tmp_path / ".env").write_text("QROSETTA_HTTP_BIND=\nOTHER=1\n")
    assert ports.dotenv_bind(str(tmp_path)) is None
    assert ports.dotenv_bind(str(tmp_path / "missing")) is None
