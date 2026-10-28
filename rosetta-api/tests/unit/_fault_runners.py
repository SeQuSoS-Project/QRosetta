"""Fake runner servers on loopback sockets for the failure-injection tests (V7): each answers
GET /capabilities and /health, and POST /run or /run_measured with a valid result or with one
chosen fault (slow, reset, closed, truncated, malformed, oversized, HTTP 500), written byte by
byte so that the API's real httpx client meets it; and the API wired to them through the real
dispatcher."""

import json
import math
import socket
import socketserver
import struct
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from qrosetta_commons.helpers import encode_statevector, get_num_qubits_from_qasm

RUNNERS = ("qiskit", "cirq", "qulacs")
URL_SETTINGS = {"qiskit": "PYTKET_QISKIT_RUNNER_URL", "cirq": "PYTKET_CIRQ_RUNNER_URL",
                "qulacs": "PYTKET_QULACS_RUNNER_URL", "qibo": "QIBO_RUNNER_URL"}
FAULTS = ("slow", "reset", "close", "truncated", "truncated_json", "not_json", "list", "null",
          "nan", "no_statevector", "html_200", "http_500", "oversized_declared", "oversized_chunked")


def _json_response(status: int, body: bytes, content_type: str = "application/json") -> bytes:
    reason = {200: "OK", 500: "Internal Server Error"}.get(status, "Status")
    return (f"HTTP/1.1 {status} {reason}\r\nContent-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body


def statevector_result(name: str, qasm: str) -> dict:
    n = get_num_qubits_from_qasm(qasm) or 1
    vector = np.full(2 ** n, 1 / math.sqrt(2 ** n), dtype=complex)
    return {"simulator": name, "statevector": encode_statevector(vector), "qubit_ordering": "lsb",
            "n_qubits": n, "transpiled_qasm": qasm, "preprocessing_applied": [],
            "compilation_time_sec": 0.001, "simulation_time_sec": 0.002,
            "execution_time_sec": 0.003, "precision": "complex128"}


class FaultRunner:
    """One fake runner. ``fault`` (None for a valid answer) applies to every run request;
    ``delay`` is how long ``slow`` waits; ``cap`` is the size an oversized body exceeds."""

    def __init__(self, name: str, fault: str = None, delay: float = 5.0, cap: int = 64 * 1024):
        self.name, self.fault, self.delay, self.cap = name, fault, delay, cap
        self.requests = []
        self._closing = threading.Event()
        runner = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                runner._handle(self.request)

        self._server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self):
        self._closing.set()
        self._server.shutdown()
        self._server.server_close()

    @staticmethod
    def _read_request(sock):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(65536)
            if not chunk:
                return None, None, None
            data += chunk
        head, body = data.split(b"\r\n\r\n", 1)
        lines = head.decode("latin-1").split("\r\n")
        method, path, _ = lines[0].split(" ", 2)
        length = 0
        for line in lines[1:]:
            key, _, value = line.partition(":")
            if key.strip().lower() == "content-length":
                length = int(value.strip())
        while len(body) < length:
            chunk = sock.recv(65536)
            if not chunk:
                break
            body += chunk
        return method, path, body

    def _handle(self, sock):
        method, path, body = self._read_request(sock)
        if method is None:
            return
        if method == "GET":
            payload = {"available": True} if path == "/capabilities" else {"status": "ok"}
            sock.sendall(_json_response(200, json.dumps(payload).encode()))
            return
        request = json.loads(body or b"{}")
        self.requests.append((path, request))
        valid = json.dumps(statevector_result(self.name, request.get("circuit_data", ""))).encode()
        fault = self.fault
        if fault == "slow":
            self._closing.wait(self.delay)
            try:
                sock.sendall(_json_response(200, valid))
            except OSError:
                pass
        elif fault == "reset":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            sock.close()
        elif fault == "close":
            sock.shutdown(socket.SHUT_RDWR)
        elif fault == "truncated":
            response = _json_response(200, valid)
            sock.sendall(response[: len(response) // 2])
            sock.shutdown(socket.SHUT_RDWR)
        elif fault == "truncated_json":
            sock.sendall(_json_response(200, valid[: len(valid) // 2]))
        elif fault in ("not_json", "html_200"):
            text = b"<html><body><h1>502 Bad Gateway</h1></body></html>"
            sock.sendall(_json_response(200, text, "text/html" if fault == "html_200" else "application/json"))
        elif fault == "list":
            sock.sendall(_json_response(200, b"[1, 2, 3]"))
        elif fault == "null":
            sock.sendall(_json_response(200, b"null"))
        elif fault == "nan":
            sock.sendall(_json_response(200, b'{"simulator": "x", "statevector": "AAAA", "simulation_time_sec": NaN}'))
        elif fault == "no_statevector":
            sock.sendall(_json_response(200, json.dumps({"simulator": self.name}).encode()))
        elif fault == "http_500":
            sock.sendall(_json_response(500, b"<html>Internal Server Error</html>", "text/html"))
        elif fault == "oversized_declared":
            sock.sendall((f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                          f"Content-Length: {self.cap * 4}\r\nConnection: close\r\n\r\n").encode()
                         + b" " * 1024)
            sock.shutdown(socket.SHUT_RDWR)
        elif fault == "oversized_chunked":
            sock.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
            piece = b" " * 8192
            try:
                for _ in range(self.cap * 4 // len(piece)):
                    sock.sendall(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
                sock.sendall(b"0\r\n\r\n")
            except OSError:
                pass
        else:
            sock.sendall(_json_response(200, valid))


def walk_strings(value):
    """Every string inside ``value`` (dict keys excluded)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from walk_strings(item)


RAW_EXCEPTION_MARKS = ("Traceback", 'File "', "/home/", "/tmp/", "site-packages", "Errno",
                       "httpx.", "builtins.", "object at 0x")


def assert_no_raw_exception_text(value, *extra):
    """No traceback, interpreter path, errno text or object repr anywhere in ``value``."""
    for text in walk_strings(value):
        for mark in RAW_EXCEPTION_MARKS + tuple(extra):
            assert mark not in text, f"{mark!r} reached the client: {text[:300]}"


class Api:
    """The real app through TestClient, dispatching over HTTP to ``runners`` (name -> FaultRunner)."""

    def __init__(self, client, runners):
        self.client, self.runners = client, runners

    def compare(self, qasm, targets=None, **fields):
        body = {"qasm_string": qasm, "target_simulators": list(targets or self.runners),
                "timeout_seconds": 10, **fields}
        r = self.client.post("/compare", json=body)
        assert r.status_code == 200, r.text
        return r.json()["job_id"]

    def batch(self, tasks, targets=None, **fields):
        body = {"tasks": tasks, "mode": "statevector", "target_simulators": list(targets or self.runners),
                "timeout_seconds": 10, **fields}
        r = self.client.post("/run_batch_suite", json=body)
        assert r.status_code == 200, r.text
        return r.json()["job_id"]

    def job(self, job_id):
        r = self.client.get(f"/jobs/{job_id}")
        assert r.status_code == 200, r.text
        return r.json()

    def finished(self, job_id, seconds=60.0):
        """The job envelope once its status is terminal; fails after ``seconds``."""
        deadline = time.monotonic() + seconds
        while True:
            env = self.job(job_id)
            if env["status"] in ("completed", "failed"):
                return env
            assert time.monotonic() < deadline, f"job {job_id} still {env['status']}"
            time.sleep(0.05)


def wire_runners(monkeypatch, runners: dict, run_timeout: int = 1, queue_budget: int = 0):
    """Point the registry, the availability probes and the dispatch URLs at ``runners`` (each
    with a ``url``); runs get ``run_timeout`` seconds and ``queue_budget`` seconds of queue
    wait, and the API's read timeout is their sum."""
    import routers.benchmark as benchmark
    import services.availability as availability
    import services.job_manager as job_manager
    from config import settings

    for name, runner in runners.items():
        monkeypatch.setattr(settings, URL_SETTINGS[name], runner.url)
    run_urls = {name: f"{runner.url}/run" for name, runner in runners.items()}
    measured_urls = {name: f"{runner.url}/run_measured" for name, runner in runners.items()}
    monkeypatch.setattr(job_manager, "STATEVECTOR_RUNNER_URLS", run_urls)
    monkeypatch.setattr(job_manager, "SAMPLED_SV_URLS", measured_urls)
    monkeypatch.setattr(job_manager, "NATIVE_SAMPLING_URLS", {})
    monkeypatch.setattr(settings, "RUNNER_QUEUE_MAX_WAIT_SEC", queue_budget)
    monkeypatch.setattr(settings, "RUNNER_DEADLINE_BUFFER_SEC", 0)
    monkeypatch.setattr(settings, "RUNNER_CONNECT_TIMEOUT_SEC", 2)

    def clamp(_seconds):
        return run_timeout
    monkeypatch.setattr(benchmark, "clamp_timeout", clamp)
    monkeypatch.setattr(job_manager, "clamp_timeout", clamp)
    availability.clear_cache()


@pytest.fixture
def api_with_runners(tmp_path, monkeypatch):
    """``make(faults)`` -> Api for the real app whose runners are FaultRunners, one per entry
    of ``faults`` (name -> fault or None). Circuit preparation runs in a thread, rate limits
    are off and the spill directory is the test's own."""
    pytest.importorskip("pytket")
    import services.availability as availability
    import services.job_manager as job_manager
    from main import app
    from services import job_store, prep_worker
    from services.security import limiter

    spill = tmp_path / "spill"
    monkeypatch.setattr(job_store, "SPILL_DIR", str(spill))
    job_store.reset_spill_dir()
    monkeypatch.setattr(limiter, "enabled", False)
    monkeypatch.setattr(prep_worker, "IN_PROCESS", True)
    before = set(job_manager.ACTIVE_JOBS)
    started = []

    def make(faults: dict, **options):
        runners = {name: FaultRunner(name, fault, **options) for name, fault in faults.items()}
        started.extend(runners.values())
        wire_runners(monkeypatch, runners)
        return Api(TestClient(app), runners)

    yield make
    for runner in started:
        runner.close()
    availability.clear_cache()
    for job_id in [j for j in job_manager.ACTIVE_JOBS if j not in before]:
        job_manager.ACTIVE_JOBS.pop(job_id, None)
