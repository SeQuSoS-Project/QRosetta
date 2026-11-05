"""`qrosetta start`: bring the stack up, wait for its runners, follow its logs, and on Ctrl-C,
SIGTERM or SIGHUP put it on standby or remove it."""

import os
import signal
import subprocess
import time
from dataclasses import dataclass

from qrosetta_cli import output
from qrosetta_cli.config import EXIT_ACTIONS
from qrosetta_cli.errors import CliError, Exit, usage
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import actions, guard, hostload
from qrosetta_cli.stack import ownership as own
from qrosetta_cli.stack import project as st
from qrosetta_cli.stack.engine import CHANGE_TIMEOUT_SEC, spawned_tail, wait_spawned
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
        raise usage(
            f"The exit action must be one of {', '.join(EXIT_ACTIONS)}, not {value!r}.",
            hint="qrosetta start --on-exit standby",
            reason="on_exit_invalid",
        )
    value = value or ("ask" if tty else "standby")
    return "standby" if value == "ask" and not tty else value


def check_bind(bind):
    """host:port, with a warning when other machines could reach it (there is no TLS)."""
    host, sep, port = bind.rpartition(":")
    if not sep or not port.isdigit() or not host:
        raise usage(
            f"--bind takes ADDRESS:PORT, not {bind!r}.",
            hint="qrosetta start -d --bind 127.0.0.1:8080",
            reason="bind_invalid",
        )
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
        hint = f"qrosetta pull {keys}" if stack.release else f"qrosetta build {keys}"
        raise CliError(
            f"No image for {', '.join(stack.services[s].id for s in blocking)}.",
            Exit.ENGINE,
            "image_missing",
            hint=hint,
        )
    return [s for s in candidates if s not in missing], missing, git_sha_env(stack, images, env)


def git_sha_env(stack, images, env):
    """QROSETTA_GIT_SHA for compose when the caller sets none: the commit baked into the image of
    a core service whose compose environment reads it (the API), else of the first core service
    with one. `images` maps refs to images, as `find_images` returns them."""
    if env.get("QROSETTA_GIT_SHA"):
        return {}
    core = stack.core_services()
    for svc in sorted(core, key=lambda s: "QROSETTA_GIT_SHA" not in stack.services[s].environment):
        img = images.get(stack.image_for(svc))
        sha = img.env.get("QROSETTA_IMAGE_GIT_SHA") if img else None
        if sha and sha != "unknown":
            return {"QROSETTA_GIT_SHA": sha}
    return {}


def config_hashes(engine):
    """{compose service: hash} as `compose config --hash` prints them under the engine's
    environment, which is the one `up` gets; None when this compose does not print them."""
    out = engine.compose("config", "--hash", "*")
    if out.returncode != 0:
        output.warn(
            f"`{engine.name} compose config --hash` failed, so containers are compared with their "
            "images only, not with the compose configuration.",
            "config_hash_unavailable",
        )
        return None
    hashes = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            hashes[parts[0]] = parts[1]
    return hashes


def config_changed(container, hashes):
    """True when compose would give the container's service another configuration than the one
    it was created with; None when either hash is unknown."""
    if not hashes or not container.config_hash or not hashes.get(container.service):
        return None
    return hashes[container.service] != container.config_hash


@dataclass
class Stale:
    """A container of this stack created from an image other than the one now under its tag
    (`current` set), or from another compose configuration than the compose file now gives
    (`config`), or both."""

    service: str
    running: bool
    image_id: str | None = None
    git_sha: str | None = None
    current: st.Image | None = None
    config: bool = False

    @property
    def reasons(self):
        return (["image"] if self.current else []) + (["config"] if self.config else [])


def stale_containers(engine, stack, found, services, hashes=None):
    """The containers among `services` that the ownership scan accepted and that were created
    from an image other than the one now under the service's tag, or whose compose config hash
    differs from `hashes` (`config_hashes`). A container is not compared with an image when its
    service has no image under its tag or the engine does not report the container's image, nor
    with the configuration when either hash is unknown."""
    containers = {c.service: c for c in found.containers if c.service in services}
    if not containers:
        return []
    with_image = [c for c in containers.values() if c.image]
    tagged = st.find_images(engine, [stack.image_for(c.service) for c in with_image]) if with_image else {}
    old = st.images_by_id(engine, [c.image for c in with_image]) if with_image else {}
    stale = []
    for service in services:
        c = containers.get(service)
        if c is None:
            continue
        img = tagged.get(stack.image_for(service)) if c.image else None
        moved = img is not None and st.image_key(c.image) != st.image_key(img.id)
        config = bool(config_changed(c, hashes))
        if not moved and not config:
            continue
        before = old.get(st.image_key(c.image)) if moved else None
        stale.append(
            Stale(
                service,
                c.running,
                c.image if moved else None,
                before.git_sha if before else None,
                img if moved else None,
                config,
            )
        )
    return stale


def _image_words(sha, ident):
    built = f"built from {sha}" if sha and sha != "unknown" else "no baked commit"
    return f"{built} (image {st.image_key(ident)[:12]})"


REASON_WORDS = {"image": "image rebuilt", "config": "compose configuration changed"}


def describe_stale(stack, stale):
    """Progress lines naming each container to recreate and why: its image and the one under
    its tag, and whether its compose configuration changed."""
    one = len(stale) == 1
    kinds = {r for s in stale for r in s.reasons}
    if kinds == {"image"}:
        head = (
            "1 service whose container was created from another image than the one now under its tag"
            if one
            else f"{len(stale)} services whose containers were created from other images than the ones now "
            "under their tags"
        )
    elif kinds == {"config"}:
        head = (
            "1 service whose container was created from another compose configuration than the compose file now gives"
            if one
            else f"{len(stale)} services whose containers were created from other "
            "compose configurations than the compose file now gives"
        )
    else:
        head = (
            "1 service whose container was created from another image and compose configuration than the current ones"
            if one
            else f"{len(stale)} services whose containers were created from other "
            "images or compose configurations than the current ones"
        )
    lines = [f"Recreating {head}:"]
    for s in stale:
        words = []
        if s.current:
            words.append(
                f"{REASON_WORDS['image']}, {_image_words(s.git_sha, s.image_id)} -> "
                f"{_image_words(s.current.git_sha, s.current.id)}"
            )
        if s.config:
            words.append(REASON_WORDS["config"])
        lines.append(f"  {stack.services[s.service].id} ({'running' if s.running else 'stopped'}): " + "; ".join(words))
    return lines


def stale_notice(stack, stale):
    """(host-load notice kind, service ids, whether the API restarts) for recreating `stale`:
    `stop` when a running container is replaced, so runs on it record stopped_by_user."""
    kind = "stop" if any(s.running for s in stale) else "start"
    gone = any(s.running and stack.kind_of(s.service) == "core" for s in stale)
    return kind, [stack.services[s.service].id for s in stale], gone


def check_startable(engine, found):
    """Refuse to start while containers, networks or volumes that are not this stack's hold its
    names; compose would otherwise recreate, replace or mount them."""
    lines = own.blockers(engine, found)
    if lines:
        first_cmd = next((line.split(": ")[-1] for line in lines if f"{engine.name} " in line), "qrosetta status")
        raise CliError(
            "Not started. " + "\n".join(lines),
            Exit.ENGINE,
            "name_conflict",
            hint=first_cmd if first_cmd.startswith(engine.name) else "qrosetta status",
        )


def up_flags(adding, recreate=False):
    """`--force-recreate` replaces the containers of the named services on the images now under
    their tags; `--no-deps` leaves the other services of a running stack alone."""
    return (["--force-recreate"] if recreate else []) + (["--no-deps"] if adding else [])


def api_health_report(engine, stack, tail=20):
    """The API container's last health check and the last `tail` lines of its log, read from this
    stack's labelled API container; '' when there is none."""
    service = getattr(stack.by_id().get("api"), "name", None)
    api = next((c for c in own.scan(engine, stack).containers if c.service == service), None)
    if api is None:
        return ""
    items = own._inspect(engine, "container", [api.id])
    state = (items[0].get("State") or {}) if items else {}
    checks = (state.get("Health") or state.get("Healthcheck") or {}).get("Log") or []
    lines = []
    if checks:
        last = checks[-1]
        lines.append(f"Last health check of {api.name}: exit code {last.get('ExitCode')}")
        lines += ["  " + x for x in (last.get("Output") or "").strip().splitlines()[-5:]]
    out = engine.cli("logs", "--timestamps", "--tail", str(tail), api.id)
    logged = sorted((out.stdout or "").splitlines() + (out.stderr or "").splitlines(), key=lambda x: x.split(" ", 1)[0])
    if logged:
        lines.append(f"Last {len(logged[-tail:])} lines of its log:")
        lines += ["  " + x for x in logged[-tail:]]
    return "\n".join(lines)


def up_failure(engine, stack, text, bind):
    """The error for a failed `compose up`, with the API's health report when it was unhealthy."""
    err = engine_error(text, "`compose up` failed", bind)
    if err.reason == "api_unhealthy" and stack is not None:
        try:
            report = api_health_report(engine, stack)
        except CliError:
            report = ""
        if report:
            err.message += "\n" + report
    return err


def up(engine, services, adding, bind=None, recreate=False, stack=None):
    """`compose up -d` for `services`; when adding to a running stack, the others are left alone."""
    proc = engine.spawn(
        ["up", "-d", "--no-build", *up_flags(adding, recreate), *services], own_session=False, capture_errors=True
    )
    if wait_spawned(proc, CHANGE_TIMEOUT_SEC, [engine.name, "compose", "up"]) != 0:
        raise up_failure(engine, stack, spawned_tail(proc), bind)


def _entries(transport, path, query, headers=None):
    resp = transport.request("GET", path, query=query, headers=headers, timeout=30)
    data = resp.json()
    return resp.status, data if isinstance(data, list) else []


def wait_ready(ctx, engine, stack, services, timeout=READY_TIMEOUT_SEC):
    """Return when the API is ready (GET /ready, when the server offers it) and every started runner
    and compiler is available, polling every 2 s; fresh probes (GET /runners?fresh=true) when the
    server offers them, else its cached availability."""
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
            block = handshake.server_block(handshake.fetch_config(transport, timeout=5))
            ctx.note_handshake(block)
            api = handshake.readiness(transport, block)
            if api is None or api[0]:
                break
            why = api[1]
        except CliError as exc:
            why = exc.message
        if _clock() >= deadline:
            raise CliError(
                f"The API at {url} was not ready within {timeout} s. {why}",
                Exit.ENGINE,
                "api_unhealthy",
                hint="qrosetta logs api --tail 50",
            )
        _sleep(READY_POLL_SEC)
    fresh, ready, entries = None, set(), {}
    probe_headers = None if getattr(transport, "token", None) else (hostload.auth_headers(ctx.env) or None)
    progress(f"Waiting for {len(wanted)} runners and compilers...")
    while True:
        for path in ("/runners", "/compilers"):
            if not any(k == ("runner" if path == "/runners" else "compiler") for k in wanted.values()):
                continue
            status, data = _entries(
                transport,
                path,
                {"fresh": "true"} if fresh is not False else None,
                probe_headers if fresh is not False else None,
            )
            if fresh is None:
                if status in (401, 403):
                    fresh = False
                    output.warn(
                        "fresh probes need `qrosetta login` or the lifecycle token, and the server took "
                        "neither; readiness comes from its 60-second cache.",
                        "fresh_probes_unauthorised",
                    )
                    status, data = _entries(transport, path, None)
                elif data and not any("fresh" in e for e in data if isinstance(e, dict)):
                    fresh = False
                    output.warn(
                        "this server has no on-demand probes (GET /runners?fresh=true); readiness comes "
                        "from its 60-second cache, so a runner can read ready up to a minute late.",
                        "fresh_probes_missing",
                    )
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
                message, hint = (
                    probe_message(kind, key)
                    if kind
                    else (
                        f"{key} not ready ({(entries.get(key) or {}).get('unavailable_reason') or 'no answer'})",
                        f"qrosetta logs {key} --tail 50",
                    )
                )
                lines.append(message)
                hints.append(hint)
            raise CliError(
                f"Not ready after {timeout} s: " + "; ".join(lines) + ".", Exit.ENGINE, "not_ready", hint=hints[0]
            )
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

    def __init__(
        self,
        engine,
        stack,
        action,
        services,
        compose_env,
        tty=False,
        ask=None,
        adding=False,
        lock=None,
        bind=None,
        notice=None,
        stale=(),
        jobs_line=None,
    ):
        self.engine, self.stack, self.action = engine, stack, action
        self.services, self.adding, self.bind = services, adding, bind
        self.stale = list(stale)
        self.jobs_line = jobs_line
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
        if self.stale:
            kind, ids, gone = stale_notice(self.stack, self.stale)
            with self.lock("start"), self.notice(kind, ids, gone) if self.adding else _null_lock():
                self._compose_up([s.service for s in self.stale], True)
        if self.services:
            progress(f"Starting {len(self.services)} services...")
            ids = [self.stack.services[s].id for s in self.services]
            with self.lock("start"), self.notice("start", ids) if self.adding else _null_lock():
                self._compose_up(self.services, False)
        progress("")
        announce_running(self.engine, self.stack)
        if self.jobs_line:
            progress(self.jobs_line)
        result("Press Ctrl-C to stop it.")

    def _compose_up(self, services, recreate):
        self.child = self.engine.spawn(
            ["up", "-d", "--no-build", *up_flags(self.adding, recreate), *services], capture_errors=True
        )
        code = wait_spawned(self.child, CHANGE_TIMEOUT_SEC, [self.engine.name, "compose", "up"])
        tail = spawned_tail(self.child)
        self.child = None
        if code != 0:
            raise up_failure(self.engine, self.stack, tail, self.bind)

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
                actions.remove_stack(self.engine, self.stack)
                return 0
            return actions.report_left(actions.stop_stack(self.engine, self.stack))


class _null_lock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def lock_for(env):
    return lambda what: guard.engine_lock(env, what)
