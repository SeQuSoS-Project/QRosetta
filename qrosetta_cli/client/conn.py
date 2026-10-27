"""A server connection for the run and result commands: GET /config read once and checked
against the handshake, JSON requests whose error statuses become CliErrors, and downloads
streamed to a .part file that is renamed into place only when complete."""

import json
import os
import shutil

from qrosetta_cli.client import handshake
from qrosetta_cli.client.commands import status_error
from qrosetta_cli.errors import CliError, Exit

LARGE_DOWNLOAD = 1 << 30


def http_error(method, path, resp, what=None, hint=None):
    """The CliError for an error status, with the server's detail verbatim; `hint` replaces the
    status's default hint for a client error."""
    code, reason, default_hint = status_error(resp.status, resp.headers.get("retry-after"))
    hint = hint if hint and resp.status < 500 and resp.status not in (401, 403, 429) else default_hint
    parsed = resp.json()
    detail = parsed if parsed is not None else resp.body.decode("utf-8", "replace")
    text = detail.get("detail", detail) if isinstance(detail, dict) else detail
    if resp.status == 404:
        code, reason = Exit.NOT_FOUND, "not_found"
    return CliError(f"{what or f'{method} {path}'} answered HTTP {resp.status}: {text}", code, reason, hint,
                    http_status=resp.status, detail=detail)


def body_bytes(payload):
    """A request body as the CLI sends it: compact JSON in UTF-8."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class Conn:
    """One server, its /config and the transport that reaches it."""

    def __init__(self, ctx, features=(), with_token=True, server=None):
        self.ctx = ctx
        self.server = server or ctx.server()
        self.transport = ctx.transport(with_token=with_token, server=self.server)
        self.config = handshake.fetch_config(self.transport)
        self.block = handshake.check(self.config, features)
        if server is None:
            ctx.note_handshake(self.block)

    @property
    def url(self):
        return self.server.url

    @property
    def local(self):
        return self.server.local

    def features(self):
        return self.block.get("features") or {}

    def has(self, name, version=1):
        have = self.features().get(name)
        return isinstance(have, int) and have >= version

    def limit(self, name, default=None):
        return (self.config.get("limits") or {}).get(name, default)

    def refresh_config(self):
        self.config = handshake.fetch_config(self.transport)
        return self.config

    def dispatches_in_flight(self, config=None):
        """Runs in flight on the server by /config's gate state (shared and exclusive)."""
        gate = (config or self.config).get("exclusive") or {}
        return int(gate.get("shared_running") or 0) + int(bool(gate.get("exclusive_running")))

    def request(self, method, path, payload=None, query=None, ok=(200,), timeout=None, what=None, hint=None):
        body = body_bytes(payload) if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        resp = self.transport.request(method, path, query=query, body=body, headers=headers, timeout=timeout)
        if resp.status not in ok:
            raise http_error(method, path, resp, what, hint)
        return resp

    def get(self, path, query=None, **kwargs):
        return self.request("GET", path, query=query, **kwargs).json()

    def post(self, path, payload=None, **kwargs):
        return self.request("POST", path, payload=payload, **kwargs).json()

    def download(self, method, path, dest, payload=None, query=None, confirm_large=None, timeout=None):
        """Stream a 2xx body to `dest` through `dest.part`; returns the bytes written. An error
        status raises the CliError of `http_error`; Content-Length is checked against the free
        space first, and `confirm_large(size)` decides a body over 1 GiB."""
        body = body_bytes(payload) if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        part = dest + ".part"

        def check(hdrs):
            try:
                size = int(hdrs.get("content-length") or -1)
            except ValueError:
                size = -1
            if size > 0:
                free = shutil.disk_usage(os.path.dirname(dest) or ".").free
                if size > free:
                    raise CliError(f"{dest}: the server sends {size} bytes and {free} are free.", Exit.REFUSED,
                                   "disk_full", hint=f"free space under {os.path.dirname(dest)}")
                if size > LARGE_DOWNLOAD and confirm_large is not None and not confirm_large(size):
                    raise CliError(f"{dest}: {size} bytes not downloaded.", Exit.USAGE, "large_download",
                                   hint="add --yes to download it")

        try:
            with open(part, "wb") as fh:
                resp = self.transport.download(method, path, fh, query=query, body=body, headers=headers,
                                               timeout=timeout, on_headers=check)
            if not 200 <= resp.status < 300:
                raise http_error(method, path, resp)
            size = os.path.getsize(part)
            os.replace(part, dest)
            return size
        finally:
            if os.path.exists(part):
                os.unlink(part)
