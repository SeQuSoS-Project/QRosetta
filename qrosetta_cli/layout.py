"""The terminal layout of checks (doctor, start's pre-checks, selftest) and of errors that carry
evidence: one row per check with a mark (a UTF-8 terminal) or the word PASS, FAIL, WARN or INFO
(anything else), a count sentence, the fixes numbered in the order to apply them, each a
sentence over an indented command block, and the next command to run."""

import re

from qrosetta_cli import output

MARKS = {"PASS": "✓", "FAIL": "✗", "WARN": "!", "INFO": "·", "SKIP": "–"}
SGR = {"PASS": "32", "FAIL": "31", "WARN": "33", "INFO": "2", "SKIP": "2"}
COMMANDS = frozenset(
    {"qrosetta", "sudo", "systemctl", "podman", "docker", "chmod", "mkdir", "printf", "export", "pip", "pipx", "curl"}
)
FIX_INDENT = 7


def label(check_id):
    """The printed name of a check id: podman_socket -> podman socket."""
    return check_id.replace("_", " ")


def mark(status, stream=None, marks=None, color=None):
    """The status as a mark or word, coloured when the stream takes colour."""
    marks = output.use_marks(stream) if marks is None else marks
    color = output.use_color(stream) if color is None else color
    text = MARKS.get(status, status) if marks else status
    if color and status in SGR:
        return f"\033[{SGR[status]}m{text}\033[0m"
    return text


def rows(items, stream=None, marks=None, color=None):
    """Lines for (status, label, message) items, labels aligned. With marks: two spaces, the
    mark, two spaces; with words: the word padded to four, as the rows have always printed."""
    marks = output.use_marks(stream) if marks is None else marks
    color = output.use_color(stream) if color is None else color
    items = list(items)
    width = max((len(lab) for _, lab, _ in items), default=0)
    lines = []
    for status, lab, message in items:
        shown = mark(status, marks=marks, color=color)
        pad = "" if marks else " " * max(4 - len(status), 0)
        column = f"{lab:<{width}}  " if width else ""
        head = ("  " if marks else "") + shown + pad + "  " + column
        indent = " " * ((5 if marks else max(len(status), 4) + 2) + len(column))
        text = str(message).splitlines() or [""]
        lines.append((head + text[0]).rstrip())
        lines += [indent + line for line in text[1:]]
    return lines


def is_command(line):
    """Whether a fix line is a command to type (starts with a known program or a path)."""
    word = line.strip().split(" ", 1)[0]
    return word in COMMANDS or word.startswith(("~/", "/", "./"))


def sentence(text, colon=False):
    """`text` with a capital first letter and a final '.' (':' when a command block follows)."""
    text = text.strip().rstrip(".:;")
    if not text:
        return ""
    return text[0].upper() + text[1:] + (":" if colon else ".")


_TRAILING_NOTE = re.compile(r"^(.*?\S)\s+\(([^()]*)\)$")


def parts(fix):
    """[(sentence, [commands])] from a fix text: each prose line starts a part and the command
    lines after it belong to it; 'prose: command' splits at the colon; a command's trailing
    parenthesis is moved into its sentence."""
    out: list = []
    for raw in (fix or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        head, sep, tail = line.partition(": ")
        if is_command(line):
            found = _TRAILING_NOTE.match(line)
            command, note = (found.group(1), found.group(2)) if found else (line, "")
            if not out:
                out.append([sentence(note, colon=True) if note else "Run:", []])
            out[-1][1].append(command)
        elif sep and is_command(tail):
            out.append([sentence(head, colon=True), [tail]])
        else:
            out.append([sentence(line), []])
    for part in out:
        if part[1] and not part[0].endswith(":"):
            part[0] = part[0][:-1] + ":"
    return [(s, c) for s, c in out]


def numbered(items):
    """Lines for numbered fixes: each fix is [(sentence, [commands])]; a blank line between fixes."""
    lines: list[str] = []
    for n, fix in enumerate(items, 1):
        if lines:
            lines.append("")
        for i, (text, commands) in enumerate(fix):
            lines.append((f"  {n}. " if i == 0 else " " * (len(str(n)) + 4)) + text)
            lines += [" " * FIX_INDENT + c for c in commands]
    return lines


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def count_sentence(failed, warned, again=None):
    """'1 check failed.', '2 checks failed, 1 warning.', 'No check failed, 1 warning.' or
    'No check failed.'; with failures and `again`, how to check again."""
    head = f"{plural(failed, 'check')} failed" if failed else "No check failed"
    text = head + (f", {plural(warned, 'warning')}" if warned else "") + "."
    if failed and again:
        text += f" Resolve {'it' if failed == 1 else 'them'}, then run `{again}` again."
    return text


def next_step(command, pending=False):
    return f"Next step{' once all checks pass' if pending else ''}:  {command}"


def fixes(checks, order):
    """The fixes of the FAIL and WARN checks, in the order of their ids in `order` (others after
    them, in report order), each once: a check's `steps`, else its `fix` text split by `parts`."""
    rank = {cid: i for i, cid in enumerate(order)}
    todo = [c for c in checks if c.status in ("FAIL", "WARN") and (c.fix or getattr(c, "steps", None))]
    todo.sort(key=lambda c: rank.get(c.id, len(rank)))
    found, seen = [], set()
    for c in todo:
        fix = getattr(c, "steps", None) or parts(c.fix)
        if fix and repr(fix) not in seen:
            seen.add(repr(fix))
            found.append(fix)
    return found


def check_rows(checks, stream=None):
    return rows(((c.status, label(c.id), c.message) for c in checks), stream)


def checks_report(checks, order, again, next_command=None, stream=None):
    """The lines of a check report: rows, the count sentence, the numbered fixes and the next step."""
    lines = check_rows(checks, stream)
    failed = sum(c.status == "FAIL" for c in checks)
    warned = sum(c.status == "WARN" for c in checks)
    lines += ["", count_sentence(failed, warned, again)]
    todo = fixes(checks, order)
    if todo:
        lines += [""] + numbered(todo)
    if next_command:
        lines += ["", next_step(next_command, pending=bool(failed))]
    return lines


def error_lines(headline, evidence=(), step=None, hint=None):
    """An error as what happened, the evidence (indented) and what to do: a sentence over the
    command, which stays the last line."""
    lines = [f"qrosetta: {headline}"]
    if evidence:
        lines += [""] + ["  " + line if line else "" for line in evidence]
    if hint:
        if step:
            lines += ["", step, "  " + hint]
        else:
            lines.append(hint)
    return lines


_STEPS = (
    (r"^qrosetta doctor$", "Check this computer:"),
    (r"^qrosetta status$", "List the services and their state:"),
    (r"^qrosetta logs api ", "Read the API's log:"),
    (r"^qrosetta logs (\S+) ", "Read the log of {0}:"),
    (r"^qrosetta start -d --bind ", "Start on another port:"),
    (r"^qrosetta start -d --no-cpu-quota$", "Or start without the CPU quota (results record it):"),
    (r"^qrosetta start --allow-emulation$", "Start under emulation (results record it):"),
    (r"^qrosetta (\S+) (--yes|--force)$", "To {0} anyway (the server records it):"),
    (r"^qrosetta pull ", "Pull them:"),
    (r"^qrosetta build ", "Build them:"),
    (r"^\S+ rmi .* && qrosetta build ", "Remove the cached images and build again:"),
    (r"^qrosetta images load ", "Load the images from the release's image archives:"),
    (r"^qrosetta images verify", "Check the images:"),
    (r"^systemctl --user enable --now podman\.socket$", "Start podman's API socket:"),
    (r"^sudo usermod -aG docker ", "Give your user access to Docker (root-equivalent), then reboot:"),
    (r"^sudo usermod --add-subuids ", "Give your user subordinate UID and GID ranges:"),
    (r"^(docker|podman) (rm|network rm) ", "Remove them (qrosetta does not):"),
    (r"^qrosetta selftest --backends ", "Test fewer backends:"),
    (r"^qrosetta show summary$", "Read the jobs' summaries:"),
)


def step_for(hint):
    """The sentence printed over an error's command: what running it does."""
    for pattern, text in _STEPS:
        found = re.match(pattern, hint or "")
        if found:
            return text.format(*found.groups())
    return "Run:"
