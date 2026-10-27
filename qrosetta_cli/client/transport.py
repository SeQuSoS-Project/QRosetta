"""Transport: how the client half reaches a server. HttpTransport speaks HTTP with urllib; tests
and a later in-image transport provide the same `request` method (spec Q3 `server.kind`)."""

import ipaddress
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from qrosetta_cli import __version__
from qrosetta_cli.errors import CliError, Exit

DEFAULT_TIMEOUT_SEC = 30


@dataclass
class Response:
    status: int
    headers: dict = field(default_factory=dict)
    body: bytes = b""

    def json(self):
        """The body as JSON, or None when it is not JSON."""
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    @property
    def content_type(self):
        return self.headers.get("content-type", "")


def is_loopback(url):
    host = urllib.parse.urlsplit(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def origin(url):
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class Transport:
    """The interface every transport implements."""

    kind = "http"
    url = ""

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        raise NotImplementedError


class HttpTransport(Transport):
    """Requests to one server origin. Loopback URLs bypass proxies; no_proxy is honoured
    otherwise; TLS certificates are always verified (SSL_CERT_FILE selects a bundle)."""

    def __init__(self, url, token=None, timeout=DEFAULT_TIMEOUT_SEC):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        handlers = [urllib.request.HTTPSHandler(context=ssl.create_default_context())]
        if is_loopback(self.url):
            handlers.append(urllib.request.ProxyHandler({}))
        self._opener = urllib.request.build_opener(*handlers)

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        url = self.url + path
        if query:
            url += ("&" if "?" in path else "?") + urllib.parse.urlencode(query, doseq=True)
        hdrs = {"User-Agent": f"qrosetta/{__version__}", "Accept": "application/json, */*"}
        hdrs.update(headers or {})
        if self.token:
            hdrs["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=body, method=method.upper(), headers=hdrs)
        try:
            with self._opener.open(req, timeout=timeout or self.timeout) as resp:
                return Response(resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read())
        except urllib.error.HTTPError as exc:
            return Response(exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read() or b"")
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise CliError(f"No answer from {self.url}: {reason}.", Exit.UNREACHABLE, "unreachable",
                           hint="qrosetta status") from None
