"""The local lifecycle token and host-load notices (spec S24). `qrosetta start` writes the token
to $XDG_RUNTIME_DIR/qrosetta/lifecycle.token and compose mounts it into the API as a secret
file. Engine actions that load the host (start beside a running stack, stop, remove, build)
open a notice with the API for their duration, kept alive by a heartbeat; runs that overlap it
record it, and an exclusive run waits for it. A notice that fails is a warning, never a
failure of the command."""

import json
import os
import secrets
import threading
from contextlib import contextmanager

from qrosetta_cli import config as cfgmod, output
from qrosetta_cli.errors import CliError

TOKEN_FILE = "lifecycle.token"
COMPOSE_VAR = "QROSETTA_LIFECYCLE_TOKEN_PATH"
ROUTE = "/local/host-load"
HEARTBEAT_SEC = 10
REQUEST_TIMEOUT_SEC = 5


def token_path(env):
    return os.path.join(cfgmod.qr_dir("runtime", env), TOKEN_FILE)


def read_token(env):
    """The token, or None when the file is missing, unreadable or empty."""
    try:
        with open(token_path(env), encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def ensure_token(env):
    """The token, written first when there is none. The directory is 0700; the file is
    rewritten in place, so a container that mounted it keeps reading the same file. It is
    readable by every user (0644) because under rootless engines the API's user inside the
    container maps to another host uid; the 0700 directory keeps other host users out."""
    token = read_token(env)
    if token:
        return token
    directory = os.path.dirname(token_path(env))
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    token = secrets.token_urlsafe(32)
    fd = os.open(token_path(env), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.fchmod(fd, 0o644)
        os.write(fd, (token + "\n").encode())
    finally:
        os.close(fd)
    return token


def compose_env(env):
    """{QROSETTA_LIFECYCLE_TOKEN_PATH: path} when the token file exists, else {} (compose then
    mounts its empty placeholder and the API accepts no lifecycle token)."""
    path = token_path(env)
    return {COMPOSE_VAR: path} if os.path.isfile(path) else {}


def auth_headers(env):
    token = read_token(env)
    return {"Authorization": f"Bearer {token}"} if token else {}


class Notice:
    """One open notice: begin, a heartbeat thread, end."""

    def __init__(self, ctx, url, kind, services, expect_server_gone=False):
        self.ctx, self.url, self.kind = ctx, url, kind
        self.services = [s for s in services or [] if s]
        self.expect_server_gone = expect_server_gone
        self.notice_id = None
        self._stop = threading.Event()
        self._thread = None

    def _post(self, body):
        from qrosetta_cli.client import servers
        transport = self.ctx.transport(server=servers.Server("local", self.url, "compose port"),
                                       timeout=REQUEST_TIMEOUT_SEC)
        headers = {"Content-Type": "application/json", **auth_headers(self.ctx.env)}
        return transport.request("POST", ROUTE, body=json.dumps(body).encode(), headers=headers,
                                 timeout=REQUEST_TIMEOUT_SEC)

    def begin(self):
        if not read_token(self.ctx.env):
            output.warn(f"{self.kind}: host load not recorded with the server: no lifecycle token at "
                        f"{token_path(self.ctx.env)} (the stack was not started by `qrosetta start`).",
                        "host_load_unrecorded")
            return
        body = {"action": "begin", "kind": self.kind}
        if self.services:
            body["services"] = self.services
        try:
            resp = self._post(body)
        except CliError as exc:
            output.warn(f"{self.kind}: host load not recorded with the server ({exc.message})", "host_load_unrecorded")
            return
        data = resp.json() if resp.status == 200 else None
        if not isinstance(data, dict) or not data.get("notice_id"):
            why = ("its lifecycle token differs from this one, or it predates host-load notices"
                   if resp.status == 404 else f"HTTP {resp.status}")
            output.warn(f"{self.kind}: host load not recorded with the server ({why}); runs beside it do not "
                        "record it.", "host_load_unrecorded")
            return
        self.notice_id = data["notice_id"]
        if data.get("gate_held") is False:
            output.warn(f"{self.kind}: an exclusive run holds the server; it records this host load.",
                        "host_load_beside_exclusive")
        self._thread = threading.Thread(target=self._beat, name="qrosetta-host-load", daemon=True)
        self._thread.start()

    def _beat(self):
        while not self._stop.wait(HEARTBEAT_SEC):
            try:
                self._post({"action": "heartbeat", "notice_id": self.notice_id})
            except CliError:
                pass

    def end(self):
        if self.notice_id is None:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(REQUEST_TIMEOUT_SEC + 1)
        try:
            resp = self._post({"action": "end", "notice_id": self.notice_id})
            failed = resp.status != 200 and f"HTTP {resp.status}"
        except CliError as exc:
            failed = exc.message
        if failed and not self.expect_server_gone:
            output.warn(f"{self.kind}: the host-load notice was not ended ({failed}); the server ends it "
                        "30 s after its last heartbeat.", "host_load_not_ended")


@contextmanager
def notice(ctx, url, kind, services=None, expect_server_gone=False):
    """Hold a host-load notice of `kind` for the with-block when a server answers at `url`."""
    if not url:
        yield None
        return
    n = Notice(ctx, url, kind, services, expect_server_gone)
    n.begin()
    try:
        yield n
    finally:
        n.end()
