"""What both halves read about the local stack: the lifecycle token `qrosetta start` writes, and
the stack settings it records in the state directory (the CPU quota setting, spec §6.1, and the
address `start` published the web server on when port 8080 was taken)."""

import json
import os
import tempfile

from qrosetta_cli import config as cfgmod

TOKEN_FILE = "lifecycle.token"
SETTINGS_FILE = "stack-settings.json"
DEFAULT_PROJECT = "qsimulators"
DEFAULT_BIND = "127.0.0.1:8080"
BIND_VAR = "QROSETTA_HTTP_BIND"


def token_path(env):
    return os.path.join(cfgmod.qr_dir("runtime", env), TOKEN_FILE)


def read_token(env):
    """The lifecycle token, or None when the file is missing, unreadable or empty."""
    try:
        with open(token_path(env), encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def token_headers(env):
    token = read_token(env)
    return {"Authorization": f"Bearer {token}"} if token else {}


def project(env):
    """The compose project `qrosetta start` uses: QROSETTA_PROJECT, else qsimulators."""
    return (env.get("QROSETTA_PROJECT") or "").strip() or DEFAULT_PROJECT


def settings_path(env):
    return os.path.join(cfgmod.qr_dir("state", env), SETTINGS_FILE)


def _read_all(env):
    try:
        with open(settings_path(env), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def stack_settings(env, name=None):
    """The recorded settings of compose project `name` (default: this environment's), or {}."""
    entry = (_read_all(env).get("projects") or {}).get(name or project(env))
    return entry if isinstance(entry, dict) else {}


def write_stack_settings(env, name, values):
    """Replace project `name`'s recorded settings with `values` (none left: the project's entry
    goes), through a temporary file."""
    data = _read_all(env)
    projects = data.get("projects") if isinstance(data.get("projects"), dict) else {}
    if values:
        projects[name] = values
    else:
        projects.pop(name, None)
    data = {"schema": "qrosetta.cli/stack-settings@1", "projects": projects}
    directory = os.path.dirname(settings_path(env))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".stack-settings.", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, settings_path(env))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def cpu_quota(env, cfg, name=None):
    """(enabled, since, source) of the CPU quota: the setting `start` recorded for the project,
    else config lifecycle.cpu_quota, else on."""
    entry = stack_settings(env, name)
    if isinstance(entry.get("cpu_quota"), bool):
        return entry["cpu_quota"], entry.get("since"), "stack setting"
    value = cfg.get("lifecycle", "cpu_quota")
    if isinstance(value, bool):
        return value, None, "config lifecycle.cpu_quota"
    return True, None, "default"


DOTENV_SOURCE = f".env {BIND_VAR}"


def chosen_bind(env, cfg):
    """(address, source) the user chose without a flag: QROSETTA_HTTP_BIND in the environment,
    else config lifecycle.bind; (None, None) when neither is set."""
    value = (env.get(BIND_VAR) or "").strip()
    if value:
        return value, f"env {BIND_VAR}"
    value = cfg.get("lifecycle", "bind")
    if value:
        return value, "config lifecycle.bind"
    return None, None


def _dotenv_value(raw):
    """A .env value as compose reads it: a quoted value up to its closing quote (a double-quoted
    one with backslash escapes), an unquoted one up to a ` #` comment, trimmed."""
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        quote, out, i = raw[0], [], 1
        while i < len(raw):
            ch = raw[i]
            if quote == '"' and ch == "\\" and i + 1 < len(raw):
                out.append({"n": "\n", "t": "\t"}.get(raw[i + 1], raw[i + 1]))
                i += 2
                continue
            if ch == quote:
                return "".join(out)
            out.append(ch)
            i += 1
        return raw
    for i, ch in enumerate(raw):
        if ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            return raw[:i].strip()
    return raw


def dotenv_bind(project_dir):
    """QROSETTA_HTTP_BIND as the checkout's .env sets it for compose, or None."""
    try:
        with open(os.path.join(project_dir, ".env"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    found = None
    for line in lines:
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if sep and key.strip() == BIND_VAR:
            found = _dotenv_value(value) or None
    return found


def local_bind(env, cfg, name=None, project_dir=None):
    """(address, source) of the local web server: a chosen address (the environment, config, or
    the .env of the checkout in `project_dir` unless it holds the default), else the one `start`
    recorded for the project (port 8080 was taken), else 127.0.0.1:8080."""
    value, source = chosen_bind(env, cfg)
    if value:
        return value, source
    value = dotenv_bind(project_dir) if project_dir else None
    if value and value != DEFAULT_BIND:
        return value, DOTENV_SOURCE
    recorded = stack_settings(env, name).get("bind")
    if isinstance(recorded, str) and recorded:
        return recorded, "stack setting"
    return DEFAULT_BIND, "default"


def record_bind(env, name, bind):
    """Record the address `start` publishes project `name` on; None or the default forgets it."""
    old = stack_settings(env, name)
    values = {k: v for k, v in old.items() if k != "bind"}
    if bind and bind != DEFAULT_BIND:
        values["bind"] = bind
    if values != old:
        write_stack_settings(env, name, values)


def forget_bind(env, name):
    """Drop the recorded address of project `name` (its containers are gone)."""
    record_bind(env, name, None)
