"""Engine failures in plain language (spec §6.11): each engine message is matched against these
rows before it is printed; an unmatched one prints the engine's last line and `qrosetta doctor`."""

import os
import re
import shutil

from qrosetta_cli.errors import CliError, Exit

DEFAULT_BIND = "127.0.0.1:8080"
OTHER_BIND = "127.0.0.1:8090"
DELEGATE_DROPIN = ("sudo mkdir -p /etc/systemd/system/user@.service.d\n"
                   "printf '[Service]\\nDelegate=cpu memory pids\\n' | sudo tee /etc/systemd/system/user@.service.d/delegate.conf\n"
                   "sudo reboot")
SUBUID_FIX = "sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER && podman system migrate"


def _free_text(path):
    probe = path
    while probe and not os.path.exists(probe):
        probe = os.path.dirname(probe)
    try:
        free = shutil.disk_usage(probe or "/").free
    except OSError:
        return ""
    return f" ({probe} has {free / 1024 ** 3:.1f} GiB free)"


def _no_space(m, text, bind):
    paths = re.findall(r"(/[^\s:\"']+)", text)
    where = os.path.dirname(paths[-1]) if paths else "a disk the engine writes to"
    staging = " Podman stages image layers in /var/tmp; set TMPDIR for builds." if "/var/tmp" in where else ""
    return (f"No space left on device under {where}{_free_text(where) if paths else ''}. Images need several GiB "
            f"free in the image store.{staging}", "no_space", "qrosetta doctor")


def _name_conflict(m, text, bind):
    name = m.group(1).lstrip("/")
    return (f"Container name {name} is held by a container that is not this stack's; qrosetta never touches it.",
            "name_conflict", "qrosetta status")


ROWS = [
    (r"address already in use|port is already allocated",
     lambda m, t, b: (f"{b} is in use.", "port_in_use", f"qrosetta start -d --bind {OTHER_BIND}")),
    (r"permission denied.*docker\.sock|docker\.sock.*permission denied",
     lambda m, t, b: ("Your user cannot use Docker: `sudo usermod -aG docker $USER` (root-equivalent) and reboot, "
                      "or use rootless podman.", "docker_permission", "sudo usermod -aG docker $USER")),
    (r"podman\.sock",
     lambda m, t, b: ("Docker Compose cannot reach podman's API socket.", "podman_socket",
                      "systemctl --user enable --now podman.socket")),
    (r"cgroup controller [`'\"]?cpu[`'\"]? is not available|controller [`'\"]?cpu[`'\"]? (?:is )?not available",
     lambda m, t, b: ("The cgroup cpu controller is not delegated to your user, so CPU limits cannot be set. "
                      "Delegate it with this drop-in, then reboot:\n" + DELEGATE_DROPIN,
                      "cpu_controller_missing", "qrosetta doctor")),
    (r"newuidmap|cannot find mappings for user|insufficient UIDs or GIDs",
     lambda m, t, b: ("Your user has no subordinate UID/GID ranges, which rootless podman needs.",
                      "subuid_missing", SUBUID_FIX)),
    (r"no space left on device", _no_space),
    (r"ghcr\.io.*(manifest unknown|denied|not found)|(manifest unknown|denied|not found).*ghcr\.io",
     lambda m, t, b: ("An image was not found in the registry. In a checkout, build it instead.",
                      "image_not_in_registry", "qrosetta build")),
    (r"exec format error",
     lambda m, t, b: ("This machine is not linux/amd64; Quantum Rosetta images are linux/amd64 only.",
                      "wrong_architecture", "qrosetta doctor")),
    (r"toomanyrequests",
     lambda m, t, b: ("The registry is rate-limiting this address; try again later.", "registry_rate_limit",
                      "qrosetta doctor")),
    (r"dependency failed to start: container \S*(?:rosetta-api|api)\S* is unhealthy",
     lambda m, t, b: ("The API did not become healthy within its healthcheck window. Starting again usually "
                      "succeeds once the page cache is warm.", "api_unhealthy", "qrosetta logs api --tail 50")),
    (r"container name \"?([^\s\"]+)\"? is already in use", _name_conflict),
]

PROBE_KINDS = {
    "dns": ("the API cannot resolve {runner} on the internal network. With rootless podman, update netavark "
            "and aardvark-dns, or use Docker", "qrosetta doctor"),
    "connect": ("{runner} is not accepting connections yet; its SDK is still loading (cold start)",
                "qrosetta status"),
    "timeout": ("{runner} did not answer within 5 s", "qrosetta logs {runner} --tail 50"),
    "http": ("{runner} answered with an error", "qrosetta logs {runner} --tail 50"),
}


def explain(text, bind=None):
    """(message, reason, hint) for a known engine message, else None."""
    bind = bind or DEFAULT_BIND
    for pattern, render in ROWS:
        m = re.search(pattern, text or "", re.IGNORECASE)
        if m:
            return render(m, text, bind)
    return None


def engine_error(text, context, bind=None):
    """A CliError (exit 16) for a failed engine call."""
    known = explain(text, bind)
    if known:
        message, reason, hint = known
        return CliError(f"{context}: {message}", Exit.ENGINE, reason, hint)
    lines = [line for line in (text or "").strip().splitlines() if line.strip()]
    return CliError(f"{context}: {lines[-1] if lines else 'no output'}", Exit.ENGINE, "engine_error",
                    hint="qrosetta doctor")


def probe_message(kind, runner):
    """(message, hint) for a fresh-probe error kind."""
    text, hint = PROBE_KINDS.get(kind, ("{runner} is not available", "qrosetta status"))
    return text.format(runner=runner), hint.format(runner=runner)
