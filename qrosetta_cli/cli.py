"""Argument parsing, the command table (stable and experimental), help, and `main`, which turns
every outcome into an exit code and, under --json, one envelope on stdout."""

import argparse
import difflib
import importlib
import os
import re
import signal
import sys
import traceback
from dataclasses import dataclass

from qrosetta_cli import config as cfgmod, output
from qrosetta_cli.config import EXIT_ACTIONS
from qrosetta_cli.context import Context, Result
from qrosetta_cli.errors import CliError, Exit

SCHEMA_PREFIX = "qrosetta.cli/"
ERROR_SCHEMA = SCHEMA_PREFIX + "error@0"


@dataclass(frozen=True)
class Spec:
    func: str
    schema: str
    help: str
    examples: tuple
    stable: bool = True
    group: str = "Lifecycle"


SPECS = {
    "start": Spec("stack.commands:cmd_start", "start@0", "start the stack, or add services to a running one",
                  ("qrosetta start -d --profile minimal", "qrosetta start", "qrosetta start -d qiskit cirq")),
    "stop": Spec("stack.commands:cmd_stop", "stop@0", "standby: stop the containers, keep everything",
                 ("qrosetta stop", "qrosetta stop --force")),
    "remove": Spec("stack.commands:cmd_remove", "remove@0", "remove containers, pods and networks; optionally images and data",
                   ("qrosetta remove", "qrosetta remove --images", "qrosetta remove --data --confirm qsimulators")),
    "status": Spec("stack.commands:cmd_status", "status@1", "services, state, memory, image provenance and URL",
                   ("qrosetta status", "qrosetta status --json")),
    "logs": Spec("stack.commands:cmd_logs", "logs@0", "container logs, passed through",
                 ("qrosetta logs api --tail 50", "qrosetta logs --no-follow")),
    "build": Spec("stack.commands:cmd_build", "build@0", "build images from this checkout (scripts/safe_boot.sh)",
                  ("qrosetta build --profile minimal", "qrosetta build qiskit")),
    "profiles": Spec("stack.commands:cmd_profiles", "profiles@0", "profiles and their services",
                     ("qrosetta profiles", "qrosetta profiles --json")),
    "doctor": Spec("stack.commands:cmd_doctor", "doctor@0", "host checks, each with its fix",
                   ("qrosetta doctor", "qrosetta doctor --json")),
    "api": Spec("client.commands:cmd_api", "api@0", "one raw request to the server, with auth, envelope and exit codes",
                ("qrosetta api GET /runners", "qrosetta api GET /config --json",
                 "qrosetta api POST /generate_circuit -f algorithm=ghz -f n_qubits=3"), group="Server"),
    "version": Spec("commands:cmd_version", "version@1", "CLI version, install mode, manifest and server version",
                    ("qrosetta version", "qrosetta version --json"), group="Help"),
    "config path": Spec("commands:cmd_config_path", "config@0", "print the config file path",
                        ("qrosetta config path",), group="Config"),
    "config show": Spec("commands:cmd_config_show", "config@0", "effective settings and where each comes from",
                        ("qrosetta config show", "qrosetta config"), group="Config"),
    "config init": Spec("commands:cmd_config_init", "config@0", "write a commented config template",
                        ("qrosetta config init",), stable=False, group="Config"),
    "config edit": Spec("commands:cmd_config_edit", "config@0", "open the config file in $VISUAL or $EDITOR",
                        ("qrosetta config edit",), stable=False, group="Config"),
    "help": Spec("", "help@0", "help for a command; `help all` lists every command",
                 ("qrosetta help start", "qrosetta help all"), group="Help"),
}
ALIASES = {"rm": "remove"}

GET_STARTED = (
    ("Get started", (("qrosetta doctor", "check this machine; every problem comes with its fix"),
                     ("qrosetta build --profile minimal", "build the images of the minimal profile"),
                     ("qrosetta start -d --profile minimal", "start the stack and wait for its runners"),
                     ("qrosetta status", "services, memory, images and the URL"))),
    ("Run and inspect", (("qrosetta api GET /runners", "any server route, with the exit codes of qrosetta"),
                         ("qrosetta logs api --tail 50", "a service's log"),
                         ("qrosetta stop", "standby: stop the containers, keep everything"),
                         ("qrosetta remove", "remove the containers; images and data stay"))),
)


class Parser(argparse.ArgumentParser):
    """No abbreviated options, Examples kept as written, and errors as exit-2 CliErrors with a
    suggestion for a mistyped command."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        super().__init__(*args, **kwargs)

    def error(self, message):
        m = re.search(r"invalid choice: '([^']*)'", message)
        if m:
            choices = [c for a in self._actions if isinstance(a, argparse._SubParsersAction) for c in a.choices]
            close = difflib.get_close_matches(m.group(1), choices, n=1)
            if close:
                message = f"unknown command {m.group(1)!r}; did you mean {close[0]}?"
        raise CliError(message, Exit.USAGE, "usage", hint=f"{self.prog} --help")


def _globals(parser, suppress):
    default = argparse.SUPPRESS if suppress else None
    group = parser.add_argument_group("global options (accepted anywhere)")
    group.add_argument("--json", action="store_true", default=argparse.SUPPRESS if suppress else False,
                       help="write one JSON envelope to stdout")
    group.add_argument("--server", default=default, metavar="URL|NAME",
                       help="server URL, or a [servers.NAME] table of the config (default: local)")
    group.add_argument("--config", default=default, metavar="FILE", help="config file (default: $QROSETTA_CONFIG, "
                       "else $XDG_CONFIG_HOME/qrosetta/config.toml)")
    group.add_argument("--project-dir", default=default, metavar="DIR",
                       help="checkout whose compose file to use (default: $QROSETTA_PROJECT_DIR, else this checkout)")


def _epilog(spec):
    lines = ["Examples:"] + [f"  {e}" for e in spec.examples]
    if not spec.stable:
        lines.append("\nExperimental: behaviour and JSON (schema @0) may change.")
    return "\n".join(lines)


def _help(spec):
    return spec.help + ("" if spec.stable else " (experimental)")


def _add(sub, name, aliases=()):
    spec = SPECS[name]
    leaf = name.split()[-1]
    p = sub.add_parser(leaf, aliases=list(aliases), help=_help(spec), description=_help(spec),
                       epilog=_epilog(spec))
    _globals(p, suppress=True)
    p.set_defaults(spec_name=name)
    return p


def build_parser():
    parser = Parser(prog="qrosetta", description="Quantum Rosetta: run the local stack and talk to its server.",
                    epilog="Examples:\n  qrosetta doctor\n  qrosetta help all")
    _globals(parser, suppress=False)
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", parser_class=Parser)

    p = _add(sub, "start")
    p.add_argument("services", nargs="*", metavar="NAME", help="service keys (default: every service with an image)")
    p.add_argument("--profile", metavar="P", help="start this profile's services (core always added)")
    p.add_argument("--detach", "-d", action="store_true",
                   help="return when every started runner and compiler is ready (up to 180 s)")
    p.add_argument("--on-exit", choices=EXIT_ACTIONS, help="what Ctrl-C, SIGTERM or SIGHUP does (default: "
                   "$QROSETTA_ON_EXIT, config lifecycle.on_exit, else ask on a terminal, standby otherwise)")
    p.add_argument("--bind", metavar="ADDR:PORT", help="publish the web server here (default: config "
                   "lifecycle.bind, else 127.0.0.1:8080); non-loopback addresses get no TLS")
    p.add_argument("--yes", "-y", action="store_true", help="start services even while runs are in flight")
    p.add_argument("--allow-emulation", action="store_true",
                   help="start on a host that is not Linux x86_64 (timings carry no promise)")

    p = _add(sub, "stop")
    p.add_argument("--force", action="store_true", help="stop even while runs are in flight (they end)")

    p = _add(sub, "remove", aliases=("rm",))
    p.add_argument("--images", action="store_true", help="also remove the stack's images")
    p.add_argument("--data", action="store_true", help="also delete the database and saved run reports")
    p.add_argument("--confirm", metavar="NAME", help="the compose project's name, which --data requires "
                   "(on a terminal it may be typed at the prompt instead)")
    p.add_argument("--force", action="store_true", help="remove even while runs are in flight (they end)")

    _add(sub, "status")

    p = _add(sub, "logs")
    p.add_argument("service", nargs="?", metavar="NAME", help="service key (default: every service)")
    p.add_argument("--tail", default="100", help="lines of history to show first (default 100)")
    p.add_argument("--no-follow", action="store_true", help="print and exit")

    p = _add(sub, "build")
    p.add_argument("services", nargs="*", metavar="NAME", help="service keys (default: every enabled service)")
    p.add_argument("--profile", metavar="P", help="build this profile's services and core")
    p.add_argument("--yes", "-y", action="store_true", help="build even while runs are in flight")

    _add(sub, "profiles")
    _add(sub, "doctor")

    p = _add(sub, "api")
    p.add_argument("method", metavar="METHOD", help="GET, POST, PUT, PATCH, DELETE or HEAD")
    p.add_argument("path", metavar="PATH", help="route path, starting with /")
    p.add_argument("--input", metavar="FILE|-", help="request body from a file, or - for stdin")
    p.add_argument("-f", "--field", action="append", metavar="KEY=VALUE",
                   help="a query parameter (GET, DELETE, HEAD) or a JSON body field; values that parse as JSON "
                   "are sent as such; split on the last '='")
    p.add_argument("-o", "--output", metavar="PATH|-", help="write the response body here (default: stdout)")
    p.add_argument("--anonymous", action="store_true", help="send no token")

    _add(sub, "version")

    p = sub.add_parser("config", help="the config file: path, show, init, edit", description="The config file.",
                       epilog="Examples:\n  qrosetta config path\n  qrosetta config show")
    _globals(p, suppress=True)
    p.set_defaults(spec_name="config show")
    csub = p.add_subparsers(dest="config_command", metavar="SUBCOMMAND", parser_class=Parser)
    for name in ("config path", "config show", "config init", "config edit"):
        _add(csub, name)

    p = _add(sub, "help")
    p.add_argument("topic", nargs="*", metavar="COMMAND", help="a command, or `all`")
    return parser


def get_started():
    lines = []
    for title, rows in GET_STARTED:
        lines.append(f"{title}:")
        width = max(len(cmd) for cmd, _ in rows)
        lines += [f"  {cmd:<{width}}  {text}" for cmd, text in rows]
        lines.append("")
    lines.append("More: qrosetta help all")
    return "\n".join(lines)


def help_all():
    lines = []
    for group in ("Lifecycle", "Server", "Config", "Help"):
        lines.append(f"{group}:")
        for name, spec in SPECS.items():
            if spec.group == group:
                alias = " (alias rm)" if name == "remove" else ""
                lines.append(f"  {name + alias:<22} {_help(spec)}")
        lines.append("")
    lines.append("Global options: --json, --server URL|NAME, --config FILE, --project-dir DIR (anywhere on the line).")
    lines.append("Exit codes: 0 = done; 3-9 = it ran and reports an outcome; 10 and above = a problem, and the "
                 "last line names the fix.")
    return "\n".join(lines)


def _run_help(parser, topic):
    if not topic:
        output.result(get_started())
        return Result(0, None)
    if topic == ["all"]:
        output.result(help_all())
        return Result(0, {"commands": {n: {"stable": s.stable, "help": s.help} for n, s in SPECS.items()}})
    parser.parse_args([ALIASES.get(topic[0], topic[0]), *topic[1:], "--help"])
    return Result(0, None)


def _load(func):
    module, _, name = func.partition(":")
    return getattr(importlib.import_module(f"qrosetta_cli.{module}"), name)


def _print_error(exc):
    output.progress(f"qrosetta: {exc.message}")
    if exc.hint:
        output.progress(exc.hint)


def _restore_sigpipe():
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def main(argv=None, checkout=None, engine_factory=None, transport_factory=None, env=None, stdin=None, tty=None):
    """Run one command and return its exit code; `checkout` is the source tree the `qrosetta`
    script lives in."""
    if argv is None:
        _restore_sigpipe()
        argv = sys.argv[1:]
    argv = list(argv)
    env = os.environ if env is None else env
    output.configure(json_mode="--json" in argv)
    schema, data, error, ctx, code = ERROR_SCHEMA, None, None, None, Exit.OK
    try:
        parser = build_parser()
        if not argv:
            output.result(get_started())
            return 0
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code or 0)
        cfg = cfgmod.load(getattr(args, "config", None), env)
        output.configure(json_mode=bool(getattr(args, "json", False)),
                         experimental_notice=cfg.get("output", "experimental_notice", default=True))
        name = getattr(args, "spec_name", None)
        if name is None:
            output.result(get_started())
            return 0
        if getattr(args, "config_command", None):
            name = f"config {args.config_command}"
        spec = SPECS[name]
        schema = SCHEMA_PREFIX + spec.schema
        if not spec.stable:
            output.experimental(name)
        if name == "logs" and output.json_mode():
            raise CliError("logs passes the engine's output through; --json is not offered.", Exit.USAGE,
                           "usage", hint="qrosetta logs --no-follow")
        ctx = Context(args=args, env=env, cfg=cfg, checkout=checkout, engine_factory=engine_factory,
                      transport_factory=transport_factory, stdin=stdin, tty=tty)
        if name == "help":
            try:
                res = _run_help(parser, args.topic)
            except SystemExit as exc:
                return int(exc.code or 0)
        else:
            res = _load(spec.func)(ctx)
        code, data = res.code, res.data
    except CliError as exc:
        code, data, error = exc.code, exc.data, exc.as_dict()
        _print_error(exc)
    except KeyboardInterrupt:
        code = Exit.SIGINT
        error = CliError("Interrupted.", Exit.SIGINT, "interrupted", hint="qrosetta status").as_dict()
        output.progress("qrosetta: interrupted. `qrosetta status` shows what is running.")
    except BrokenPipeError:
        output.discard_output()
        return int(Exit.SIGPIPE)
    except Exception:
        from qrosetta_cli.commands import write_log
        path = write_log(env, traceback.format_exc())
        exc_type, exc_value = sys.exc_info()[:2]
        exc = CliError(f"internal error ({exc_type.__name__}: {exc_value}).", Exit.INTERNAL, "internal",
                       hint=path or "rerun with the same arguments and report the traceback")
        code, error = exc.code, exc.as_dict()
        _print_error(exc)
    if output.json_mode():
        server = ctx.server_block if ctx is not None else None
        output.emit_envelope(output.envelope(schema, code, data=data, error=error, server=server))
    try:
        sys.stdout.flush()
    except OSError:
        output.discard_output()
    return int(code)
