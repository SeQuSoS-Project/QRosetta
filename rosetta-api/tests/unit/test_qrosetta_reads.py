"""qrosetta info, backends, compilers, circuits, login, logout and whoami without a server
(job `cli`, stdlib only): the handshake outcomes of info, the fresh-probe rules, catalog
filters, the password and token rules, and the credentials file's permissions."""

import base64
import io
import json
import os
import stat
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from qrosetta_cli.cli import build_parser, main  # noqa: E402
from qrosetta_cli.client import account, reads  # noqa: E402
from qrosetta_cli.client.transport import Response  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402

FEATURES = {"plan": 1, "summary": 1, "selftest": 1, "fresh_probes": 1}
RUNNERS = [
    {"id": "qiskit", "enabled": True, "available": True, "unavailable_reason": None, "device": None,
     "optimization_levels": {"0": "none", "1": "light", "2": "more", "3": "most"}, "default_selected": True,
     "precision": {"statevector": "complex128", "measured": "complex128"},
     "qubit_ordering": {"statevector": "lsb", "measured": "lsb"}, "profiles": ["minimal", "cpu"]},
    {"id": "qsim-cirq", "enabled": True, "available": False, "unavailable_reason": "unreachable", "device": None,
     "optimization_levels": {"0": "none"}, "default_selected": True,
     "precision": {"statevector": "complex64", "measured": None},
     "qubit_ordering": {"statevector": "msb", "measured": "msb"}, "profiles": ["cpu"]},
]


def _jwt(exp):
    part = base64.urlsafe_b64encode(json.dumps({"sub": "1", "exp": exp}).encode()).decode().rstrip("=")
    return f"e30.{part}.sig"


class Api:
    """A transport factory answering a fixed set of routes; records requests and tokens."""

    def __init__(self, block=None, routes=None, url="http://localhost:8080"):
        self.block = block if block is not None else {"platform_version": "2.0.0", "api_levels": [1, 1],
                                                       "features": dict(FEATURES)}
        self.routes = routes or {}
        self.requests, self.tokens = [], []
        self.url = url

    def __call__(self, server, token=None, timeout=None):
        self.tokens.append(token)
        self.url = server.url
        return self

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        self.requests.append((method, path, query, body))
        if (method, path) == ("GET", "/config"):
            data = {"limits": {"job_ttl_sec": 1800}, "exclusive": {"enabled": True, "shared_running": 0}}
            if self.block is not False:
                data["server"] = self.block
            return Response(200, {"content-type": "application/json"}, json.dumps(data).encode())
        status, payload, hdrs = self.routes.get((method, path), (404, {"detail": "Not Found"}, {}))
        payload = payload(query, body) if callable(payload) else payload
        return Response(status, {"content-type": "application/json", **hdrs}, json.dumps(payload).encode())


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg")}


def run(argv, env, api, stdin="", tty=False):
    return main(argv, env=env, transport_factory=api, stdin=io.StringIO(stdin), tty=tty)


def doc(capsys):
    return json.loads(capsys.readouterr().out)


def test_there_is_no_password_argument():
    for argv in (["login", "--password", "x"], ["login", "x"]):
        with pytest.raises(CliError) as err:
            build_parser().parse_args(argv)
        assert err.value.code == Exit.USAGE


def test_info_states_the_handshake_and_still_prints_an_old_server(env, capsys):
    assert run(["info", "--json"], env, Api()) == 0
    d = doc(capsys)
    assert d["data"]["compatibility"] == {"cli_api_levels": [1, 1], "server_api_levels": [1, 1], "ok": True,
                                          "missing_features": []}
    assert run(["info", "--json"], env, Api(block=False)) == Exit.INCOMPATIBLE
    d = doc(capsys)
    assert d["error"]["reason"] == "server_too_old" and d["data"]["config"]["limits"] == {"job_ttl_sec": 1800}
    assert run(["info"], env, Api(block={"platform_version": "3.0.0", "api_levels": [2, 2], "features": {}})) == 12
    captured = capsys.readouterr()
    assert "incompatible" in captured.out and "API levels [2, 2]" in captured.err
    assert run(["info", "--json"], env, Api(block={"platform_version": "2.0.0", "api_levels": [1, 1],
                                                    "features": {"plan": 1}})) == 0
    d = doc(capsys)
    assert d["data"]["compatibility"]["missing_features"] == ["summary@1", "selftest@1", "fresh_probes@1"]
    assert any("qrosetta run, wait, selftest, show summary" in w["message"] for w in d["warnings"])


def test_backends_table_ids_and_levels(env, capsys):
    api = Api(routes={("GET", "/runners"): (200, RUNNERS, {})})
    assert run(["backends"], env, api) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].split()[:7] == ["qiskit", "yes", "yes", "0-3", "-", "complex128", "lsb"]
    assert "sv complex64, m per run" in lines[2] and lines[2].rstrip().endswith("unreachable")
    assert run(["backends", "--ids"], env, api) == 0
    assert capsys.readouterr().out == "qiskit\n"
    assert api.tokens == [None, None] and api.requests[1][2] is None


def test_fresh_probe_rules(env, capsys):
    rows = [dict(RUNNERS[0], fresh=False, reason="busy", error_kind=None, probed_at=None),
            dict(RUNNERS[1], fresh=True, reason=None, error_kind="dns", probed_at="2026-10-27T10:00:00Z")]
    api = Api(routes={("GET", "/runners"): (200, rows, {})})
    assert run(["backends", "--fresh", "--json"], env, api) == Exit.AUTH
    assert doc(capsys)["error"]["reason"] == "not_signed_in" and len(api.requests) == 0
    signed = dict(env, QROSETTA_TOKEN="tok")
    assert run(["backends", "--fresh"], signed, api) == 0
    out = capsys.readouterr().out
    assert "busy: a run is using it (not probed)" in out and "no answer (dns)" in out
    assert api.requests[-1][2] == {"fresh": "true"} and api.tokens[-1] == "tok"
    cached = [dict(r, fresh=False, reason="exclusive_run") for r in RUNNERS]
    api = Api(routes={("GET", "/runners"): (200, cached, {})})
    assert run(["backends", "--fresh", "--json"], signed, api) == 0
    d = doc(capsys)
    assert [w["reason"] for w in d["warnings"]] == ["exclusive_run"]
    api = Api(routes={("GET", "/compilers"): (429, {"detail": "Rate limit exceeded"}, {"retry-after": "42"})})
    assert run(["compilers", "--fresh", "--json"], signed, api) == Exit.BUSY
    assert "42 s" in doc(capsys)["error"]["hint"]
    old = Api(block={"platform_version": "2.0.0", "api_levels": [1, 1], "features": {}})
    assert run(["backends", "--fresh", "--json"], signed, old) == Exit.INCOMPATIBLE
    assert doc(capsys)["error"]["reason"] == "feature_missing"


def test_catalog_filters_and_ranges():
    assert reads._ranges([0, 1, 2, 5, 7, 8]) == "0-2,5,7-8" and reads._ranges([]) == "-"
    algos = [{"id": "ghz", "min_qubits": 2, "name": "GHZ"}, {"id": "qft", "min_qubits": 5, "description": "Fourier"}]
    assert [a["id"] for a in reads._filter("algorithms", algos, 3, None)] == ["ghz"]
    assert [a["id"] for a in reads._filter("algorithms", algos, None, "fourier")] == ["qft"]
    assert reads._filter("mqt", {"ghz": [2, 3, 9], "dj": [8]}, 3, None) == {"ghz": [2, 3]}
    assert reads._filter("qasmbench", ["adder_n4", "qft_n4"], None, "ADD") == ["adder_n4"]
    assert reads.table(("A", "BB"), [("x", "y"), ("long", "z")]) == "A     BB\nx     y\nlong  z"


def test_qasmbench_has_no_qubit_filter(env, capsys):
    api = Api()
    assert run(["circuits", "qasmbench", "--max-qubits", "3", "--json"], env, api) == Exit.USAGE
    assert api.requests == [] and doc(capsys)["error"]["hint"].startswith("qrosetta circuits qasmbench")


def test_circuits_get_reads_a_file_without_a_server(env, tmp_path, capsys):
    src = tmp_path / "c.qasm"
    src.write_text("OPENQASM 2.0;\n")
    api = Api()
    assert run(["circuits", "get", str(src), "-o", str(tmp_path / "out.qasm")], env, api) == 0
    assert (tmp_path / "out.qasm").read_text() == "OPENQASM 2.0;\n" and api.requests == []


def _token_route(token="tok.en.x", expires_in=1800):
    def answer(query, body):
        return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}
    return {("POST", "/auth/token"): (200, answer, {})}


def test_login_needs_a_terminal_or_password_stdin(env, capsys):
    api = Api(routes=_token_route())
    assert run(["login", "--email", "a@b.org", "--json"], env, api) == Exit.USAGE
    d = doc(capsys)
    assert d["error"]["reason"] == "prompt_without_tty" and "--password-stdin" in d["error"]["hint"]
    assert run(["login", "--json"], env, api) == Exit.USAGE
    assert run(["login", "--email", "a@b.org", "--password-stdin"], env, api, stdin="\n") == Exit.USAGE
    assert not any(r[1] == "/auth/token" for r in api.requests)


def test_login_stores_the_token_privately_and_never_prints_it(env, tmp_path, capsys):
    other = {"https://other.example.org": {"token": "keep"}}
    creds = tmp_path / "state" / "qrosetta" / "credentials.json"
    creds.parent.mkdir(parents=True)
    creds.write_text(json.dumps(other))
    os.chmod(creds, 0o600)
    api = Api(routes=_token_route("se.cr.et"))
    assert run(["login", "--email", "a@b.org", "--password-stdin", "--json"], env, api, stdin="pw-123456\n") == 0
    captured = capsys.readouterr()
    assert "se.cr.et" not in captured.out + captured.err and "pw-123456" not in captured.out + captured.err
    stored = json.loads(creds.read_text())
    assert stored["https://other.example.org"] == {"token": "keep"}
    assert stored["http://localhost:8080"]["token"] == "se.cr.et"
    (method, path, _, body), = [r for r in api.requests if r[1] == "/auth/token"]
    assert body == b"username=a%40b.org&password=pw-123456"
    if os.name == "posix":
        assert stat.S_IMODE(creds.stat().st_mode) == 0o600
        assert stat.S_IMODE(creds.parent.stat().st_mode) == 0o700
    assert run(["logout"], env, api) == 0
    assert json.loads(creds.read_text()) == other


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_a_readable_credentials_file_is_refused(env, tmp_path, capsys):
    creds = tmp_path / "state" / "qrosetta" / "credentials.json"
    creds.parent.mkdir(parents=True)
    creds.write_text("{}")
    os.chmod(creds, 0o644)
    api = Api(routes=_token_route())
    for argv in (["login", "--email", "a@b.org", "--password-stdin", "--json"], ["logout", "--json"]):
        assert run(argv, env, api, stdin="pw\n") == Exit.AUTH
        assert doc(capsys)["error"]["hint"] == f"chmod 600 {creds}"
    assert not any(r[1] == "/auth/token" for r in api.requests)


def test_no_password_over_plain_http_to_another_host(env, tmp_path, capsys):
    api = Api(routes=_token_route())
    argv = ["login", "--server", "http://qr.example.org", "--email", "a@b.org", "--password-stdin", "--json"]
    assert run(argv, env, api, stdin="pw\n") == Exit.AUTH
    assert doc(capsys)["error"]["reason"] == "insecure_http" and api.requests == []
    cfg = tmp_path / "cfg" / "qrosetta" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('[servers.lab]\nurl = "http://qr.example.org"\nallow_insecure_http = true\n')
    argv[2] = "lab"
    assert run(argv, env, api, stdin="pw\n") == 0
    assert doc(capsys)["data"]["server"] == "http://qr.example.org"
    assert [r[1] for r in api.requests] == ["/config", "/auth/token"]


def test_whoami_reads_the_environment_token_and_its_expiry(env, capsys):
    me = {"id": 3, "email": "a@b.org", "auth_provider": "local", "is_active": True, "created_at": "2026-10-27T10:00:00Z"}
    token = _jwt(2_000_000_000)
    api = Api(routes={("GET", "/auth/me"): (200, me, {})})
    assert run(["whoami", "--json"], dict(env, QROSETTA_TOKEN=token), api) == 0
    d = doc(capsys)
    assert d["data"]["user"] == me and d["data"]["token_source"] == "QROSETTA_TOKEN"
    assert d["data"]["expires_at"] == "2033-05-18T03:33:20Z" and token not in json.dumps(d)
    assert account.token_expiry("not-a-jwt") is None
    api = Api(routes={("GET", "/auth/me"): (401, {"detail": "Could not validate credentials"}, {})})
    assert run(["whoami", "--json"], dict(env, QROSETTA_TOKEN=token), api) == Exit.AUTH
    d = doc(capsys)
    assert d["error"]["reason"] == "token_expired" and d["error"]["hint"] == "qrosetta login"


def _stored(tmp_path, token="stored.to.ken"):
    creds = tmp_path / "state" / "qrosetta" / "credentials.json"
    creds.parent.mkdir(parents=True, exist_ok=True)
    creds.write_text(json.dumps({"http://localhost:8080": {"token": token, "expires_at": "2033-05-18T03:33:20Z"}}))
    os.chmod(creds, 0o600)
    return creds


class _HeaderApi(Api):
    """Api that also records the Authorization header of each request."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.authorizations = []

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        self.authorizations.append((method, path, (headers or {}).get("Authorization")))
        return super().request(method, path, query=query, body=body, headers=headers, timeout=timeout)


@pytest.mark.parametrize("status, revoked", [(204, True), (401, True), (500, False)])
def test_logout_signs_out_on_a_server_that_offers_it(env, tmp_path, capsys, status, revoked):
    creds = _stored(tmp_path)
    api = _HeaderApi(block={"platform_version": "2.0.0", "api_levels": [1, 1], "features": {**FEATURES, "logout": 1}},
                     routes={("POST", "/auth/logout"): (status, {}, {})})
    assert run(["logout", "--json"], env, api) == 0
    d = doc(capsys)
    assert d["data"]["removed"] is True and d["data"]["revoked"] is revoked
    assert ("POST", "/auth/logout", "Bearer stored.to.ken") in api.authorizations
    assert json.loads(creds.read_text()) == {}
    assert "stored.to.ken" not in json.dumps(d)
    assert [w["reason"] for w in d["warnings"]] == ([] if revoked else ["logout_refused"])


def test_logout_on_a_server_without_sign_out_only_deletes_the_token(env, tmp_path, capsys):
    creds = _stored(tmp_path)
    api = _HeaderApi()
    assert run(["logout"], env, api) == 0
    assert "cannot revoke a token" in capsys.readouterr().err
    assert not any(path == "/auth/logout" for _, path, _ in api.authorizations)
    assert json.loads(creds.read_text()) == {}


def test_logout_deletes_the_token_when_the_server_is_not_reached(env, tmp_path, capsys):
    from qrosetta_cli.client.transport import Transient
    creds = _stored(tmp_path)

    class Down(Api):
        def request(self, method, path, query=None, body=None, headers=None, timeout=None):
            raise Transient("Connection refused.", Exit.UNREACHABLE, "unreachable")

    assert run(["logout", "--json"], env, Down()) == 0
    d = doc(capsys)
    assert d["data"]["revoked"] is False and json.loads(creds.read_text()) == {}
    assert [w["reason"] for w in d["warnings"]] == ["server_not_reached"]
