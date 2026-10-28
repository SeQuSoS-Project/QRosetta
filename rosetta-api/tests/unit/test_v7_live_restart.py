"""V7(e) Failure injection, a real API restart: the API served by uvicorn in its own process,
dispatching to fake runners, is killed while `qrosetta run` (the real HTTP transport) waits for
its job, and started again on the same port. The CLI rides out the refused connections, meets
the restarted server's 404 and ends with exit 14 `job_lost` and STATUS `job-lost`; a job sent
to the new process runs."""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tests.unit._fault_runners import FaultRunner
from tests.unit._qrosetta_fake import REPO as _REPO  # noqa: F401

pytest.importorskip("pytket")

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import results, waiting  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402

API_DIR = Path(__file__).resolve().parents[2]
REPO = API_DIR.parent
QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LiveApi:
    """main:app under uvicorn on ``port``; ``start()`` returns the seconds until /health answered."""

    def __init__(self, port, env):
        self.port, self.env, self.process = port, env, None
        self.url = f"http://127.0.0.1:{port}"

    def start(self, timeout=120.0):
        t0 = time.monotonic()
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(self.port),
             "--log-level", "warning"], cwd=API_DIR, env=self.env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        while time.monotonic() - t0 < timeout:
            try:
                with urllib.request.urlopen(f"{self.url}/health", timeout=1) as resp:
                    if resp.status == 200:
                        return time.monotonic() - t0
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("the API did not start")

    def kill(self):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(10)


@pytest.fixture
def live(tmp_path):
    slow = FaultRunner("qiskit", "slow", delay=6.0)
    fast = FaultRunner("cirq")
    env = {k: v for k, v in os.environ.items() if not k.startswith("QROSETTA_")}
    env.update({
        "PYTHONPATH": os.pathsep.join([str(API_DIR), str(REPO / "shared")]),
        "EXECUTION_MODE": "local",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'api.db'}",
        "QROSETTA_JOB_SPILL_DIR": str(tmp_path / "spill"),
        "QROSETTA_JOB_SPILL_MIN_FREE_MIB": "0",
        "PYTKET_QISKIT_RUNNER_URL": slow.url,
        "PYTKET_CIRQ_RUNNER_URL": fast.url,
        "RUNNER_QUEUE_MAX_WAIT_SEC": "5",
        "TMPDIR": os.environ.get("TMPDIR", str(Path.home() / ".tmp")),
    })
    api = LiveApi(_free_port(), env)
    try:
        yield api, slow
    finally:
        api.kill()
        slow.close()
        fast.close()


def test_v7_05_qrosetta_run_meets_a_real_api_restart(live, tmp_path, capsys, monkeypatch):
    api, slow = live
    first_start = api.start()
    monkeypatch.setattr(waiting, "pause", lambda seconds: time.sleep(min(seconds, 0.5)))
    circuit = tmp_path / "bell.qasm"
    circuit.write_text(QASM)
    env = {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
           "XDG_RUNTIME_DIR": str(tmp_path / "run"), "QROSETTA_RESULTS_DIR": str(tmp_path / "res"),
           "QROSETTA_SERVER": api.url}
    restart = {}

    def restart_when_dispatched():
        deadline = time.monotonic() + 60
        while not slow.requests and time.monotonic() < deadline:
            time.sleep(0.05)
        api.kill()
        time.sleep(1.0)
        restart["seconds"] = api.start()

    thread = threading.Thread(target=restart_when_dispatched, daemon=True)
    thread.start()
    code = main(["run", str(circuit), "--backends", "qiskit,cirq", "--json"], env=env)
    thread.join(120)
    out = capsys.readouterr()
    doc = json.loads(out.out)
    assert slow.requests, "the job never reached the runner"
    assert code == Exit.NOT_FOUND, doc
    assert doc["error"]["reason"] == "job_lost"
    assert doc["error"]["message"].startswith("The server no longer has job ")
    (job,) = doc["data"]["jobs"]
    assert results.read_status(job["dir"]) == "job-lost"
    assert "Traceback" not in out.err and "internal error" not in out.err.lower()
    assert restart["seconds"] < 60

    try:
        urllib.request.urlopen(f"{api.url}/jobs/{job['job_id']}", timeout=5)
        raise AssertionError("the restarted API still has the job")
    except urllib.error.HTTPError as err:
        assert err.code == 404 and err.headers["content-type"] == "application/json"
        assert "lost if the server restarts" in json.loads(err.read())["detail"]
    print(f"API start {first_start:.1f} s, restart {restart['seconds']:.1f} s")
