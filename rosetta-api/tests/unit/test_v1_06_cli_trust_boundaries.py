"""V1-06: the CLI sends its token only to the server's own origin over a channel it may use,
reaches servers over http(s) only, names files only after a valid job id, and an image
archive cannot tag anything qrosetta did not compute."""
import http.server
import json
import os
import threading

import pytest

from tests.unit import _qrosetta_scripted
from tests.unit._qrosetta_fake import FakeEngine, image_labels, write_archive
from tests.unit._qrosetta_scripted import Scripted
from tests.unit.test_qrosetta_images import calls, env, project, run as run_stack  # noqa: F401

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import results, servers, waiting  # noqa: E402
from qrosetta_cli.client.transport import HttpTransport  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402
from qrosetta_cli.stack import archive  # noqa: E402


class _Server:
    """A loopback HTTP server that records the Authorization header of each request and
    answers /hop with a redirect to ``target``."""

    def __init__(self, target=None):
        seen = self.seen = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, self.headers.get("Authorization")))
                if self.path == "/hop":
                    self.send_response(302)
                    self.send_header("Location", (target() if target else "") + "/land")
                    self.end_headers()
                    return
                body = b"{}"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def test_v1_06_a_redirect_to_another_origin_drops_the_token():
    other = _Server()
    first = _Server(target=lambda: other.url)
    same = _Server(target=lambda: same.url)
    try:
        assert HttpTransport(first.url, token="secret-token").request("GET", "/hop").status == 200
        assert HttpTransport(same.url, token="secret-token").request("GET", "/hop").status == 200
    finally:
        for server in (other, first, same):
            server.close()
    assert first.seen == [("/hop", "Bearer secret-token")]
    assert other.seen == [("/land", None)]
    assert same.seen == [("/hop", "Bearer secret-token"), ("/land", "Bearer secret-token")]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.org/x", "http://"])
def test_v1_06_only_http_and_https_servers_are_accepted(url, tmp_path):
    with pytest.raises(CliError) as err:
        servers.select(None, {"QROSETTA_SERVER": url}, _Cfg())
    assert err.value.code == Exit.USAGE and err.value.reason == "server_url"
    with pytest.raises(CliError):
        HttpTransport(url)


class _Cfg:
    def get(self, *keys):
        return None


def test_v1_06_an_environment_token_never_goes_to_a_plain_http_remote_host(tmp_path, capsys):
    env = {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "s"), "XDG_CONFIG_HOME": str(tmp_path / "c"),
           "XDG_RUNTIME_DIR": str(tmp_path / "r"), "QROSETTA_TOKEN": "secret-token"}
    assert main(["whoami", "--server", "http://qr.example.org", "--json"], env=env) == Exit.AUTH
    out = capsys.readouterr()
    assert json.loads(out.out)["error"]["reason"] == "insecure_http"
    assert "secret-token" not in out.out + out.err


@pytest.mark.parametrize("job_id", ["../../outside", "a/b", "", None, 7, "0F8FAD5B-D9CB-469F-A165-70867728950E"])
def test_v1_06_a_job_id_that_is_not_a_uuid_names_no_file(job_id, tmp_path, monkeypatch, capsys):
    with pytest.raises(CliError) as err:
        results.server_job_id({"job_id": job_id}, "POST /compare")
    assert err.value.code == Exit.INCOMPATIBLE

    class _Uuid:
        @staticmethod
        def uuid4():
            return job_id
    monkeypatch.setattr(_qrosetta_scripted, "uuid", _Uuid)
    monkeypatch.setattr(waiting, "pause", lambda seconds: None)
    circuit = tmp_path / "bell.qasm"
    circuit.write_text('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n')
    env = {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
           "XDG_RUNTIME_DIR": str(tmp_path / "run"), "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}
    assert main(["run", str(circuit), "--json"], env=env, transport_factory=Scripted()) == Exit.INCOMPATIBLE
    assert json.loads(capsys.readouterr().out)["error"]["reason"] == "bad_job_id"
    assert not os.path.exists(tmp_path / "outside")
    (invocation,) = [d for d in os.listdir(tmp_path / "res") if d != "latest"]
    assert os.listdir(tmp_path / "res" / invocation) == ["plan.json"]


def test_v1_06_an_archive_that_carries_its_own_tags_is_not_loaded(env, project, tmp_path, capsys):  # noqa: F811
    out = tmp_path / "arch"
    out.mkdir()
    config = {"config": {"Labels": image_labels("qiskit_runner"), "Env": ["QROSETTA_IMAGE_GIT_SHA=abc123"]},
              "history": [{"created_by": "x"}]}
    digest = write_archive(out / "qiskit.tar", config, repo_tags=["docker.io/library/postgres:16"])
    archive.write_index(str(out), {"schema": archive.SCHEMA, "project": "qr", "images": [{
        "service": "qiskit", "compose_service": "qiskit_runner", "file": "qiskit.tar",
        "image_id": "sha256:" + digest, "config_digest": "sha256:" + digest, "git_sha": "abc123", "digest": None,
        "sha256": archive.sha256_file(out / "qiskit.tar")}]})
    fake = FakeEngine()
    fake.add_image("i-postgres", ["docker.io/library/postgres:16"], {})
    assert run_stack(["images", "load", str(out), "--json"], env, fake, checkout=project) == Exit.ENGINE
    doc = json.loads(capsys.readouterr().out)
    assert "postgres:16" in doc["data"]["failed"][0]["message"]
    assert not calls(fake, ["load"]) and not calls(fake, ["tag"])
    assert fake.images["i-postgres"]["RepoTags"] == ["docker.io/library/postgres:16"]
