"""A server connection for the run and result commands: GET /config read once and checked
against the handshake, JSON requests whose error statuses become CliErrors, and downloads
streamed to a .part file that is renamed into place only when complete."""

import json
import os
import re
import shutil

from qrosetta_cli import output
from qrosetta_cli.client import handshake, waiting
from qrosetta_cli.client.commands import status_error
from qrosetta_cli.client.transport import Transient
from qrosetta_cli.errors import CliError, Exit

LARGE_DOWNLOAD = 1 << 30
DOWNLOAD_TIMEOUT_SEC = 330
RETRY_DELAYS_SEC = (1, 2, 4)
RETRY_STATUSES = (502, 503, 504)
MAX_RETRY_AFTER_SEC = 30
_READ_POSTS = re.compile(r"^(/jobs/[^/]+)?/(export|summary|publication/render|publication/artifacts)$|^/plan$")


def repeatable(method, path):
    """True for a request that starts no work on the server: GET, and the POST routes that only
    read a report (export, summary, publication, plan). A run is never sent twice."""
    return method.upper() in ("GET", "HEAD") or (method.upper() == "POST" and bool(_READ_POSTS.match(path)))


def _retry_delay(resp, attempt):
    """Seconds to wait before repeating a request that got `resp`, or None for no retry."""
    if attempt >= len(RETRY_DELAYS_SEC):
        return None
    if resp.status in RETRY_STATUSES:
        return RETRY_DELAYS_SEC[attempt]
    if resp.status == 429:
        try:
            after = int(resp.headers.get("retry-after") or "")
        except ValueError:
            return None
        return after if 0 <= after <= MAX_RETRY_AFTER_SEC else None
    return None


def with_retries(method, path, send, retry=None):
    """`send()` once, or up to len(RETRY_DELAYS_SEC) more times with backoff when the request is
    `repeatable` (or `retry` says so) and it failed in transit or got 429/502/503/504."""
    retry = repeatable(method, path) if retry is None else retry
    attempt = 0
    while True:
        try:
            resp = send()
        except Transient as exc:
            if not retry or attempt >= len(RETRY_DELAYS_SEC):
                raise
            delay: int | None = RETRY_DELAYS_SEC[attempt]
            output.progress(f"{exc.message} Trying again in {delay} s.")
        else:
            delay = _retry_delay(resp, attempt) if retry else None
            if delay is None:
                return resp
            output.progress(f"{method.upper()} {path} answered HTTP {resp.status}; trying again in {delay} s.")
        waiting.pause(delay)
        attempt += 1


PROXY_PAGE = "an HTML error page from a proxy in front of the API; the API may be stopped or restarting"


def _is_html(resp):
    return "html" in resp.content_type.lower() or resp.body.lstrip()[:1] == b"<"


def http_error(method, path, resp, what=None, hint=None):
    """The CliError for an error status, with the server's detail verbatim; `hint` replaces the
    status's default hint for a client error. An HTML body (a proxy's error page) is named, not
    printed."""
    code, reason, default_hint = status_error(resp.status, resp.headers.get("retry-after"))
    hint = hint if hint and resp.status < 500 and resp.status not in (401, 403, 429) else default_hint
    parsed = resp.json()
    if parsed is not None:
        detail = parsed
    elif _is_html(resp):
        detail = PROXY_PAGE if resp.status in RETRY_STATUSES else "an HTML page"
    else:
        detail = resp.body.decode("utf-8", "replace")
    text = detail.get("detail", detail) if isinstance(detail, dict) else detail
    if resp.status == 404:
        code, reason = Exit.NOT_FOUND, "not_found"
    return CliError(
        f"{what or f'{method} {path}'} answered HTTP {resp.status}: {text}",
        code,
        reason,
        hint,
        http_status=resp.status,
        detail=detail,
    )


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

    def request(
        self,
        method,
        path,
        payload=None,
        query=None,
        ok=(200,),
        timeout=None,
        what=None,
        hint=None,
        headers=None,
        retry=None,
    ):
        body = body_bytes(payload) if payload is not None else None
        headers = dict(headers or {}, **({"Content-Type": "application/json"} if body is not None else {}))
        resp = with_retries(
            method,
            path,
            lambda: self.transport.request(method, path, query=query, body=body, headers=headers, timeout=timeout),
            retry,
        )
        if resp.status not in ok:
            raise http_error(method, path, resp, what, hint)
        return resp

    def get(self, path, query=None, **kwargs):
        return self.request("GET", path, query=query, **kwargs).json()

    def post(self, path, payload=None, **kwargs):
        return self.request("POST", path, payload=payload, **kwargs).json()

    def download(self, method, path, dest, payload=None, query=None, confirm_large=None, timeout=None, retry=None):
        """Stream a 2xx body to `dest` through `dest.part`; returns the bytes written. An error
        status raises the CliError of `http_error`; Content-Length is checked against the free
        space first, and `confirm_large(size)` decides a body over 1 GiB. Each socket operation
        may take DOWNLOAD_TIMEOUT_SEC (a crate is built before its first byte); a transfer cut off
        part way is started again from the beginning (`with_retries`)."""
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
                    raise CliError(
                        f"{dest}: the server sends {size} bytes and {free} are free.",
                        Exit.REFUSED,
                        "disk_full",
                        hint=f"free space under {os.path.dirname(dest)}",
                    )
                if size > LARGE_DOWNLOAD and confirm_large is not None and not confirm_large(size):
                    raise CliError(
                        f"{dest}: {size} bytes not downloaded.",
                        Exit.USAGE,
                        "large_download",
                        hint="add --yes to download it",
                    )

        def send():
            with open(part, "wb") as fh:
                return self.transport.download(
                    method,
                    path,
                    fh,
                    query=query,
                    body=body,
                    headers=headers,
                    timeout=timeout or DOWNLOAD_TIMEOUT_SEC,
                    on_headers=check,
                )

        try:
            resp = with_retries(method, path, send, retry)
            if not 200 <= resp.status < 300:
                raise http_error(method, path, resp)
            size = os.path.getsize(part)
            os.replace(part, dest)
            return size
        finally:
            if os.path.exists(part):
                os.unlink(part)
