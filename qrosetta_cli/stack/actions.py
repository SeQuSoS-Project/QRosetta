"""Stop (standby) and remove: what each leaves behind, and the confirmation that --data needs."""

import os
import re
import sys

from qrosetta_cli import ownership as own
from qrosetta_cli.engine import CliError

DATA_CONFIRMATION = "delete"
STANDBY_HINT = "On standby: containers, images and data are kept. `qrosetta start` restarts it; `qrosetta remove` removes it."


def say(*parts):
    """Print; once the terminal has gone away (VS Code closing the panel), send output to /dev/null."""
    try:
        print(*parts, flush=True)
    except (OSError, ValueError, RuntimeError):
        discard_output()


def discard_output():
    """Point stdout and stderr at /dev/null, so writes and the flush at exit cannot fail."""
    try:
        null = os.open(os.devnull, os.O_WRONLY)
        for stream in (sys.stdout, sys.stderr):
            os.dup2(null, stream.fileno())
    except (OSError, ValueError):
        pass


def human_bytes(n):
    """Binary units (KiB, MiB, GiB), as compose memory limits are."""
    if n is None:
        return "?"
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TiB"


_UNITS = {"b": 1, "kb": 1e3, "kib": 1024, "mb": 1e6, "mib": 1024 ** 2, "gb": 1e9,
          "gib": 1024 ** 3, "tb": 1e12, "tib": 1024 ** 4}


def parse_size(text):
    """Bytes in a size such as '34.48MB', '1.2GiB' or '512kB'; None if unreadable."""
    m = re.fullmatch(r"\s*([\d.]+)\s*([a-zA-Z]*)\s*", text or "")
    if not m:
        return None
    unit = (m.group(2) or "b").lower()
    if unit not in _UNITS:
        return None
    return int(float(m.group(1)) * _UNITS[unit])


def volume_sizes(engine):
    """Volume name -> bytes, from the 'Local Volumes space usage' table of `system df -v`."""
    lines = iter(engine.cli("system", "df", "-v").stdout.splitlines())
    for line in lines:
        if line.strip().lower().startswith("local volumes space usage"):
            break
    sizes = {}
    for line in lines:
        cols = line.split()
        if not cols:
            if sizes:
                break
            continue
        if line.rstrip().endswith(":"):
            break
        size = parse_size(cols[-1])
        if cols[0] != "VOLUME" and size is not None:
            sizes[cols[0]] = size
    return sizes


def stop_stack(engine, stack):
    """Stop this stack's running containers and pods; containers, images and data stay.
    Returns the containers still running afterwards (this stack's, and unlabelled ones of the
    project that qrosetta does not stop)."""
    found = own.scan(engine, stack)
    running = [c for c in found.containers if c.running]
    if running:
        say(f"Stopping {len(running)} containers...")
        own.act(engine, "container", "stop", [c.target for c in running])
    own.act(engine, "pod", "stop", found.pods)
    if not running:
        say("Nothing of this stack was running.")
    after = own.scan(engine, stack)
    if after.containers and not after.running():
        say(STANDBY_HINT)
    for line in own.leftovers(engine, after, found.shared_pods):
        say(line)
    return after.running()


def report_left(left, stack):
    if left:
        say(f"Still running: {', '.join(c.name for c in left)}")
    return 1 if left else 0


def confirm_data(volumes, sizes, ask=None, tty=None):
    """Ask the user to type DATA_CONFIRMATION after naming every volume and what it holds."""
    tty = sys.stdin.isatty() if tty is None else tty
    ask = ask or input
    say("--data deletes these volumes:")
    for vol in volumes:
        say(f"  {vol.name} ({human_bytes(sizes.get(vol.name))})")
    say("They hold the local database (accounts, saved circuits, run history) and the saved run reports.")
    if not tty:
        raise CliError("--data needs a terminal to confirm; nothing was deleted.")
    try:
        answer = ask(f"Type '{DATA_CONFIRMATION}' to delete them, anything else to keep them: ")
    except EOFError:
        answer = ""
    return answer.strip() == DATA_CONFIRMATION


def remove_stack(engine, stack, images=False, data=False, ask=None, tty=None):
    """Remove this stack's containers, pods and networks; with images/data also its images and
    volumes. Returns an exit status."""
    found = own.scan(engine, stack)
    volumes = found.volumes if data else []
    if volumes and not confirm_data(volumes, volume_sizes(engine), ask, tty):
        say("Kept the data volumes; nothing was removed.")
        return 1
    running = [c for c in found.containers if c.running]
    if running:
        say(f"Stopping {len(running)} containers...")
        own.act(engine, "container", "stop", [c.target for c in running])
    if found.containers:
        say(f"Removing {len(found.containers)} containers...")
        own.act(engine, "container", "remove", [c.target for c in found.containers])
    own.act(engine, "pod", "remove", found.pods)
    own.act(engine, "network", "remove", found.networks)
    status = 0
    if images:
        owned, refused = own.image_scan(engine, stack)
        if owned:
            say(f"Removing {len(owned)} images, {human_bytes(sum(t.size for t in owned))}.")
            out = own.act(engine, "image", "remove", owned)
            if out.returncode != 0:
                say(out.stderr.strip())
                status = 1
        if refused:
            say("Images qrosetta does not remove:")
            for ref, reason, _ in refused:
                say(f"  {ref} {reason}")
            built = [ref for ref, _, mine in refused if mine]
            if built:
                say(f"To remove the names this stack builds yourself: {engine.name} rmi {' '.join(built)}")
    if volumes:
        out = own.act(engine, "volume", "remove", volumes)
        if out.returncode != 0:
            say(out.stderr.strip())
            status = 1
    after = own.scan(engine, stack)
    if after.containers:
        say(f"Not removed: {', '.join(c.name for c in after.containers)}")
        status = 1
    kept_what = [w for w, flag in (("images", images), ("data", data)) if not flag]
    say(f"Removed this stack's containers, pods and networks"
        f"{'; kept ' + ' and '.join(kept_what) if kept_what else ''}.")
    for line in own.leftovers(engine, after, found.shared_pods):
        say(line)
    return status
