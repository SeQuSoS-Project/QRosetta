"""What both halves read about the local stack: the lifecycle token `qrosetta start` writes, and
the stack settings it records in the state directory (the CPU quota setting, spec §6.1)."""

import json
import os
import tempfile

from qrosetta_cli import config as cfgmod

TOKEN_FILE = "lifecycle.token"
SETTINGS_FILE = "stack-settings.json"
DEFAULT_PROJECT = "qsimulators"


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
    """Replace project `name`'s recorded settings with `values`, through a temporary file."""
    data = _read_all(env)
    projects = data.get("projects") if isinstance(data.get("projects"), dict) else {}
    projects[name] = values
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
