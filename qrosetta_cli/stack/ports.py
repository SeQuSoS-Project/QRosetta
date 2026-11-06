"""The address `start` publishes the web server on. A chosen address (--bind, QROSETTA_HTTP_BIND
in the environment or the checkout's .env, config lifecycle.bind) is used as given. Otherwise
`start` uses the address it recorded for the project, else 127.0.0.1:8080; when another program
holds that one, it takes the first free port of 127.0.0.1:8080-8089 and records it. Nothing
holding a port is ever stopped."""

import os
from dataclasses import dataclass

from qrosetta_cli import localstack, mode as modes
from qrosetta_cli.errors import CliError

FALLBACK_HOST = "127.0.0.1"
FALLBACK_PORTS = tuple(range(8080, 8090))
DOTENV_SOURCE = f".env {localstack.BIND_VAR}"


@dataclass
class Bind:
    address: str
    source: str

    @property
    def chosen(self):
        """Whether the user chose the address (start then never moves it)."""
        return self.source not in ("default", "stack setting", "fallback")

    @property
    def compose_value(self):
        """The value `start` gives compose as QROSETTA_HTTP_BIND, or None where compose finds the
        address itself (its default, or the caller's .env)."""
        return None if self.source in ("default", DOTENV_SOURCE) else self.address


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
        if sep and key.strip() == localstack.BIND_VAR:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            found = value or None
    return found


def _project_dir(ctx):
    try:
        mode = modes.detect(ctx.opt("project_dir"), ctx.env, ctx.checkout)
    except CliError:
        return None
    return mode.project_dir if mode.name == "checkout" else None


def resolve(ctx, with_flag=True):
    """The address in effect before any search: --bind (`with_flag`), the environment, config,
    the checkout's .env, the recorded address, else the default."""
    if with_flag and ctx.opt("bind"):
        return Bind(ctx.opt("bind"), "--bind")
    value, source = localstack.chosen_bind(ctx.env, ctx.cfg)
    if value:
        return Bind(value, source)
    project_dir = _project_dir(ctx)
    value = dotenv_bind(project_dir) if project_dir else None
    if value:
        return Bind(value, DOTENV_SOURCE)
    value, source = localstack.local_bind(ctx.env, ctx.cfg)
    return Bind(value, source)


def search(host, ours, skip=None, candidates=FALLBACK_PORTS):
    """The first of 127.0.0.1:8080-8089 (`candidates`) other than `skip` that is free or this
    stack's own (`ours(address)`), or None when another program holds all of them."""
    for port in candidates:
        address = f"{FALLBACK_HOST}:{port}"
        if address != skip and (host.port_free(FALLBACK_HOST, port) or ours(address)):
            return address
    return None


def port_of(address):
    return address.rpartition(":")[2]


def moved_line(old, new, holder="program"):
    """`holder`: "quantum_rosetta" when a Quantum Rosetta of another project or user answers there."""
    if holder == "quantum_rosetta":
        return f"Port {port_of(old)} is used by another Quantum Rosetta (not this project); using {port_of(new)}."
    return f"Port {port_of(old)} is in use by another program; using {port_of(new)}."


def range_text():
    return f"{FALLBACK_HOST}:{FALLBACK_PORTS[0]} to {FALLBACK_HOST}:{FALLBACK_PORTS[-1]}"
