"""Qiskit's qelib1.inc (qelib1_qiskit.inc, copied verbatim from Qiskit 2.5.2, Apache-2.0) and
insertion of its definitions for the gates a parser lacks."""

import functools
import re
from pathlib import Path

from qrosetta_commons.helpers import strip_qasm_comments

QELIB1_SOURCE = "qiskit/qasm/libs/qelib1.inc of Qiskit 2.5.2"
_PATH = Path(__file__).with_name("qelib1_qiskit.inc")
_KEYWORDS = frozenset({"OPENQASM", "include", "qreg", "creg", "gate", "opaque", "measure",
                       "barrier", "reset", "if", "U", "CX"})
_GATE_DEF = re.compile(r"gate\s+(\w+)\s*(?:\([^)]*\))?\s*[^{]*\{([^}]*)\}")
_STATEMENT_NAME = re.compile(r"(?:^|[;{}])\s*(?:if\s*\([^)]*\)\s*)?([A-Za-z_]\w*)")
_INCLUDE = re.compile(r'include\s+"qelib1\.inc"\s*;')


@functools.lru_cache(maxsize=None)
def qelib1_definitions() -> dict:
    """Gate name -> definition text (comments removed), in the file's order."""
    text = strip_qasm_comments(_PATH.read_text())
    return {m.group(1): " ".join(m.group(0).split()) for m in _GATE_DEF.finditer(text)}


def called_names(text: str) -> set:
    """Names of the gates called in ``text`` (top level and inside gate bodies)."""
    return {name for name in _STATEMENT_NAME.findall(text) if name not in _KEYWORDS}


def add_qelib1_definitions(qasm: str, missing, builtin_rewrites=None):
    """(qasm, names): ``qasm`` with qelib1.inc's definitions of the gates in ``missing`` that
    it calls and does not define itself, and of the gates in ``missing`` those definitions
    call, inserted after the include line in dependency order. ``builtin_rewrites`` maps a
    builtin the parser lacks to the qelib1 gate with the same matrix (``{"U": "u3"}``: qelib1
    defines u3 as U), applied to the inserted text only. Unchanged when nothing is missing
    or the circuit has no ``include "qelib1.inc";``."""
    text = strip_qasm_comments(qasm)
    defined = {m.group(1) for m in _GATE_DEF.finditer(text)}
    library = qelib1_definitions()
    missing = set(missing)
    order = []

    def visit(name):
        if name in order or name in defined or name not in missing or name not in library:
            return
        for dependency in sorted(called_names(library[name].split("{", 1)[1])):
            visit(dependency)
        order.append(name)

    for name in sorted(called_names(text)):
        visit(name)
    match = _INCLUDE.search(qasm)
    if not order or match is None:
        return qasm, []
    definitions = [library[name] for name in order]
    for builtin, replacement in (builtin_rewrites or {}).items():
        pattern = re.compile(rf"(?<![\w.]){re.escape(builtin)}(?=\s*[(\s])")
        definitions = [d if d.startswith(f"gate {replacement}") else pattern.sub(replacement, d)
                       for d in definitions]
    return qasm[:match.end()] + "\n" + "\n".join(definitions) + qasm[match.end():], order


def renamed_qelib1_definitions(qasm: str, names, prefix: str = "qelib1_"):
    """(qasm, {name: new name}): like ``add_qelib1_definitions`` for the gates in ``names``,
    for a parser that knows those names but reads them differently from qelib1.inc. Each
    inserted definition and every call of it (top level and inside gate bodies) is renamed
    ``prefix + name`` (more underscores when the circuit already uses that name), so the
    parser reads the qelib1.inc definition as a gate defined in the circuit."""
    text, added = add_qelib1_definitions(qasm, names)
    if not added:
        return qasm, {}
    used = set(re.findall(r"[A-Za-z_]\w*", strip_qasm_comments(qasm)))
    while any(prefix + name in used for name in added):
        prefix += "_"
    renames = {name: prefix + name for name in added}
    pattern = re.compile(r"(?<![\w.])(" + "|".join(map(re.escape, added)) + r")(?=\s*[(\s])")
    return pattern.sub(lambda m: renames[m.group(1)], text), renames
