"""Structural checks on submitted OpenQASM 2.0 text: characters, header, declarations,
register indices and gate names, each reported with its line number."""

import difflib
import re
import unicodedata

from fastapi import HTTPException
from qrosetta_commons.qelib1 import qelib1_definitions

_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_HEADER_RE = re.compile(r"^OPENQASM\s+2(\.0)?$")
_INCLUDE_RE = re.compile(r'^include\s+"([^"]*)"$')
_REG_RE = re.compile(r"^(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")
_DEF_RE = re.compile(r"^(gate|opaque)\s+([A-Za-z_]\w*)")
_OP_RE = re.compile(r"^(?:if\s*\(\s*([A-Za-z_]\w*)\s*==\s*\d+\s*\)\s*)?([A-Za-z_]\w*)")
_REF_RE = re.compile(r"([A-Za-z_]\w*)\s*(?:\[\s*(\d+)\s*\])?")
_BUILTINS = {"U", "CX"}
_NON_GATES = {"measure", "reset", "barrier"}
_KINDS = {"qreg": "quantum register", "creg": "classical register",
          "gate": "gate", "opaque": "opaque gate"}
_ALIASES = {"cnot": "cx", "toffoli": "ccx", "fredkin": "cswap", "phase": "p", "cphase": "cp",
            "i": "id", "identity": "id"}


def _bad_request(detail: str):
    raise HTTPException(status_code=400, detail=detail)


def _blank_comments(qasm: str) -> str:
    """``qasm`` with every comment character replaced by a space; newlines are kept, so
    offsets, lines and columns are those of the submitted text."""
    return _COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), qasm)


def _line(code: str, offset: int) -> int:
    return code.count("\n", 0, offset) + 1


def _statements(code: str):
    """``(offset, text)`` for each top-level statement; a gate definition is one item that
    includes its body. ``offset`` is that of the first non-space character."""
    depth, start = 0, 0
    for i, ch in enumerate(code):
        end = None
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
            end = i + 1 if depth == 0 else None
        elif ch == ";" and depth == 0:
            end = i
        if end is not None:
            text = code[start:end]
            if text.strip():
                yield start + len(text) - len(text.lstrip()), text.strip()
            start = i + 1


def check_ascii(qasm: str) -> None:
    """400 naming the line, column and Unicode name of the first non-ASCII character outside
    a comment."""
    code = _blank_comments(qasm)
    for i, ch in enumerate(code):
        if ord(ch) > 127:
            line = _line(code, i)
            column = i - (code.rfind("\n", 0, i) + 1) + 1
            name = unicodedata.name(ch, "unnamed character")
            _bad_request(
                f"Line {line}, column {column}: character U+{ord(ch):04X} ({name}) is not "
                f"allowed. OpenQASM 2.0 programs use ASCII characters only (outside comments); "
                f"replace it, for example with a plain space or letter.")


def _suggestion(name: str, known: set) -> str:
    guess = _ALIASES.get(name.lower())
    if guess is None and name.lower() in known:
        guess = name.lower()
    if guess is None:
        close = difflib.get_close_matches(name, sorted(known), n=1, cutoff=0.8)
        guess = close[0] if close else None
    return f" Did you mean '{guess}'? Gate names are case-sensitive." if guess in known else ""


def _check_header(code: str, items: list) -> None:
    if not items or not _HEADER_RE.match(" ".join(items[0][1].split())):
        _bad_request("The circuit must start with the header 'OPENQASM 2.0;' (comments may come "
                     "before it), usually followed by 'include \"qelib1.inc\";'.")
    for offset, text in items[1:]:
        if text.startswith("OPENQASM"):
            _bad_request(f"Line {_line(code, offset)}: the 'OPENQASM' header appears a second "
                         f"time; it may only be the first statement.")


def _check_call(code, offset, text, op, known, included, where=""):
    if op in known or op in _NON_GATES:
        return
    line = _line(code, offset)
    if op in qelib1_definitions() and not included:
        _bad_request(f"Line {line}: gate '{op}'{where} is defined in qelib1.inc, which the "
                     f"circuit does not include; add 'include \"qelib1.inc\";' after the header.")
    _bad_request(f"Line {line}: unknown gate '{op}'{where}. It is not defined in the circuit"
                 f"{' or in qelib1.inc' if included else ''}.{_suggestion(op, known)}")


def _check_operands(code, offset, args, registers, condition):
    line = _line(code, offset)
    if condition is not None:
        if registers.get(condition, ("",))[0] != "creg":
            _bad_request(f"Line {line}: the condition of 'if' names '{condition}', which is not "
                         f"a declared classical register.")
    for m in _REF_RE.finditer(args):
        name, index = m.group(1), m.group(2)
        if name not in registers:
            _bad_request(f"Line {line}: '{name}' is not a declared register.")
        kind, size = registers[name]
        if index is not None and int(index) >= size:
            noun = "qubit" if kind == "qreg" else "bit"
            _bad_request(f"Line {line}: {name}[{index}] is outside the declared register '{name}', which has "
                         f"{size} {noun}{'s' if size != 1 else ''} (indices 0 to {size - 1}).")


def _operands(text: str, start: int) -> str:
    """The operand list of a statement whose operation name ends at ``start``."""
    rest = text[start:].lstrip()
    if rest.startswith("("):
        depth = 0
        for k, ch in enumerate(rest):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0:
                return rest[k + 1:]
    return rest


def check_structure(qasm: str) -> None:
    """Nothing for a circuit with no qreg (the qubit check reports it). Otherwise 400 for a
    missing or repeated header, a name declared twice (registers, gates and
    opaque gates share one namespace), a register index outside its register, an operand
    that is not a declared register, or a call of a gate that neither the circuit nor an
    included qelib1.inc defines."""
    code = _blank_comments(qasm)
    items = list(_statements(code))
    if not any(_REG_RE.match(" ".join(t.split())) and t.startswith("qreg") for _, t in items):
        return
    _check_header(code, items)
    included = any(_INCLUDE_RE.match(" ".join(t.split())) and "qelib1.inc" in t for _, t in items)
    known = set(_BUILTINS) | (set(qelib1_definitions()) if included else set())
    declared, registers = {}, {}
    for offset, text in items[1:]:
        flat = " ".join(text.split())
        reg, definition = _REG_RE.match(flat), _DEF_RE.match(flat)
        if not (reg or definition):
            continue
        kind, name = (reg or definition).group(1), (reg or definition).group(2)
        line = _line(code, offset)
        if name in declared:
            first_kind, first_line = declared[name]
            _bad_request(
                f"Line {line}: '{name}' is already declared as a {_KINDS[first_kind]} on line "
                f"{first_line}. Registers and gates share one set of names in OpenQASM 2.0, so "
                f"each name can be declared once; rename one of them.")
        declared[name] = (kind, line)
        if reg:
            registers[name] = (kind, int(reg.group(3)))
            continue
        if kind == "gate" and "{" in text:
            body = text[text.index("{") + 1:text.rindex("}")]
            body_offset = offset + text.index("{") + 1
            for inner_offset, inner in _statements(body):
                op = _OP_RE.match(inner)
                if op:
                    _check_call(code, body_offset + inner_offset, inner, op.group(2), known,
                                included, where=f" (inside the definition of '{name}')")
        known.add(name)
    for offset, text in items[1:]:
        flat = " ".join(text.split())
        if _REG_RE.match(flat) or _DEF_RE.match(flat) or _INCLUDE_RE.match(flat):
            continue
        op = _OP_RE.match(flat)
        if not op:
            continue
        _check_call(code, offset, flat, op.group(2), known, included)
        args = _operands(flat, op.end())
        if op.group(2) == "measure":
            args = args.replace("->", ",")
        _check_operands(code, offset, args, registers, op.group(1))
