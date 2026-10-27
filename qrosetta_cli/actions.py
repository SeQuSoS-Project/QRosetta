"""Stop (standby) and remove: what each leaves behind, and the confirmation that --data needs."""

import os
import re
import sys

from qrosetta_cli.engine import CliError
from qrosetta_cli import stack as st

DATA_CONFIRMATION = "delete"


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
    """Stop every running container of the stack and its pods; containers, images and data stay.
    Returns the containers still running afterwards."""
    containers = st.find_containers(engine, stack)
    running = [c for c in containers if c.running]
    if running:
        say(f"Stopping {len(running)} containers...")
        engine.cli("stop", *[c.name for c in running])
    pods = st.find_pods(engine, st.projects_of(stack, containers), containers)
    if pods:
        engine.cli("pod", "stop", *pods)
    left = [c for c in st.find_containers(engine, stack) if c.running]
    others = sorted({c.project for c in running if c.project != stack.name})
    if others:
        say(f"Also stopped containers of compose project(s) {', '.join(others)}, which use the same names.")
    if not running:
        say("Nothing was running.")
    return left


def report_left(left, stack):
    if left:
        say(f"Still running: {', '.join(c.name for c in left)}")
        say("Run `qrosetta stop` again, or stop them with your container engine.")
    return 1 if left else 0


def image_plan(engine, stack, projects):
    """Images named after the stack's services in each project, and the bytes their removal frees
    (an image that also carries another tag is only untagged)."""
    refs = [stack.image_for(s, p) for p in projects for s in stack.services]
    found = st.find_images(engine, refs)
    names = {st.normalise_tag(r) for r in found}
    removing = {t for img in found.values() for t in img.tags if st.normalise_tag(t) in names}
    freed, kept, seen = 0, [], set()
    for img in found.values():
        if img.id in seen:
            continue
        seen.add(img.id)
        if set(img.tags) <= removing:
            freed += img.size
        else:
            kept.append(img)
    return found, freed, kept


def confirm_data(volumes, sizes, ask=input, tty=None):
    """Ask the user to type DATA_CONFIRMATION after naming every volume and what it holds."""
    tty = sys.stdin.isatty() if tty is None else tty
    say("--data deletes these volumes:")
    for vol in volumes:
        say(f"  {vol.name} ({human_bytes(sizes.get(vol.name))}, project {vol.project or '?'})")
    say("They hold the local database (accounts, saved circuits, run history) and the saved run reports.")
    if not tty:
        raise CliError("--data needs a terminal to confirm; nothing was deleted.")
    try:
        answer = ask(f"Type '{DATA_CONFIRMATION}' to delete them, anything else to keep them: ")
    except EOFError:
        answer = ""
    return answer.strip() == DATA_CONFIRMATION


def remove_stack(engine, stack, images=False, data=False, ask=input, tty=None):
    """Remove containers, pods and networks; with images/data also the images and volumes.
    Returns an exit status."""
    containers = st.find_containers(engine, stack)
    projects = st.projects_of(stack, containers)
    volumes = st.find_volumes(engine, stack) if data else []
    if data and volumes and not confirm_data(volumes, volume_sizes(engine), ask, tty):
        say("Kept the data volumes; nothing was removed.")
        return 1
    running = [c for c in containers if c.running]
    if running:
        say(f"Stopping {len(running)} containers...")
        engine.cli("stop", *[c.name for c in running])
    if containers:
        say(f"Removing {len(containers)} containers...")
        engine.cli("rm", "-f", *[c.name for c in containers])
    pods = st.find_pods(engine, projects, containers)
    if pods:
        engine.cli("pod", "rm", "-f", *pods)
    nets = st.find_networks(engine, projects)
    if nets:
        engine.cli("network", "rm", *nets)
    status = 0
    if images:
        found, freed, kept = image_plan(engine, stack, projects)
        if found:
            say(f"Removing {len(found)} images, about {human_bytes(freed)}.")
            for img in kept:
                other = [t for t in img.tags if st.normalise_tag(t) != st.normalise_tag(img.ref)]
                say(f"  {img.ref} is also tagged {', '.join(other)}; only its name is removed.")
            out = engine.cli("rmi", *found)
            if out.returncode != 0:
                say(out.stderr.strip())
                status = 1
    if volumes:
        out = engine.cli("volume", "rm", *[v.name for v in volumes])
        if out.returncode != 0:
            say(out.stderr.strip())
            status = 1
    left = st.find_containers(engine, stack)
    if left:
        say(f"Not removed: {', '.join(c.name for c in left)}")
        return 1
    kept_what = [w for w, flag in (("images", images), ("data", data)) if not flag]
    say(f"Removed containers, pods and networks{'; kept ' + ' and '.join(kept_what) if kept_what else ''}.")
    return status
