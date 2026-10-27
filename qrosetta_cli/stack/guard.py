"""Spec P10: engine actions are refused while the server reports dispatches in flight, and two
qrosetta processes never change the stack at once ($XDG_RUNTIME_DIR/qrosetta/engine.lock)."""

import os
from contextlib import contextmanager

from qrosetta_cli import config as cfgmod, output
from qrosetta_cli.errors import CliError, Exit


def in_flight(ctx, url):
    """(dispatches in flight or None, note). None with a note when the server cannot say; None
    without one when no server answers at `url` (then nothing is in flight on it)."""
    if not url:
        return None, ""
    from qrosetta_cli.client import handshake, servers
    server = servers.Server("local", url, "compose port")
    try:
        config = handshake.fetch_config(ctx.transport(server=server, timeout=5))
    except CliError as exc:
        if exc.code == Exit.UNREACHABLE:
            return None, ""
        return None, f"could not read the server's run gate ({exc.message})"
    ctx.note_handshake(handshake.server_block(config))
    gate = config.get("exclusive")
    if not isinstance(gate, dict) or "shared_running" not in gate:
        return None, "this server does not report runs in flight (GET /config has no gate state)"
    return int(gate.get("shared_running") or 0) + (1 if gate.get("exclusive_running") else 0), ""


def refuse_if_busy(ctx, url, command, flag, overridden, effect):
    """Raise exit 15 while dispatches are in flight, unless `flag` was given."""
    count, note = in_flight(ctx, url)
    if count is None:
        if note:
            output.warn(f"{note}; continuing.", "gate_unknown")
        return 0
    if count == 0:
        return 0
    if not overridden:
        raise CliError(f"{count} dispatch{'es are' if count != 1 else ' is'} in flight on this server; {effect}.",
                       Exit.BUSY, "runs_in_flight", hint=f"qrosetta {command} {flag}")
    output.warn(f"{count} dispatch{'es' if count != 1 else ''} in flight; continuing because of {flag}. The "
                f"server is told of the {command} (a host-load notice): runs beside it record it, and a run "
                "that loses its runner to a stop records stopped_by_user.", "runs_in_flight")
    return count


@contextmanager
def engine_lock(env, what):
    """Hold the engine lock for one stack-changing action; exit 15 if another qrosetta holds it."""
    try:
        import fcntl
    except ImportError:
        yield
        return
    directory = cfgmod.qr_dir("runtime", env)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    path = os.path.join(directory, "engine.lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            holder = os.pread(fd, 200, 0).decode("utf-8", "replace").strip() or "unknown"
            raise CliError(f"Another qrosetta command is changing the stack (process {holder}).", Exit.BUSY,
                           "engine_locked", hint="qrosetta status") from None
        os.ftruncate(fd, 0)
        os.pwrite(fd, f"{os.getpid()} {what}".encode(), 0)
        try:
            yield
        finally:
            os.ftruncate(fd, 0)
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
