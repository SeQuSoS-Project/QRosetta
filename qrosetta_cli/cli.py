"""Argument parsing and the subcommands of `qrosetta`."""

import argparse
import os
import subprocess
import sys

from qrosetta_cli import actions
from qrosetta_cli import serve
from qrosetta_cli import stack as st
from qrosetta_cli.actions import say
from qrosetta_cli.engine import CliError, Engine, detect_engine
from qrosetta_cli.status import status


def build_parser():
    parser = argparse.ArgumentParser(
        prog="qrosetta", description="Start, stop and remove the local Quantum Rosetta stack.")
    parser.add_argument("--project-dir", help="directory holding the compose file "
                        "(default: $QROSETTA_HOME, else this checkout)")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("start", help="start the stack; Ctrl-C puts it on standby or removes it")
    p.add_argument("services", nargs="*", help="start only these services (default: every service with an image)")
    p.add_argument("--detach", "-d", action="store_true", help="start in the background and return")
    p.add_argument("--on-exit", choices=serve.EXIT_ACTIONS,
                   help="what Ctrl-C, SIGTERM or SIGHUP does (default: $QROSETTA_ON_EXIT, "
                   "else ask on a terminal and standby otherwise)")

    sub.add_parser("stop", help="stop every container; keep containers, images and data (standby)")

    p = sub.add_parser("remove", help="remove containers, pods and networks; keep images and data")
    p.add_argument("--images", action="store_true", help="also remove the stack's images")
    p.add_argument("--data", action="store_true",
                   help="also delete the volumes with the database and saved runs (asks to confirm)")

    sub.add_parser("status", help="services, memory per container, image and data disk use")

    p = sub.add_parser("logs", help="follow the logs of the stack or one service")
    p.add_argument("service", nargs="?", help="compose service or container name")
    p.add_argument("--tail", default="100", help="lines of history to show first (default 100)")
    p.add_argument("--no-follow", action="store_true", help="print and exit")

    p = sub.add_parser("build", help="build images with scripts/safe_boot.sh (default: every enabled service)")
    p.add_argument("services", nargs="*", help="compose service or container names")
    return parser


def cmd_start(engine, stack, args):
    containers = st.find_containers(engine, stack)
    serve.check_conflicts(containers, stack)
    services, missing, compose_env = serve.plan_start(engine, stack, args.services)
    if missing:
        say(f"Not started (no image): {', '.join(missing)}. `qrosetta build <service>` builds one.")
    if args.detach:
        engine.env.update(compose_env)
        if engine.spawn(["up", "-d", "--no-build", *services], own_session=False).wait() != 0:
            raise CliError("`compose up` failed. `qrosetta status` shows what is running.")
        url = serve.stack_url(engine, stack)
        say(f"Quantum Rosetta is running at {url}" if url else "Quantum Rosetta is running.")
        say("`qrosetta stop` puts it on standby; `qrosetta remove` removes it.")
        return 0
    if any(c.running for c in containers):
        say("Quantum Rosetta is already running; this terminal now controls it.")
    action = serve.exit_action(args.on_exit)
    return serve.Server(engine, stack, action, services, compose_env).run()


def cmd_stop(engine, stack, args):
    left = actions.stop_stack(engine, stack)
    if not left:
        say(serve.STANDBY_HINT)
    return actions.report_left(left, stack)


def cmd_remove(engine, stack, args):
    return actions.remove_stack(engine, stack, images=args.images, data=args.data)


def cmd_logs(engine, stack, args):
    cmd = ["logs", "--tail", str(args.tail)]
    if not args.no_follow:
        cmd.append("-f")
    if args.service:
        cmd.append(stack.resolve_service(args.service))
    try:
        return engine.spawn(cmd, own_session=False).wait()
    except KeyboardInterrupt:
        return 0


def cmd_build(engine, stack, args):
    script = os.path.join(stack.project_dir, "scripts", "safe_boot.sh")
    if not os.path.isfile(script):
        raise CliError(f"Building needs a source checkout with scripts/safe_boot.sh; {stack.project_dir} has none.")
    services = [stack.resolve_service(s) for s in args.services]
    env = dict(engine.env, QR_BUILD_ONLY="1", QR_ENGINE=engine.name, QR_BUILD_SERVICES=" ".join(services))
    try:
        return subprocess.call(["bash", script], env=env, cwd=stack.project_dir)
    except KeyboardInterrupt:
        print("qrosetta: interrupted. `qrosetta status` shows what is running.", file=sys.stderr)
        return 130


COMMANDS = {"start": cmd_start, "stop": cmd_stop, "remove": cmd_remove, "status": lambda e, s, a: status(e, s),
            "logs": cmd_logs, "build": cmd_build}


def main(argv=None, checkout=None, engine_factory=None):
    """Run one subcommand; `checkout` is the source tree the `qrosetta` script lives in."""
    args = build_parser().parse_args(argv)
    try:
        project_dir = st.find_project_dir(args.project_dir, checkout=checkout)
        engine = (engine_factory or (lambda d: Engine(detect_engine(), d)))(project_dir)
        engine.check_compose()
        stack = st.load_stack(engine)
        status = COMMANDS[args.command](engine, stack, args)
        try:
            sys.stdout.flush()
        except OSError:
            actions.discard_output()
        return status
    except CliError as exc:
        print(f"qrosetta: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("qrosetta: interrupted. `qrosetta status` shows what is running.", file=sys.stderr)
        return 130
