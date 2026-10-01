"""Circuit text handling on the API side: resolving tasks to QASM and preparing dispatch copies.

``resolve_circuit_qasm`` turns one batch or experiment task into OpenQASM 2.0 text.
``prepare_statevector_dispatch`` and ``prepare_measured_dispatch`` build the exact circuit
text each runner group receives, and return every change made to it as a list of
``"API: ..."`` strings. With preprocessing they raise ``ParameterExpressionError`` or
``RoundTripIntegrityError`` rather than dispatch a circuit pytket cannot parse faithfully. ``strip_terminal_measurements`` raises
``StatevectorIncompatible`` for circuits statevector mode cannot represent.
"""

import ast
import math
import re

from config import settings
import services.benchmark_library as benchmark_library
import services.circuit_library as circuit_library
from qrosetta_commons.helpers import strip_qasm_comments


def resolve_circuit_qasm(
    source: str | None,
    algorithm: str | None,
    qubits: int | None,
    qasm_string: str | None = None,
    mode: str = "measured",
) -> str:
    """Return the OpenQASM 2.0 text for one task.

    ``mode`` selects which qubit cap a generated preset is checked against.
    Raises ValueError for an unknown source or a task the source cannot satisfy.
    """
    normalized = (source or "preset").lower()

    if normalized == "qasm":
        if not qasm_string:
            raise ValueError("source 'qasm' requires qasm_string")
        return qasm_string

    if qasm_string:
        return qasm_string

    if normalized == "mqt":
        return benchmark_library.get_mqt_benchmark(algorithm, int(qubits or 0))

    if normalized == "qasmbench":
        return benchmark_library.get_qasmbench_circuit(algorithm)

    if normalized == "preset":
        n_qubits = int(qubits or 0)
        max_qubits = settings.max_qubits_for_mode(mode)
        if n_qubits > max_qubits:
            raise ValueError(f"Qubit count {n_qubits} exceeds limit of {max_qubits}")
        return circuit_library.generate_circuit(algorithm, n_qubits)

    raise ValueError(f"unknown circuit source '{source}'")


# --- OpenQASM 2.0 text utilities -------------------------------------------------------

_DECL_RE = re.compile(r"^\s*(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]\s*;\s*$")
_GATE_NAME_RE = re.compile(r"^\s*(?:gate|opaque)\s+([A-Za-z_]\w*)")
_OP_RE = re.compile(r"^(\s*(?:if\s*\([^)]*\)\s*)?)([A-Za-z_]\w*)")
_REF_RE = re.compile(r"\b([A-Za-z_]\w*)\b(\s*\[\s*(\d+)\s*\])?")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_MEASURE_RE = re.compile(r"\bmeasure\b")
_BARRIER_RE = re.compile(r"\bbarrier\b")
_PASSTHROUGH_OPS = {"OPENQASM", "include", "qreg", "creg", "gate", "opaque"}
_IF_RE = re.compile(r"^\s*if\s*\(")
_PYTKET_CNX_RE = re.compile(r"^(\s*(?:if\s*\([^)]*\)\s*)?)c4x(\s+)([^;]*);", re.MULTILINE)
_CNX_NAMES = {2: "cx", 3: "ccx", 4: "c3x", 5: "c4x"}

_USE_MEASURED_MODE = ("Statevector mode reports the pre-measurement state of a unitary "
                      "circuit; run this circuit in measured mode instead.")


class StatevectorIncompatible(ValueError):
    """The circuit has mid-circuit measurement, reset or classical control."""


def split_statements(qasm: str) -> list:
    """Split comment-free QASM into top-level statements (``...;`` or a whole gate block)."""
    items, buf, depth = [], [], 0
    for ch in strip_qasm_comments(qasm):
        buf.append(ch)
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                items.append("".join(buf).strip())
                buf = []
        elif ch == ";" and depth == 0:
            items.append("".join(buf).strip())
            buf = []
    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    return [s for s in items if s]


def declared_registers(qasm: str) -> list:
    """Return ``[(kind, name, size)]`` for every qreg/creg, in declaration order."""
    regs = []
    for stmt in split_statements(qasm):
        m = _DECL_RE.match(stmt)
        if m:
            regs.append((m.group(1), m.group(2), int(m.group(3))))
    return regs


def has_measurements(qasm: str) -> bool:
    """True if the circuit contains any ``measure`` statement."""
    return bool(_MEASURE_RE.search(strip_qasm_comments(qasm)))


def has_barriers(qasm: str) -> bool:
    """True if the circuit contains any ``barrier`` statement."""
    return bool(_BARRIER_RE.search(strip_qasm_comments(qasm)))


def _fresh_name(base: str, taken: set) -> str:
    name, i = base, 0
    while name in taken:
        name = f"{base}{i}"
        i += 1
    return name


def _split_op(stmt: str):
    """Split a statement into (head, args): head is any ``if(...)`` prefix, the op and its
    parenthesised parameters; args is the operand list."""
    m = _OP_RE.match(stmt)
    if not m:
        return None, stmt, ""
    op, pos = m.group(2), m.end()
    rest = stmt[pos:]
    stripped = rest.lstrip()
    if stripped.startswith("("):
        pos += len(rest) - len(stripped)
        depth = 0
        for k in range(pos, len(stmt)):
            if stmt[k] == "(":
                depth += 1
            elif stmt[k] == ")":
                depth -= 1
                if depth == 0:
                    pos = k + 1
                    break
    return op, stmt[:pos], stmt[pos:]


def flatten_qregs(qasm: str):
    """Merge every qreg into one register, indexed in declaration order.

    Returns ``(qasm, note)``; ``note`` is None and the text is returned unchanged when the
    circuit declares at most one qreg. Register broadcasts (``h a;``, ``measure a -> c;``)
    are expanded per qubit and ``barrier a;`` lists every qubit. Comments are removed.
    """
    regs = declared_registers(qasm)
    qregs = [(name, size) for kind, name, size in regs if kind == "qreg"]
    if len(qregs) <= 1:
        return qasm, None

    statements = split_statements(qasm)
    cregs = {name for kind, name, _ in regs if kind == "creg"}
    gate_names = {m.group(1) for s in statements for m in [_GATE_NAME_RE.match(s)] if m}
    flat = _fresh_name("q", cregs | gate_names)

    offsets, total = {}, 0
    for name, size in qregs:
        offsets[name] = (total, size)
        total += size

    def rewrite(args: str, j, is_barrier: bool) -> str:
        def sub(m):
            name, idx = m.group(1), m.group(3)
            if name in offsets:
                off, size = offsets[name]
                if idx is not None:
                    return f"{flat}[{off + int(idx)}]"
                if is_barrier:
                    return ",".join(f"{flat}[{off + k}]" for k in range(size))
                return f"{flat}[{off + j}]"
            if name in cregs and idx is None and j is not None:
                return f"{name}[{j}]"
            return m.group(0)
        return _REF_RE.sub(sub, args)

    out, declared = [], False
    for stmt in statements:
        decl = _DECL_RE.match(stmt)
        if decl and decl.group(1) == "qreg":
            if not declared:
                out.append(f"qreg {flat}[{total}];")
                declared = True
            continue
        op, head, args = _split_op(stmt)
        if op is None or op in _PASSTHROUGH_OPS:
            out.append(stmt)
            continue
        bare = [m.group(1) for m in _REF_RE.finditer(args)
                if m.group(1) in offsets and m.group(3) is None]
        if op == "barrier" or not bare:
            out.append(head + rewrite(args, None, op == "barrier"))
            continue
        width = max(offsets[name][1] for name in bare)
        out.extend(head + rewrite(args, j, False) for j in range(width))

    layout = ", ".join(f"{name}[0..{size - 1}] -> {flat}[{offsets[name][0]}..{offsets[name][0] + size - 1}]"
                       for name, size in qregs)
    note = (f"API: merged {len(qregs)} quantum registers into one register '{flat}[{total}]' in "
            f"declaration order ({layout}); register broadcasts expanded per qubit; comments removed")
    return "\n".join(out) + "\n", note


def append_measure_all(qasm: str):
    """Append a fresh classical register and ``measure`` of every qubit, in declaration order.

    Returns ``(qasm, note)``. The register name does not collide with any identifier in
    the circuit. The input text is kept verbatim and the new lines are appended.
    """
    qubits = [(name, i) for kind, name, size in declared_registers(qasm) if kind == "qreg"
              for i in range(size)]
    creg = _fresh_name("meas", set(_IDENT_RE.findall(strip_qasm_comments(qasm))))
    lines = [f"creg {creg}[{len(qubits)}];"]
    lines += [f"measure {name}[{i}] -> {creg}[{k}];" for k, (name, i) in enumerate(qubits)]
    text = qasm if qasm.endswith("\n") else qasm + "\n"
    note = (f"API: circuit had no measure statements; appended 'creg {creg}[{len(qubits)}]' and "
            f"measured qubit k (declaration order) into {creg}[k] for all {len(qubits)} qubits")
    return text + "\n".join(lines) + "\n", note


def _qubits_in(args: str, qregs: dict) -> set:
    """``(register, index)`` pairs an operand list refers to; a bare register means all of
    its qubits."""
    qubits = set()
    for m in _REF_RE.finditer(args):
        name, idx = m.group(1), m.group(3)
        if name not in qregs:
            continue
        if idx is None:
            qubits.update((name, k) for k in range(qregs[name]))
        else:
            qubits.add((name, int(idx)))
    return qubits


def strip_terminal_measurements(qasm: str):
    """Remove terminal ``measure`` statements for statevector dispatch.

    A measurement is terminal when no gate acts on its qubit afterwards (barriers do not
    count). Returns ``(qasm, note)``; with no measurements the text is returned unchanged
    and ``note`` is None. Otherwise the text is rebuilt from its statements, so comments
    are removed; creg declarations are kept. Raises ``StatevectorIncompatible`` for
    ``reset``, ``if(...)`` or a gate after a measurement on the same qubit.
    """
    qregs = {name: size for kind, name, size in declared_registers(qasm) if kind == "qreg"}
    measured, removed, kept = set(), 0, []
    for stmt in split_statements(qasm):
        if _IF_RE.match(stmt):
            raise StatevectorIncompatible(
                f"Circuit uses classical control ('{stmt}'). {_USE_MEASURED_MODE}")
        op, _head, args = _split_op(stmt)
        if op is None or op in _PASSTHROUGH_OPS:
            kept.append(stmt)
            continue
        if op == "reset":
            raise StatevectorIncompatible(f"Circuit uses reset ('{stmt}'). {_USE_MEASURED_MODE}")
        if op == "measure":
            qubits = _qubits_in(args.split("->", 1)[0], qregs)
            measured |= qubits
            removed += len(qubits)
            continue
        if op != "barrier":
            after = sorted(_qubits_in(args, qregs) & measured)
            if after:
                name, idx = after[0]
                raise StatevectorIncompatible(
                    f"Circuit has a mid-circuit measurement: '{stmt}' acts on {name}[{idx}] "
                    f"after it was measured. {_USE_MEASURED_MODE}")
        kept.append(stmt)

    if not removed:
        return qasm, None
    note = (f"API: removed {removed} terminal measurement(s); statevector mode reports the "
            f"pre-measurement state (comments removed, classical registers kept)")
    return "\n".join(kept) + "\n", note


# --- '^' in gate parameters ------------------------------------------------------------

class ParameterExpressionError(ValueError):
    """A gate parameter expression the API cannot evaluate before the pytket round-trip."""


_QASM_FUNCTIONS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
                   "ln": math.log, "sqrt": math.sqrt}
_BINARY_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
               ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
               ast.Pow: lambda a, b: a ** b}
_CARET_NOTE = ("API: evaluated constant gate parameters (pytket's parser does not accept '^' "
               "or exp()): each parameter of a top-level gate statement containing either was "
               "replaced by its value in full double precision")
_EXP_RE = re.compile(r"\bexp\s*\(")


def _needs_evaluation(text: str) -> bool:
    """True when ``text`` uses '^' or exp(), which pytket's QASM parser rejects."""
    return "^" in text or bool(_EXP_RE.search(text))


def _eval_node(node, env=None):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Name) and env and node.id in env:
        return env[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id == "pi":
        return math.pi
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval_node(node.operand, env)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        return _BINARY_OPS[type(node.op)](_eval_node(node.left, env), _eval_node(node.right, env))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _QASM_FUNCTIONS and len(node.args) == 1 and not node.keywords):
        return _QASM_FUNCTIONS[node.func.id](_eval_node(node.args[0], env))
    raise ParameterExpressionError("only numbers, pi, + - * / ^, unary minus and "
                                   "sin/cos/tan/exp/ln/sqrt are allowed")


_NON_QASM_NUMBER_RE = re.compile(r"\b0[xXoObB]|\d_|_\d|\d[jJ]\b")


def evaluate_constant_expression(text: str, env: dict = None) -> float:
    """Value of an OpenQASM 2.0 constant expression (numbers, pi, + - * / ^, unary minus,
    sin cos tan exp ln sqrt), computed in floating point. Raises
    ParameterExpressionError for anything else or a non-finite value."""
    if "**" in text or _NON_QASM_NUMBER_RE.search(text):
        raise ParameterExpressionError(
            "only OpenQASM 2.0 numbers (decimal, optional exponent) and '^' for powers are allowed")
    try:
        tree = ast.parse(text.replace("^", "**").strip(), mode="eval")
        value = _eval_node(tree, env)
    except ParameterExpressionError:
        raise
    except RecursionError:
        raise ParameterExpressionError("the expression is nested too deeply")
    except OverflowError:
        raise ParameterExpressionError("the value is too large")
    except ZeroDivisionError:
        raise ParameterExpressionError("division by zero")
    except (SyntaxError, ValueError) as exc:
        raise ParameterExpressionError(str(exc) or type(exc).__name__)
    if not math.isfinite(value):
        raise ParameterExpressionError("the value is not finite")
    return value


def _split_params(text: str) -> list:
    parts, depth, buf = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def _evaluated_statement(stmt: str) -> str:
    op, head, args = _split_op(stmt)
    open_at = head.find("(", _OP_RE.match(head).end()) if op is not None else -1
    if open_at < 0 or not _needs_evaluation(head[open_at:]):
        raise ParameterExpressionError(f"'^' or exp() outside a gate parameter list in '{stmt}'")
    inner = head[open_at + 1:-1]
    values = []
    for param in _split_params(inner):
        if not _needs_evaluation(param):
            values.append(param.strip())
            continue
        try:
            values.append(repr(evaluate_constant_expression(param)))
        except ParameterExpressionError as exc:
            raise ParameterExpressionError(
                f"cannot evaluate the parameter '{param.strip()}' of '{stmt}': {exc}")
    return f"{head[:open_at]}({', '.join(values)}){args}"


MAX_PARAMETER_MAGNITUDE = 1e6


def gate_body_statements(stmt: str) -> list:
    """The statements inside a ``gate`` definition's body, [] for any other statement."""
    if not _GATE_NAME_RE.match(stmt) or "{" not in stmt:
        return []
    body = stmt[stmt.index("{") + 1:stmt.rindex("}")] if "}" in stmt else ""
    return [part.strip() + ";" for part in body.split(";") if part.strip()]


def gate_parameter_names(stmt: str) -> set:
    """The parameter names of a ``gate`` definition (``gate g(a, b) q { ... }`` -> {a, b})."""
    head = stmt.split("{", 1)[0]
    if "(" not in head:
        return set()
    inner = head[head.index("(") + 1:head.rindex(")")] if ")" in head else ""
    return {p.strip() for p in inner.split(",") if p.strip()}


def statement_parameters(stmt: str) -> list:
    """The parameter expressions of a gate statement (``rx(pi/2) q[0];`` -> ["pi/2"]), [] for
    a statement without a parameter list or for a definition."""
    if _GATE_NAME_RE.match(stmt):
        return []
    op, head, _args = _split_op(stmt)
    if op is None:
        return []
    open_at = head.find("(", _OP_RE.match(head).end())
    if open_at < 0 or not head.endswith(")"):
        return []
    return [p for p in _split_params(head[open_at + 1:-1]) if p.strip()]


def check_parameter_value(text: str, env: dict = None) -> float:
    """Value of a gate parameter (constant, or in terms of ``env``'s names); raises
    ParameterExpressionError when it is not finite or its magnitude exceeds
    MAX_PARAMETER_MAGNITUDE."""
    value = evaluate_constant_expression(text, env)
    if abs(value) > MAX_PARAMETER_MAGNITUDE:
        raise ParameterExpressionError(
            f"|{value!r}| exceeds {MAX_PARAMETER_MAGNITUDE:g}: at that size a double "
            f"cannot hold the angle modulo 2*pi precisely, and the SDKs reduce it in "
            f"different ways")
    return value


def evaluate_caret_parameters(qasm: str):
    """Replace every parameter of a top-level gate statement that contains '^' with its
    value, for pytket's parser, which rejects '^'.

    Returns ``(qasm, note)``; ``note`` is None and the text is unchanged when no top-level
    statement contains '^'. Otherwise the text is rebuilt from its statements (comments
    removed). Raises ParameterExpressionError for '^' inside a gate definition, where the
    expression is symbolic, or for a parameter that is not a constant expression.
    """
    statements = split_statements(qasm)
    if not any(_needs_evaluation(stmt) for stmt in statements):
        return qasm, None
    out = []
    for stmt in statements:
        if not _needs_evaluation(stmt):
            out.append(stmt)
            continue
        name = _GATE_NAME_RE.match(stmt)
        if name:
            raise ParameterExpressionError(
                f"gate definition '{name.group(1)}' uses '^' or exp() in its body, which pytket's "
                f"parser does not accept; write the power as a product (e.g. theta*theta) or run "
                f"with apply_preprocessing=false")
        out.append(_evaluated_statement(stmt))
    return "\n".join(out) + "\n", _CARET_NOTE


def _restore_register_order(emitted: str, original: str) -> str:
    """Reorder the register declarations of ``emitted`` to their order in ``original``."""
    order = {(kind, name): k for k, (kind, name, _) in enumerate(declared_registers(original))}
    lines = emitted.split("\n")
    slots = [i for i, line in enumerate(lines) if _DECL_RE.match(line)]
    decls = [lines[i] for i in slots]
    keys = [_DECL_RE.match(line).group(1, 2) for line in decls]
    if sorted(keys) != sorted(order):
        return emitted
    for i, line in zip(slots, sorted(decls, key=lambda d: order[_DECL_RE.match(d).group(1, 2)])):
        lines[i] = line
    return "\n".join(lines)


def _classical_width(qasm: str) -> int:
    """pytket ``maxwidth`` that admits every creg of ``qasm``: the total declared classical
    bits, at least pytket's default of 32."""
    return max(32, sum(size for kind, _, size in declared_registers(qasm) if kind == "creg"))


# --- pytket round-trip ------------------------------------------------------------------

class RoundTripIntegrityError(ValueError):
    """pytket's parse of the circuit dropped or replaced a user-defined gate."""


def _custom_gate_names(circ) -> set:
    from pytket.circuit import OpType
    names = set()
    for cmd in circ.get_commands():
        op = cmd.op
        if op.type == OpType.Conditional:
            op = op.op
        if op.type == OpType.CustomGate:
            names.add(op.gate.name)
    return names


def _empty_custom_gate_names(circ) -> list:
    """Names of custom gates in ``circ`` whose definition has no operations."""
    from pytket.circuit import OpType
    names = set()
    for cmd in circ.get_commands():
        op = cmd.op.op if cmd.op.type == OpType.Conditional else cmd.op
        if op.type == OpType.CustomGate and op.get_circuit().n_gates == 0:
            names.add(op.gate.name)
    return sorted(names)


def check_round_trip_integrity(circ, qasm: str) -> None:
    """Raise RoundTripIntegrityError when pytket's parse of ``qasm`` turned a gate call
    into a barrier, or when a user-defined gate called at top level is not a custom gate
    in ``circ`` (pytket substituted a built-in operation for it)."""
    from pytket.circuit import OpType
    for cmd in circ.get_commands():
        data = getattr(cmd.op, "data", "") if cmd.op.type == OpType.Barrier else ""
        if data:
            raise RoundTripIntegrityError(
                f"pytket's parser turned the gate call '{data}' into a barrier, which would "
                f"delete it from the dispatched circuit; rename the gate")
    statements = split_statements(qasm)
    defined = {m.group(1) for stmt in statements for m in [_GATE_NAME_RE.match(stmt)] if m}
    called = {op for stmt in statements for op, _h, _a in [_split_op(stmt)] if op in defined}
    missing = sorted(called - _custom_gate_names(circ))
    if missing:
        raise RoundTripIntegrityError(
            f"pytket's parser replaced the user-defined gate(s) {', '.join(missing)} with a "
            f"different operation instead of their definitions; rename the gate(s)")


def _pytket_round_trip(qasm: str, remove_barriers: bool):
    """Parse and re-emit ``qasm`` with pytket, optionally removing barriers.

    Register declarations keep their order in ``qasm``. Raises RoundTripIntegrityError
    (see ``check_round_trip_integrity``) instead of emitting a circuit that lost a gate.
    """
    import pytket.qasm
    from pytket.passes import DecomposeBoxes, RemoveBarriers

    qasm = strip_qasm_comments(qasm)
    maxwidth = _classical_width(qasm)
    circ = pytket.qasm.circuit_from_qasm_str(qasm, maxwidth=maxwidth)
    check_round_trip_integrity(circ, qasm)
    notes = [
        "API: parsed and re-emitted with pytket (circuit_from_qasm_str / circuit_to_qasm_str): "
        "register declarations kept in declaration order, custom gate definitions inlined, "
        "gates rewritten into pytket's QASM gate set (e.g. u -> u3 with angles as multiples of "
        "pi), register broadcasts expanded, comments removed"
    ]
    empty = _empty_custom_gate_names(circ)
    if empty:
        DecomposeBoxes().apply(circ)
        notes.append(f"API: removed the calls to {', '.join(empty)}, whose gate definition is "
                     f"empty (the identity), because pytket's QASM writer rejects empty gates "
                     f"(pytket DecomposeBoxes)")
    if remove_barriers and has_barriers(qasm):
        RemoveBarriers().apply(circ)
        notes.append("API: removed barrier statements (pytket RemoveBarriers)")
    emitted, renamed = _name_cnx_by_size(pytket.qasm.circuit_to_qasm_str(circ, maxwidth=maxwidth))
    if renamed:
        notes.append(f"API: pytket writes every multi-controlled X as c4x; calls with fewer qubits "
                     f"renamed to {', '.join(renamed)} by their operand count")
    return _restore_register_order(emitted, qasm), notes


def _name_cnx_by_size(emitted: str):
    """(text, renamed): pytket 1.33/1.34 writes every multi-controlled X as ``c4x``; each such
    call is renamed by its operand count to the qelib1 gate with that many qubits."""
    renamed = []

    def rename(match):
        operands = [o for o in match.group(3).split(",") if o.strip()]
        name = _CNX_NAMES.get(len(operands))
        if name is None:
            raise RoundTripIntegrityError(
                f"pytket wrote a multi-controlled X on {len(operands)} qubits, which qelib1.inc "
                f"has no gate for")
        if name != "c4x":
            renamed.append(name)
        return f"{match.group(1)}{name}{match.group(2)}{match.group(3)};"

    return _PYTKET_CNX_RE.sub(rename, emitted), sorted(set(renamed))


def _preprocessed_base(qasm: str):
    """Register merge, '^' parameter evaluation and the pytket round-trip, with notes."""
    notes = []
    text, note = flatten_qregs(qasm)
    if note:
        notes.append(note)
    text, note = evaluate_caret_parameters(text)
    if note:
        notes.append(note)
    text, rt_notes = _pytket_round_trip(text, remove_barriers=True)
    return text, notes + rt_notes


def prepare_statevector_dispatch(qasm: str, apply_preprocessing: bool) -> dict:
    """Return ``{"qasm", "api_preprocessing_applied"}`` for the statevector runners.

    Terminal measurements are always removed (``strip_terminal_measurements``, which
    raises ``StatevectorIncompatible`` for mid-circuit measurement, reset or ``if``). With
    preprocessing, multi-register circuits are then merged in declaration order and
    round-tripped through pytket with barriers removed (parameters containing '^' are
    evaluated first, see ``evaluate_caret_parameters``); without it the text is otherwise
    dispatched unchanged.
    """
    text, note = strip_terminal_measurements(qasm)
    notes = [note] if note else []
    if not apply_preprocessing:
        return {"qasm": text, "api_preprocessing_applied": notes}
    text, pp_notes = _preprocessed_base(text)
    return {"qasm": text, "api_preprocessing_applied": notes + pp_notes}


def prepare_measured_dispatch(qasm: str, apply_preprocessing: bool) -> dict:
    """Return the dispatched circuits for measured mode, keyed by runner group.

    ``measured_sampled`` runners sample a statevector and receive the circuit without
    added measurements. ``measured_native`` runners sample natively and receive the same
    circuit plus measure-all when it has no measure statements. With preprocessing, both
    groups get the declaration-order register merge and the pytket round-trip with
    barriers removed, as the statevector group does; without it both receive the input
    text (plus measure-all for the native group).
    """
    base, base_notes = qasm, []
    if apply_preprocessing:
        base, base_notes = _preprocessed_base(qasm)

    native, native_notes = base, list(base_notes)
    if not has_measurements(native):
        native, note = append_measure_all(native)
        native_notes.append(note)

    return {
        "measured_sampled": {"qasm": base, "api_preprocessing_applied": base_notes},
        "measured_native": {"qasm": native, "api_preprocessing_applied": native_notes},
    }
