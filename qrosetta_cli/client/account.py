"""`qrosetta login`, `logout` and `whoami` (spec §6.22, Q14): the password comes from a terminal
prompt or --password-stdin, never an argument; the token is stored per server origin in the
credentials file (0600, directory 0700) and never printed or logged."""

import base64
import getpass
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

from qrosetta_cli import config as cfgmod, output
from qrosetta_cli.client import servers
from qrosetta_cli.client.conn import Conn, http_error
from qrosetta_cli.client.transport import is_loopback, origin
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage


def _iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(text):
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def _when(epoch, now=None):
    """'14:30 UTC, in 22 min' or 'expired 5 min ago'."""
    if epoch is None:
        return "unknown expiry"
    now = time.time() if now is None else now
    clock = datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    minutes = int(round(abs(epoch - now) / 60))
    return f"until {clock}, in {minutes} min" if epoch > now else f"expired at {clock}, {minutes} min ago"


def token_expiry(token):
    """The `exp` claim of a JWT, read without verifying it, for display only; None otherwise."""
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        exp = claims.get("exp")
        return float(exp) if isinstance(exp, (int, float)) else None
    except (IndexError, ValueError, AttributeError):
        return None


def _read_store(path):
    """The credentials file's entries; refuses a file other users can read (exit 13)."""
    if not servers.check_private(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise CliError(f"Cannot read {path}: {exc.strerror}.", Exit.AUTH, "credentials_unreadable",
                       hint=f"chmod 600 {path}") from None
    except json.JSONDecodeError:
        output.warn(f"{path} is not JSON; it is replaced.", "credentials_invalid")
        return {}
    return data if isinstance(data, dict) else {}


def _write_store(path, data, env):
    """Write the credentials file as 0600 through a temporary file in the same directory; the
    default directory is made 0700."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, mode=0o700, exist_ok=True)
    if os.name == "posix" and os.path.abspath(directory) == os.path.abspath(cfgmod.qr_dir("state", env)):
        os.chmod(directory, 0o700)
    tmp = f"{path}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _email(ctx):
    email = ctx.opt("email")
    if email:
        return email.strip()
    if not ctx.tty:
        raise usage("No terminal to ask for the email on.", hint="qrosetta login --email EMAIL --password-stdin",
                    reason="prompt_without_tty")
    line = output.prompt("Email: ", stdin=ctx.stdin)
    if not line or not line.strip():
        raise usage("No email given.", hint="qrosetta login --email EMAIL")
    return line.strip()


def _password(ctx, email):
    if ctx.opt("password_stdin"):
        data = ctx.stdin.readline()
        password = (data.decode("utf-8") if isinstance(data, bytes) else data).rstrip("\r\n")
        if not password:
            raise usage("--password-stdin read an empty line.",
                        hint=f"printf '%s\\n' \"$PASSWORD\" | qrosetta login --email {email} --password-stdin",
                        reason="empty_password")
        return password
    if not ctx.tty:
        raise usage("The password is read from a terminal prompt or from --password-stdin, never from an argument.",
                    hint=f"printf '%s\\n' \"$PASSWORD\" | qrosetta login --email {email} --password-stdin",
                    reason="prompt_without_tty")
    password = getpass.getpass("Password: ", stream=sys.stderr)
    if not password:
        raise usage("No password given.", hint="qrosetta login")
    return password


def _detail(resp):
    parsed = resp.json()
    return parsed.get("detail") if isinstance(parsed, dict) else None


def _refuse_plain_http(server):
    if server.url.startswith("http://") and not is_loopback(server.url) and not server.allow_insecure_http:
        raise CliError(f"Not sending a password to {server.url} over plain HTTP.", Exit.AUTH, "insecure_http",
                       hint=f"set allow_insecure_http = true in [servers.{server.name}] of the config file, "
                       "or use https")


def cmd_login(ctx):
    server = ctx.server()
    path = servers.credentials_path(ctx.cfg, ctx.env)
    store = _read_store(path)
    _refuse_plain_http(server)
    email = _email(ctx)
    password = _password(ctx, email)
    conn = Conn(ctx, with_token=False)
    body = urllib.parse.urlencode({"username": email, "password": password}).encode()
    password = None
    resp = conn.transport.request("POST", "/auth/token", body=body,
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    body = None
    if resp.status != 200:
        if resp.status in (401, 403):
            detail = _detail(resp)
            raise CliError(f"{server.url} refused the sign-in: {detail or f'HTTP {resp.status}'}.", Exit.AUTH,
                           "login_refused" if resp.status == 401 else "account_deactivated",
                           hint=f"qrosetta login --email {email}", http_status=resp.status, detail=resp.json())
        raise http_error("POST", "/auth/token", resp, what="Sign-in", hint=f"qrosetta login --email {email}")
    answer = resp.json() or {}
    token = answer.get("access_token")
    if not isinstance(token, str) or not token:
        raise CliError("The sign-in answer carries no token.", Exit.INCOMPATIBLE, "unexpected_response",
                       hint="qrosetta info")
    expires_in = answer.get("expires_in")
    now = time.time()
    expires_at = _iso(now + expires_in) if isinstance(expires_in, (int, float)) else None
    store = _read_store(path) or store
    store[origin(server.url)] = {"token": token, "token_type": answer.get("token_type"), "email": email,
                                 "expires_at": expires_at, "saved_at": _iso(now)}
    _write_store(path, store, ctx.env)
    output.result(f"Signed in to {server.url} as {email}; the token is valid "
                  f"{_when(_parse_iso(expires_at), now) if expires_at else 'until the server says otherwise'}.")
    output.progress(f"Token stored in {path} (readable by you only).")
    if ctx.env.get("QROSETTA_TOKEN"):
        output.warn("QROSETTA_TOKEN is set and takes precedence over the stored token.", "env_token")
    return Result(0, {"server": server.url, "email": email, "expires_at": expires_at, "expires_in": expires_in,
                      "credentials": path})


def cmd_logout(ctx):
    server = ctx.server()
    path = servers.credentials_path(ctx.cfg, ctx.env)
    store = _read_store(path)
    entry = store.pop(origin(server.url), None)
    if entry is None:
        output.result(f"No token stored for {server.url}.")
    else:
        _write_store(path, store, ctx.env)
        expiry = _parse_iso(entry.get("expires_at")) if isinstance(entry, dict) else None
        output.result(f"Signed out of {server.url}: the stored token is deleted.")
        output.progress("The server cannot revoke a token; a copy of it stays valid "
                        f"{_when(expiry) if expiry else 'until it expires'}.")
    if ctx.env.get("QROSETTA_TOKEN"):
        output.warn("QROSETTA_TOKEN is still set; commands keep sending it until it is unset.", "env_token")
    return Result(0, {"server": server.url, "removed": entry is not None, "credentials": path})


def cmd_whoami(ctx):
    server = ctx.server()
    token = servers.token_for(server, ctx.cfg, ctx.env)
    if not token:
        raise CliError(f"Not signed in to {server.url}.", Exit.AUTH, "not_signed_in",
                       hint="qrosetta login" + (f" --server {ctx.opt('server')}" if ctx.opt("server") else ""))
    source = "QROSETTA_TOKEN" if ctx.env.get("QROSETTA_TOKEN") else "credentials file"
    expiry = token_expiry(token)
    if source == "credentials file":
        entry = _read_store(servers.credentials_path(ctx.cfg, ctx.env)).get(origin(server.url)) or {}
        expiry = _parse_iso(entry.get("expires_at")) or expiry
    conn = Conn(ctx, with_token=True)
    resp = conn.transport.request("GET", "/auth/me")
    if resp.status in (401, 403):
        detail = _detail(resp)
        raise CliError(f"{server.url} does not accept the token from the {source}: "
                       f"{detail or f'HTTP {resp.status}'}.", Exit.AUTH,
                       "token_expired" if resp.status == 401 else "forbidden", hint="qrosetta login",
                       http_status=resp.status, detail=resp.json())
    if resp.status != 200:
        raise http_error("GET", "/auth/me", resp, what="GET /auth/me")
    user = resp.json() or {}
    state = "active" if user.get("is_active") else "deactivated"
    output.result(f"Signed in to {server.url} as {user.get('email', '?')} (account {user.get('id', '?')}, {state}).")
    output.result(f"Token from the {source}, valid {_when(expiry)}.")
    return Result(0, {"server": server.url, "user": user, "token_source": source,
                      "expires_at": _iso(expiry) if expiry else None})
