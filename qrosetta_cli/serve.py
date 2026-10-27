"""`qrosetta start`: bring the stack up, follow its logs, and on Ctrl-C, SIGTERM or SIGHUP put
it on standby or remove it."""

import os
import select
import signal
import subprocess
import sys
import time

from qrosetta_cli import actions
from qrosetta_cli import stack as st
from qrosetta_cli.actions import say
from qrosetta_cli.engine import CliError

EXIT_ACTIONS = ("standby", "remove", "ask")
ASK_TIMEOUT_SEC = 10
HANDLED_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
STANDBY_HINT = "On standby: containers, images and data are kept. `qrosetta start` restarts it; `qrosetta remove` removes it."


class Interrupted(Exception):
    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


class Abandoned(Exception):
    """Ctrl-C pressed twice more while the exit action was running."""


def exit_action(flag, env=None, tty=None):
    """--on-exit, else QROSETTA_ON_EXIT, else ask on a terminal and standby otherwise."""
    env = os.environ if env is None else env
    tty = sys.stdin.isatty() if tty is None else tty
    value = (flag or env.get("QROSETTA_ON_EXIT") or "").strip().lower()
    if value and value not in EXIT_ACTIONS:
        raise CliError(f"The exit action must be one of {', '.join(EXIT_ACTIONS)}, not {value!r}.")
    value = value or ("ask" if tty else "standby")
    return "standby" if value == "ask" and not tty else value


LOOPBACK = ("127.0.0.1", "::1", "localhost")


def published(engine, stack):
    """(URL, host:port as published) of the stack's published port, from `compose port`;
    (None, None) when nothing is published."""
    for svc in stack.services.values():
        for port in svc.ports:
            target = port.get("target") if isinstance(port, dict) else None
            if not target:
                continue
            out = engine.compose("port", svc.name, str(target))
            address = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
            host, _, number = address.rpartition(":")
            if out.returncode != 0 or not number.isdigit():
                continue
            host = host.strip("[]")
            if host in ("", "0.0.0.0", "::") + LOOPBACK:
                host = "localhost"
            elif ":" in host:
                host = f"[{host}]"
            return f"http://{host}" + ("" if number == "80" else f":{number}"), address
    return None, None


def stack_url(engine, stack):
    return published(engine, stack)[0]


def announce_running(engine, stack):
    """Print the URL and the address the web server is published on."""
    url, address = published(engine, stack)
    if not url:
        say("Quantum Rosetta is running.")
        return
    say(f"Quantum Rosetta is running at {url}")
    host = address.rpartition(":")[0].strip("[]")
    reach = "this machine only" if host in LOOPBACK else "reachable from other machines"
    say(f"Published on {address} ({reach}); QROSETTA_HTTP_BIND in .env or the environment changes it.")


def plan_start(engine, stack, requested=None, env=None):
    """The services to start, those skipped for lack of an image, and the environment for compose."""
    env = os.environ if env is None else env
    wanted = [stack.resolve_service(s) for s in requested] if requested else list(stack.services)
    core = stack.core_services()
    candidates = wanted + [c for c in core if c not in wanted]
    images = st.find_images(engine, [stack.image_for(s) for s in candidates])
    missing = [s for s in candidates if stack.image_for(s) not in images]
    blocking = [s for s in missing if s in core or requested]
    if blocking:
        raise CliError(f"No image for {', '.join(blocking)}. Build with `qrosetta build "
                       f"{' '.join(blocking)}` (or `qrosetta build` for every service).")
    extra = {}
    if not env.get("QROSETTA_GIT_SHA"):
        for svc in core:
            sha = images[stack.image_for(svc)].env.get("QROSETTA_IMAGE_GIT_SHA")
            if sha and sha != "unknown":
                extra["QROSETTA_GIT_SHA"] = sha
                break
    return [s for s in candidates if s not in missing], missing, extra


def check_conflicts(engine, stack, conflicts):
    if conflicts:
        raise CliError(st.conflict_help(engine, stack, conflicts))


def prompt(question, timeout=ASK_TIMEOUT_SEC, stdin=None):
    """One line from the terminal, or None after `timeout` seconds without an answer."""
    stdin = stdin or sys.stdin
    try:
        sys.stdout.write(question)
        sys.stdout.flush()
    except OSError:
        return None
    ready, _, _ = select.select([stdin], [], [], timeout)
    if not ready:
        say(f"\nNo answer in {timeout} s.")
        return None
    return stdin.readline()


def _signal_group(child, signum):
    """Signal the child's whole process group: `podman compose` runs docker-compose as its own child."""
    try:
        os.killpg(child.pid, signum)
    except (ProcessLookupError, PermissionError, AttributeError, TypeError):
        try:
            child.send_signal(signum)
        except (ProcessLookupError, AttributeError):
            pass


class Server:
    """Foreground run of the stack. Signal handling by phase: while running, the first signal
    starts the exit action; while it runs, Ctrl-C once warns and twice more stops waiting."""

    def __init__(self, engine, stack, action, services, compose_env, tty=None, ask=prompt):
        self.engine, self.stack, self.action = engine, stack, action
        self.services, self.ask = services, ask
        self.tty = sys.stdin.isatty() if tty is None else tty
        self.engine.env.update(compose_env)
        self.phase = "running"
        self.extra_sigints = 0
        self.child = None

    def _handle(self, signum, frame):
        if self.phase in ("running", "prompt"):
            self.phase = "closing"
            raise Interrupted(signum)
        if self.phase != "shutdown" or signum != signal.SIGINT:
            return
        self.extra_sigints += 1
        if self.extra_sigints == 1:
            say("\nStill shutting down. Press Ctrl-C again to stop waiting and leave the rest running.")
        else:
            raise Abandoned()

    def run(self):
        previous = {s: signal.signal(s, self._handle) for s in HANDLED_SIGNALS}
        try:
            status = 0
            try:
                self._up()
                return self._follow()
            except Interrupted as exc:
                self.phase = "closing"
                self._end_child()
                action = self._choose(exc.signum)
            except CliError as exc:
                say(f"qrosetta: {exc}")
                self.phase = "closing"
                self._end_child()
                action, status = ("remove" if self.action == "remove" else "standby"), 1
            self.phase = "shutdown"
            try:
                return self._exit(action) or status
            except Abandoned:
                left = [c for c in st.find_containers(self.engine, self.stack) if c.running]
                say(f"Stopped waiting. Still running: {', '.join(c.name for c in left) or 'nothing'}.")
                if left:
                    say("`qrosetta stop` stops them; `qrosetta remove` removes them.")
                return 130
        finally:
            for s, handler in previous.items():
                signal.signal(s, handler)

    def _up(self):
        say(f"Starting {len(self.services)} services...")
        self.child = self.engine.spawn(["up", "-d", "--no-build", *self.services])
        if self.child.wait() != 0:
            raise CliError("`compose up` failed.")
        self.child = None
        say("")
        announce_running(self.engine, self.stack)
        say("Press Ctrl-C to stop it.\n")

    def _follow(self):
        tail = "20"
        while True:
            self.child = self.engine.spawn(["logs", "-f", "--tail", tail])
            self.child.wait()
            self.child = None
            if not any(c.running for c in st.find_containers(self.engine, self.stack)):
                say("Every Quantum Rosetta container has stopped.")
                return 0
            tail = "0"
            time.sleep(2)

    def _end_child(self):
        child, self.child = self.child, None
        if child is None or child.poll() is not None:
            return
        _signal_group(child, signal.SIGTERM)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _signal_group(child, signal.SIGKILL)
            child.wait()

    def _choose(self, signum):
        if self.action != "ask":
            return self.action
        if signum != signal.SIGINT or not self.tty:
            say(f"\n{signal.Signals(signum).name} received: putting the stack on standby.")
            return "standby"
        self.phase = "prompt"
        try:
            answer = self.ask("\nKeep on standby or remove? [S/r] ")
        except (Interrupted, EOFError):
            answer = None
        self.phase = "closing"
        return "remove" if (answer or "").strip().lower() in ("r", "remove") else "standby"

    def _exit(self, action):
        if action == "remove":
            return actions.remove_stack(self.engine, self.stack)
        left = actions.stop_stack(self.engine, self.stack)
        if not left:
            say(STANDBY_HINT)
        return actions.report_left(left, self.stack)
