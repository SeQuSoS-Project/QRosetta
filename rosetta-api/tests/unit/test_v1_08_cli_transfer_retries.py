"""V1-08: a dropped connection is a transient error the CLI repeats for requests that start no
work (GETs, exports), with backoff; a run is never submitted twice, and polling survives a few
failed polls."""
import http.server
import json
import os
import socket
import threading

import pytest

from tests.unit._qrosetta_scripted import Scripted

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import conn as connmod, results, waiting  # noqa: E402
from qrosetta_cli.client.transport import HttpTransport, Response, Transient  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    pauses = []
    monkeypatch.setattr(waiting, "pause", pauses.append)
    return pauses


def _cut_off_server():
    """A loopback server that promises 1000 bytes and closes after 10."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "1000")
            self.end_headers()
            self.wfile.write(b"0123456789")
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_RDWR)

        def log_message(self, *args):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def test_v1_08_a_body_cut_off_part_way_is_a_transient_error(tmp_path):
    httpd, url = _cut_off_server()
    try:
        with pytest.raises(Transient) as err, open(tmp_path / "x", "wb") as sink:
            HttpTransport(url).download("GET", "/report", sink)
        with pytest.raises(Transient):
            HttpTransport(url).request("GET", "/report")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert err.value.code == Exit.UNREACHABLE and err.value.reason == "connection_lost"


class _Flaky:
    """A transport whose first `fail` calls write part of the body and then drop."""

    def __init__(self, fail, body=b'{"ok": true}', status=200):
        self.fail, self.body, self.status, self.calls = fail, body, status, []

    def _maybe_fail(self, method, path, sink=None):
        self.calls.append((method, path))
        if len(self.calls) <= self.fail:
            if sink is not None:
                sink.write(self.body[:3])
            raise Transient("The connection broke off.", Exit.UNREACHABLE, "connection_lost")

    def request(self, method, path, **kwargs):
        self._maybe_fail(method, path)
        return Response(self.status, {}, self.body)

    def download(self, method, path, sink, timeout=None, on_headers=None, **kwargs):
        self.timeout = timeout
        self._maybe_fail(method, path, sink)
        sink.write(self.body)
        return Response(200, {}, b"")


def _conn(transport):
    conn = connmod.Conn.__new__(connmod.Conn)
    conn.transport = transport
    conn.config = {}
    return conn


def test_v1_08_downloads_start_again_after_a_drop_and_wait_long_for_the_first_byte(tmp_path, no_pause):
    transport = _Flaky(fail=2)
    dest = str(tmp_path / "ro-crate.zip")
    assert _conn(transport).download("POST", "/jobs/abc/export", dest, {"x": 1}) == len(transport.body)
    assert open(dest, "rb").read() == transport.body and not os.path.exists(dest + ".part")
    assert len(transport.calls) == 3 and no_pause == [1, 2]
    assert transport.timeout == connmod.DOWNLOAD_TIMEOUT_SEC


def test_v1_08_retries_stop_after_the_last_delay(tmp_path):
    transport = _Flaky(fail=10)
    with pytest.raises(Transient):
        _conn(transport).download("GET", "/jobs/abc/report", str(tmp_path / "r.json"))
    assert len(transport.calls) == len(connmod.RETRY_DELAYS_SEC) + 1
    assert not os.path.exists(tmp_path / "r.json.part")


@pytest.mark.parametrize("path", ["/compare", "/compare_measured", "/run_batch_suite", "/experiments", "/auth/token"])
def test_v1_08_a_run_is_never_sent_twice(path, no_pause):
    transport = _Flaky(fail=1)
    with pytest.raises(Transient):
        _conn(transport).post(path, {"qasm_string": QASM})
    assert transport.calls == [("POST", path)] and no_pause == []


def test_v1_08_gets_are_repeated_on_502_503_504_and_a_short_retry_after(no_pause):
    class Statuses:
        def __init__(self, statuses):
            self.statuses, self.calls = list(statuses), 0

        def request(self, method, path, **kwargs):
            self.calls += 1
            status, headers = self.statuses.pop(0)
            return Response(status, headers, b'{"status": "running"}')

    transport = Statuses([(503, {}), (429, {"retry-after": "5"}), (200, {})])
    assert _conn(transport).get("/jobs/abc") == {"status": "running"}
    assert transport.calls == 3 and no_pause == [1, 5]
    transport = Statuses([(429, {"retry-after": "600"})])
    with pytest.raises(CliError) as err:
        _conn(transport).get("/jobs/abc")
    assert err.value.http_status == 429 and transport.calls == 1


def test_v1_08_a_run_survives_dropped_polls_and_a_dropped_report_download(tmp_path, capsys):
    class Dropping(Scripted):
        dropped = {"poll": 0, "report": 0}

        def request(self, method, path, query=None, body=None, headers=None, timeout=None):
            if method == "GET" and path.startswith("/jobs/") and path.count("/") == 2 and self.dropped["poll"] < 6:
                self.dropped["poll"] += 1
                raise Transient("No answer.", Exit.UNREACHABLE, "unreachable")
            return super().request(method, path, query=query, body=body, headers=headers, timeout=timeout)

        def download(self, method, path, sink, **kwargs):
            if path.endswith("/report") and not self.dropped["report"]:
                self.dropped["report"] += 1
                sink.write(b'{"trunc')
                raise Transient("The connection broke off.", Exit.UNREACHABLE, "connection_lost")
            return super().download(method, path, sink, **kwargs)

    circuit = tmp_path / "bell.qasm"
    circuit.write_text(QASM)
    env = {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
           "XDG_RUNTIME_DIR": str(tmp_path / "run"), "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}
    server = Dropping()
    assert main(["run", str(circuit), "--json"], env=env, transport_factory=server) == 0
    (job,) = json.loads(capsys.readouterr().out)["data"]["jobs"]
    assert results.read_status(job["dir"]) == "complete"
    assert json.load(open(os.path.join(job["dir"], "report.json")))
    assert [entry[1] for entry in server.log if entry[0] == "POST"].count("/compare") == 1
    assert server.dropped == {"poll": 6, "report": 1}
