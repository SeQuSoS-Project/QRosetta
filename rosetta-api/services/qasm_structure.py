"""Structural checks on submitted OpenQASM 2.0 text: characters, header, declarations,
register indices, gate names and the shape of each call (parameters, operands, broadcasts),
each reported with its line number."""

import difflib
import functools
import re
import unicodedata

from fastapi import HTTPException
from qrosetta_commons.qelib1 import qelib1_definitions

_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_HEADER_RE = re.compile(r"^OPENQASM\s+2\.0$")
_SHORT_HEADER_RE = re.compile(r"^OPENQASM\s+2$")
_INCLUDE_RE = re.compile(r'^include\s+"([^"]*)"$')
_REG_RE = re.compile(r"^(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")
_DEF_RE = re.compile(r"^(gate|opaque)\s+([A-Za-z_]\w*)")
_OP_RE = re.compile(r"^(?:if\s*\(\s*([A-Za-z_]\w*)\s*==\s*\d+\s*\)\s*)?([A-Za-z_]\w*)")
_OPERAND_RE = re.compile(r"^([A-Za-z_]\w*)\s*(?:\[\s*(\d+)\s*\])?$")
_SIGNATURE_RE = re.compile(r"^(?:gate|opaque)\s+[A-Za-z_]\w*\s*(?:\(([^)]*)\))?\s*([^{]*)")
_EMPTY_STATEMENT_RE = re.compile(r"(?:^|[;{}])\s*(;)")
_NAME_RE = re.compile(r"(?<![\w.])[A-Za-z_]\w*")
_LINE_OR_BLOCK_START_RE = re.compile(r"//[^\n]*|/\*")
_FUNCTIONS = {"sin", "cos", "tan", "exp", "ln", "sqrt"}
_ALLOWED_CONTROLS = {"\t", "\n", "\r"}
_CONTROL_NAMES = {"\x00": "null", "\x0b": "vertical tab", "\x0c": "form feed", "\x7f": "delete"}
_BUILTINS = {"U", "CX"}
_BUILTIN_SIGNATURES = {"U": (3, 1), "CX": (0, 2)}
_NON_GATES = {"measure", "reset", "barrier"}
_KINDS = {"qreg": "quantum register", "creg": "classical register",
          "gate": "gate", "opaque": "opaque gate"}
HEADER_MESSAGE = ("The circuit must start with the header 'OPENQASM 2.0;' (comments may come "
                  "before it), usually followed by 'include \"qelib1.inc\";'.")
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
    """400 naming the line, column and Unicode name of the first non-ASCII character or
    control character other than tab, line feed and carriage return, outside a comment."""
    code = _blank_comments(qasm)
    for i, ch in enumerate(code):
        if (ord(ch) < 32 and ch not in _ALLOWED_CONTROLS) or ord(ch) == 127:
            line = _line(code, i)
            column = i - (code.rfind("\n", 0, i) + 1) + 1
            name = _CONTROL_NAMES.get(ch, "control character")
            _bad_request(
                f"Line {line}, column {column}: control character U+{ord(ch):04X} ({name}) is "
                f"not allowed. OpenQASM 2.0 separates tokens with spaces, tabs and line breaks "
                f"only; replace it with a space.")
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
    first = " ".join(items[0][1].split()) if items else ""
    if _SHORT_HEADER_RE.match(first):
        _bad_request(f"Line {_line(code, items[0][0])}: write the version as 'OPENQASM 2.0;'; "
                     f"the simulators' parsers accept only that form.")
    if not _HEADER_RE.match(first):
        _bad_request(HEADER_MESSAGE)
    for offset, text in items[1:]:
        if text.startswith("OPENQASM"):
            _bad_request(f"Line {_line(code, offset)}: the 'OPENQASM' header appears a second "
                         f"time; it may only be the first statement.")


def _check_empty_statements(code: str) -> None:
    m = _EMPTY_STATEMENT_RE.search(code)
    if m:
        _bad_request(f"Line {_line(code, m.start(1))}: a semicolon with no statement before it; "
                     f"remove the extra ';'.")


def _split_list(text: str) -> list:
    """Comma-separated items of ``text`` at bracket depth 0, stripped; [] for blank text."""
    items, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        depth += ch in "(["
        depth -= ch in ")]"
        if ch == "," and depth == 0:
            items.append(text[start:i].strip())
            start = i + 1
    items.append(text[start:].strip())
    return [] if items == [""] else items


def _signature(flat: str) -> tuple:
    """(number of parameters, number of qubit arguments) of a gate or opaque declaration."""
    m = _SIGNATURE_RE.match(flat)
    return len(_split_list(m.group(1) or "")), len(_split_list(m.group(2)))


@functools.lru_cache(maxsize=1)
def _qelib1_signatures() -> dict:
    return {name: _signature(text) for name, text in qelib1_definitions().items()}


def _call_parts(text: str, start: int):
    """(parameter list or None, operand text) of a statement whose name ends at ``start``."""
    rest = text[start:].lstrip()
    if not rest.startswith("("):
        return None, rest
    depth = 0
    for k, ch in enumerate(rest):
        depth += ch == "("
        depth -= ch == ")"
        if depth == 0:
            return _split_list(rest[1:k]), rest[k + 1:]
    return _split_list(rest[1:]), ""


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _check_call(code, offset, text, op, known, included, where=""):
    if op in known or op in _NON_GATES:
        return
    line = _line(code, offset)
    if op in qelib1_definitions() and not included:
        _bad_request(f"Line {line}: gate '{op}'{where} is defined in qelib1.inc, which the "
                     f"circuit does not include; add 'include \"qelib1.inc\";' after the header.")
    _bad_request(f"Line {line}: unknown gate '{op}'{where}. It is not defined in the circuit"
                 f"{' or in qelib1.inc' if included else ''}.{_suggestion(op, known)}")


def _check_opaque_call(line, op, opaque, uses_opaque):
    """400 for a top-level call of an opaque gate or of a gate whose expansion calls one."""
    if op in opaque:
        _bad_request(
            f"Line {line}: '{op}' is declared 'opaque' on line {opaque[op]}, so it has no "
            f"definition and no simulator can apply it. Declare it with 'gate {op} ... "
            f"{{ ... }}' and a body instead.")
    if op in uses_opaque:
        name, call_line = uses_opaque[op]
        _bad_request(
            f"Line {line}: '{op}' calls '{name}' (line {call_line}, in its expansion), which is "
            f"declared 'opaque' on line {opaque[name]}, so it has no definition and no "
            f"simulator can apply it. Declare '{name}' with 'gate {name} ... {{ ... }}' and a "
            f"body instead.")


def _check_shape(line, op, params, operands, signatures, where=""):
    """400 for a gate call with the wrong number of parameters or operands."""
    if op in _NON_GATES:
        return
    n_params, n_qubits = signatures[op]
    given = len(params or [])
    if given != n_params or any(not p for p in params or []):
        _bad_request(f"Line {line}: '{op}'{where} takes {_plural(n_params, 'parameter')} in "
                     f"parentheses, but the call gives {given}.")
    if len(operands) != n_qubits or any(not o for o in operands):
        _bad_request(f"Line {line}: '{op}'{where} acts on {_plural(n_qubits, 'qubit')}, but the "
                     f"call lists {_plural(len([o for o in operands if o]), 'operand')} "
                     f"(operands are separated by commas).")


def _check_body_operands(line, op, operands, qubit_args, where):
    """400 for an operand inside a gate body that is not one of the gate's qubit arguments,
    or that a call names twice."""
    for i, operand in enumerate(operands):
        if operand not in qubit_args:
            _bad_request(f"Line {line}: '{operand}'{where} is not one of the gate's qubit "
                         f"arguments ({', '.join(qubit_args)}); a gate body acts on its arguments only.")
        if op != "barrier" and operand in operands[:i]:
            _bad_request(f"Line {line}: '{op}'{where} names '{operand}' twice; the qubits of "
                         f"one gate call must be different.")


def _parse_operands(line, args, registers):
    """[(register, index or None)] of a top-level operand list; 400 for an operand that is
    not 'name' or 'name[index]', or that names an undeclared register or an index outside it."""
    refs = []
    for operand in _split_list(args):
        m = _OPERAND_RE.match(operand)
        if not m:
            _bad_request(f"Line {line}: '{operand}' is not an operand; write 'name' or "
                         f"'name[index]', separated by commas.")
        name, index = m.group(1), m.group(2)
        if name not in registers:
            _bad_request(f"Line {line}: '{name}' is not a declared register.")
        kind, size = registers[name]
        if index is not None and int(index) >= size:
            noun = "qubit" if kind == "qreg" else "bit"
            _bad_request(f"Line {line}: {name}[{index}] is outside the declared register '{name}', which has "
                         f"{size} {noun}{'s' if size != 1 else ''} (indices 0 to {size - 1}).")
        refs.append((name, None if index is None else int(index)))
    return refs


def _check_top_level_operands(line, op, args, registers):
    """400 for a malformed or undeclared operand, a gate operand that is a classical
    register, a qubit named twice in one call (directly or through its whole register), or a
    broadcast over registers of different sizes."""
    if op == "measure":
        parts = args.split("->")
        refs = [] if len(parts) != 2 else [_parse_operands(line, part, registers) for part in parts]
        if len(refs) != 2 or [len(r) for r in refs] != [1, 1]:
            _bad_request(f"Line {line}: measure is written 'measure q[i] -> c[j];' or "
                         f"'measure q -> c;'.")
        (qname, qindex), (cname, cindex) = refs[0][0], refs[1][0]
        if registers[qname][0] != "qreg" or registers[cname][0] != "creg":
            _bad_request(f"Line {line}: measure reads a quantum register and writes a classical "
                         f"one ('measure q[i] -> c[j];').")
        sizes = [1 if qindex is not None else registers[qname][1],
                 1 if cindex is not None else registers[cname][1]]
        if sizes[0] != sizes[1]:
            shown = [name if index is None else f"{name}[{index}]"
                     for name, index in ((qname, qindex), (cname, cindex))]
            _bad_request(f"Line {line}: measure {shown[0]} -> {shown[1]} has operands of different "
                         f"sizes ({_plural(sizes[0], 'qubit')}, {_plural(sizes[1], 'bit')}); measure "
                         f"one qubit into one bit, or a whole register into a register of the "
                         f"same size.")
        return
    refs = _parse_operands(line, args, registers)
    for name, _ in refs:
        if registers[name][0] != "qreg":
            _bad_request(f"Line {line}: '{name}' is a classical register; '{op}' acts on qubits.")
    if op == "barrier":
        return
    for i, (name, index) in enumerate(refs):
        if any(n == name and (index is None or i_ is None or index == i_) for n, i_ in refs[:i]):
            shown = name if index is None else f"{name}[{index}]"
            _bad_request(f"Line {line}: '{op}' names {shown} more than once (directly or through "
                         f"its whole register); the qubits of one gate call must be different.")
    whole = [name for name, index in refs if index is None]
    if len({registers[name][1] for name in whole}) > 1:
        listed = ", ".join(f"{name}[{registers[name][1]}]" for name in whole)
        _bad_request(f"Line {line}: '{op}' broadcasts over registers of different sizes "
                     f"({listed}); every whole-register operand of one statement must have "
                     f"the same size.")


def _check_body_parameters(line, op, params, gate, param_names, where):
    """400 for a name in a parameter of a call inside a gate body that is neither one of the
    gate's parameters nor pi or a function name."""
    for param in params or []:
        for name in _NAME_RE.findall(param):
            if name in param_names or name == "pi" or name in _FUNCTIONS:
                continue
            listed = f"its parameters are {', '.join(sorted(param_names))}" if param_names \
                else "it has no parameters"
            _bad_request(f"Line {line}: '{name}' in the parameter '{param}' of '{op}'{where} is "
                         f"not a parameter of '{gate}' ({listed}). Parameters may use the gate's "
                         f"parameters, numbers, pi, + - * / ^ and sin/cos/tan/exp/ln/sqrt.")


def _register_name_problem(name: str):
    if "a" <= name[0] <= "z":
        return None
    suggestion = name[0].lower() + name[1:] if name[0].isalpha() else "q" + name.lstrip("_")
    return (f"register name '{name}' must start with a lowercase letter (OpenQASM 2.0 "
            f"identifiers are a lowercase letter followed by letters, digits and '_'); rename "
            f"it, for example to '{suggestion}'")


def check_block_comments(qasm: str) -> None:
    """400 naming the line of the first '/*' outside a '//' comment; OpenQASM 2.0 has line
    comments only."""
    for m in _LINE_OR_BLOCK_START_RE.finditer(qasm):
        if m.group(0) == "/*":
            _bad_request(f"Line {_line(qasm, m.start())}: '/* ... */' comments are not part of "
                         f"OpenQASM 2.0; write each comment line with '//' instead.")


def definition_line(qasm: str, name: str):
    """Line of the ``gate``/``opaque`` declaration of ``name``, or None."""
    code = _blank_comments(qasm)
    m = re.search(rf"\b(?:gate|opaque)\s+{re.escape(name)}\b", code)
    return _line(code, m.start()) if m else None


def check_structure(qasm: str) -> None:
    """Nothing for a circuit with no qreg (the qubit check reports it). Otherwise 400 for a
    missing, repeated or short-form header, an empty statement, a name declared twice
    (registers, gates and opaque gates share one namespace; it also holds U, CX and, with
    ``include "qelib1.inc"``, the qelib1 gates), a register name that does not start with a
    lowercase letter, a register or gate used before its declaration, a register index outside
    its register, a malformed operand or one that is not a declared register, a call of a gate
    that neither the circuit nor an included qelib1.inc defines, a top-level call of an opaque
    gate or of a gate whose expansion calls one, a call with the wrong number of parameters or
    qubits or a repeated qubit, a name in a gate body's parameter that is not one of the
    gate's parameters, a measure whose operands differ in size, or a broadcast over registers
    of different sizes."""
    code = _blank_comments(qasm)
    items = list(_statements(code))
    if not any(_REG_RE.match(" ".join(t.split())) and t.startswith("qreg") for _, t in items):
        return
    _check_header(code, items)
    _check_empty_statements(code)
    included = any(_INCLUDE_RE.match(" ".join(t.split())) and "qelib1.inc" in t for _, t in items)
    signatures = dict(_BUILTIN_SIGNATURES)
    if included:
        signatures.update(_qelib1_signatures())
    known = set(signatures)
    declared, registers, opaque, uses_opaque, offsets = {}, {}, {}, {}, {}
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
        if reg and name in signatures:
            source = ("a built-in gate" if name in _BUILTINS
                      else "a gate in qelib1.inc, which the circuit includes")
            _bad_request(
                f"Line {line}: '{name}' is already declared as {source}. Registers and gates "
                f"share one set of names in OpenQASM 2.0; rename the register.")
        if reg and _register_name_problem(name):
            _bad_request(f"Line {line}: {_register_name_problem(name)}.")
        declared[name] = (kind, line)
        offsets[name] = offset
        if reg:
            registers[name] = (kind, int(reg.group(3)))
            continue
        if kind == "gate" and "{" in text:
            body = text[text.index("{") + 1:text.rindex("}")]
            body_offset = offset + text.index("{") + 1
            head = _SIGNATURE_RE.match(flat)
            qubit_args = _split_list(head.group(2))
            param_names = set(_split_list(head.group(1) or ""))
            where = f" (inside the definition of '{name}')"
            for inner_offset, inner in _statements(body):
                inner_flat = " ".join(inner.split())
                op = _OP_RE.match(inner_flat)
                if not op:
                    continue
                inner_line = _line(code, body_offset + inner_offset)
                _check_call(code, body_offset + inner_offset, inner, op.group(2), known,
                            included, where=where)
                params, args = _call_parts(inner_flat, op.end())
                operands = _split_list(args)
                _check_shape(inner_line, op.group(2), params, operands, signatures, where=where)
                _check_body_operands(inner_line, op.group(2), operands, qubit_args, where)
                _check_body_parameters(inner_line, op.group(2), params, name, param_names, where)
                if name not in uses_opaque:
                    if op.group(2) in opaque:
                        uses_opaque[name] = (op.group(2), inner_line)
                    elif op.group(2) in uses_opaque:
                        uses_opaque[name] = uses_opaque[op.group(2)]
        signatures[name] = _signature(flat)
        if kind == "opaque":
            opaque[name] = line
        known.add(name)
    for offset, text in items[1:]:
        flat = " ".join(text.split())
        if _REG_RE.match(flat) or _DEF_RE.match(flat) or _INCLUDE_RE.match(flat):
            continue
        op = _OP_RE.match(flat)
        if not op:
            continue
        name = op.group(2)
        _check_call(code, offset, flat, name, known, included)
        line = _line(code, offset)
        used = [name] + _NAME_RE.findall(flat[op.end():])
        if op.group(1) is not None:
            used.append(op.group(1))
        for used_name in used:
            if offsets.get(used_name, -1) > offset:
                noun = _KINDS[declared[used_name][0]]
                _bad_request(f"Line {line}: {noun} '{used_name}' is used before its declaration on "
                             f"line {declared[used_name][1]}; OpenQASM 2.0 requires every gate and "
                             f"register to be declared before the statements that use it.")
        if op.group(1) is not None and registers.get(op.group(1), ("",))[0] != "creg":
            _bad_request(f"Line {line}: the condition of 'if' names '{op.group(1)}', which is not "
                         f"a declared classical register.")
        params, args = _call_parts(flat, op.end())
        _check_opaque_call(line, name, opaque, uses_opaque)
        _check_shape(line, name, params, _split_list(args), signatures)
        _check_top_level_operands(line, name, args, registers)
