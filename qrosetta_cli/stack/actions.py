"""Stop (standby) and remove: what each leaves behind, and the confirmation that --data needs."""

import re

from qrosetta_cli import output
from qrosetta_cli.errors import CliError, Exit
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import ownership as own

STANDBY_HINT = "On standby: containers, images and data are kept. `qrosetta start` restarts it; `qrosetta remove` removes it."


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


def stop_stack(engine, stack, quiet=False):
    """Stop this stack's running containers and pods; containers, images and data stay.
    Returns the containers still running afterwards (this stack's, and unlabelled ones of the
    project that qrosetta does not stop)."""
    found = own.scan(engine, stack)
    running = [c for c in found.containers if c.running]
    if running:
        progress(f"Stopping {len(running)} containers...")
        out = own.act(engine, "container", "stop", [c.target for c in running])
        if out is not None and out.returncode != 0:
            progress(out.stderr.strip())
    own.act(engine, "pod", "stop", found.pods)
    after = own.scan(engine, stack)
    if not running:
        result("Nothing of this stack was running.")
    elif after.containers and not after.running():
        result(STANDBY_HINT)
    for line in own.leftovers(engine, after, found.shared_pods):
        progress(line)
    return after.running()


def report_left(left):
    """Exit 16 when containers still run after stop or remove."""
    if left:
        raise CliError(f"Still running: {', '.join(c.name for c in left)}.", Exit.ENGINE, "still_running",
                       hint="qrosetta status")
    return 0


def confirm_data(volumes, sizes, project, given=None, ask=None, tty=False):
    """True when the user named the compose project, with --confirm or at a prompt on a terminal."""
    label = f"Quantum Rosetta's compose project `{project}`"
    progress(f"--data deletes the data volumes of {label}:")
    for vol in volumes:
        progress(f"  {vol.name} ({human_bytes(sizes.get(vol.name))})")
    progress("They hold the local database (accounts, saved circuits, run history) and the saved run reports.")
    if given is not None:
        if given == project:
            return True
        raise CliError(f"--confirm {given!r} does not name {label}; nothing was deleted.", Exit.USAGE,
                       "confirmation_mismatch", hint=f"qrosetta remove --data --confirm {project}")
    if not tty:
        raise CliError(f"--data needs --confirm {project} without a terminal; nothing was deleted.", Exit.USAGE,
                       "confirmation_needed", hint=f"qrosetta remove --data --confirm {project}")
    answer = (ask or output.prompt)(f"Type the name of {label} ({project}) to delete them: ")
    if (answer or "").strip() == project:
        return True
    raise CliError("The name did not match; nothing was removed.", Exit.USAGE, "confirmation_mismatch",
                   hint=f"qrosetta remove --data --confirm {project}")


def remove_stack(engine, stack, images=False, data=False, confirm=None, ask=None, tty=False):
    """Remove this stack's containers, pods and networks; with images/data also its images and
    volumes. Returns an exit status."""
    found = own.scan(engine, stack)
    volumes = found.volumes if data else []
    if volumes:
        confirm_data(volumes, volume_sizes(engine), stack.name, confirm, ask, tty)
    running = [c for c in found.containers if c.running]
    if running:
        progress(f"Stopping {len(running)} containers...")
        own.act(engine, "container", "stop", [c.target for c in running])
    if found.containers:
        progress(f"Removing {len(found.containers)} containers...")
        own.act(engine, "container", "remove", [c.target for c in found.containers])
    own.act(engine, "pod", "remove", found.pods)
    own.act(engine, "network", "remove", found.networks)
    failures = []
    if images:
        owned, refused = own.image_scan(engine, stack)
        if owned:
            progress(f"Removing {len(owned)} images, {human_bytes(sum(t.size for t in owned))}.")
            out = own.act(engine, "image", "remove", owned)
            if out.returncode != 0:
                progress(out.stderr.strip())
                failures.append("images")
        if refused:
            progress("Images qrosetta does not remove:")
            for ref, reason, _ in refused:
                progress(f"  {ref} {reason}")
            built = [ref for ref, _, mine in refused if mine]
            if built:
                progress(f"To remove the names this stack builds yourself: {engine.name} rmi {' '.join(built)}")
    if volumes:
        out = own.act(engine, "volume", "remove", volumes)
        if out.returncode != 0:
            progress(out.stderr.strip())
            failures.append("data volumes")
    after = own.scan(engine, stack)
    if after.containers:
        failures.append("containers " + ", ".join(c.name for c in after.containers))
    for line in own.leftovers(engine, after, found.shared_pods):
        progress(line)
    if failures:
        raise CliError(f"Not removed: {'; '.join(failures)}.", Exit.ENGINE, "remove_failed", hint="qrosetta status")
    kept_what = [w for w, flag in (("images", images), ("data", data)) if not flag]
    result(f"Removed this stack's containers, pods and networks"
           f"{'; kept ' + ' and '.join(kept_what) if kept_what else ''}.")
    return 0
