"""A real runner (runners/<dir>/main.py), or the shared scaffolding around test processors
(tests/unit/_watcher_server.py), served by uvicorn on a free loopback port in its own process,
for the failure-injection tests that kill runner processes or drop their callers (V7)."""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[3]
_SERVE = ("import sys, uvicorn; import main; "
          "uvicorn.run(main.app, host='127.0.0.1', port=int(sys.argv[1]), log_level='warning')")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class RealRunner:
    """``runners/<directory>/main.py`` serving on 127.0.0.1; ``url``, ``pid``, ``run_children()``."""

    def __init__(self, directory: str, start_timeout: float = 120.0):
        runner_dir = REPO / "runners" / directory
        self._start([sys.executable, "-c", _SERVE], runner_dir,
                    [str(runner_dir), str(REPO / "shared")], f"runner {directory}", start_timeout)

    def _start(self, command, cwd, pythonpath, name, start_timeout):
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        env = {k: v for k, v in os.environ.items() if not k.startswith("QROSETTA_HOST_")}
        env["PYTHONPATH"] = os.pathsep.join(pythonpath)
        env.setdefault("TMPDIR", os.environ.get("TMPDIR", str(Path.home() / ".tmp")))
        self.process = subprocess.Popen([*command, str(self.port)], cwd=cwd,
                                        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                        start_new_session=True)
        deadline = time.monotonic() + start_timeout
        while True:
            try:
                with urllib.request.urlopen(f"{self.url}/health", timeout=1) as resp:
                    if resp.status == 200:
                        break
            except OSError:
                pass
            if self.process.poll() is not None:
                raise RuntimeError(f"{name} exited: {self.process.stderr.read().decode()[-2000:]}")
            if time.monotonic() > deadline:
                self.close()
                raise RuntimeError(f"{name} did not start in {start_timeout:g} s")
            time.sleep(0.2)

    @property
    def pid(self) -> int:
        return self.process.pid

    def run_children(self) -> list:
        """The isolated run processes the server has spawned (not multiprocessing's helpers)."""
        try:
            children = psutil.Process(self.pid).children(recursive=False)
        except psutil.NoSuchProcess:
            return []
        out = []
        for child in children:
            try:
                cmd = " ".join(child.cmdline())
            except psutil.Error:
                continue
            if "multiprocessing" in cmd and "resource_tracker" not in cmd:
                out.append(child)
        return out

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process.wait(10)
        if self.process.stderr is not None:
            self.process.stderr.close()


class ScaffoldServer(RealRunner):
    """``tests/unit/_watcher_server.py``: the shared runner (``kind`` runner) or compiler
    (``compiler``) scaffolding around ``_isolated_fixture.sleeps_from_circuit``, served with the
    uvicorn event loop ``loop`` and HTTP implementation ``http``."""

    def __init__(self, kind: str, loop: str, http: str, start_timeout: float = 60.0):
        api_dir = REPO / "rosetta-api"
        self._start([sys.executable, "-m", "tests.unit._watcher_server", kind, loop, http], api_dir,
                    [str(api_dir), str(REPO / "shared")], f"{kind} scaffold", start_timeout)
