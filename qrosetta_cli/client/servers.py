"""Which server a command talks to (spec Q5), the bearer token for it (spec Q14), and the
envelope's `server` block."""

import json
import os
import stat
import urllib.parse
from dataclasses import dataclass

from qrosetta_cli import config as cfgmod, localstack, output
from qrosetta_cli.client.transport import HttpTransport, is_loopback, origin
from qrosetta_cli.errors import CliError, Exit, usage

LOCAL = "local"
DEFAULT_BIND = localstack.DEFAULT_BIND


def bind_url(bind):
    """The URL a browser on this machine uses for a published address."""
    host, _, port = (bind or DEFAULT_BIND).rpartition(":")
    host = host.strip("[]")
    if host in ("", "0.0.0.0", "::", "127.0.0.1", "::1"):
        host = "localhost"
    elif ":" in host:
        host = f"[{host}]"
    return f"http://{host}" + ("" if port == "80" else f":{port}")


@dataclass
class Server:
    name: str
    url: str
    source: str
    allow_insecure_http: bool = False

    @property
    def local(self):
        return self.name == LOCAL

    def block(self, handshake=None):
        """The envelope's server object."""
        handshake = handshake or {}
        return {
            "kind": "http",
            "url": self.url,
            "platform_version": handshake.get("platform_version"),
            "api_levels": handshake.get("api_levels"),
        }


def select(flag, env, cfg):
    """--server (a URL when it contains ://, else a [servers.NAME] table), else QROSETTA_SERVER,
    else default_server, else the local stack."""
    for value, source in (
        (flag, "--server"),
        (env.get("QROSETTA_SERVER"), "env QROSETTA_SERVER"),
        (cfg.get("default_server"), "config default_server"),
    ):
        if value:
            return resolve(value, source, cfg, env)
    return resolve(LOCAL, "default", cfg, env)


def check_url(url, source):
    """A server URL must be http:// or https:// with a host."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise usage(
            f"The server URL {url!r} (from {source}) is not an http:// or https:// URL with a host.",
            hint="qrosetta config show",
            reason="server_url",
        )
    return url


def resolve(value, source, cfg, env=None):
    """A server by URL or [servers.NAME] table; the local stack without a url is found at the
    address it is published on (`localstack.local_bind`)."""
    if "://" in value:
        url = check_url(value.rstrip("/"), source)
        return Server(url, url, source)
    table = cfg.get("servers", value)
    if table is None and value != LOCAL:
        names = sorted((cfg.get("servers") or {}).keys())
        raise usage(
            f"Unknown server {value!r} (from {source}). Configured: {', '.join(names) or 'none'}.",
            hint="qrosetta config show",
            reason="unknown_server",
        )
    table = table or {}
    url = table.get("url") or bind_url(localstack.local_bind(os.environ if env is None else env, cfg)[0])
    url = check_url(url.rstrip("/"), f"[servers.{value}] url")
    return Server(value, url, source, bool(table.get("allow_insecure_http")))


def credentials_path(cfg, env):
    custom = cfg.get("auth", "credentials")
    return cfgmod.expand(custom, env) if custom else os.path.join(cfgmod.qr_dir("state", env), "credentials.json")


def check_private(path):
    """Refuse a credentials file that group or other can read."""
    try:
        mode = os.stat(path).st_mode
    except OSError:
        return False
    if os.name == "posix" and mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise CliError(
            f"{path} is readable by other users; qrosetta does not use it.",
            Exit.AUTH,
            "credentials_permissions",
            hint=f"chmod 600 {path}",
        )
    return True


def token_for(server, cfg, env):
    """QROSETTA_TOKEN, else the token stored for this server's origin; never written here."""
    if env.get("QROSETTA_TOKEN"):
        return env["QROSETTA_TOKEN"]
    path = credentials_path(cfg, env)
    if not check_private(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            stored = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    entry = stored.get(origin(server.url)) if isinstance(stored, dict) else None
    return entry.get("token") if isinstance(entry, dict) else None


def plain_http_ok(server, token):
    """Loopback is silent; other http:// hosts warn once, and a token goes there only with
    allow_insecure_http on that server."""
    if not server.url.startswith("http://") or is_loopback(server.url):
        return True
    output.warn(f"{server.url} is plain HTTP; requests and answers are not encrypted.", "insecure_http")
    if token and not server.allow_insecure_http:
        raise CliError(
            f"Not sending a token to {server.url} over plain HTTP.",
            Exit.AUTH,
            "insecure_http",
            hint=f"set allow_insecure_http = true in [servers.{server.name}] of the config file, or use https",
        )
    return True


def transport(server, token=None, timeout=None):
    plain_http_ok(server, token)
    kwargs = {"timeout": timeout} if timeout else {}
    return HttpTransport(server.url, token=token, **kwargs)
