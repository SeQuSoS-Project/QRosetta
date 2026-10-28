"""The config file (spec Q5), the CLI-owned environment variables and the XDG paths.

The config holds no measurement setting: an unknown key is refused, so a request field written
into the file is an error rather than a silent default."""

import os
from dataclasses import dataclass, field
from typing import Any

from qrosetta_cli.errors import CliError, Exit, usage

EXIT_ACTIONS = ("standby", "remove", "ask")
RESERVED_PROFILES = ("minimal", "cpu", "gpu", "compilers", "full", "core", "all", "none", "default")

CLI_ENV = (
    "QROSETTA_SERVER",
    "QROSETTA_TOKEN",
    "QROSETTA_CONFIG",
    "QROSETTA_PROJECT_DIR",
    "QROSETTA_HOME",
    "QROSETTA_PROJECT",
    "QROSETTA_ENGINE",
    "QROSETTA_ON_EXIT",
    "QROSETTA_RESULTS_DIR",
    "QROSETTA_SIF_DIR",
    "NO_COLOR",
    "CLICOLOR_FORCE",
    "TERM",
)
SHARED_WITH_COMPOSE = ("QROSETTA_PROJECT",)

_STR, _BOOL, _LIST = "string", "boolean", "list of strings"
SCHEMA = {
    "default_server": _STR,
    "servers": {"*": {"url": _STR, "allow_insecure_http": _BOOL}},
    "lifecycle": {"engine": ("docker", "podman"), "on_exit": EXIT_ACTIONS, "bind": _STR, "cpu_quota": _BOOL},
    "results": {"dir": _STR},
    "auth": {"credentials": _STR},
    "output": {
        "color": ("auto", "always", "never"),
        "progress": ("auto", "plain", "none"),
        "experimental_notice": _BOOL,
    },
    "profiles": {"*": {"services": _LIST, "extends": _STR}},
}

TEMPLATE = """\
# qrosetta configuration. It holds no measurement setting: shots, seeds, timeouts, backends
# and every other run setting are flags of `qrosetta run`, so a command copied from a paper
# specifies its run completely.

# default_server = "local"

# [servers.local]
# url = "http://localhost:8080"

# [servers.remote]
# url = "https://qrosetta.example.org"
# allow_insecure_http = false        # send a token to a non-loopback http:// URL

[lifecycle]
# engine = "podman"                  # docker | podman; default: the first whose `info` answers
# on_exit = "ask"                    # standby | remove | ask
# bind = "127.0.0.1:8080"
# cpu_quota = true                   # false: start every service without its CPU limit, as
#                                    # `start --no-cpu-quota`; results record it

[output]
# experimental_notice = true

# [profiles.mine]                    # experimental; start and build only, never run
# extends = "minimal"
# services = ["quimb", "qsim-cirq"]
"""


def _home(env):
    return env.get("HOME") or os.path.expanduser("~")


def xdg(kind, env=None):
    """$XDG_CONFIG_HOME, $XDG_STATE_HOME, $XDG_CACHE_HOME or $XDG_RUNTIME_DIR, with the spec's
    fallbacks; the runtime directory falls back to the state directory."""
    env = os.environ if env is None else env
    defaults = {"config": (".config",), "state": (".local", "state"), "cache": (".cache",)}
    if kind == "runtime":
        return env.get("XDG_RUNTIME_DIR") or xdg("state", env)
    return env.get(f"XDG_{kind.upper()}_HOME") or os.path.join(_home(env), *defaults[kind])


def qr_dir(kind, env=None):
    return os.path.join(xdg(kind, env), "qrosetta")


def default_path(env=None):
    return os.path.join(qr_dir("config", env), "config.toml")


def expand(path, env=None):
    env = os.environ if env is None else env
    for kind in ("state", "cache", "config"):
        path = path.replace(f"$XDG_{kind.upper()}_HOME", xdg(kind, env))
    return os.path.expanduser(path)


@dataclass
class Config:
    path: str
    explicit: bool
    data: dict = field(default_factory=dict)
    loaded: bool = False

    def get(self, *keys, default=None):
        node: Any = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node


def _check(node, schema, where, path):
    if not isinstance(node, dict):
        raise usage(f"{path}: [{where}] must be a table.", hint=f"edit {path}", reason="config_invalid")
    for key, value in node.items():
        here = f"{where}.{key}" if where else key
        rule = schema.get(key, schema.get("*"))
        if rule is None:
            raise usage(
                f"{path}: unknown key '{here}'. The config file holds no measurement setting; "
                "run settings are flags of `qrosetta run`.",
                hint=f"edit {path}",
                reason="config_unknown_key",
            )
        if isinstance(rule, dict):
            _check(value, rule, here, path)
        elif rule == _STR and not isinstance(value, str):
            raise usage(f"{path}: '{here}' must be a string.", hint=f"edit {path}", reason="config_invalid")
        elif rule == _BOOL and not isinstance(value, bool):
            raise usage(f"{path}: '{here}' must be true or false.", hint=f"edit {path}", reason="config_invalid")
        elif rule == _LIST and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            raise usage(f"{path}: '{here}' must be a list of strings.", hint=f"edit {path}", reason="config_invalid")
        elif isinstance(rule, tuple) and value not in rule:
            raise usage(
                f"{path}: '{here}' must be one of {', '.join(rule)}, not {value!r}.",
                hint=f"edit {path}",
                reason="config_invalid",
            )


def validate(data, path):
    """Refuse unknown keys, wrong types and reserved user-profile names."""
    _check(data, SCHEMA, "", path)
    for name in data.get("profiles") or {}:
        if name in RESERVED_PROFILES or name.startswith("qrosetta-"):
            raise usage(
                f"{path}: profile name '{name}' is reserved for built-in profiles.",
                hint=f"edit {path}",
                reason="config_reserved_profile",
            )
    return data


def load(flag=None, env=None):
    """The config from --config, else QROSETTA_CONFIG, else the XDG default (absent is fine)."""
    env = os.environ if env is None else env
    chosen = flag or env.get("QROSETTA_CONFIG")
    path = os.path.abspath(os.path.expanduser(chosen)) if chosen else default_path(env)
    cfg = Config(path=path, explicit=bool(chosen))
    if not os.path.isfile(path):
        if chosen:
            raise CliError(
                f"Config file {path} does not exist.", Exit.NOT_FOUND, "config_missing", hint="qrosetta config init"
            )
        return cfg
    try:
        import tomllib
    except ImportError:
        raise CliError(
            f"Reading {path} needs Python 3.11 or later (tomllib).",
            Exit.USAGE,
            "python_too_old",
            hint=f"move {path} aside, or run qrosetta with Python 3.11+",
        ) from None
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise usage(f"{path}: {exc}", hint=f"edit {path}", reason="config_invalid") from None
    cfg.data = validate(data, path)
    cfg.loaded = True
    return cfg


def env_or_config(env, var, cfg, *keys):
    """(value, source) for a setting an environment variable overrides."""
    if env.get(var):
        return env[var], f"env {var}"
    value = cfg.get(*keys)
    if value is not None:
        return value, f"config {'.'.join(keys)}"
    return None, "default"
