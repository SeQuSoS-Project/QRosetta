"""Container engine detection (docker or podman) and the subprocess calls made through it."""

import os
import re
import shutil
import subprocess


COMPOSE_INSTALL = (
    "With Docker, install the docker-compose-plugin package "
    "(https://docs.docker.com/compose/install/linux/). With podman, download the docker-compose "
    "binary for your platform from https://github.com/docker/compose/releases, save it as "
    "~/.docker/cli-plugins/docker-compose and make it executable; `podman compose` then uses it "
    "instead of podman-compose.")


class CliError(Exception):
    """An error reported to the user as one message, without a traceback."""


def _is_podman_shim(docker_path, run):
    try:
        out = run([docker_path, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return "podman" in (out.stdout + out.stderr).lower()


def detect_engine(env=None, which=shutil.which, run=subprocess.run):
    """Return "docker" or "podman": QROSETTA_ENGINE if set, else docker unless it is podman's
    docker emulation, else podman."""
    env = os.environ if env is None else env
    chosen = env.get("QROSETTA_ENGINE", "").strip().lower()
    if chosen:
        if chosen not in ("docker", "podman"):
            raise CliError(f"QROSETTA_ENGINE must be docker or podman, not {chosen!r}.")
        if not which(chosen):
            raise CliError(f"QROSETTA_ENGINE={chosen} but {chosen} is not on PATH.")
        return chosen
    docker = which("docker")
    podman = which("podman")
    if docker and not (podman and _is_podman_shim(docker, run)):
        return "docker"
    if podman:
        return "podman"
    raise CliError("Neither docker nor podman is installed. Install one of them with Compose v2.")


DEFAULT_PROJECT = "qsimulators"
_PROJECT_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
_BASE_FILES = ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml")


def project_name(env=None):
    """QROSETTA_PROJECT, else qsimulators. COMPOSE_PROJECT_NAME is never read."""
    env = os.environ if env is None else env
    name = env.get("QROSETTA_PROJECT", "").strip() or DEFAULT_PROJECT
    if not _PROJECT_NAME.fullmatch(name):
        raise CliError(f"QROSETTA_PROJECT={name!r} is not a compose project name "
                       "(lowercase letters, digits, '-' and '_', starting with a letter or digit).")
    return name


def compose_files(project_dir):
    """The compose file in project_dir and its override file, if any."""
    for base in _BASE_FILES:
        path = os.path.join(project_dir, base)
        if os.path.isfile(path):
            stem, ext = os.path.splitext(base)
            override = os.path.join(project_dir, f"{stem}.override{ext}")
            return [path] + ([override] if os.path.isfile(override) else [])
    raise CliError(f"No compose file in {project_dir}.")


def child_env(project, base=None):
    """The environment for compose and safe_boot.sh: no COMPOSE_* variable from the caller (they
    could name another project or file); this project set explicitly."""
    base = os.environ if base is None else base
    env = {k: v for k, v in base.items() if not k.startswith("COMPOSE_")}
    env["QROSETTA_PROJECT"] = project
    env["PODMAN_COMPOSE_WARNING_LOGS"] = "false"
    return env


class Engine:
    """Runs engine and compose commands in the project directory. Every compose call names the
    project (-p) and the compose files (-f) explicitly.

    Captured commands run in their own session, so a Ctrl-C at the terminal reaches only this
    process, which decides what to stop."""

    def __init__(self, name, project_dir, project=None, run=subprocess.run,
                 popen=subprocess.Popen, env=None):
        self.name = name
        self.project_dir = project_dir
        self.project = project or project_name(env)
        self.files = compose_files(project_dir)
        self._run = run
        self._popen = popen
        self.env = child_env(self.project, env)

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
            raise CliError(f"{cmd[0]} not found: {exc}") from exc
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            raise CliError(f"`{' '.join(cmd[:4])} ...` failed: {detail[-1] if detail else 'no output'}")
        return result

    def spawn(self, args, own_session=True, compose=True):
        """Start a command whose output goes straight to this terminal."""
        cmd = self.compose_args(*args) if compose else [self.name, *args]
        return self._popen(cmd, cwd=self.project_dir, env=self.env, start_new_session=own_session)

    def check_compose(self):
        """Fail unless `<engine> compose` is Docker Compose v2, which `config --format json` needs."""
        out = self.compose("version")
        text = (out.stdout + out.stderr).strip()
        if out.returncode != 0 or "docker compose" not in text.lower():
            raise CliError(
                f"qrosetta needs Docker Compose v2, and `{self.name} compose version` printed: "
                f"{text.splitlines()[0] if text else 'nothing'}. " + COMPOSE_INSTALL)
