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


class _SinkError(Exception):
    def __init__(self, error):
        super().__init__(str(error))
        self.error = error


class Transport:
    """The interface every transport implements."""

    kind = "http"
    url = ""

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        raise NotImplementedError

    def download(self, method, path, sink, query=None, body=None, headers=None, timeout=None, on_headers=None):
        """Like `request`, but a 2xx body goes to `sink` and the Response carries none;
        `on_headers(headers)` runs before the body is read. This default reads the body
        whole; HttpTransport streams it."""
        resp = self.request(method, path, query=query, body=body, headers=headers, timeout=timeout)
        if 200 <= resp.status < 300:
            if on_headers:
                on_headers(resp.headers)
            sink.write(resp.body)
            return Response(resp.status, resp.headers, b"")
        return resp


class _SameOriginAuthRedirect(urllib.request.HTTPRedirectHandler):
    """Follows redirects, but the Authorization header only to the origin it was sent to."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and origin(newurl) != origin(req.full_url):
            for name in [k for k in new.headers if k.lower() == "authorization"]:
                del new.headers[name]
            new.unredirected_hdrs.pop("Authorization", None)
        return new


def _opener(loopback):
    """An opener for http and https only (no file:, ftp: or data: handlers)."""
    opener = urllib.request.OpenerDirector()
    for handler in (urllib.request.ProxyHandler({} if loopback else None), urllib.request.UnknownHandler(),
                    urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(context=ssl.create_default_context()),
                    urllib.request.HTTPDefaultErrorHandler(), _SameOriginAuthRedirect(),
                    urllib.request.HTTPErrorProcessor()):
        opener.add_handler(handler)
    return opener


class HttpTransport(Transport):
    """Requests to one server origin over http or https. Loopback URLs bypass proxies; no_proxy
    is honoured otherwise; TLS certificates are always verified (SSL_CERT_FILE selects a
    bundle); a redirect to another origin is followed without the Authorization header."""

    def __init__(self, url, token=None, timeout=DEFAULT_TIMEOUT_SEC):
        self.url = url.rstrip("/")
        parts = urllib.parse.urlsplit(self.url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise CliError(f"{self.url} is not an http:// or https:// URL with a host.", Exit.USAGE, "server_url")
        self.token = token
        self.timeout = timeout
        self._opener = _opener(is_loopback(self.url))

    def _request(self, method, path, query, body, headers):
        url = self.url + path
        if query:
            url += ("&" if "?" in path else "?") + urllib.parse.urlencode(query, doseq=True)
        hdrs = {"User-Agent": f"qrosetta/{__version__}", "Accept": "application/json, */*"}
        hdrs.update(headers or {})
        if self.token:
            hdrs["Authorization"] = f"Bearer {self.token}"
        return urllib.request.Request(url, data=body, method=method.upper(), headers=hdrs)

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        return self.download(method, path, None, query, body, headers, timeout)

    def download(self, method, path, sink, query=None, body=None, headers=None, timeout=None, on_headers=None):
        req = self._request(method, path, query, body, headers)
        try:
            with self._opener.open(req, timeout=timeout or self.timeout) as resp:
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                if sink is None:
                    return Response(resp.status, hdrs, resp.read())
                if on_headers:
                    on_headers(hdrs)
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    try:
                        sink.write(chunk)
                    except OSError as exc:
                        raise _SinkError(exc) from None
                return Response(resp.status, hdrs, b"")
        except _SinkError as exc:
            raise exc.error from None
        except urllib.error.HTTPError as exc:
            return Response(exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read() or b"")
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise CliError(f"No answer from {self.url}: {reason}.", Exit.UNREACHABLE, "unreachable",
                           hint="qrosetta status") from None
