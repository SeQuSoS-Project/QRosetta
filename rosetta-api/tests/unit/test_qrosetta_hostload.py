"""qrosetta's side of host-load notices (spec S24): the lifecycle token `start` writes and
compose mounts, the notices `start`, `stop`, `remove` and `build` hold, the heartbeat, and
warnings in place of failures when the server does not take a notice."""

import json
import os
import stat
import subprocess
import time

import pytest

from tests.unit._qrosetta_fake import FakeEngine, FakeServer, ours
from tests.unit.test_qrosetta_cli import _safe_boot, cli, env, fake, project  # noqa: F401

from qrosetta_cli.client.transport import Response  # noqa: E402
from qrosetta_cli.context import Context  # noqa: E402
from qrosetta_cli.stack import hostload, serve  # noqa: E402


class NoticeServer(FakeServer):
    """A FakeServer that also answers POST /local/host-load for one token."""

    def __init__(self, token=None, answer=200, **kwargs):
        super().__init__(**kwargs)
        self.token = token
        self.answer = answer
        self.notices = []
        self.auth = []

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        auth = (headers or {}).get("Authorization")
        if path != hostload.ROUTE:
            self.auth.append((path, query, auth))
            return super().request(method, path, query, body, headers, timeout)
        doc = json.loads(body)
        self.notices.append((doc, auth))
        if self.answer != 200 or (self.token is not None and auth != f"Bearer {self.token}"):
            return Response(404, {"content-type": "application/json"}, b'{"detail": "Not Found"}')
        out = {"notice_id": "a" * 32, "gate_held": True}
        return Response(200, {"content-type": "application/json"}, json.dumps(out).encode())


def test_the_token_file_is_private_by_its_directory_and_kept(env):
    token = hostload.ensure_token(env)
    path = hostload.token_path(env)
    assert len(token) >= 40 and open(path).read().strip() == token
    assert stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o644
    inode = os.stat(path).st_ino
    assert hostload.ensure_token(env) == token and os.stat(path).st_ino == inode
    assert hostload.compose_env(env) == {hostload.COMPOSE_VAR: path}
    assert hostload.compose_env({**env, "XDG_RUNTIME_DIR": env["XDG_RUNTIME_DIR"] + "-other"}) == {}


def _ctx(env, server):
    return Context(args=None, env=env, cfg=None, transport_factory=server)


def test_a_notice_begins_beats_and_ends(env, monkeypatch):
    token = hostload.ensure_token(env)
    server = NoticeServer(token)
    monkeypatch.setattr(hostload, "HEARTBEAT_SEC", 0.01)
    with hostload.notice(_ctx(env, server), "http://localhost:8080", "build", ["qiskit"]) as n:
        assert n.notice_id == "a" * 32
        deadline = time.monotonic() + 5
        while not any(d["action"] == "heartbeat" for d, _a in server.notices):
            assert time.monotonic() < deadline
            time.sleep(0.01)
    actions = [d["action"] for d, _a in server.notices]
    assert actions[0] == "begin" and actions[-1] == "end"
    assert server.notices[0][0] == {"action": "begin", "kind": "build", "services": ["qiskit"]}
    assert all(auth == f"Bearer {token}" for _d, auth in server.notices)
    count = len(server.notices)
    time.sleep(0.05)
    assert len(server.notices) == count, "the heartbeat stopped with the notice"


def test_without_a_server_no_notice_is_sent(env):
    server = NoticeServer("x")
    with hostload.notice(_ctx(env, server), None, "build") as n:
        assert n is None
    assert server.notices == []


@pytest.mark.parametrize("case", ["no_token", "rejected", "unreachable"])
def test_a_notice_that_fails_is_a_warning(env, capsys, case):
    from tests.unit._qrosetta_fake import Unreachable
    if case != "no_token":
        hostload.ensure_token(env)
    server = Unreachable() if case == "unreachable" else NoticeServer("other-token")
    ran = []
    with hostload.notice(_ctx(env, server), "http://localhost:8080", "pull"):
        ran.append(True)
    assert ran == [True]
    err = capsys.readouterr().err
    assert "host load not recorded" in err
    assert {"no_token": "no lifecycle token", "rejected": "lifecycle token differs",
            "unreachable": "No answer"}[case] in err


def test_stop_and_build_hold_notices(fake, project, env, monkeypatch, capsys):
    token = hostload.ensure_token(env)
    busy = NoticeServer(token, gate={"exclusive_running": False, "shared_running": 1})
    assert cli(fake, project, env, ["stop", "--force"], server=busy) == 0
    assert [d["action"] for d, _a in busy.notices] == ["begin", "end"]
    assert busy.notices[0][0] == {"action": "begin", "kind": "stop"}
    assert "runs beside it record it" in capsys.readouterr().err

    _safe_boot(project)
    fake2 = FakeEngine().standard()
    order = []
    server = NoticeServer(token)
    real = server.request

    def request(method, path, *args, **kwargs):
        if path == hostload.ROUTE:
            order.append(json.loads(args[1] if len(args) > 1 else kwargs["body"])["action"])
        return real(method, path, *args, **kwargs)

    server.request = request
    monkeypatch.setattr(subprocess, "call", lambda cmd, env, cwd: order.append("build") or 0)
    assert cli(fake2, project, env, ["build", "api"], server=server) == 0
    assert order == ["begin", "build", "end"]
    assert server.notices[0][0] == {"action": "begin", "kind": "build", "services": ["api"]}


def test_start_writes_the_token_and_passes_it_to_compose(fake, project, env, monkeypatch):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    server = NoticeServer(None, fresh=True)
    assert cli(fake, project, env, ["start", "-d", "qiskit", "--yes"], server=server) == 0
    token = hostload.read_token(env)
    assert token
    assert [d for d, _a in server.notices] == [{"action": "begin", "kind": "start", "services": ["qiskit"]},
                                               {"action": "end", "notice_id": "a" * 32}]
    assert all(a == f"Bearer {token}" for _d, a in server.notices)
    fresh = [a for p, q, a in server.auth if p == "/runners" and q == {"fresh": "true"}]
    assert fresh and all(a == f"Bearer {token}" for a in fresh)
    compose_envs = [e for cmd, e in fake.calls if "compose" in cmd]
    assert compose_envs and all(e.get(hostload.COMPOSE_VAR) == hostload.token_path(env) for e in compose_envs)


def test_recreating_running_containers_holds_a_stop_notice(fake, project, env, monkeypatch, capsys):
    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    fake.add("qiskit-runner", ours("qiskit_runner"), image="i-qiskit")
    fake.rebuild("qiskit_runner", "j-qiskit")
    server = NoticeServer(None, fresh=True)
    assert cli(fake, project, env, ["start", "-d", "qiskit"], server=server) == 0
    assert [d for d, _a in server.notices] == [{"action": "begin", "kind": "stop", "services": ["qiskit"]},
                                               {"action": "end", "notice_id": "a" * 32}]
    assert fake.recreated == ["c-qiskit-runner"]
    capsys.readouterr()
    fake.rebuild("api", "j-api")
    server = NoticeServer(None, fresh=True)
    original = server.request

    def api_restarted(method, path, query=None, body=None, headers=None, timeout=None):
        if path == hostload.ROUTE and json.loads(body)["action"] == "end":
            return Response(404, {"content-type": "application/json"}, b'{"detail": "Not Found"}')
        return original(method, path, query, body, headers, timeout)

    server.request = api_restarted
    assert cli(fake, project, env, ["start", "-d"], server=server) == 0
    assert server.notices[0][0] == {"action": "begin", "kind": "stop", "services": ["api"]}
    assert "not ended" not in capsys.readouterr().err
