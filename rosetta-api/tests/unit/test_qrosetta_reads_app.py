"""qrosetta info, backends, compilers, circuits, login, logout and whoami against the real
FastAPI app through TestClient (job `cli-contract`): data embedded verbatim from the server,
tables, fresh probes after signing in, catalog references, and the token kept out of every
output."""

import io
import json
import os
import stat

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests.unit._qrosetta_app import AppTransport

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from tests.unit.test_qrosetta_contracts import validate_envelope  # noqa: E402

EMAIL, PASSWORD = "reader@example.org", "testpass123"


class TokenTransport(AppTransport):
    """AppTransport that sends the token the CLI chose as a bearer header."""

    def __call__(self, server, token=None, timeout=None):
        self.token = token
        return super().__call__(server, token, timeout)

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        headers = dict(headers or {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return super().request(method, path, query=query, body=body, headers=headers, timeout=timeout)


@pytest.fixture
def server(monkeypatch):
    """(transport factory, TestClient) for the app with an in-memory database, rate limits
    off and every probe answered without a network."""
    import db.database as database
    import services.availability as availability
    import services.fresh_probes as fresh_probes
    import services.service_listing as listing
    from config import settings
    from db.database import Base, get_db
    from main import app
    from services.security import limiter

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _get_db():
        db = session()
        try:
            yield db
        finally:
            db.close()

    async def cached(names=None, services=None):
        registry = services if services is not None else settings.get_runner_services()
        return {n: {"available": n in ("qiskit", "cirq", "bqskit"), "reason": None if n in ("qiskit", "cirq", "bqskit")
                    else "unreachable", "device": None} for n in (names if names is not None else registry)}

    async def probe_now(names, services, timeout):
        return {n: ({"available": n != "cirq", "reason": None if n != "cirq" else "unreachable", "device": None},
                    "connect" if n == "cirq" else None) for n in names}

    app.dependency_overrides[get_db] = _get_db
    monkeypatch.setattr(database, "SessionLocal", session)
    monkeypatch.setattr(settings, "EXECUTION_MODE", "local")
    monkeypatch.setattr(listing, "runner_availability", cached)
    monkeypatch.setattr(availability, "probe_now", probe_now)
    monkeypatch.setattr(limiter, "enabled", False)
    fresh_probes.reset()
    client = TestClient(app)
    yield TokenTransport(client), client
    app.dependency_overrides.pop(get_db, None)
    fresh_probes.reset()
    engine.dispose()


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg")}


def cli(argv, env, transport, stdin=None, tty=False):
    return main(argv, env=env, transport_factory=transport, stdin=stdin or io.StringIO(""), tty=tty)


def envelope(capsys):
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    return doc


def register(client):
    assert client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD}).status_code == 201


def login(env, transport):
    return cli(["login", "--email", EMAIL, "--password-stdin"], env, transport, stdin=io.StringIO(PASSWORD + "\n"))


def test_info_embeds_config_and_states_compatibility(server, env, capsys):
    transport, client = server
    assert cli(["info", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert doc["schema"] == "qrosetta.cli/info@1"
    config = client.get("/config").json()
    for volatile in ("exclusive",):
        config.pop(volatile)
        doc["data"]["config"].pop(volatile)
    assert doc["data"]["config"] == config
    assert doc["data"]["compatibility"] == {"cli_api_levels": [1, 1], "server_api_levels": [1, 1], "ok": True,
                                           "missing_features": []}
    assert doc["server"]["api_levels"] == [1, 1]
    assert cli(["info"], env, transport) == 0
    out = capsys.readouterr().out
    assert "API levels 1-1 (this CLI speaks 1-1: compatible)" in out
    assert f"shots {config['default_n_shots']}" in out and "Jobs kept" in out


def test_backends_and_compilers_list_the_server_rows_verbatim(server, env, capsys):
    transport, client = server
    assert cli(["backends", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert doc["data"]["runners"] == client.get("/runners").json()
    assert doc["data"]["fresh"] is False and doc["data"]["default_ids"] == ["qiskit", "cirq"]
    assert cli(["backends"], env, transport) == 0
    captured = capsys.readouterr()
    header, *rows = captured.out.splitlines()
    assert header.split() == ["ID", "AVAILABLE", "DEFAULT", "LEVELS", "DEVICE", "PRECISION", "ORDER", "PROFILES", "NOTE"]
    qiskit = next(r for r in rows if r.startswith("qiskit "))
    assert qiskit.split()[:7] == ["qiskit", "yes", "yes", "0-3", "-", "complex128", "lsb"]
    assert "minimal,cpu,gpu,full" in qiskit
    assert "unreachable" in next(r for r in rows if r.startswith("qulacs "))
    assert "2 of" in captured.err
    assert cli(["backends", "--ids"], env, transport) == 0
    assert capsys.readouterr().out.split() == ["qiskit", "cirq"]
    assert cli(["backends", "--levels"], env, transport) == 0
    assert "  3  Aer transpiler level 3" in capsys.readouterr().out
    assert cli(["compilers", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert doc["data"]["compilers"] == client.get("/compilers").json()
    assert doc["data"]["available_ids"] == ["bqskit"]
    assert cli(["compilers"], env, transport) == 0
    assert capsys.readouterr().out.splitlines()[0].split() == ["ID", "NAME", "AVAILABLE", "LEVELS", "PROFILES",
                                                               "NOTE", "VERSIONS"]
    assert transport.tokens == [None] * len(transport.tokens)


def test_fresh_probes_need_a_sign_in_and_then_probe(server, env, capsys):
    transport, client = server
    assert cli(["backends", "--fresh", "--json"], env, transport) == Exit.AUTH
    doc = envelope(capsys)
    assert doc["error"]["reason"] == "not_signed_in" and doc["error"]["hint"] == "qrosetta login"
    register(client)
    assert login(env, transport) == 0
    capsys.readouterr()
    assert cli(["backends", "--fresh", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert doc["data"]["fresh"] is True
    rows = {r["id"]: r for r in doc["data"]["runners"]}
    assert rows["qulacs"]["available"] is True and rows["qulacs"]["fresh"] is True
    assert rows["cirq"]["error_kind"] == "connect"
    assert cli(["backends", "--fresh"], env, transport) == 0
    out = capsys.readouterr().out
    assert "no answer (connect)" in next(r for r in out.splitlines() if r.startswith("cirq "))


def test_circuit_catalogs_filter_and_name_their_references(server, env, capsys):
    transport, client = server
    assert cli(["circuits", "algorithms", "--max-qubits", "2", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert doc["data"]["total"] == len(client.get("/algorithms").json())
    assert doc["data"]["items"] and all(a["min_qubits"] <= 2 for a in doc["data"]["items"])
    assert cli(["circuits", "examples", "--filter", "rotation"], env, transport) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines()[0].split() == ["NAME", "QUBITS", "MODE", "TITLE"]
    assert "rotation_1q" in captured.out and "example:NAME" in captured.err
    assert cli(["circuits", "mqt", "--max-qubits", "4", "--filter", "ghz"], env, transport) == 0
    assert capsys.readouterr().out.splitlines()[1].split() == ["ghz", "2-4"]
    assert cli(["circuits", "qasmbench", "--filter", "adder", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert "adder_n4" in doc["data"]["items"]
    assert cli(["circuits", "qasmbench", "--max-qubits", "4"], env, transport) == Exit.USAGE
    capsys.readouterr()
    assert cli(["circuits"], env, transport) == 0
    assert capsys.readouterr().out.startswith("ID ")


def test_circuits_get_writes_the_server_text(server, env, tmp_path, capsys):
    pytest.importorskip("pytket")
    transport, client = server
    assert cli(["circuits", "get", "example:rotation_1q"], env, transport) == 0
    out, text = capsys.readouterr().out, client.get("/examples/rotation_1q.qasm").json()["qasm"]
    assert out == (text if text.endswith("\n") else text + "\n")
    target = tmp_path / "ghz4.qasm"
    assert cli(["circuits", "get", "mqt:ghz:4", "-o", str(target), "--json"], env, transport) == 0
    doc = envelope(capsys)
    expected = client.get("/benchmarks/mqt", params={"algorithm": "ghz", "qubits": 4}).json()["qasm"]
    assert target.read_text() == expected == doc["data"]["qasm"] and doc["data"]["path"] == str(target)
    assert cli(["circuits", "get", "algorithm:qft:4,seed=3", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert doc["data"]["qasm"] == client.post("/generate_circuit", json={"algorithm": "qft", "qubits": 4,
                                                                          "seed": 3}).json()["qasm"]
    assert cli(["circuits", "get", "qasmbench:adder_n4", "-o", "-"], env, transport) == 0
    assert capsys.readouterr().out.startswith("OPENQASM 2.0;")


@pytest.mark.parametrize("ref, code, reason, words", [
    ("algorithm:ghzz:3", Exit.NOT_FOUND, "unknown_algorithm", "did you mean ghz"),
    ("example:rotation_q1", Exit.NOT_FOUND, "unknown_example", "did you mean rotation_1q"),
    ("mqt:ghz:99", Exit.REFUSED, "refused", "exceeds limit"),
    ("mqt:ghz:1", Exit.NOT_FOUND, "unknown_size", "2-"),
    ("mqt:ghzz:3", Exit.NOT_FOUND, "unknown_algorithm", "did you mean ghz"),
    ("qasmbench:adder_n44", Exit.NOT_FOUND, "unknown_circuit", "did you mean adder_n4"),
    ("algorithm:ghz:999", Exit.REFUSED, "refused", "exceeds limit"),
    ("bogus:x", Exit.USAGE, "unknown_reference", "./bogus:x"),
])
def test_circuits_get_errors(server, env, capsys, ref, code, reason, words):
    pytest.importorskip("pytket")
    transport, _ = server
    assert cli(["circuits", "get", ref, "--json"], env, transport) == code
    doc = envelope(capsys)
    assert doc["error"]["reason"] == reason and words in doc["error"]["message"], doc["error"]


def test_login_whoami_logout(server, env, tmp_path, capsys):
    transport, client = server
    register(client)
    assert cli(["whoami", "--json"], env, transport) == Exit.AUTH
    assert envelope(capsys)["error"]["reason"] == "not_signed_in"
    assert login(env, transport) == 0
    captured = capsys.readouterr()
    assert f"Signed in to http://localhost:8080 as {EMAIL}" in captured.out
    creds = tmp_path / "state" / "qrosetta" / "credentials.json"
    assert stat.S_IMODE(creds.stat().st_mode) == 0o600
    assert stat.S_IMODE(creds.parent.stat().st_mode) == 0o700
    stored = json.loads(creds.read_text())["http://localhost:8080"]
    token = stored["token"]
    assert stored["email"] == EMAIL and stored["expires_at"].endswith("Z")
    assert token not in captured.out + captured.err and PASSWORD not in captured.out + captured.err
    assert cli(["whoami", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert doc["data"]["user"] == client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert doc["data"]["token_source"] == "credentials file" and token not in json.dumps(doc)
    assert cli(["whoami"], env, transport) == 0
    assert f"as {EMAIL} (account " in capsys.readouterr().out
    assert cli(["logout", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert doc["data"]["removed"] is True and json.loads(creds.read_text()) == {}
    assert doc["data"]["revoked"] is True
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert cli(["logout"], env, transport) == 0
    assert "No token stored" in capsys.readouterr().out
    assert cli(["whoami"], env, transport) == Exit.AUTH
    capsys.readouterr()
    for path in (tmp_path / "state").rglob("*"):
        if path.is_file():
            assert token not in path.read_text(errors="replace")


def test_login_refusals(server, env, capsys):
    transport, client = server
    register(client)
    wrong = cli(["login", "--email", EMAIL, "--password-stdin", "--json"], env, transport,
                stdin=io.StringIO("wrongpass99\n"))
    assert wrong == Exit.AUTH
    doc = envelope(capsys)
    assert doc["error"]["reason"] == "login_refused" and "wrongpass99" not in json.dumps(doc)
    assert cli(["login", "--email", EMAIL, "--json"], env, transport) == Exit.USAGE
    doc = envelope(capsys)
    assert "--password-stdin" in doc["error"]["hint"] and doc["error"]["reason"] == "prompt_without_tty"
    assert cli(["whoami"], env, transport) == Exit.AUTH
    capsys.readouterr()
    token_env = dict(env, QROSETTA_TOKEN="not-a-jwt")
    assert cli(["whoami", "--json"], token_env, transport) == Exit.AUTH
    doc = envelope(capsys)
    assert doc["error"]["reason"] == "token_expired" and "not-a-jwt" not in json.dumps(doc)


def test_login_prompts_on_a_terminal(server, env, monkeypatch, capsys):
    from qrosetta_cli.client import account
    transport, client = server
    register(client)
    monkeypatch.setattr(account.getpass, "getpass", lambda prompt, stream=None: PASSWORD)
    assert cli(["login"], env, transport, stdin=io.StringIO(EMAIL + "\n"), tty=True) == 0
    assert "Email: " in capsys.readouterr().err
    assert os.path.isfile(os.path.join(env["XDG_STATE_HOME"], "qrosetta", "credentials.json"))
