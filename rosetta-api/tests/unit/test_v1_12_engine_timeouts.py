"""V1-12: every engine call qrosetta makes has a timeout; a hung engine ends the command with exit
16 after releasing the engine lock and ending the host-load notice; a heartbeat answered 404
stops the notice with a warning."""
import json
import subprocess
import time

import pytest

from tests.unit._qrosetta_fake import FakeEngine
from tests.unit.test_qrosetta_cli import _safe_boot, cli, env, project  # noqa: F401
from tests.unit.test_qrosetta_hostload import NoticeServer, _ctx

from qrosetta_cli.client.transport import Response  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from qrosetta_cli.stack import engine as eng, guard, hostload  # noqa: E402


class HungEngine(FakeEngine):
    """A FakeEngine that records each call's timeout and never finishes `hang` commands."""

    def __init__(self, hang=()):
        super().__init__()
        self.hang = set(hang)
        self.timeouts = []

    def __call__(self, cmd, **kwargs):
        self.timeouts.append((list(cmd), kwargs.get("timeout")))
        if self.hang & set(cmd[1:3]):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
        return super().__call__(cmd, **kwargs)


def test_v1_12_default_timeouts_follow_the_command():
    assert eng.default_timeout(["pull", "x"]) == eng.TRANSFER_TIMEOUT_SEC
    assert eng.default_timeout(["load", "-i", "f"]) == eng.TRANSFER_TIMEOUT_SEC
    assert eng.default_timeout(["stop", "id"]) == eng.CHANGE_TIMEOUT_SEC
    assert eng.default_timeout(["network", "rm", "id"]) == eng.CHANGE_TIMEOUT_SEC
    assert eng.default_timeout(["image", "inspect", "id"]) == eng.READ_TIMEOUT_SEC
    assert eng.default_timeout(["ps", "-a"]) == eng.READ_TIMEOUT_SEC


def test_v1_12_every_call_of_a_stop_carries_a_timeout(env, project):  # noqa: F811
    fake = HungEngine().standard()
    assert cli(fake, project, env, ["stop", "--force"]) == 0
    assert fake.timeouts and all(t is not None for _cmd, t in fake.timeouts), fake.timeouts


def test_v1_12_a_hung_engine_releases_the_lock_and_ends_the_notice(env, project, capsys):  # noqa: F811
    token = hostload.ensure_token(env)
    server = NoticeServer(token, gate={"exclusive_running": False, "shared_running": 1})
    fake = HungEngine(hang={"stop"}).standard()
    assert cli(fake, project, env, ["stop", "--force", "--json"], server=server) == Exit.ENGINE
    assert json.loads(capsys.readouterr().out)["error"]["reason"] == "engine_timeout"
    assert [d["action"] for d, _a in server.notices] == ["begin", "end"]
    with guard.engine_lock(env, "next command"):
        pass


def test_v1_12_a_hung_compose_up_is_stopped(monkeypatch):
    class Proc:
        def __init__(self):
            self.ended = None

        def wait(self, timeout=None):
            if self.ended is None:
                raise subprocess.TimeoutExpired("up", timeout)
            return self.ended

        def terminate(self):
            self.ended = -15

        def kill(self):
            self.ended = -9

    with pytest.raises(Exception) as err:
        eng.wait_spawned(Proc(), 0.01, ["podman", "compose", "up"])
    assert getattr(err.value, "reason", None) == "engine_timeout"


def test_v1_12_a_build_that_never_ends_releases_the_lock(env, project, monkeypatch, capsys):  # noqa: F811
    _safe_boot(project)

    def hung(cmd, env, cwd, timeout=None, **kw):
        assert timeout == eng.TRANSFER_TIMEOUT_SEC
        raise subprocess.TimeoutExpired(cmd, timeout)
    monkeypatch.setattr(subprocess, "call", hung)
    assert cli(FakeEngine().standard(), project, env, ["build", "api", "--json"]) == Exit.ENGINE
    assert json.loads(capsys.readouterr().out)["error"]["reason"] == "engine_timeout"
    with guard.engine_lock(env, "next command"):
        pass


def test_v1_12_a_heartbeat_answered_404_ends_the_notice_with_a_warning(env, monkeypatch, capsys):  # noqa: F811
    token = hostload.ensure_token(env)

    class Forgetful(NoticeServer):
        def request(self, method, path, query=None, body=None, headers=None, timeout=None):
            if path == hostload.ROUTE and json.loads(body)["action"] != "begin":
                self.notices.append((json.loads(body), None))
                return Response(404, {"content-type": "application/json"}, b'{"detail": "No open notice"}')
            return super().request(method, path, query, body, headers, timeout)

    server = Forgetful(token)
    monkeypatch.setattr(hostload, "HEARTBEAT_SEC", 0.01)
    with hostload.notice(_ctx(env, server), "http://localhost:8080", "build") as n:
        deadline = time.monotonic() + 5
        while not n.lost:
            assert time.monotonic() < deadline
            time.sleep(0.01)
        beats = len(server.notices)
        time.sleep(0.05)
        assert len(server.notices) == beats
    assert [d["action"] for d, _a in server.notices] == ["begin", "heartbeat"]
    assert "no longer holds this host-load notice" in capsys.readouterr().err
