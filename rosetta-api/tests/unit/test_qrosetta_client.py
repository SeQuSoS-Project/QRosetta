"""qrosetta_cli client half: the HTTP transport, server selection, tokens, the handshake, the
`api` command and its exit codes; and that the client half imports nothing from the stack half
and every module imports where fcntl and SIGHUP do not exist."""

import ast
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.unit._qrosetta_fake import REPO, FakeServer, Unreachable

from qrosetta_cli import config as cfgmod  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import handshake, servers  # noqa: E402
from qrosetta_cli.client.commands import parse_fields, parse_value, status_error  # noqa: E402
from qrosetta_cli.client.transport import HttpTransport, is_loopback, origin  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *args):
        pass

    def _reply(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Handler.seen.append(("GET", self.path, self.headers.get("Authorization")))
        if self.path.startswith("/config"):
            self._reply(200, {"limits": {}, "server": {"platform_version": "2.0.0", "api_levels": [1, 1]}})
        else:
            self._reply(404, {"detail": "Not Found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        Handler.seen.append(("POST", self.path, body))
        self._reply(200, {"echo": json.loads(body or b"null")})


@pytest.fixture
def live():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    Handler.seen = []
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_http_transport_reads_answers_and_error_statuses(live):
    t = HttpTransport(live, token="tok")
    resp = t.request("GET", "/config", query={"a": "1"})
    assert resp.status == 200 and resp.json()["server"]["api_levels"] == [1, 1]
    assert Handler.seen[-1] == ("GET", "/config?a=1", "Bearer tok")
    assert t.request("GET", "/missing").status == 404
    resp = t.request("POST", "/x", body=b'{"k": 1}', headers={"Content-Type": "application/json"})
    assert resp.json() == {"echo": {"k": 1}}


def test_unreachable_server_is_exit_11():
    with pytest.raises(CliError) as err:
        HttpTransport("http://127.0.0.1:9", timeout=2).request("GET", "/config")
    assert err.value.code == Exit.UNREACHABLE


def test_loopback_and_origin():
    assert is_loopback("http://localhost:8080") and is_loopback("http://127.0.0.1") and is_loopback("http://[::1]:80")
    assert not is_loopback("https://qrosetta.example.org")
    assert origin("https://h.example:8443/x/y") == "https://h.example:8443"


class Cfg:
    def __init__(self, data=None, path="/c.toml"):
        self.data, self.path = data or {}, path

    def get(self, *keys, default=None):
        node = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node


def test_server_selection():
    cfg = Cfg({"servers": {"csc": {"url": "https://q.example/"}}, "lifecycle": {"bind": "0.0.0.0:9000"}})
    assert servers.select(None, {}, cfg).url == "http://localhost:9000"
    assert servers.select("csc", {}, cfg).url == "https://q.example"
    assert servers.select(None, {"QROSETTA_SERVER": "csc"}, cfg).source == "env QROSETTA_SERVER"
    assert servers.select("https://other.example", {"QROSETTA_SERVER": "csc"}, cfg).url == "https://other.example"
    assert servers.select(None, {}, Cfg({"default_server": "csc", **cfg.data})).name == "csc"
    with pytest.raises(CliError) as err:
        servers.select("nosuch", {}, cfg)
    assert err.value.code == Exit.USAGE and "csc" in err.value.message
    assert servers.bind_url("127.0.0.1:80") == "http://localhost" and servers.bind_url("[fe80::1]:81") == "http://[fe80::1]:81"


@pytest.mark.skipif(os.name != "posix", reason="file modes")
def test_tokens_come_from_the_environment_or_a_private_credentials_file(tmp_path):
    env = {"XDG_STATE_HOME": str(tmp_path)}
    server = servers.Server("x", "https://q.example", "test")
    assert servers.token_for(server, Cfg(), dict(env, QROSETTA_TOKEN="from-env")) == "from-env"
    path = tmp_path / "qrosetta" / "credentials.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"https://q.example": {"token": "stored"}}))
    path.chmod(0o600)
    assert servers.token_for(server, Cfg(), env) == "stored"
    assert servers.token_for(servers.Server("y", "https://other.example", "t"), Cfg(), env) is None
    path.chmod(0o644)
    with pytest.raises(CliError) as err:
        servers.token_for(server, Cfg(), env)
    assert err.value.code == Exit.AUTH and err.value.hint == f"chmod 600 {path}"


def test_plain_http_rules(capsys):
    assert servers.plain_http_ok(servers.Server("l", "http://localhost:8080", "t"), "tok")
    assert capsys.readouterr().err == ""
    remote = servers.Server("r", "http://q.example", "t")
    assert servers.plain_http_ok(remote, None) and "plain HTTP" in capsys.readouterr().err
    with pytest.raises(CliError) as err:
        servers.plain_http_ok(remote, "tok")
    assert err.value.code == Exit.AUTH and "allow_insecure_http" in err.value.hint
    assert servers.plain_http_ok(servers.Server("r", "http://q.example", "t", allow_insecure_http=True), "tok")


def test_handshake_checks():
    good = {"limits": {}, "server": {"platform_version": "2.0.0", "api_levels": [1, 2], "features": {"summary": 1}}}
    assert handshake.check(good, ["summary"])["platform_version"] == "2.0.0"
    assert handshake.describe(good["server"]) == "platform 2.0.0, API levels 1-2"
    for config, reason in (({"limits": {}}, "server_too_old"),
                           ({"limits": {}, "server": {"api_levels": [2, 3]}}, "api_levels"),
                           (good, "feature_missing")):
        with pytest.raises(CliError) as err:
            handshake.check(config, [("summary", 2)] if reason == "feature_missing" else ())
        assert err.value.code == Exit.INCOMPATIBLE and err.value.reason == reason
    with pytest.raises(CliError) as err:
        handshake.fetch_config(FakeServer(status={"/config": (200, ["not", "config"])}))
    assert err.value.code == Exit.INCOMPATIBLE


def test_field_parsing_splits_on_the_last_equals_and_types_json_literals():
    assert parse_fields(["a=1", "x=y=z"]) == {"a": "1", "x=y": "z"}
    assert parse_value("3") == 3 and parse_value("true") is True and parse_value("[1]") == [1]
    assert parse_value("ghz") == "ghz"
    with pytest.raises(CliError):
        parse_fields(["novalue"])


@pytest.mark.parametrize("status,code", [(400, 10), (413, 10), (422, 10), (401, 13), (403, 13), (404, 14),
                                         (429, 15), (503, 15), (500, 11), (418, 10)])
def test_api_status_codes(status, code):
    assert status_error(status)[0] == code


def _api(argv, server, env=None, stdin=None):
    return main(["api", *argv], env=env or {}, transport_factory=server, stdin=stdin)


def test_api_get_post_and_output(tmp_path, capsys):
    server = FakeServer()
    assert _api(["GET", "/runners", "-f", "fresh=true"], server) == 0
    assert server.requests[-1][:3] == ("GET", "/runners", {"fresh": "true"})
    assert json.loads(capsys.readouterr().out)[0]["id"] == "qiskit"
    server.status["/generate_circuit"] = (200, {"qasm": "OPENQASM 2.0;"})
    assert _api(["post", "/generate_circuit", "-f", "algorithm=ghz", "-f", "n_qubits=3"], server) == 0
    assert json.loads(server.requests[-1][3]) == {"algorithm": "ghz", "n_qubits": 3}
    body = tmp_path / "b.json"
    body.write_text('{"x": 1}')
    assert _api(["POST", "/generate_circuit", "--input", str(body), "-o", str(tmp_path / "out.json")], server) == 0
    assert server.requests[-1][3] == b'{"x": 1}' and json.loads((tmp_path / "out.json").read_text())["qasm"]
    capsys.readouterr()
    assert _api(["GET", "/config", "--json"], server) == 0
    assert json.loads(capsys.readouterr().out)["data"]["exclusive"]["shared_running"] == 0


def test_api_usage_errors(tmp_path):
    server = FakeServer()
    assert _api(["FETCH", "/x"], server) == Exit.USAGE
    assert _api(["GET", "runners"], server) == Exit.USAGE
    body = tmp_path / "b.json"
    body.write_text("{}")
    assert _api(["POST", "/x", "--input", str(body), "-f", "a=1"], server) == Exit.USAGE
    assert _api(["POST", "/x", "--input", str(tmp_path / "missing")], server) == Exit.NOT_FOUND
    assert not server.requests


def test_api_error_carries_the_server_detail(capsys):
    server = FakeServer(status={"/compare": (429, {"detail": "slow down"})})
    assert _api(["POST", "/compare", "--json"], server) == Exit.BUSY
    doc = json.loads(capsys.readouterr().out)
    assert doc["error"]["detail"] == {"detail": "slow down"} and doc["error"]["http_status"] == 429


def test_api_sends_the_token_unless_anonymous():
    server = FakeServer()
    assert _api(["GET", "/config"], server, env={"QROSETTA_TOKEN": "t0k"}) == 0
    assert _api(["GET", "/config", "--anonymous"], server, env={"QROSETTA_TOKEN": "t0k"}) == 0
    assert server.tokens == ["t0k", None]


def test_the_token_never_appears_in_output_errors_or_the_log(tmp_path, capsys, monkeypatch):
    marker = "-".join(["not", "a", "real", "token"])
    env = {"QROSETTA_TOKEN": marker, "XDG_STATE_HOME": str(tmp_path)}
    server = FakeServer(status={"/x": (403, {"detail": "forbidden"})})
    assert _api(["GET", "/x", "--json"], server, env=env) == Exit.AUTH
    assert _api(["GET", "/x"], server, env=env) == Exit.AUTH
    import qrosetta_cli.cli as climod
    monkeypatch.setattr(climod, "_load", lambda func: (lambda ctx: 1 / 0))
    assert main(["api", "GET", "/x"], env=env, transport_factory=server) == Exit.INTERNAL
    out, err = capsys.readouterr()
    log = (tmp_path / "qrosetta" / "cli.log").read_text()
    assert marker not in out + err + log


def test_api_unreachable_is_exit_11(capsys):
    assert _api(["GET", "/config"], Unreachable()) == Exit.UNREACHABLE
    assert capsys.readouterr().err.strip().splitlines()[-1] == "qrosetta status"


def _imports(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""
            yield from (f"{node.module}.{a.name}" for a in node.names)


def test_client_half_imports_nothing_from_the_stack_half():
    root = REPO / "qrosetta_cli"
    shared = [root / n for n in ("__init__.py", "cli.py", "commands.py", "config.py", "context.py", "errors.py",
                                  "mode.py", "output.py")]
    for path in list((root / "client").glob("*.py")) + shared:
        bad = [m for m in _imports(path) if m.startswith("qrosetta_cli.stack")]
        assert not bad, (path.name, bad)


def test_every_module_imports_without_fcntl_or_sighup():
    code = ("import sys, signal; sys.modules['fcntl'] = None\n"
            "for n in ('SIGHUP', 'SIGPIPE'):\n    hasattr(signal, n) and delattr(signal, n)\n"
            f"sys.path.insert(0, {str(REPO)!r})\n"
            "import pkgutil, importlib, qrosetta_cli\n"
            "for m in pkgutil.walk_packages(qrosetta_cli.__path__, 'qrosetta_cli.'):\n"
            "    if m.name != 'qrosetta_cli.__main__':\n        importlib.import_module(m.name)\n"
            "from qrosetta_cli.stack import guard\n"
            "with guard.engine_lock({'XDG_RUNTIME_DIR': sys.argv[1]}, 'x'):\n    pass\n"
            "print('ok')\n")
    out = subprocess.run([sys.executable, "-I", "-c", code, str(REPO / ".no-such-runtime-dir")],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == "ok", out.stderr


def test_cli_owned_names_include_every_spec_variable():
    assert set(cfgmod.CLI_ENV) >= {"QROSETTA_SERVER", "QROSETTA_TOKEN", "QROSETTA_CONFIG", "QROSETTA_PROJECT_DIR",
                                   "QROSETTA_PROJECT", "QROSETTA_ENGINE", "QROSETTA_ON_EXIT",
                                   "QROSETTA_RESULTS_DIR", "QROSETTA_SIF_DIR"}
