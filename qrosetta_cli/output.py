"""Where qrosetta writes (spec P4): data to stdout; progress, prompts, warnings and errors to
stderr. Under --json stdout carries only the envelope (spec Q3)."""

import codecs
import json
import os
import select
import sys
from datetime import UTC, datetime
from typing import Any

from qrosetta_cli import __version__
from qrosetta_cli.errors import Exit

_state: dict[str, Any] = {
    "json": False,
    "warnings": [],
    "notices": set(),
    "notice_enabled": True,
    "color": "auto",
    "env": None,
}


def configure(json_mode=False, experimental_notice=True, color=None, env=None):
    """`color` is the config's [output] color (auto, always, never); `env` the environment
    NO_COLOR, CLICOLOR_FORCE and TERM are read from (os.environ when None)."""
    _state.update(
        json=bool(json_mode),
        warnings=[],
        notices=set(),
        notice_enabled=experimental_notice,
        color=(color or "auto").strip().lower() if isinstance(color, str) else "auto",
        env=env,
    )


def json_mode():
    return _state["json"]


def _isatty(stream):
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def use_marks(stream=None):
    """Whether `stream` takes the check marks (a terminal whose encoding is UTF-8); otherwise
    rows print the words PASS, FAIL, WARN and INFO."""
    stream = stream or sys.stdout
    try:
        utf8 = codecs.lookup(getattr(stream, "encoding", None) or "ascii").name == "utf-8"
    except LookupError:
        utf8 = False
    return utf8 and _isatty(stream)


def use_color(stream=None):
    """Colour on `stream`: [output] color = never, then NO_COLOR, turn it off; color = always,
    then CLICOLOR_FORCE (not 0), turn it on; TERM=dumb turns it off; otherwise on a terminal."""
    env = os.environ if _state["env"] is None else _state["env"]
    setting = _state["color"]
    if setting == "never" or env.get("NO_COLOR"):
        return False
    if setting == "always" or env.get("CLICOLOR_FORCE", "0") not in ("", "0"):
        return True
    if env.get("TERM") == "dumb":
        return False
    return _isatty(stream or sys.stdout)


def _write(stream, text):
    """Write and flush; a character the stream's encoding lacks prints as '?', and a stream
    that has gone away sends the rest of the output to /dev/null."""
    try:
        try:
            stream.write(text)
        except UnicodeEncodeError:
            encoding = getattr(stream, "encoding", None) or "ascii"
            stream.write(text.encode(encoding, "replace").decode(encoding))
        stream.flush()
    except (OSError, ValueError, RuntimeError, LookupError):
        discard_output()


def progress(*parts):
    """A progress or status line on stderr."""
    _write(sys.stderr, " ".join(str(p) for p in parts) + "\n")


def result(*parts):
    """A line of the command's result on stdout; suppressed under --json."""
    if not _state["json"]:
        _write(sys.stdout, " ".join(str(p) for p in parts) + "\n")


def raw(data):
    """Bytes or text straight to stdout (the api command's body)."""
    if isinstance(data, str):
        data = data.encode()
    try:
        sys.stdout.flush()
        out = getattr(sys.stdout, "buffer", None)
        if out is None:
            sys.stdout.write(data.decode("utf-8", "replace"))
        else:
            out.write(data)
        sys.stdout.flush()
    except (OSError, ValueError):
        discard_output()


def warn(message, reason="warning"):
    """A warning on stderr, also recorded for the envelope."""
    _state["warnings"].append({"reason": reason, "message": message})
    progress(f"qrosetta: warning: {message}")


def warnings():
    return list(_state["warnings"])


def experimental(command):
    """One stderr notice per invocation for an experimental command (spec P14)."""
    if not _state["notice_enabled"] or command in _state["notices"]:
        return
    _state["notices"].add(command)
    progress(
        f"qrosetta: `{command}` is experimental: its behaviour and JSON (schema @0) may change. "
        "[output] experimental_notice = false in the config file silences this."
    )


def prompt(question, timeout=None, stdin=None):
    """Ask on stderr and read one line from the terminal; None after `timeout` seconds or at EOF."""
    stdin = stdin or sys.stdin
    _write(sys.stderr, question)
    if timeout is not None:
        try:
            ready, _, _ = select.select([stdin], [], [], timeout)
        except (OSError, ValueError, TypeError):
            ready = [stdin]
        if not ready:
            progress(f"\nNo answer in {timeout} s.")
            return None
    line = stdin.readline()
    return line if line else None


def discard_output():
    """Point stdout and stderr at /dev/null, so writes and the flush at exit cannot fail
    once the terminal has gone away."""
    try:
        null = os.open(os.devnull, os.O_WRONLY)
        for stream in (sys.stdout, sys.stderr):
            os.dup2(null, stream.fileno())
    except (OSError, ValueError, AttributeError):
        pass


def utc_now():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope(schema, code, data=None, error=None, server=None, outcome=None):
    """The --json object (spec Q3)."""
    return {
        "schema": schema,
        "cli_version": __version__,
        "server": server,
        "ok": code == Exit.OK,
        "exit_code": int(code),
        "outcome": outcome,
        "data": data,
        "warnings": warnings(),
        "error": error,
    }


def emit_envelope(obj):
    _write(sys.stdout, json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n")
