"""Container engine choice (docker or podman, by whose `info` answers) and the subprocess calls
made through it."""

import collections
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field

from qrosetta_cli import config as cfgmod
from qrosetta_cli.errors import CliError, Exit, usage
from qrosetta_cli.mode import BASE_FILES

COMPOSE_INSTALL = (
    "Install Docker Compose v2: on Ubuntu or Debian `sudo apt install docker-compose-v2` (with podman add "
    "--no-install-recommends, so docker.io is not pulled in). Elsewhere, with Docker install the "
    "docker-compose-plugin package (https://docs.docker.com/compose/install/linux/); with podman, save the "
    "docker-compose binary from https://github.com/docker/compose/releases as "
    "~/.docker/cli-plugins/docker-compose and make it executable. podman-compose 1.x is not supported.")


@dataclass
class Choice:
    """The engine qrosetta uses, why, and what its `info` reported."""
    name: str
    reason: str
    info: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    @property
    def rootless(self):
        return engine_rootless(self.name, self.info)

    @property
    def version(self):
        return engine_version(self.name, self.info)


def engine_rootless(name, info):
    if name == "podman":
        return bool(((info.get("host") or {}).get("security") or {}).get("rootless"))
    return any("rootless" in str(opt) for opt in info.get("SecurityOptions") or [])


def engine_version(name, info):
    if name == "podman":
        return (info.get("version") or {}).get("Version") or ""
    return info.get("ServerVersion") or ""


def image_store(name, info):
    if name == "podman":
        return (info.get("store") or {}).get("graphRoot") or ""
    return info.get("DockerRootDir") or ""


def _is_podman_shim(docker_path, run):
    try:
        out = run([docker_path, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return "podman" in (out.stdout + out.stderr).lower()


def query_info(name, run=subprocess.run):
    """(info dict or None, error text) from `<engine> info`."""
    try:
        out = run([name, "info", "--format", "{{json .}}"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if out.returncode != 0:
        return None, (out.stderr or out.stdout).strip()
    try:
        data = json.loads(out.stdout or "{}")
    except json.JSONDecodeError:
        data = {}
    return (data if isinstance(data, dict) else {}), ""


def choose_engine(env=None, configured=None, which=shutil.which, run=subprocess.run):
    """QROSETTA_ENGINE, else config lifecycle.engine, else the first of docker and podman whose
    `info` answers. Docker that is podman's emulation counts as podman."""
    env = os.environ if env is None else env
    forced, source = (env.get("QROSETTA_ENGINE", "").strip().lower(), "QROSETTA_ENGINE")
    if not forced and configured:
        forced, source = configured.strip().lower(), "config lifecycle.engine"
    if forced:
        if forced not in ("docker", "podman"):
            raise usage(f"{source} must be docker or podman, not {forced!r}.", hint="qrosetta config show",
                        reason="engine_invalid")
        if not which(forced):
            raise CliError(f"{source} chooses {forced}, which is not on PATH.", Exit.ENGINE, "engine_missing",
                           hint="qrosetta doctor")
        info, err = query_info(forced, run)
        if info is None:
            raise CliError(f"{forced} (chosen by {source}) does not answer: {_last(err)}", Exit.ENGINE,
                           "engine_unavailable", hint="qrosetta doctor")
        return Choice(forced, f"chosen by {source}", info)
    docker, podman = which("docker"), which("podman")
    notes, docker_err = [], ""
    if docker and podman and _is_podman_shim(docker, run):
        notes.append("docker is podman's emulation")
        docker = None
    if docker:
        info, docker_err = query_info("docker", run)
        if info is not None:
            return Choice("docker", "docker answers", info, notes + (["podman is also installed"] if podman else []))
    if podman:
        info, podman_err = query_info("podman", run)
        if info is not None:
            if docker_err:
                why = ("docker: permission denied for this user" if "permission denied" in docker_err.lower()
                       else f"docker does not answer: {_last(docker_err)}")
            else:
                why = notes[0] if notes else "docker is not installed"
            return Choice("podman", f"using podman ({why})", info, notes)
        raise CliError(f"podman does not answer: {_last(podman_err)}", Exit.ENGINE, "engine_unavailable",
                       hint="qrosetta doctor")
    if docker_err:
        raise CliError(f"docker does not answer: {_last(docker_err)}", Exit.ENGINE, "engine_unavailable",
                       hint="qrosetta doctor")
    raise CliError("Neither docker nor podman is installed.", Exit.ENGINE, "engine_missing", hint="qrosetta doctor")


def detect_engine(env=None, which=shutil.which, run=subprocess.run, configured=None):
    """The chosen engine's name."""
    return choose_engine(env, configured, which, run).name


def _last(text):
    lines = [line for line in (text or "").strip().splitlines() if line.strip()]
    return lines[-1] if lines else "no output"


DEFAULT_PROJECT = "qsimulators"
_PROJECT_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")


def project_name(env=None):
    """QROSETTA_PROJECT, else qsimulators. COMPOSE_PROJECT_NAME is never read."""
    env = os.environ if env is None else env
    name = env.get("QROSETTA_PROJECT", "").strip() or DEFAULT_PROJECT
    if not _PROJECT_NAME.fullmatch(name):
        raise usage(f"QROSETTA_PROJECT={name!r} is not a compose project name "
                    "(lowercase letters, digits, '-' and '_', starting with a letter or digit).",
                    hint="export QROSETTA_PROJECT=qsimulators", reason="project_invalid")
    return name


def compose_files(project_dir):
    """The compose file in project_dir and its override file, if any."""
    for base in BASE_FILES:
        path = os.path.join(project_dir, base)
        if os.path.isfile(path):
            stem, ext = os.path.splitext(base)
            override = os.path.join(project_dir, f"{stem}.override{ext}")
            return [path] + ([override] if os.path.isfile(override) else [])
    raise usage(f"No compose file in {project_dir}.", hint="qrosetta --project-dir DIR status",
                reason="project_dir_invalid")


def child_env(project, base=None):
    """The environment for compose and safe_boot.sh: no COMPOSE_* variable and no CLI-owned
    variable from the caller (they could name another project, file or a token); this project
    set explicitly."""
    base = os.environ if base is None else base
    drop = set(cfgmod.CLI_ENV) - set(cfgmod.SHARED_WITH_COMPOSE)
    env = {k: v for k, v in base.items() if not k.startswith("COMPOSE_") and k not in drop}
    env["QROSETTA_PROJECT"] = project
    env["PODMAN_COMPOSE_WARNING_LOGS"] = "false"
    return env


def _tee(stream, tail):
    for line in iter(stream.readline, ""):
        tail.append(line)
        try:
            sys.stderr.write(line)
            sys.stderr.flush()
        except (OSError, ValueError):
            pass


class Engine:
    """Runs engine and compose commands in the project directory. Every compose call names the
    project (-p) and the compose files (-f) explicitly.

    Captured commands run in their own session, so a Ctrl-C at the terminal reaches only this
    process, which decides what to stop."""

    def __init__(self, name, project_dir, project=None, run=subprocess.run,
                 popen=subprocess.Popen, env=None, info=None, reason=""):
        self.name = name
        self.project_dir = project_dir
        self.project = project or project_name(env)
        self.files = compose_files(project_dir)
        self._run = run
        self._popen = popen
        self.env = child_env(self.project, env)
        self.info = info or {}
        self.reason = reason

    @property
    def rootless(self):
        return engine_rootless(self.name, self.info)

    @property
    def version(self):
        return engine_version(self.name, self.info)

    def describe(self):
        """'podman 5.4 (rootless)'."""
        text = " ".join(p for p in (self.name, self.version) if p)
        if self.info:
            text += " (rootless)" if self.rootless else " (rootful)"
        return text

    def compose_args(self, *args):
        base = [self.name, "compose", "-p", self.project, "--project-directory", self.project_dir]
        for path in self.files:
            base += ["-f", path]
        return base + list(args)

    def cli(self, *args, check=False, timeout=None):
        """Run `<engine> args...` and capture its output."""
        return self._call([self.name, *args], check, timeout)

    def compose(self, *args, check=False, timeout=None):
        """Run `<engine> compose args...` and capture its output."""
        return self._call(self.compose_args(*args), check, timeout)

    def _call(self, cmd, check, timeout):
        try:
            result = self._run(cmd, capture_output=True, text=True, cwd=self.project_dir,
                               env=self.env, timeout=timeout, start_new_session=True)
        except FileNotFoundError as exc:
            raise CliError(f"{cmd[0]} not found: {exc}", Exit.ENGINE, "engine_missing", hint="qrosetta doctor") from exc
        if check and result.returncode != 0:
            from qrosetta_cli.stack.explain import engine_error
            raise engine_error(result.stderr or result.stdout, f"`{' '.join(cmd[:4])} ...` failed")
        return result

    def spawn(self, args, own_session=True, compose=True, capture_errors=False):
        """Start a command whose output goes to this terminal; with capture_errors its stderr is
        copied to ours and its last lines kept as `qr_tail` for explaining a failure."""
        cmd = self.compose_args(*args) if compose else [self.name, *args]
        kwargs = {"stderr": subprocess.PIPE, "text": True} if capture_errors else {}
        proc = self._popen(cmd, cwd=self.project_dir, env=self.env, start_new_session=own_session, **kwargs)
        tail = collections.deque(maxlen=40)
        stream = getattr(proc, "stderr", None) if capture_errors else None
        if stream is not None and hasattr(stream, "readline"):
            thread = threading.Thread(target=_tee, args=(stream, tail), daemon=True)
            thread.start()
            proc.qr_thread = thread
        if not hasattr(proc, "qr_tail"):
            proc.qr_tail = tail
        return proc

    def check_compose(self):
        """Fail unless `<engine> compose` is Docker Compose v2, which `config --format json` needs."""
        out = self.compose("version")
        text = (out.stdout + out.stderr).strip()
        if out.returncode != 0 or "docker compose" not in text.lower():
            raise CliError(
                f"qrosetta needs Docker Compose v2, and `{self.name} compose version` printed: "
                f"{text.splitlines()[0] if text else 'nothing'}. " + COMPOSE_INSTALL, Exit.ENGINE,
                "compose_missing", hint="qrosetta doctor")


def spawned_tail(proc):
    """The captured stderr of a spawned command, once it has ended."""
    thread = getattr(proc, "qr_thread", None)
    if thread is not None:
        thread.join(timeout=5)
    return "".join(getattr(proc, "qr_tail", []) or [])
