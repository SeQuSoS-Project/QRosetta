"""`start`'s checks before compose runs: doctor's engine, Compose v2, podman socket (podman
only), cgroup delegation (where `quota.check_host` refuses) and port checks. A failure stops
`start` with doctor's rows and numbered fixes and exit 16; nothing is started. The port check
also picks the address `start` publishes on (`ports`)."""

import sys

from qrosetta_cli import layout, output
from qrosetta_cli.client import servers
from qrosetta_cli.errors import CliError, Exit
from qrosetta_cli.stack import doctor, ports, quota

CHECKS = ("engine", "compose", "podman_socket", "cgroup", "port")


def effective_bind(ctx):
    """The address `start` publishes the web server on before any search (`ports.resolve`)."""
    return ports.resolve(ctx).address


def _ours(ctx, host, engine_name, bind, own=None):
    """Whether the busy port is this stack's: its running web server container publishes it
    (also while the API is unhealthy), or a Quantum Rosetta answers there."""
    from qrosetta_cli.client import handshake

    if (own or doctor.own_addresses(host, engine_name, ctx.env))(bind):
        return True
    server = servers.Server(servers.LOCAL, servers.bind_url(bind), "start --bind")
    try:
        handshake.fetch_config(ctx.transport(server=server, timeout=5), timeout=5)
    except CliError:
        return False
    return True


def run(ctx, host, bind, cpu_quota, movable=False, recorded=False):
    """The report of the checks `start` makes on `host`. `movable`: the user did not choose
    `bind`, so a port another program holds moves to the first free one of 8080-8089
    (`rep.port_choice`)."""
    rep = doctor.Report()
    choice = doctor.check_engine(host, rep, ctx.cfg.get("lifecycle", "engine"))
    if choice:
        doctor.check_compose(host, rep, choice)
        if choice.name == "podman":
            doctor.check_podman(host, rep, choice)
        try:
            quota.check_host(choice, cpu_quota, host.read, host.exists, host.uid())
        except CliError:
            doctor.check_controllers(host, rep, choice, cpu_quota)
    own = doctor.own_addresses(host, choice and choice.name, ctx.env)
    doctor.check_port(
        host,
        rep,
        bind,
        lambda: _ours(ctx, host, choice and choice.name, bind, own),
        ctx.cfg,
        (lambda: ports.search(host, own, skip=bind)) if movable else None,
        recorded,
    )
    rep.checks = [c for c in rep.checks if c.id in CHECKS]
    return rep


def decide(ctx, cpu_quota):
    """The address `start` publishes on (a `ports.Bind`) after its checks on the host
    (`ctx.host_factory`'s, else this machine unless an engine factory stands in for it, when
    there is no check and no search); exit 16 with the report when a check fails."""
    bind = ports.resolve(ctx)
    if ctx.host_factory is not None:
        host = ctx.host_factory(ctx.env)
    elif ctx.engine_factory is None:
        host = doctor.Host(ctx.env)
    else:
        return bind
    rep = run(ctx, host, bind.address, cpu_quota, not bind.chosen, bind.source == "stack setting")
    failed = rep.failed
    if not failed:
        if rep.port_choice and rep.port_choice != bind.address:
            output.progress(ports.moved_line(bind.address, rep.port_choice))
            return ports.Bind(rep.port_choice, "fallback")
        return bind
    first = failed[0]
    err = CliError(
        f"Not started: {len(failed)} check(s) failed: {', '.join(c.id for c in failed)}.",
        Exit.ENGINE,
        first.reason or f"{first.id}_failed",
        hint=(first.fix or "qrosetta doctor").splitlines()[0],
    )
    if not output.json_mode():
        for line in report_lines(rep, sys.stderr):
            output.progress(line)
        err.shown = True
    raise err


def report_lines(rep, stream=None):
    """What happened, the rows as evidence, and the numbered fixes; the last line is a command."""
    failed = len(rep.failed)
    lines = [f"qrosetta: not started, because {layout.plural(failed, 'check')} failed.", ""]
    lines += layout.check_rows(rep.checks, stream)
    lines += [""] + layout.numbered(layout.fixes(rep.checks, doctor.FIX_ORDER))
    if not layout.is_command(lines[-1]):
        lines += ["", "Then run the same `qrosetta start` command again."]
    return lines
