"""`qrosetta doctor` (spec §6.10): host checks with their fixes, then live checks when a stack
answers. Exit 0 unless a check FAILs (17)."""

import os
import platform
import shlex
import shutil
import socket
import stat
import subprocess
from dataclasses import dataclass, field

from qrosetta_cli import __version__, jobstore, layout, localstack, output
from qrosetta_cli.errors import CliError, Exit
from qrosetta_cli.output import result
from qrosetta_cli.stack import engine as eng, hostload, quota
from qrosetta_cli.stack.explain import DELEGATE_DROPIN, OTHER_BIND, SUBUID_FIX, probe_message

GIB = 1024**3
LOW_DISK_GIB = 10
ORDER = ("PASS", "INFO", "WARN", "FAIL", "SKIP")
FIX_ORDER = (
    "os",
    "engine",
    "rootful_docker",
    "compose",
    "podman_socket",
    "subuid",
    "cgroup",
    "port",
    "disk",
    "jobs",
    "credentials",
    "server",
    "ready",
    "runners",
    "compilers",
)
DROPIN_LINES = DELEGATE_DROPIN.splitlines()


@dataclass
class Check:
    """One check. `steps` ([(sentence, [commands])]) and `reason` (the exit reason `start` uses
    when the check stops it) are for the terminal and `start`; the JSON carries `fix`."""

    id: str
    status: str
    message: str
    fix: str = ""
    steps: list | None = None
    reason: str | None = None

    def as_dict(self):
        return {"id": self.id, "status": self.status, "message": self.message, "fix": self.fix or None}


class Host:
    """What doctor reads from the machine; tests replace it."""

    def __init__(self, env=None, run=subprocess.run, which=shutil.which):
        self.env = os.environ if env is None else env
        self.run = run
        self.which = which

    def system(self):
        return platform.system()

    def machine(self):
        return platform.machine().lower()

    def uid(self):
        return os.getuid() if hasattr(os, "getuid") else 0

    def user(self):
        return self.env.get("USER") or ""

    def read(self, path):
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return None

    def exists(self, path):
        return os.path.exists(path)

    def running_services(self, ctx):
        """Ids of the services whose containers this stack runs, or None when the stack cannot
        be read (no compose, no published manifest, another engine error)."""
        from qrosetta_cli.stack import ownership
        from qrosetta_cli.stack.commands import open_stack

        try:
            _, engine, stack = open_stack(ctx)
            found = ownership.scan(engine, stack)
        except (CliError, OSError):
            return None
        return {stack.services[c.service].id for c in found.running() if c.service in stack.services}

    def free_bytes(self, path):
        probe = path
        while probe and not os.path.exists(probe):
            probe = os.path.dirname(probe)
        try:
            return shutil.disk_usage(probe or "/").free
        except OSError:
            return None

    def port_free(self, host, port):
        """Whether a server could listen on host:port now: SO_REUSEADDR, as nginx and the engines'
        port forwarders set it, so connections of a server that has stopped do not count (on
        Windows the option would let the probe bind over a listener)."""
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            if os.name != "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return True
            except OSError:
                return False

    def mode(self, path):
        try:
            return os.stat(path).st_mode
        except OSError:
            return None

    def images_present(self, ctx):
        """Whether the images of this stack's core services are present, or None when the stack
        cannot be read."""
        from qrosetta_cli.stack import project as st
        from qrosetta_cli.stack.commands import open_stack

        try:
            _, engine, stack = open_stack(ctx)
            refs = [stack.image_for(s) for s in stack.core_services()]
            return bool(refs) and set(refs) <= set(st.find_images(engine, refs))
        except (CliError, OSError):
            return None


def local_services(ctx):
    """{"running", "created": service ids, "profile": the profile whose runners and compilers are
    exactly the created ones, else None} for this checkout's or installation's stack; None when
    it cannot be read."""
    from qrosetta_cli.stack import ownership, profiles
    from qrosetta_cli.stack.commands import open_stack

    try:
        _, engine, stack = open_stack(ctx)
        found = ownership.scan(engine, stack)
        created = {c.service for c in found.containers if c.service in stack.services}
        running = {c.service for c in found.running() if c.service in stack.services}
        members = {
            name: {s for s in svcs if stack.kind_of(s) in ("runner", "compiler")}
            for name, svcs in profiles.built_in(stack).items()
        }
    except (CliError, OSError):
        return None
    backends = {s for s in created if stack.kind_of(s) in ("runner", "compiler")}
    profile = next((name for name, svcs in members.items() if svcs and svcs == backends), None)
    return {
        "running": {stack.services[s].id for s in running},
        "created": {stack.services[s].id for s in created},
        "profile": profile,
    }


@dataclass
class Report:
    checks: list = field(default_factory=list)
    next_command: str | None = None

    def add(self, cid, status, message, fix="", steps=None, reason=None):
        self.checks.append(Check(cid, status, message, fix, steps, reason))

    @property
    def failed(self):
        return [c for c in self.checks if c.status == "FAIL"]


def _subids(host, path):
    text = host.read(path) or ""
    names = {host.user(), str(host.uid())}
    return any(line.split(":", 1)[0] in names for line in text.splitlines() if ":" in line)


def check_os(host, rep):
    machine = host.machine()
    if host.system() == "Linux" and machine in ("x86_64", "amd64"):
        rep.add("os", "PASS", "Linux x86_64")
    else:
        rep.add(
            "os",
            "FAIL",
            f"{host.system()} {machine}: Quantum Rosetta images are linux/amd64 only",
            "use a Linux x86_64 machine",
            [("Use a Linux x86_64 machine; Quantum Rosetta images are linux/amd64 only.", [])],
            "wrong_architecture",
        )


def check_engine(host, rep, configured):
    try:
        choice = eng.choose_engine(host.env, configured, host.which, host.run)
    except CliError as exc:
        docker_refused = "permission denied" in exc.message.lower()
        fix = (
            "sudo usermod -aG docker $USER (root-equivalent), then reboot; or install rootless podman"
            if docker_refused
            else "install Docker with Compose v2, or rootless podman (README, Requirements)"
        )
        steps = (
            [
                (
                    "Add your user to the docker group (root-equivalent), then reboot:",
                    ["sudo usermod -aG docker $USER"],
                ),
                ("Or install rootless podman (README, Requirements).", []),
            ]
            if docker_refused
            else [("Install Docker with Compose v2, or rootless podman (README, Requirements).", [])]
        )
        rep.add("engine", "FAIL", exc.message, fix, steps, exc.reason)
        return None
    status = "INFO" if choice.name == "podman" and "permission denied" in choice.reason else "PASS"
    rep.add(
        "engine",
        status,
        f"{choice.name} {choice.version} ({'rootless' if choice.rootless else 'rootful'}); "
        f"{choice.reason}" + "".join(f"; {n}" for n in choice.notes if n not in choice.reason),
    )
    if choice.name == "docker" and not choice.rootless:
        rep.add(
            "rootful_docker", "INFO", "the Docker daemon runs as root; members of the docker group are root-equivalent"
        )
    return choice


def check_compose(host, rep, choice):
    try:
        out = host.run([choice.name, "compose", "version"], capture_output=True, text=True, timeout=30)
        text = (out.stdout + out.stderr).strip()
        ok = out.returncode == 0 and "docker compose" in text.lower()
    except (OSError, subprocess.SubprocessError) as exc:
        text, ok = str(exc), False
    if ok:
        rep.add("compose", "PASS", text.splitlines()[0])
    else:
        step = eng.compose_install_step(host.read("/etc/os-release"), choice.name)
        rep.add(
            "compose",
            "FAIL",
            f"`{choice.name} compose` is not Docker Compose v2 "
            f"({text.splitlines()[0] if text else 'no output'}); podman-compose 1.x is not supported",
            step,
            _compose_steps(step),
            "compose_missing",
        )


def _compose_steps(step):
    """The install step as a sentence over its command, or as one sentence when it is prose."""
    found = layout.parts(step)
    if found and found[0][1]:
        where = found[0][0].rstrip(":")
        sentence = "Install Docker Compose v2" + (f" ({where[0].lower()}{where[1:]})" if where != "Run" else "")
        return [(sentence + ":", found[0][1])]
    return [(layout.sentence(f"install Docker Compose v2: {step}"), [])]


def check_podman(host, rep, choice):
    runtime = host.env.get("XDG_RUNTIME_DIR") or f"/run/user/{host.uid()}"
    sock = os.path.join(runtime, "podman", "podman.sock")
    if host.exists(sock):
        rep.add("podman_socket", "PASS", f"podman.socket at {sock}")
    else:
        rep.add(
            "podman_socket",
            "FAIL",
            f"no podman API socket at {sock}; Docker Compose needs it",
            "systemctl --user enable --now podman.socket",
            [
                (
                    "Start podman's API socket, which Docker Compose connects to:",
                    ["systemctl --user enable --now podman.socket"],
                )
            ],
            "podman_socket",
        )
    if not choice.rootless:
        return
    if _subids(host, "/etc/subuid") and _subids(host, "/etc/subgid"):
        rep.add("subuid", "PASS", f"subuid and subgid ranges for {host.user() or host.uid()}")
    else:
        rep.add(
            "subuid",
            "FAIL",
            f"no subuid/subgid entries for {host.user() or host.uid()}",
            SUBUID_FIX,
            [
                (
                    "Give your user subordinate UID and GID ranges, which rootless podman needs:",
                    [c.strip() for c in SUBUID_FIX.split("&&")],
                )
            ],
            "subuid_missing",
        )


def check_controllers(host, rep, choice, quota_on=True):
    if not choice.rootless:
        return
    have = quota.user_controllers(host.read, host.exists, host.uid())
    if have == "v1":
        rep.add(
            "cgroup",
            "FAIL",
            "rootless containers on cgroup v1: memory and CPU limits are absent",
            "boot with cgroup v2 (systemd.unified_cgroup_hierarchy=1)",
            [("Boot with cgroup v2 (kernel parameter systemd.unified_cgroup_hierarchy=1).", [])],
            "cgroup_v1",
        )
        return
    missing = [c for c in ("cpu", "memory", "pids") if c not in (have or set())]
    if not missing:
        rep.add("cgroup", "PASS", "cpu, memory and pids controllers delegated to your user")
        return
    without_flag = DELEGATE_DROPIN + f"\nor, without sudo: {quota.FLAG_HINT} (no CPU limits; results record it)"
    if missing == ["cpu"] and not quota_on:
        rep.add(
            "cgroup",
            "WARN",
            "the cpu controller is not delegated to your user; the stack starts without "
            "the CPU quota (--no-cpu-quota), so timings are not comparable with runs under it",
            DELEGATE_DROPIN,
            [("To run under the CPU quota, delegate the controllers to your user, then reboot:", DROPIN_LINES)],
        )
        return
    steps = [
        (
            f"Delegate the {', '.join(missing)} controller{'s' * (len(missing) > 1)} to your user, then reboot:",
            DROPIN_LINES,
        )
    ]
    if missing == ["cpu"]:
        steps.append(
            ("Or, without sudo, start without the CPU quota (no CPU limits; results record it):", [quota.FLAG_HINT])
        )
    rep.add(
        "cgroup",
        "FAIL",
        f"controllers not delegated to your user: {', '.join(missing)}; `start` cannot "
        "apply the " + ("CPU and memory limits" if "memory" in missing else "CPU limits"),
        without_flag if missing == ["cpu"] else DELEGATE_DROPIN,
        steps,
        "memory_controller_missing" if "memory" in missing else "cpu_controller_missing",
    )


def check_port(host, rep, bind, answers, cfg=None):
    """`answers`: whether a Quantum Rosetta answers at `bind` (a callable is asked only when the
    port is in use); `cfg` lets the fix name the config file."""
    address, _, port = bind.rpartition(":")
    address = address.strip("[]") or "127.0.0.1"
    if not port.isdigit():
        rep.add(
            "port",
            "FAIL",
            f"{bind} is not ADDRESS:PORT",
            "edit [lifecycle] bind in the config file",
            [
                (
                    "Set [lifecycle] bind to ADDRESS:PORT in the config file, whose path this prints:",
                    ["qrosetta config path"],
                )
            ],
            "bind_invalid",
        )
    elif host.port_free(address, int(port)):
        rep.add("port", "PASS", f"{bind} is free")
    elif answers() if callable(answers) else answers:
        rep.add("port", "PASS", f"{bind} is in use by a running Quantum Rosetta")
    else:
        rep.add(
            "port",
            "FAIL",
            f"{bind} is in use",
            f"qrosetta start -d --bind {OTHER_BIND}\n"
            f'Later commands use {bind} until [lifecycle] bind = "{OTHER_BIND}" is in the file '
            "`qrosetta config path` prints; with it, `start` needs no --bind.",
            port_steps(cfg),
            "port_in_use",
        )


def port_steps(cfg):
    """Use OTHER_BIND from now on: the config file gets [lifecycle] bind (created, appended to, or
    edited by hand when it has a [lifecycle] table), then `start -d` needs no --bind."""
    port = OTHER_BIND.rpartition(":")[2]
    head = f"Use port {port} for this and every later command:"
    line = f'bind = "{OTHER_BIND}"'
    if cfg is None:
        return [(head, [f"qrosetta start -d --bind {OTHER_BIND}"])]
    path = shlex.quote(cfg.path)
    if not cfg.loaded:
        commands = [
            f"mkdir -p {shlex.quote(os.path.dirname(cfg.path) or '.')}",
            f"printf '[lifecycle]\\n{line}\\n' > {path}",
        ]
    elif cfg.get("lifecycle") is None:
        commands = [f"printf '\\n[lifecycle]\\n{line}\\n' >> {path}"]
    else:
        return [
            (f"Use port {port} for this and every later command. In {cfg.path}, under [lifecycle], set:", [line]),
            ("Then start:", ["qrosetta start -d"]),
        ]
    return [(head, commands + ["qrosetta start -d"])]


def check_disk(host, rep, choice):
    """Free space of the image store and cache; returns the image store's free bytes or None."""
    store_free = None
    places = [
        ("image store", eng.image_store(choice.name, choice.info) if choice else ""),
        ("cache", os.path.join(host.env.get("XDG_CACHE_HOME") or os.path.join(host.env.get("HOME") or "~", ".cache"))),
    ]
    for label, path in places:
        if not path:
            continue
        free = host.free_bytes(path)
        if free is None:
            continue
        if label == "image store":
            store_free = free
        if free < LOW_DISK_GIB * GIB:
            rep.add(
                "disk",
                "WARN",
                f"{label} {path}: {free / GIB:.1f} GiB free (under {LOW_DISK_GIB} GiB)",
                f"free space under {path}",
                [(f"Free space under {path} ({LOW_DISK_GIB} GiB or more).", [])],
            )
        else:
            rep.add("disk", "PASS", f"{label} {path}: {free / GIB:.1f} GiB free")
    tmp = host.free_bytes("/var/tmp") if choice and choice.name == "podman" else None
    if tmp is not None:
        rep.add("disk", "INFO", f"/var/tmp: {tmp / GIB:.1f} GiB free (podman stages image layers there)")
    return store_free


def check_jobs(host, rep, cfg, store_free):
    """The finished-job settings `start` gives the API, and a warning when the job storage budget
    is more than the image store's free space less 1 GiB (the reports live in the API container),
    or the job memory budget is at least the API container's memory limit less 512 MiB."""
    try:
        jobs = jobstore.resolve(host.env, cfg)
    except CliError as exc:
        rep.add("jobs", "FAIL", exc.message, exc.hint or "")
        return
    rep.add("jobs", "INFO", jobstore.line(jobs))
    budget = jobs["job_storage"][0] * jobstore.MIB
    if store_free is not None and budget > store_free - GIB:
        rep.add(
            "jobs",
            "WARN",
            f"job storage {budget / GIB:.1f} GiB is more than the image store's free space less 1 GiB "
            f"({max(store_free - GIB, 0) / GIB:.1f} GiB)",
            "set [lifecycle] job_storage lower (qrosetta config path), or free space in the image store",
        )
    memory, ceiling = jobs["job_memory"][0], jobstore.API_MEMORY_LIMIT_MIB - 512
    if memory >= ceiling:
        rep.add(
            "jobs",
            "WARN",
            f"job memory {memory} MiB is at least the API container's {jobstore.API_MEMORY_LIMIT_MIB} MiB "
            f"memory limit less 512 MiB ({ceiling} MiB)",
            "set [lifecycle] job_memory lower (qrosetta config path)",
        )


def check_credentials(host, rep, path):
    mode = host.mode(path)
    if mode is None:
        return
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        rep.add(
            "credentials",
            "FAIL",
            f"{path} is readable by other users",
            f"chmod 600 {path}",
            [("Make the credentials file readable by your user only:", [f"chmod 600 {shlex.quote(path)}"])],
        )
    else:
        rep.add("credentials", "PASS", f"{path} is private")


def check_extras(host, rep):
    gpu = host.exists("/dev/nvidia0") or bool(host.which("nvidia-smi"))
    rep.add(
        "gpu", "INFO", "NVIDIA GPU present (cuQuantum can run)" if gpu else "no NVIDIA GPU (cuQuantum is unavailable)"
    )
    tool = host.which("apptainer") or host.which("singularity")
    rep.add("apptainer", "INFO", f"Apptainer at {tool}" if tool else "Apptainer not installed (HPC images only)")


def check_live(rep, config, transport, env=None, running=None):
    """Server, readiness and service availability. ``running``: the ids of the services this
    stack runs, when known; an enabled service outside it is listed as not started, not as a
    failed probe."""
    from qrosetta_cli.client import handshake

    block = handshake.server_block(config)
    if block is None:
        rep.add(
            "server",
            "WARN",
            "the running server predates the version handshake (needs platform 2.0.0)",
            "rebuild the stack from this checkout: qrosetta build",
            [("Rebuild the stack from this checkout:", ["qrosetta build"])],
        )
    else:
        try:
            handshake.check(config)
            rep.add("server", "PASS", handshake.describe(block))
        except CliError as exc:
            rep.add("server", "WARN", exc.message, exc.hint or "")
    try:
        api = handshake.readiness(transport, block)
    except CliError as exc:
        api = (False, exc.message)
    if api is None:
        rep.add("ready", "SKIP", "the running server has no readiness check (GET /ready)")
    elif api[0]:
        rep.add("ready", "PASS", "the API's database and job storage work (GET /ready)")
    else:
        rep.add(
            "ready",
            "FAIL",
            api[1],
            "qrosetta logs api --tail 50",
            [("Read the API's log:", ["qrosetta logs api --tail 50"])],
        )
    headers = hostload.auth_headers(env or {})
    for path, label in (("/runners", "runners"), ("/compilers", "compilers")):
        try:
            data, how = _service_rows(transport, path, headers)
        except CliError as exc:
            rep.add(
                label,
                "WARN",
                exc.message,
                "qrosetta status",
                [("List the services and their state:", ["qrosetta status"])],
            )
            continue
        if not isinstance(data, list):
            continue
        enabled = [e for e in data if isinstance(e, dict) and e.get("enabled")]
        if running is not None:
            absent = [e["id"] for e in enabled if e.get("id") not in running]
            enabled = [e for e in enabled if e.get("id") in running]
            if absent:
                rep.add(label, "INFO", f"not started in this stack: {', '.join(absent)} (`qrosetta status` lists them)")
            if not enabled:
                continue
        down = [e for e in enabled if not e.get("available")]
        if not down:
            rep.add(label, "PASS", f"{len(enabled)} {label} available ({how})")
            continue
        parts = []
        for e in down:
            kind = e.get("error_kind")
            parts.append(probe_message(kind, e["id"])[0] if kind else f"{e['id']} ({e.get('unavailable_reason')})")
        rep.add(
            label,
            "WARN",
            f"{len(enabled) - len(down)} of {len(enabled)} {label} available ({how}); not "
            "available: " + "; ".join(parts),
            "qrosetta start -d (adds the services that are not running)",
            [("Start the services that are not running:", ["qrosetta start -d"])],
        )


def _service_rows(transport, path, headers):
    """(rows, how they were read): a fresh probe round with the lifecycle token when the server
    takes it, else its cached availability."""
    if headers:
        resp = transport.request("GET", path, query={"fresh": "true"}, headers=headers, timeout=30)
        data = resp.json()
        if resp.status == 200 and isinstance(data, list) and any(isinstance(e, dict) and "fresh" in e for e in data):
            return data, "probed now"
        why = {
            401: "the server did not take the lifecycle token",
            403: "the server did not take the lifecycle token",
            429: "fresh probes are rate-limited",
        }.get(resp.status, "the server has no on-demand probes")
    else:
        why = "no lifecycle token"
    return transport.request("GET", path, timeout=30).json(), f"cached availability: {why}"


def run(ctx, host=None):
    """All checks; returns the report."""
    from qrosetta_cli.client import handshake, servers

    host = host or Host(ctx.env)
    rep = Report()
    check_os(host, rep)
    choice = check_engine(host, rep, ctx.cfg.get("lifecycle", "engine"))
    if choice:
        check_compose(host, rep, choice)
        if choice.name == "podman":
            check_podman(host, rep, choice)
        check_controllers(host, rep, choice, localstack.cpu_quota(host.env, ctx.cfg)[0])
    bind = ctx.cfg.get("lifecycle", "bind") or servers.DEFAULT_BIND
    server = servers.Server(servers.LOCAL, servers.bind_url(bind), "lifecycle.bind")
    config, transport = None, None
    try:
        transport = ctx.transport(server=server, timeout=5)
        config = handshake.fetch_config(transport, timeout=5)
        ctx._server = server
        ctx.note_handshake(handshake.server_block(config))
    except CliError:
        config = None
    check_port(host, rep, bind, config is not None, ctx.cfg)
    check_jobs(host, rep, ctx.cfg, check_disk(host, rep, choice))
    check_credentials(host, rep, servers.credentials_path(ctx.cfg, ctx.env))
    check_extras(host, rep)
    if config is not None:
        check_live(rep, config, transport, ctx.env, host.running_services(ctx))
    else:
        rep.add("server", "INFO", f"no Quantum Rosetta answers at {server.url}; live checks skipped")
    rep.next_command = next_command(ctx, host, config is not None)
    return rep


def next_command(ctx, host, answers):
    """The one command to run after doctor: the self-test when a stack answers, `start -d` when
    its core images are present, else pull (installed) or build (checkout) of the minimal profile."""
    from qrosetta_cli import mode as modes

    if answers:
        return "qrosetta selftest"
    if host.images_present(ctx):
        return "qrosetta start -d"
    try:
        checkout = modes.detect(ctx.opt("project_dir"), ctx.env, ctx.checkout).name == "checkout"
    except CliError:
        checkout = False
    return f"qrosetta {'build' if checkout else 'pull'} --profile minimal"


def report_lines(rep, stream=None):
    return [f"Quantum Rosetta {__version__}: checks for this computer", ""] + layout.checks_report(
        rep.checks, FIX_ORDER, "qrosetta doctor", rep.next_command, stream
    )


def print_report(rep):
    for line in report_lines(rep):
        result(line)


def cmd_doctor(ctx, host=None):
    from qrosetta_cli.context import Result

    host = host or (ctx.host_factory(ctx.env) if ctx.host_factory else None)
    rep = run(ctx, host)
    print_report(rep)
    data = {
        "checks": [c.as_dict() for c in rep.checks],
        "failed": len(rep.failed),
        "warnings": sum(c.status == "WARN" for c in rep.checks),
    }
    if rep.failed:
        first = rep.failed[0]
        err = CliError(
            f"{len(rep.failed)} check(s) failed: {', '.join(c.id for c in rep.failed)}.",
            Exit.CHECKS_FAILED,
            "checks_failed",
            hint=(first.fix or "qrosetta doctor").splitlines()[0],
            data=data,
        )
        err.shown = not output.json_mode()
        raise err
    return Result(0, data)
