"""`qrosetta start`: bring the stack up, wait for its runners, follow its logs, and on Ctrl-C,
SIGTERM or SIGHUP put it on standby or remove it."""

import os
import signal
import subprocess
import time

from qrosetta_cli import output
from qrosetta_cli.config import EXIT_ACTIONS
from qrosetta_cli.errors import CliError, Exit, usage
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import actions, guard, hostload
from qrosetta_cli.stack import ownership as own
from qrosetta_cli.stack import project as st
from qrosetta_cli.stack.engine import spawned_tail
from qrosetta_cli.stack.explain import engine_error, probe_message

ASK_TIMEOUT_SEC = 10
READY_TIMEOUT_SEC = 180
READY_POLL_SEC = 2
HANDLED_SIGNALS = tuple(getattr(signal, n) for n in ("SIGINT", "SIGTERM", "SIGHUP") if hasattr(signal, n))
LOOPBACK = ("127.0.0.1", "::1", "localhost")

_clock = time.monotonic
_sleep = time.sleep


class Interrupted(Exception):
    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


class Abandoned(Exception):
    """Ctrl-C pressed twice more while the exit action was running."""


def exit_action(flag, env=None, tty=False, configured=None):
    """--on-exit, else QROSETTA_ON_EXIT, else config lifecycle.on_exit, else ask on a terminal
    and standby otherwise. Without a terminal `ask` means standby."""
    env = os.environ if env is None else env
    value = (flag or env.get("QROSETTA_ON_EXIT") or configured or "").strip().lower()
    if value and value not in EXIT_ACTIONS:
        raise usage(f"The exit action must be one of {', '.join(EXIT_ACTIONS)}, not {value!r}.",
                    hint="qrosetta start --on-exit standby", reason="on_exit_invalid")
    value = value or ("ask" if tty else "standby")
    return "standby" if value == "ask" and not tty else value


def check_bind(bind):
    """host:port, with a warning when other machines could reach it (there is no TLS)."""
    host, sep, port = bind.rpartition(":")
    if not sep or not port.isdigit() or not host:
        raise usage(f"--bind takes ADDRESS:PORT, not {bind!r}.", hint="qrosetta start -d --bind 127.0.0.1:8080",
                    reason="bind_invalid")
    if host.strip("[]") not in LOOPBACK:
        output.warn(f"{bind} is reachable from other machines, over plain HTTP without TLS.", "bind_public")
    return bind


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


def announce_running(engine, stack, to_stdout=True):
    """Print the URL and the address the web server is published on."""
    url, address = published(engine, stack)
    say = result if to_stdout else progress
    if not url:
        say("Quantum Rosetta is running.")
        return None
    say(f"Quantum Rosetta is running at {url}")
    host = address.rpartition(":")[0].strip("[]")
    reach = "this machine only" if host in LOOPBACK else "reachable from other machines"
    progress(f"Published on {address} ({reach}); `qrosetta start --bind ADDRESS:PORT` changes it.")
    return url


def requested_services(stack, names, profile, cfg=None):
    """Compose services for NAME… and --profile; None means every service."""
    wanted = [stack.resolve_service(s) for s in names or []]
    if profile:
        from qrosetta_cli.stack.profiles import members
        wanted += [s for s in members(stack, profile, cfg) if s not in wanted]
    return wanted or None


def plan_start(engine, stack, requested=None, env=None):
    """The services to start, those skipped for lack of an image, and the environment for compose."""
    env = os.environ if env is None else env
    wanted = list(requested) if requested else list(stack.services)
    core = stack.core_services()
    candidates = wanted + [c for c in core if c not in wanted]
    images = st.find_images(engine, [stack.image_for(s) for s in candidates])
    missing = [s for s in candidates if stack.image_for(s) not in images]
    blocking = [s for s in missing if s in core or requested]
    if blocking:
        keys = " ".join(stack.services[s].id for s in blocking)
        raise CliError(f"No image for {', '.join(stack.services[s].id for s in blocking)}.", Exit.ENGINE,
                       "image_missing", hint=f"qrosetta build {keys}")
    extra = {}
    if not env.get("QROSETTA_GIT_SHA"):
        for svc in core:
            sha = images[stack.image_for(svc)].env.get("QROSETTA_IMAGE_GIT_SHA")
            if sha and sha != "unknown":
                extra["QROSETTA_GIT_SHA"] = sha
                break
    return [s for s in candidates if s not in missing], missing, extra


def check_startable(engine, found):
    """Refuse to start while containers, networks or volumes that are not this stack's hold its
    names; compose would otherwise recreate, replace or mount them."""
    lines = own.blockers(engine, found)
    if lines:
        first_cmd = next((line.split(": ")[-1] for line in lines if f"{engine.name} " in line), "qrosetta status")
        raise CliError("Not started. " + "\n".join(lines), Exit.ENGINE, "name_conflict",
                       hint=first_cmd if first_cmd.startswith(engine.name) else "qrosetta status")


def up(engine, services, adding, bind=None):
    """`compose up -d` for `services`; when adding to a running stack, the others are left alone."""
    deps = ["--no-deps"] if adding else []
    proc = engine.spawn(["up", "-d", "--no-build", *deps, *services], own_session=False, capture_errors=True)
    if proc.wait() != 0:
        raise engine_error(spawned_tail(proc), "`compose up` failed", bind)


def _entries(transport, path, query, headers=None):
    resp = transport.request("GET", path, query=query, headers=headers, timeout=30)
    data = resp.json()
    return resp.status, data if isinstance(data, list) else []


def wait_ready(ctx, engine, stack, services, timeout=READY_TIMEOUT_SEC):
    """Return when every started runner and compiler is available, polling every 2 s; fresh
    probes (GET /runners?fresh=true) when the server offers them, else its cached availability."""
    from qrosetta_cli.client import handshake, servers
    url = stack_url(engine, stack)
    wanted = {stack.services[s].id: stack.kind_of(s) for s in services if stack.kind_of(s) in ("runner", "compiler")}
    if not url or not wanted:
        return []
    server = servers.Server("local", url, "compose port")
    transport = ctx.transport(server=server, with_token=True)
    started = _clock()
    deadline = started + timeout
    while True:
        try:
            ctx.note_handshake(handshake.server_block(handshake.fetch_config(transport, timeout=5)))
            break
        except CliError as exc:
            if _clock() >= deadline:
                raise CliError(f"The API at {url} did not answer within {timeout} s: {exc.message}", Exit.ENGINE,
                               "api_unhealthy", hint="qrosetta logs api --tail 50") from None
            _sleep(READY_POLL_SEC)
    fresh, ready, entries = None, set(), {}
    probe_headers = None if getattr(transport, "token", None) else (hostload.auth_headers(ctx.env) or None)
    progress(f"Waiting for {len(wanted)} runners and compilers...")
    while True:
        for path in ("/runners", "/compilers"):
            if not any(k == ("runner" if path == "/runners" else "compiler") for k in wanted.values()):
                continue
            status, data = _entries(transport, path, {"fresh": "true"} if fresh is not False else None,
                                    probe_headers if fresh is not False else None)
            if fresh is None:
                if status in (401, 403):
                    fresh = False
                    output.warn("fresh probes need `qrosetta login` or the lifecycle token, and the server took "
                                "neither; readiness comes from its 60-second cache.", "fresh_probes_unauthorised")
                    status, data = _entries(transport, path, None)
                elif data and not any("fresh" in e for e in data if isinstance(e, dict)):
                    fresh = False
                    output.warn("this server has no on-demand probes (GET /runners?fresh=true); readiness comes "
                                "from its 60-second cache, so a runner can read ready up to a minute late.",
                                "fresh_probes_missing")
                elif data:
                    fresh = True
            for entry in data:
                if isinstance(entry, dict) and entry.get("id") in wanted:
                    entries[entry["id"]] = entry
                    if entry.get("available") and entry["id"] not in ready:
                        ready.add(entry["id"])
                        progress(f"  {entry['id']} ready ({_clock() - started:.0f} s)")
        if set(wanted) <= ready:
            return sorted(ready)
        if _clock() >= deadline:
            lines, hints = [], []
            for key in sorted(set(wanted) - ready):
                kind = (entries.get(key) or {}).get("error_kind")
                message, hint = probe_message(kind, key) if kind else (
                    f"{key} not ready ({(entries.get(key) or {}).get('unavailable_reason') or 'no answer'})",
                    f"qrosetta logs {key} --tail 50")
                lines.append(message)
                hints.append(hint)
            raise CliError(f"Not ready after {timeout} s: " + "; ".join(lines) + ".", Exit.ENGINE, "not_ready",
                           hint=hints[0])
        _sleep(READY_POLL_SEC)


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

    def __init__(self, engine, stack, action, services, compose_env, tty=False, ask=None, adding=False,
                 lock=None, bind=None, notice=None):
        self.engine, self.stack, self.action = engine, stack, action
        self.services, self.adding, self.bind = services, adding, bind
        self.ask = ask or (lambda q: output.prompt(q, timeout=ASK_TIMEOUT_SEC))
        self.tty = tty
        self.lock = lock or (lambda what: _null_lock())
        self.notice = notice or (lambda kind, services=None, gone=False: _null_lock())
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
            progress("\nStill shutting down. Press Ctrl-C again to stop waiting and leave the rest running.")
        else:
            raise Abandoned()

    def run(self):
        previous = {s: signal.signal(s, self._handle) for s in HANDLED_SIGNALS}
        try:
            failure = None
            try:
                self._up()
                return self._follow()
            except Interrupted as exc:
                self.phase = "closing"
                self._end_child()
                action = self._choose(exc.signum)
            except CliError as exc:
                failure = exc
                progress(f"qrosetta: {exc.message}")
                self.phase = "closing"
                self._end_child()
                action = "remove" if self.action == "remove" else "standby"
            self.phase = "shutdown"
            try:
                with self.lock(f"start exit action {action}"):
                    status = self._exit(action)
            except Abandoned:
                left = own.scan(self.engine, self.stack).running()
                progress(f"Stopped waiting. Still running: {', '.join(c.name for c in left) or 'nothing'}.")
                if left:
                    progress("`qrosetta stop` stops them; `qrosetta remove` removes them.")
                return int(Exit.SIGINT)
            if failure is not None:
                raise failure
            return status
        finally:
            for s, handler in previous.items():
                signal.signal(s, handler)

    def _up(self):
        if self.services:
            progress(f"Starting {len(self.services)} services...")
            ids = [self.stack.services[s].id for s in self.services]
            with self.lock("start"), (self.notice("start", ids) if self.adding else _null_lock()):
                deps = ["--no-deps"] if self.adding else []
                self.child = self.engine.spawn(["up", "-d", "--no-build", *deps, *self.services], capture_errors=True)
                code = self.child.wait()
                tail = spawned_tail(self.child)
                self.child = None
                if code != 0:
                    raise engine_error(tail, "`compose up` failed", self.bind)
        progress("")
        announce_running(self.engine, self.stack)
        result("Press Ctrl-C to stop it.")

    def _follow(self):
        tail = "20"
        while True:
            self.child = self.engine.spawn(["logs", "-f", "--tail", tail])
            self.child.wait()
            self.child = None
            if not own.scan(self.engine, self.stack).running():
                progress("Every Quantum Rosetta container has stopped.")
                return 0
            tail = "0"
            _sleep(2)

    def _end_child(self):
        child, self.child = self.child, None
        if child is None or child.poll() is not None:
            return
        _signal_group(child, signal.SIGTERM)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _signal_group(child, getattr(signal, "SIGKILL", signal.SIGTERM))
            child.wait()

    def _choose(self, signum):
        if self.action != "ask":
            return self.action
        if signum != signal.SIGINT or not self.tty:
            progress(f"\n{signal.Signals(signum).name} received: putting the stack on standby.")
            return "standby"
        self.phase = "prompt"
        try:
            answer = self.ask("\nKeep on standby or remove? [S/r] ")
        except (Interrupted, EOFError):
            answer = None
        self.phase = "closing"
        return "remove" if (answer or "").strip().lower() in ("r", "remove") else "standby"

    def _exit(self, action):
        with self.notice("remove" if action == "remove" else "stop", None, True):
            if action == "remove":
                return actions.remove_stack(self.engine, self.stack)
            return actions.report_left(actions.stop_stack(self.engine, self.stack))


class _null_lock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def lock_for(env):
    return lambda what: guard.engine_lock(env, what)
