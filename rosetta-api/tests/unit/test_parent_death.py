"""An isolated run's child dies with the runner worker that spawned it."""
import os
import signal
import subprocess
import sys
import time

import pytest

from qrosetta_commons import helpers
from tests.unit import _isolated_fixture as fx

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"),
                                reason="PR_SET_PDEATHSIG is Linux only")

API_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _wait_for_pid(path, worker, seconds=30.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists() and path.read_text():
            return int(path.read_text())
        assert worker.poll() is None, f"worker exited with {worker.returncode}"
        time.sleep(0.05)
    raise AssertionError(f"{path} was not written")


@pytest.mark.parametrize("measured", [True, False])
def test_child_dies_when_its_worker_is_killed(tmp_path, measured):
    pid_file = tmp_path / "pid"
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
    worker = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; from tests.unit._isolated_fixture import serve_one_slow_run; "
         "serve_one_slow_run(sys.argv[1], sys.argv[2] == 'measured')",
         str(pid_file), "measured" if measured else "direct"],
        env=env, cwd=API_ROOT)
    child_pid = None
    try:
        child_pid = _wait_for_pid(pid_file, worker)
        worker.send_signal(signal.SIGKILL)
        worker.wait()
        t0 = time.monotonic()
        while fx.process_alive(child_pid) and time.monotonic() - t0 < 5:
            time.sleep(0.02)
        took = time.monotonic() - t0
        alive = fx.process_alive(child_pid)
    finally:
        if worker.poll() is None:
            worker.kill()
        if child_pid and fx.process_alive(child_pid):
            os.kill(child_pid, signal.SIGKILL)
    assert not alive, f"the child was still running {took:.1f} s after its worker was killed"


def test_child_exits_when_its_parent_is_already_gone():
    result_q = helpers._SPAWN_CTX.Queue()
    proc = helpers._SPAWN_CTX.Process(
        target=helpers._isolated_target,
        args=(result_q, fx.fast.__module__, "fast", {"x": 1}, False, os.getppid()))
    proc.start()
    proc.join(30)
    assert proc.exitcode == -signal.SIGKILL
    assert result_q.empty()
