"""Container engine detection (docker or podman) and the subprocess calls made through it."""

import os
import shutil
import subprocess


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


class Engine:
    """Runs engine and compose commands in the project directory.

    Captured commands run in their own session, so a Ctrl-C at the terminal reaches only this
    process, which decides what to stop."""

    def __init__(self, name, project_dir, project_name=None, run=subprocess.run,
                 popen=subprocess.Popen):
        self.name = name
        self.project_dir = project_dir
        self.project_name = project_name
        self._run = run
        self._popen = popen
        self.env = dict(os.environ)
        if name == "podman":
            self.env["PODMAN_COMPOSE_WARNING_LOGS"] = "false"

    def compose_args(self, *args):
        base = [self.name, "compose"]
        if self.project_name:
            base += ["-p", self.project_name]
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
                f"`{self.name} compose` is not Docker Compose v2 ({text.splitlines()[0] if text else 'no output'}). "
                "Install the docker-compose v2 plugin; podman uses it as its compose provider.")
