"""Circuit text handling on the API side: resolving tasks to QASM and preparing dispatch copies.

``resolve_circuit_qasm`` turns one batch or experiment task into OpenQASM 2.0 text.
``prepare_statevector_dispatch`` and ``prepare_measured_dispatch`` build the exact circuit
text each runner group receives, and return every change made to it as a list of
``"API: ..."`` strings. ``strip_terminal_measurements`` raises
``StatevectorIncompatible`` for circuits statevector mode cannot represent.
"""

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


def _pytket_round_trip(qasm: str, remove_barriers: bool):
    """Parse and re-emit ``qasm`` with pytket, optionally removing barriers."""
    import pytket.qasm
    from pytket.passes import RemoveBarriers

    circ = pytket.qasm.circuit_from_qasm_str(qasm)
    notes = [
        "API: parsed and re-emitted with pytket (circuit_from_qasm_str / circuit_to_qasm_str): "
        "register declarations re-emitted in pytket's order, custom gate definitions inlined, "
        "gates rewritten into pytket's QASM gate set (e.g. u -> u3 with angles as multiples of "
        "pi), register broadcasts expanded, comments removed"
    ]
    if remove_barriers and has_barriers(qasm):
        RemoveBarriers().apply(circ)
        notes.append("API: removed barrier statements (pytket RemoveBarriers)")
    return pytket.qasm.circuit_to_qasm_str(circ), notes


def prepare_statevector_dispatch(qasm: str, apply_preprocessing: bool) -> dict:
    """Return ``{"qasm", "api_preprocessing_applied"}`` for the statevector runners.

    Terminal measurements are always removed (``strip_terminal_measurements``, which
    raises ``StatevectorIncompatible`` for mid-circuit measurement, reset or ``if``). With
    preprocessing, multi-register circuits are then merged in declaration order and
    round-tripped through pytket with barriers removed; without it the text is otherwise
    dispatched unchanged.
    """
    text, note = strip_terminal_measurements(qasm)
    notes = [note] if note else []
    if not apply_preprocessing:
        return {"qasm": text, "api_preprocessing_applied": notes}
    text, note = flatten_qregs(text)
    if note:
        notes.append(note)
    text, rt_notes = _pytket_round_trip(text, remove_barriers=True)
    return {"qasm": text, "api_preprocessing_applied": notes + rt_notes}


def prepare_measured_dispatch(qasm: str, apply_preprocessing: bool) -> dict:
    """Return the dispatched circuits for measured mode, keyed by runner group.

    ``measured_sampled`` runners sample a statevector and receive the circuit without
    added measurements. ``measured_native`` runners sample natively and receive the same
    circuit plus measure-all when it has no measure statements. With preprocessing, both
    groups get the declaration-order register merge, and the native group is also
    round-tripped through pytket with barriers removed.
    """
    base, base_notes = qasm, []
    if apply_preprocessing:
        base, note = flatten_qregs(qasm)
        if note:
            base_notes.append(note)

    native, native_notes = base, list(base_notes)
    if apply_preprocessing:
        native, rt_notes = _pytket_round_trip(native, remove_barriers=True)
        native_notes += rt_notes
    if not has_measurements(native):
        native, note = append_measure_all(native)
        native_notes.append(note)

    return {
        "measured_sampled": {"qasm": base, "api_preprocessing_applied": base_notes},
        "measured_native": {"qasm": native, "api_preprocessing_applied": native_notes},
    }
