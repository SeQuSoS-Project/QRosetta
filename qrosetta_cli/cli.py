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
    notes: str = ""


RUN_NOTES = """
Exit codes: 0 when the jobs finished and nothing in --fail-on matched (the default is none: a
difference is a result); 3, 8 and 4 when --fail-on matched an outcome whose role is a difference,
not established, or runs without output; 5 for a failed job; 7 at --wait-timeout.

In CI: pin -b and --seed, and fail on differs and runs_without_output. differs_by_only is left out:
with one backend grossly wrong, Benjamini-Yekutieli alone flags a correct pair in 6.0-6.7% of runs
(DESIGN_DECISIONS.md, false-flag figures).
A CI job's SIGTERM stops the waiting and leaves the job running on the server (and an exclusive run
holding the server), so set --wait-timeout below the CI job's time limit.

Ctrl-C stops waiting; the job keeps running, and `qrosetta wait job:ID` saves it later."""

WAIT_NOTES = """
While the server gives no answer, or a proxy answers 502, 503 or 504 for it (the API is stopped or
restarting), wait asks again after 3, 6, 12, 24, then every 30 s, for up to 5 minutes, both before
following the first job and between polls; after that it exits 11, and the jobs may still be running.
That time counts toward --wait-timeout. A job the server answers 404 for is lost (exit 14)."""

SPECS = {
    "start": Spec(
        "stack.commands:cmd_start",
        "start@0",
        "start the stack, or add services to a running one",
        (
            "qrosetta start -d --profile minimal",
            "qrosetta start",
            "qrosetta start -d qiskit cirq",
            "qrosetta start -d --no-cpu-quota",
        ),
    ),
    "stop": Spec(
        "stack.commands:cmd_stop",
        "stop@0",
        "standby: stop the containers, keep everything",
        ("qrosetta stop", "qrosetta stop --force"),
    ),
    "remove": Spec(
        "stack.commands:cmd_remove",
        "remove@0",
        "remove containers, pods and networks; optionally images and data",
        (
            "qrosetta remove",
            "qrosetta remove --images",
            "qrosetta remove --data --confirm qsimulators",
            "qrosetta remove --all --confirm qsimulators",
        ),
    ),
    "status": Spec(
        "stack.commands:cmd_status",
        "status@1",
        "services, state, memory, image provenance and URL",
        ("qrosetta status", "qrosetta status --json"),
    ),
    "logs": Spec(
        "stack.commands:cmd_logs",
        "logs@0",
        "container logs, passed through",
        ("qrosetta logs api --tail 50", "qrosetta logs --no-follow"),
    ),
    "build": Spec(
        "stack.commands:cmd_build",
        "build@0",
        "build images from this checkout (scripts/safe_boot.sh)",
        ("qrosetta build --profile minimal", "qrosetta build qiskit"),
    ),
    "pull": Spec(
        "stack.pull:cmd_pull",
        "pull@0",
        "pull the release's images by digest, checking digests, labels "
        "and, with cosign installed, signatures (installed mode)",
        (
            "qrosetta pull --profile minimal",
            "qrosetta pull qiskit cirq",
            "qrosetta pull --core",
            "qrosetta pull --all --require-signature",
        ),
    ),
    "images list": Spec(
        "stack.images:cmd_images_list",
        "images@1",
        "this stack's images: missing, pulled, loaded, built or unknown, with sizes",
        ("qrosetta images", "qrosetta images --profile minimal", "qrosetta images --json"),
    ),
    "images verify": Spec(
        "stack.images:cmd_images_verify",
        "images-verify@0",
        "check each image: labels, baked "
        "commit, build identity and, in installed mode, digest or image id against the release "
        "manifest and the cosign signature",
        ("qrosetta images verify", "qrosetta images verify qiskit", "qrosetta images verify --require-signature"),
    ),
    "images save": Spec(
        "stack.transfer:cmd_images_save",
        "images-save@0",
        "write this stack's images to a directory of archives with an index, for machines without registry access",
        ("qrosetta images save -o qrosetta-images", "qrosetta images save --profile minimal -o dir"),
        stable=False,
    ),
    "images load": Spec(
        "stack.transfer:cmd_images_load",
        "images-load@0",
        "load archives written by `images save`, "
        "checked against their index (and in installed mode the release manifest)",
        ("qrosetta images load qrosetta-images", "qrosetta images load dir qiskit"),
    ),
    "profiles": Spec(
        "stack.commands:cmd_profiles",
        "profiles@0",
        "profiles and their services",
        ("qrosetta profiles", "qrosetta profiles --json"),
    ),
    "doctor": Spec(
        "stack.commands:cmd_doctor",
        "doctor@0",
        "host checks, each with its fix",
        ("qrosetta doctor", "qrosetta doctor --json"),
    ),
    "api": Spec(
        "client.commands:cmd_api",
        "api@0",
        "one raw request to the server, with auth, envelope and exit codes",
        (
            "qrosetta api GET /runners",
            "qrosetta api GET /config --json",
            "qrosetta api POST /generate_circuit -f algorithm=ghz -f n_qubits=3",
        ),
        group="Server",
    ),
    "info": Spec(
        "client.reads:cmd_info",
        "info@1",
        "the server's version, API levels, features, mode, run gate, request defaults and limits",
        ("qrosetta info", "qrosetta info --json"),
        group="Server",
    ),
    "backends": Spec(
        "client.reads:cmd_backends",
        "backends@0",
        "the server's simulators: availability, default selection, levels, device, precision, bit order and profiles",
        ("qrosetta backends", "qrosetta backends --ids", "qrosetta backends --levels", "qrosetta backends --fresh"),
        group="Server",
    ),
    "compilers": Spec(
        "client.reads:cmd_compilers",
        "compilers@0",
        "the server's compile-only services: availability, levels, profiles and versions",
        ("qrosetta compilers", "qrosetta compilers --ids", "qrosetta compilers --levels"),
        group="Server",
    ),
    "circuits algorithms": Spec(
        "client.reads:cmd_circuits",
        "circuits@0",
        "preset algorithms the server generates (algorithm:ID:QUBITS)",
        ("qrosetta circuits algorithms", "qrosetta circuits algorithms --max-qubits 4"),
        group="Server",
    ),
    "circuits examples": Spec(
        "client.reads:cmd_circuits",
        "circuits@0",
        "bundled example circuits (example:NAME)",
        ("qrosetta circuits examples", "qrosetta circuits examples --filter rotation"),
        group="Server",
    ),
    "circuits mqt": Spec(
        "client.reads:cmd_circuits",
        "circuits@0",
        "bundled MQT Bench circuits (mqt:ALGORITHM:QUBITS)",
        ("qrosetta circuits mqt", "qrosetta circuits mqt --max-qubits 5"),
        group="Server",
    ),
    "circuits qasmbench": Spec(
        "client.reads:cmd_circuits",
        "circuits@0",
        "bundled QASMBench circuits (qasmbench:NAME)",
        ("qrosetta circuits qasmbench", "qrosetta circuits qasmbench --filter adder"),
        group="Server",
    ),
    "circuits get": Spec(
        "client.reads:cmd_circuits_get",
        "circuit@0",
        "one circuit's OpenQASM 2.0 text, to stdout or a file",
        (
            "qrosetta circuits get algorithm:ghz:3",
            "qrosetta circuits get mqt:ghz:4 -o ghz4.qasm",
            "qrosetta circuits get example:rotation_1q --json",
        ),
        group="Server",
    ),
    "login": Spec(
        "client.account:cmd_login",
        "session@0",
        "sign in and store the token for this server (password from a prompt or --password-stdin)",
        ("qrosetta login", "qrosetta login --email me@example.org --password-stdin"),
        group="Account",
    ),
    "logout": Spec(
        "client.account:cmd_logout",
        "session@0",
        "sign out on the server (the account's earlier tokens stop working) and delete the stored token",
        ("qrosetta logout", "qrosetta logout --server http://localhost:8080"),
        group="Account",
    ),
    "whoami": Spec(
        "client.account:cmd_whoami",
        "session@0",
        "the account the stored token (or QROSETTA_TOKEN) signs in as",
        ("qrosetta whoami", "qrosetta whoami --json"),
        group="Account",
    ),
    "version": Spec(
        "commands:cmd_version",
        "version@1",
        "CLI version, install mode, manifest and server version",
        ("qrosetta version", "qrosetta version --json"),
        group="Help",
    ),
    "config path": Spec(
        "commands:cmd_config_path", "config@0", "print the config file path", ("qrosetta config path",), group="Config"
    ),
    "config show": Spec(
        "commands:cmd_config_show",
        "config@0",
        "effective settings and where each comes from",
        ("qrosetta config show", "qrosetta config"),
        group="Config",
    ),
    "config init": Spec(
        "commands:cmd_config_init",
        "config@0",
        "write a commented config template",
        ("qrosetta config init",),
        stable=False,
        group="Config",
    ),
    "config edit": Spec(
        "commands:cmd_config_edit",
        "config@0",
        "open the config file in $VISUAL or $EDITOR",
        ("qrosetta config edit",),
        stable=False,
        group="Config",
    ),
    "help": Spec(
        "",
        "help@0",
        "help for a command; `help all` lists every command",
        ("qrosetta help start", "qrosetta help all"),
        group="Help",
    ),
    "run": Spec(
        "client.run:cmd_run",
        "run-result@1",
        "plan through the server, run the jobs one after another, follow them and save their results",
        (
            "qrosetta run algorithm:ghz:3",
            "qrosetta run circuit.qasm -m statevector,measured --shots 20000 -b qiskit,cirq,qulacs --crate",
            "qrosetta run --playlist suite.json --exclusive --repeats 5 --compiler bqskit=1,2",
            "qrosetta run circuit.qasm -m measured --seed 7 -b qiskit,cirq --fail-on differs,runs_without_output "
            "--wait-timeout 50m",
            "qrosetta run circuit.qasm --dry-run --json",
        ),
        group="Runs",
        notes=RUN_NOTES,
    ),
    "wait": Spec(
        "client.run:cmd_wait",
        "run-result@1",
        "follow detached jobs and save them where their run created their directories",
        ("qrosetta wait", "qrosetta wait job:1a2b3c4d", "qrosetta wait --all"),
        group="Runs",
        notes=WAIT_NOTES,
    ),
    "jobs list": Spec(
        "client.jobs:cmd_jobs",
        "jobs@1",
        "the jobs this machine submitted, with their server status",
        ("qrosetta jobs", "qrosetta jobs --offline"),
        group="Runs",
    ),
    "jobs status": Spec(
        "client.jobs:cmd_jobs_status",
        "job@1",
        "one job's status, without its report",
        ("qrosetta jobs status job:1a2b3c4d",),
        group="Runs",
    ),
    "selftest": Spec(
        "client.selftest:cmd_selftest",
        "selftest@1",
        "known-answer and environment checks of the backends, with reports and crates saved",
        ("qrosetta selftest", "qrosetta selftest --backends qiskit,cirq"),
        group="Runs",
    ),
    "show summary": Spec(
        "client.show:cmd_show_summary",
        "summary@1",
        "the server's summary of a result: outcomes, per-backend counts, caveats",
        ("qrosetta show summary", "qrosetta show summary --result job:1a2b3c4d"),
        group="Results",
    ),
    "export crate": Spec(
        "client.export:cmd_export_crate",
        "export@1",
        "write a result's RO-Crate ZIP",
        ("qrosetta export crate", "qrosetta export crate --result job:1a2b3c4d -o crate.zip"),
        group="Results",
    ),
    "export report": Spec(
        "client.export:cmd_export_report",
        "export@1",
        "write a result's full report JSON",
        ("qrosetta export report", "qrosetta export report --result job:1a2b3c4d -o -"),
        group="Results",
    ),
    "show circuits": Spec(
        "client.circuits:cmd_show_circuits",
        "circuit-texts@0",
        "the circuit texts of a result: submitted, dispatched, executed, compiled",
        ("qrosetta show circuits", "qrosetta show circuits --pane executed:qiskit", "qrosetta show circuits --task 2"),
        stable=False,
        group="Results",
    ),
    "show diff": Spec(
        "client.circuits:cmd_show_diff",
        "diff@0",
        "a unified diff of two circuit texts of a result (difflib; display only)",
        (
            "qrosetta show diff",
            "qrosetta show diff executed:qiskit",
            "qrosetta show diff dispatched:default executed:cirq --ignore comments,whitespace",
        ),
        stable=False,
        group="Results",
    ),
    "show artifacts": Spec(
        "client.figures:cmd_show_artifacts",
        "artifacts@0",
        "the figures and tables a result offers",
        ("qrosetta show artifacts", "qrosetta show artifacts --task 0"),
        stable=False,
        group="Results",
    ),
    "show views": Spec(
        "client.figures:cmd_show_views",
        "views@0",
        "the export views with their parameters, defaults and formats",
        ("qrosetta show views",),
        stable=False,
        group="Results",
    ),
    "export figure": Spec(
        "client.figures:cmd_export_figure",
        "export-file@0",
        "write one figure or table of a result",
        (
            "qrosetta export figure fidelity_heatmap",
            "qrosetta export figure counts_overview --param layout=panels -o counts.pdf",
            "qrosetta export figure agreement --format csv -o -",
        ),
        stable=False,
        group="Results",
    ),
    "export views": Spec(
        "client.figures:cmd_export_views",
        "export-file@0",
        "write the export views listing (GET /publication/views) as JSON",
        ("qrosetta export views", "qrosetta export views -o -"),
        stable=False,
        group="Results",
    ),
}
ALIASES = {"rm": "remove"}
GROUPS = {
    "jobs": "jobs list",
    "show": "show summary",
    "config": "config show",
    "circuits": "circuits algorithms",
    "images": "images list",
}
EXPERIMENTAL_RUN_FLAGS = (
    ("order", "--order"),
    ("execution_target", "--execution-target"),
    ("bypass_limits", "--bypass-limits"),
    ("keep_statevectors", "--keep-statevectors"),
    ("set", "--set"),
)

GET_STARTED = (
    (
        "Get started",
        (
            ("qrosetta doctor", "check this machine; every problem comes with its fix"),
            ("qrosetta build --profile minimal", "build the images of the minimal profile"),
            ("qrosetta start -d --profile minimal", "start the stack and wait for its runners"),
            ("qrosetta selftest", "known-answer checks of every started backend"),
            ("qrosetta show summary", "what the newest result says"),
        ),
    ),
    (
        "Run and inspect",
        (
            ("qrosetta run algorithm:ghz:3", "plan, run and save; results in ./qrosetta-results"),
            ("qrosetta wait", "follow a detached job and save it"),
            ("qrosetta export crate", "the newest result's RO-Crate"),
            ("qrosetta status", "services, memory, images and the URL"),
            ("qrosetta stop", "standby: stop the containers, keep everything"),
            ("qrosetta remove", "remove the containers; images and data stay"),
        ),
    ),
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
    group.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS if suppress else False,
        help="write one JSON envelope to stdout",
    )
    group.add_argument(
        "--server",
        default=default,
        metavar="URL|NAME",
        help="server URL, or a [servers.NAME] table of the config (default: local)",
    )
    group.add_argument(
        "--config",
        default=default,
        metavar="FILE",
        help="config file (default: $QROSETTA_CONFIG, else $XDG_CONFIG_HOME/qrosetta/config.toml)",
    )
    group.add_argument(
        "--project-dir",
        default=default,
        metavar="DIR",
        help="checkout whose compose file to use (default: $QROSETTA_PROJECT_DIR, else this checkout)",
    )


def _epilog(spec):
    lines = ["Examples:"] + [f"  {e}" for e in spec.examples]
    if spec.notes:
        lines.append(spec.notes)
    if not spec.stable:
        lines.append("\nExperimental: behaviour and JSON (schema @0) may change.")
    return "\n".join(lines)


def _help(spec):
    return spec.help + ("" if spec.stable else " (experimental)")


def _add(sub, name, aliases=()):
    spec = SPECS[name]
    leaf = name.split()[-1]
    p = sub.add_parser(leaf, aliases=list(aliases), help=_help(spec), description=_help(spec), epilog=_epilog(spec))
    _globals(p, suppress=True)
    p.set_defaults(spec_name=name)
    return p


def build_parser():
    parser = Parser(
        prog="qrosetta",
        description="Quantum Rosetta: run the local stack and talk to its server.",
        epilog="Examples:\n  qrosetta doctor\n  qrosetta help all",
    )
    _globals(parser, suppress=False)
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", parser_class=Parser)

    p = _add(sub, "start")
    p.add_argument("services", nargs="*", metavar="NAME", help="service keys (default: every service with an image)")
    p.add_argument("--profile", metavar="P", help="start this profile's services (core always added)")
    p.add_argument(
        "--detach",
        "-d",
        action="store_true",
        help="return when the API and every started runner and compiler are ready (up to 180 s)",
    )
    p.add_argument(
        "--on-exit",
        choices=EXIT_ACTIONS,
        help="what Ctrl-C, SIGTERM or SIGHUP does (default: "
        "$QROSETTA_ON_EXIT, config lifecycle.on_exit, else ask on a terminal, standby otherwise)",
    )
    p.add_argument(
        "--bind",
        metavar="ADDR:PORT",
        help="publish the web server here (default: config "
        "lifecycle.bind, else 127.0.0.1:8080); non-loopback addresses get no TLS",
    )
    p.add_argument("--yes", "-y", action="store_true", help="start services even while runs are in flight")
    p.add_argument(
        "--allow-emulation",
        action="store_true",
        help="start on a host that is not Linux x86_64 (timings carry no promise)",
    )
    quota_flags = p.add_mutually_exclusive_group()
    quota_flags.add_argument(
        "--no-cpu-quota",
        dest="cpu_quota",
        action="store_false",
        default=None,
        help="start every service without its compose CPU limit, for hosts that do not "
        "delegate the cgroup cpu controller; memory limits stay, results record it, and "
        "the choice is kept for later starts",
    )
    quota_flags.add_argument(
        "--cpu-quota",
        dest="cpu_quota",
        action="store_true",
        default=None,
        help="start with the compose CPU limits again (the default)",
    )

    p = _add(sub, "stop")
    p.add_argument("--force", action="store_true", help="stop even while runs are in flight (they end)")

    p = _add(sub, "remove", aliases=("rm",))
    p.add_argument("--images", action="store_true", help="also remove the stack's images")
    p.add_argument("--data", action="store_true", help="also delete the database and saved run reports")
    p.add_argument(
        "--all",
        action="store_true",
        help="containers, networks, the stack's images and its data "
        "volume in one command; lists them first and needs --confirm",
    )
    p.add_argument(
        "--confirm",
        metavar="NAME",
        help="the compose project's name, which --data and --all require "
        "(on a terminal it may be typed at the prompt instead)",
    )
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

    _add_images(sub)
    _add(sub, "profiles")
    _add(sub, "doctor")

    p = _add(sub, "api")
    p.add_argument("method", metavar="METHOD", help="GET, POST, PUT, PATCH, DELETE or HEAD")
    p.add_argument("path", metavar="PATH", help="route path, starting with /")
    p.add_argument("--input", metavar="FILE|-", help="request body from a file, or - for stdin")
    p.add_argument(
        "-f",
        "--field",
        action="append",
        metavar="KEY=VALUE",
        help="a query parameter (GET, DELETE, HEAD) or a JSON body field; values that parse as JSON "
        "are sent as such; split on the last '='",
    )
    p.add_argument("-o", "--output", metavar="PATH|-", help="write the response body here (default: stdout)")
    p.add_argument("--anonymous", action="store_true", help="send no token")

    _add(sub, "version")

    p = sub.add_parser(
        "config",
        help="the config file: path, show, init, edit",
        description="The config file.",
        epilog="Examples:\n  qrosetta config path\n  qrosetta config show",
    )
    _globals(p, suppress=True)
    p.set_defaults(spec_name="config show")
    csub = p.add_subparsers(dest="config_command", metavar="SUBCOMMAND", parser_class=Parser)
    for name in ("config path", "config show", "config init", "config edit"):
        _add(csub, name)

    _add_runs(sub)
    _add_reads(sub)

    p = _add(sub, "help")
    p.add_argument("topic", nargs="*", metavar="COMMAND", help="a command, or `all`")
    return parser


def _add_images(sub):
    p = _add(sub, "pull")
    p.add_argument("services", nargs="*", metavar="NAME", help="service keys")
    p.add_argument("--profile", metavar="P", help="this profile's services and core")
    p.add_argument("--core", action="store_true", help="the core services (web server and API)")
    p.add_argument("--all", action="store_true", help="every service the release publishes")
    p.add_argument(
        "--require-signature",
        action="store_true",
        help="refuse an image whose cosign signature is not verified (needs cosign)",
    )
    p.add_argument("--yes", "-y", action="store_true", help="pull even while runs are in flight")

    gsub = _group(
        sub,
        "images",
        "this stack's images: list, verify, save, load",
        ("qrosetta images", "qrosetta images verify", "qrosetta images load qrosetta-images"),
    )
    sub.choices["images"].add_argument("--profile", metavar="P", help=argparse.SUPPRESS)
    p = _add(gsub, "images list", aliases=("ls",))
    p.add_argument("--profile", metavar="P", help="only this profile's services")
    p = _add(gsub, "images verify")
    p.add_argument("services", nargs="*", metavar="NAME", help="service keys (default: every service)")
    p.add_argument("--profile", metavar="P", help="this profile's services")
    p.add_argument(
        "--require-signature",
        action="store_true",
        help="fail an image whose cosign signature is not verified (release images; needs cosign)",
    )
    p = _add(gsub, "images save")
    p.add_argument("services", nargs="*", metavar="NAME", help="service keys (default: every image of the stack)")
    p.add_argument("--profile", metavar="P", help="this profile's services")
    p.add_argument("-o", "--output", required=True, metavar="DIR", help="a new or empty directory")
    p.add_argument("--yes", "-y", action="store_true", help="save even while runs are in flight")
    p = _add(gsub, "images load")
    p.add_argument("path", metavar="DIR", help="the directory `images save` wrote, or its qrosetta-images.json")
    p.add_argument("services", nargs="*", metavar="NAME", help="load only these services' images")
    p.add_argument("--yes", "-y", action="store_true", help="load even while runs are in flight")


def _save_flags(p, crate_toggle=True):
    if crate_toggle:
        p.add_argument(
            "--save",
            action="append",
            metavar="LIST",
            help="what to save: any of report, summary, "
            "circuits, crate, or minimal (request.json and job.json only); default report,summary, plus "
            "the crate on a local stack whose server offers gated saves",
        )
        p.add_argument(
            "--crate", action=argparse.BooleanOptionalAction, default=None, help="add (or leave out) the RO-Crate"
        )
    p.add_argument("--statevectors", action="store_true", help="the crate carries every statevector")
    p.add_argument("--author", metavar="NAME", help="author recorded in the crate")
    p.add_argument("--affiliation", metavar="TEXT", help="author affiliation recorded in the crate")
    p.add_argument(
        "--item",
        action="append",
        metavar="VIEW=FMT[,FMT]|@FILE",
        help="a publication view to write into the crate (repeatable)",
    )
    p.add_argument("--yes", "-y", action="store_true", help="download reports over 1 GiB without asking")


def _group(sub, name, help_text, examples, required=False):
    p = sub.add_parser(
        name, help=help_text, description=help_text, epilog="Examples:\n" + "\n".join(f"  {e}" for e in examples)
    )
    _globals(p, suppress=True)
    if name in GROUPS:
        p.set_defaults(spec_name=GROUPS[name])
    gsub = p.add_subparsers(dest=f"{name}_command", metavar="SUBCOMMAND", parser_class=Parser)
    gsub.required = required
    return gsub


def _add_runs(sub):
    p = _add(sub, "run")
    p.add_argument(
        "circuits",
        nargs="*",
        metavar="CIRCUIT",
        help="a file, - for stdin, or algorithm:ALGO:QUBITS"
        "[,seed=S], example:NAME, mqt:ALGO:QUBITS, qasmbench:NAME; two or more make a playlist",
    )
    p.add_argument("--playlist", metavar="FILE", help="a playlist file in the page's format")
    p.add_argument(
        "-m",
        "--mode",
        action="append",
        metavar="MODE",
        help="statevector, measured or compile "
        "(repeatable or a comma list; two modes make two jobs); default statevector",
    )
    p.add_argument("--compile-only", action="store_true", help="the same as --mode compile")
    p.add_argument("--shots", type=int, metavar="N", help="n_shots (default: the server's)")
    p.add_argument(
        "-b",
        "--backends",
        action="append",
        metavar="KEYS",
        help="backend keys, or all (default: the server's default selection)",
    )
    p.add_argument("--skip", action="append", metavar="KEYS", help="leave these backends out")
    p.add_argument(
        "-O",
        "--opt-level",
        action="append",
        metavar="[KEY=]N[,N]",
        help="N: optimization_level; KEY=N or KEY=0,0,3: runner_config (repeatable)",
    )
    p.add_argument("--timeout", metavar="DURATION", help="timeout_seconds, e.g. 90 or 5m")
    p.add_argument("--repeats", type=int, metavar="N", help="timing_repeats")
    p.add_argument(
        "--exclusive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="run every backend alone on the server (exclusive)",
    )
    p.add_argument(
        "--preprocessing",
        choices=("on", "off", "both"),
        help="apply_preprocessing; both runs an experiment (experimental)",
    )
    p.add_argument(
        "--compiler",
        action="append",
        metavar="KEY=L[,L]|KEY=all",
        help="a compile-only service and its levels (repeatable)",
    )
    p.add_argument("--threshold", action="append", metavar="NAME=VALUE", help="an agreement threshold (repeatable)")
    p.add_argument("--seed", type=int, metavar="N", help="the master seed of a measured run")
    p.add_argument("--name", metavar="TEXT", help="the run's name (crate, history, results directory)")
    p.add_argument("--circuit-name", metavar="TEXT", help="the circuit name in crate figures and captions")
    p.add_argument("--order", action="append", metavar="KEY=K", help="runner_phases (experimental)")
    p.add_argument("--execution-target", choices=("local", "kubernetes"), help="execution_target (experimental)")
    p.add_argument(
        "--bypass-limits", action=argparse.BooleanOptionalAction, default=None, help="bypass_limits (experimental)"
    )
    p.add_argument("--keep-statevectors", action="store_true", help="keep_statevectors of an experiment (experimental)")
    p.add_argument(
        "--set",
        action="append",
        metavar="FIELD=JSON",
        help="any other request field the server lists, planned through POST /plan (experimental)",
    )
    _save_flags(p)
    p.add_argument("-o", "--output", metavar="DIR", help="the exact results directory of this invocation")
    p.add_argument(
        "--results-dir",
        metavar="DIR",
        help="the parent results directory (default: $QROSETTA_RESULTS_DIR, [results] dir, else ./qrosetta-results)",
    )
    p.add_argument("--detach", action="store_true", help="submit one job and return; `qrosetta wait` saves it")
    p.add_argument("--dry-run", action="store_true", help="print the plan and send nothing")
    p.add_argument("--request", metavar="FILE", help="replay a saved plan.json or request.json")
    p.add_argument("--force", action="store_true", help="replay across API levels (recorded)")
    p.add_argument(
        "--fail-on",
        action="append",
        metavar="LIST",
        help="outcome names that make the exit code non-zero "
        "(default none); names from GET /config summary_outcomes, e.g. differs,runs_without_output",
    )
    p.add_argument("--wait-timeout", metavar="DURATION", help="stop waiting after this long (exit 7)")

    p = _add(sub, "wait")
    p.add_argument("jobs", nargs="*", metavar="JOB", help="job:ID or an id prefix (default: the newest unfinished job)")
    p.add_argument("--all", action="store_true", help="every unfinished job of this server")
    p.add_argument("--wait-timeout", metavar="DURATION", help="stop waiting after this long (exit 7)")
    p.add_argument("--save", action="append", metavar="LIST", help="what to save (default: what the run chose)")
    p.add_argument("--no-save", action="store_true", help="the same as --save minimal")
    p.add_argument("--fail-on", action="append", metavar="LIST", help="as for run (default: what the run chose)")
    p.add_argument("--yes", "-y", action="store_true", help="download reports over 1 GiB without asking")

    gsub = _group(
        sub,
        "jobs",
        "the jobs this machine submitted: list, status",
        ("qrosetta jobs", "qrosetta jobs status job:1a2b3c4d"),
    )
    p = _add(gsub, "jobs list", aliases=("ls",))
    p.add_argument("--offline", action="store_true", help="read only the job index; ask no server")
    p = _add(gsub, "jobs status")
    p.add_argument("job", metavar="JOB", help="job:ID or an id prefix")
    sub.choices["jobs"].add_argument("--offline", action="store_true", help="read only the job index; ask no server")

    p = _add(sub, "selftest")
    p.add_argument(
        "--backends",
        action="append",
        metavar="KEYS",
        help="test these backends (default: every started "
        "runner on a local stack, else the server's default selection)",
    )
    p.add_argument("--no-images", action="store_true", help="skip the image contract probes")
    p.add_argument("-o", "--output", metavar="DIR", help="the exact results directory of this invocation")
    p.add_argument("--results-dir", metavar="DIR", help="the parent results directory")
    p.add_argument("--yes", "-y", action="store_true", help="download reports over 1 GiB without asking")

    gsub = _group(
        sub,
        "show",
        "print a result: summary, circuits, diff, artifacts; the export views",
        ("qrosetta show summary", "qrosetta show circuits", "qrosetta show views"),
    )
    for name in ("show summary", "show circuits", "show diff", "show artifacts"):
        p = _add(gsub, name)
        if name == "show diff":
            p.add_argument(
                "panes",
                nargs="*",
                metavar="PANE",
                help="A and B: pane ids or result keys (default: "
                "B's source and B; with none, the first derived pane and its source)",
            )
            p.add_argument("--ignore", action="append", metavar="LIST", help="any of comments, header, whitespace")
        p.add_argument("--result", metavar="REF", help="latest (default), job:ID or a path")
        p.add_argument("--task", type=int, metavar="N", help="one playlist circuit (0-based)")
        p.add_argument("--job", metavar="MODE", help="one job of the result: statevector, measured or compile")
        p.add_argument("--results-dir", metavar="DIR", help="the parent results directory")
        if name == "show circuits":
            p.add_argument("--pane", metavar="ID", help="print this pane's text only")
    _add(gsub, "show views")
    sub.choices["show"].add_argument("--result", metavar="REF", help=argparse.SUPPRESS)

    gsub = _group(
        sub,
        "export",
        "write a result's files: crate, report, figure; the export views",
        ("qrosetta export crate", "qrosetta export report -o report.json"),
        required=True,
    )
    _add_exports(gsub)


def _add_experimental_exports(gsub):
    p = _add(gsub, "export figure")
    p.add_argument("artifact", metavar="ARTIFACT", help="an artifact id from `qrosetta show artifacts`")
    p.add_argument("--result", metavar="REF", help="latest (default), job:ID or a path")
    p.add_argument("--job", metavar="MODE", help="one job of the result: statevector, measured or compile")
    p.add_argument("--task", type=int, metavar="N", help="one playlist circuit (0-based)")
    p.add_argument(
        "--format",
        metavar="FMT",
        help="svg, png, pdf, csv, latex, ... (default: from -o's extension, else the artifact's first format)",
    )
    p.add_argument("--scale", type=int, choices=range(1, 5), metavar="1-4", help="raster resolution multiplier")
    p.add_argument(
        "--param",
        action="append",
        metavar="K=V|@FILE",
        help="a view parameter (repeatable); `qrosetta show views` lists them",
    )
    p.add_argument(
        "-o", "--output", metavar="PATH|-", help="where to write (default: the job's directory); - for stdout"
    )
    p.add_argument("--results-dir", metavar="DIR", help="the parent results directory")
    p = _add(gsub, "export views")
    p.add_argument(
        "-o",
        "--output",
        metavar="PATH|-",
        help="where to write (default: publication-views.json in the results directory); - for stdout",
    )
    p.add_argument("--results-dir", metavar="DIR", help="the parent results directory")


def _add_exports(gsub):
    for name in ("export crate", "export report"):
        p = _add(gsub, name)
        p.add_argument("--result", metavar="REF", help="latest (default), job:ID or a path")
        p.add_argument("--job", metavar="MODE", help="one job of the result: statevector, measured or compile")
        p.add_argument(
            "-o", "--output", metavar="PATH|-", help="where to write (default: the job's directory); - for stdout"
        )
        p.add_argument("--results-dir", metavar="DIR", help="the parent results directory")
        if name == "export crate":
            _save_flags(p, crate_toggle=False)
            p.add_argument(
                "--allow-supplied",
                action="store_true",
                help="after the job has expired, build the crate "
                "from the saved report.json (recorded as client_supplied)",
            )
        else:
            p.add_argument("--yes", "-y", action="store_true", help="download reports over 1 GiB without asking")
    _add_experimental_exports(gsub)


def _add_reads(sub):
    for name in ("backends", "compilers"):
        p = _add(sub, name)
        p.add_argument(
            "--ids",
            action="store_true",
            help="print only the keys a run without -b uses, one per line"
            if name == "backends"
            else "print only the available compiler ids, one per line",
        )
        p.add_argument("--levels", action="store_true", help="print each optimization level's description")
        p.add_argument(
            "--fresh",
            action="store_true",
            help="probe every service now instead of reading the "
            "server's 60-second cache (needs `qrosetta login`; 6 a minute)",
        )
    _add(sub, "info")

    gsub = _group(
        sub,
        "circuits",
        "the server's circuit catalogs, and one circuit's text",
        ("qrosetta circuits algorithms", "qrosetta circuits get algorithm:ghz:3"),
    )
    sub.choices["circuits"].set_defaults(catalog="algorithms")
    for catalog in ("algorithms", "examples", "mqt", "qasmbench"):
        p = _add(gsub, f"circuits {catalog}")
        p.set_defaults(catalog=catalog)
        p.add_argument(
            "--max-qubits",
            type=int,
            metavar="N",
            help="only entries a circuit of at most N qubits can come from"
            if catalog != "qasmbench"
            else argparse.SUPPRESS,
        )
        p.add_argument(
            "--filter", metavar="TEXT", help="only entries whose names or descriptions contain TEXT (case-insensitive)"
        )
    p = _add(gsub, "circuits get")
    p.add_argument(
        "ref",
        metavar="REF",
        help="algorithm:ID:QUBITS[,seed=S], example:NAME, mqt:ALGORITHM:QUBITS, qasmbench:NAME, a file, or - for stdin",
    )
    p.add_argument("-o", "--output", metavar="PATH|-", help="write the text here (default: stdout)")

    p = _add(sub, "login")
    p.add_argument("--email", metavar="EMAIL", help="the account's email (asked for on a terminal otherwise)")
    p.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the password from the first line of stdin "
        "(otherwise it is asked for on the terminal; it is never an argument)",
    )
    _add(sub, "logout")
    _add(sub, "whoami")


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
    for group in ("Lifecycle", "Runs", "Results", "Server", "Account", "Config", "Help"):
        lines.append(f"{group}:")
        for name, spec in SPECS.items():
            if spec.group == group:
                alias = {
                    "remove": " (alias rm)",
                    "jobs list": " (alias ls; bare jobs)",
                    "images list": " (alias ls; bare images)",
                }.get(name, "")
                lines.append(f"  {name + alias:<22} {_help(spec)}")
        lines.append("")
    lines.append("Global options: --json, --server URL|NAME, --config FILE, --project-dir DIR (anywhere on the line).")
    lines.append(
        "Exit codes: 0 = done; 3-9 = it ran and reports an outcome; 10 and above = a problem, and the "
        "last line names the fix."
    )
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
    schema, data, error, ctx, code, outcome = ERROR_SCHEMA, None, None, None, Exit.OK, None
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
        output.configure(
            json_mode=bool(getattr(args, "json", False)),
            experimental_notice=cfg.get("output", "experimental_notice", default=True),
        )
        name = getattr(args, "spec_name", None)
        if name is None:
            output.result(get_started())
            return 0
        spec = SPECS[name]
        schema = SCHEMA_PREFIX + spec.schema
        if not spec.stable:
            output.experimental(name)
        if name == "run":
            used = [flag for attr, flag in EXPERIMENTAL_RUN_FLAGS if getattr(args, attr, None) not in (None, False, [])]
            if getattr(args, "preprocessing", None) == "both":
                used.append("--preprocessing both")
            for flag in used:
                output.experimental(f"run {flag}")
        if name == "logs" and output.json_mode():
            raise CliError(
                "logs passes the engine's output through; --json is not offered.",
                Exit.USAGE,
                "usage",
                hint="qrosetta logs --no-follow",
            )
        ctx = Context(
            args=args,
            env=env,
            cfg=cfg,
            checkout=checkout,
            engine_factory=engine_factory,
            transport_factory=transport_factory,
            stdin=stdin,
            tty=tty,
        )
        if name == "help":
            try:
                res = _run_help(parser, args.topic)
            except SystemExit as exc:
                return int(exc.code or 0)
        else:
            res = _load(spec.func)(ctx)
        code, data, outcome = res.code, res.data, res.outcome
        if res.schema:
            schema = SCHEMA_PREFIX + res.schema
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
    except Exception as failure:
        from qrosetta_cli.commands import write_log

        path = write_log(env, traceback.format_exc())
        internal = CliError(
            f"internal error ({type(failure).__name__}: {failure}).",
            Exit.INTERNAL,
            "internal",
            hint=path or "rerun with the same arguments and report the traceback",
        )
        code, error = internal.code, internal.as_dict()
        _print_error(internal)
    if output.json_mode():
        server = ctx.server_block if ctx is not None else None
        output.emit_envelope(output.envelope(schema, code, data=data, error=error, server=server, outcome=outcome))
    try:
        sys.stdout.flush()
    except OSError:
        output.discard_output()
    return int(code)
