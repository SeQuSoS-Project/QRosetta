"""The address `start` publishes the web server on. A chosen address (--bind, QROSETTA_HTTP_BIND
in the environment or the checkout's .env, config lifecycle.bind) is used as given; a .env value
equal to the default chooses nothing. Otherwise
`start` uses the address it recorded for the project, else 127.0.0.1:8080; when another program
holds that one, it takes the first free port of 127.0.0.1:8080-8089 and records it. Nothing
holding a port is ever stopped."""

from dataclasses import dataclass

from qrosetta_cli import localstack

FALLBACK_HOST = "127.0.0.1"
FALLBACK_PORTS = tuple(range(8080, 8090))
DOTENV_SOURCE = localstack.DOTENV_SOURCE


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


dotenv_bind = localstack.dotenv_bind


def resolve(ctx, with_flag=True):
    """The address in effect before any search: --bind (`with_flag`), the environment, config,
    the checkout's .env (a .env holding the default, as .env.example did, chooses nothing), the
    recorded address, else the default."""
    if with_flag and ctx.opt("bind"):
        return Bind(ctx.opt("bind"), "--bind")
    value, source = localstack.local_bind(ctx.env, ctx.cfg, project_dir=ctx.checkout_dir())
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
