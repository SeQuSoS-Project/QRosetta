"""Counts keys over a circuit's classical bits.

A counts key holds every declared classical bit, with no separators. The flat classical-bit
index follows creg declaration order (``creg a[2]; creg b[1]`` gives a[0]=0, a[1]=1, b[0]=2).
Bit order ``"lsb"`` puts flat clbit 0 rightmost; ``"msb"`` puts it leftmost. A classical bit
that no ``measure`` statement writes reads 0.
"""

import re
from collections import Counter

import numpy as np

PYTKET_QASM_MAXWIDTH = 1024
MID_CIRCUIT_ERROR = "mid-circuit measurement is not supported by this adapter"
STATEVECTOR_TERMINAL_ERROR = "statevector simulation needs every measurement to be terminal"

STRIP_MEASUREMENTS_NOTE = (
    "Measurement statements removed from the QASM before statevector simulation; every "
    "measurement was terminal, so the returned state is the pre-measurement state. Applied "
    "regardless of apply_preprocessing.")

FINAL_STATE_SAMPLING_NOTE = (
    "Terminal measure statements removed from the QASM; shots are drawn over the qubits of "
    "the final state and each classical bit takes the value of the qubit last measured into "
    "it (unmeasured classical bits read 0). Counts keys hold every declared classical bit. "
    "Applied regardless of apply_preprocessing.")

STATEVECTOR_REORDER_NOTE = (
    "Statevector reordered from pytket's alphabetical register order to declaration order, "
    "after the timed window; the index convention (qubit_ordering) is unchanged.")

IMPLICIT_MEASURE_ALL_NOTE = (
    "The circuit has no measure statements, so every qubit is read out into an added "
    "classical register '{creg}', declared after the circuit's own (qubit k in declaration "
    "order into {creg}[k]), as the API's measure-all for natively sampling runners does. "
    "Counts keys hold the circuit's declared classical bits, which read 0, and then {creg}.")

_QREG_RE = re.compile(r"^qreg\s+(\w+)\s*\[\s*(\d+)\s*\]$")
_CREG_RE = re.compile(r"^creg\s+(\w+)\s*\[\s*(\d+)\s*\]$")
_GATE_DEF_RE = re.compile(r"\b(?:gate)\s+[^{;]*\{[^}]*\}", re.S)
_MEASURE_RE = re.compile(r"^measure\s+(.+?)\s*->\s*(.+)$", re.S)
_MEASURE_STMT_RE = re.compile(r"\bmeasure\b[^;]*;")
_ARG_RE = re.compile(r"^(\w+)\s*(?:\[\s*(\d+)\s*\])?$")
_NAME_RE = re.compile(r"^([A-Za-z_]\w*)")
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_SKIPPED_KEYWORDS = ("OPENQASM", "include", "opaque", "barrier")
MEASURE_ALL_BASE = "meas"


def _strip_comments(qasm: str) -> str:
    return _LINE_COMMENT_RE.sub("", _BLOCK_COMMENT_RE.sub("", qasm))


def measure_all_register(qasm: str) -> str:
    """Name of the register a measure-all appends: ``meas``, else ``meas0``, ``meas1``, ...

    The name differs from every identifier in the circuit (comments excluded).
    """
    taken = set(_IDENT_RE.findall(_strip_comments(qasm)))
    name, i = MEASURE_ALL_BASE, 0
    while name in taken:
        name = f"{MEASURE_ALL_BASE}{i}"
        i += 1
    return name


def _statements(qasm: str):
    body = _GATE_DEF_RE.sub("", _strip_comments(qasm))
    for piece in body.split(";"):
        stmt = " ".join(piece.split())
        if stmt:
            yield stmt


def _gate_args(stmt: str) -> str:
    """The operand list of a gate call, after its name and any balanced parameter list."""
    match = _NAME_RE.match(stmt)
    rest = stmt[match.end():].lstrip() if match else stmt
    if rest.startswith("("):
        depth = 0
        for i, ch in enumerate(rest):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0:
                return rest[i + 1:]
    return rest


class MeasurementLayout:
    """Registers and measure statements of an OpenQASM 2.0 circuit.

    ``qubits`` / ``clbits`` are ``(register, index)`` pairs in flat declaration order.
    ``measures`` lists ``(flat_qubit, flat_clbit)`` in program order. ``non_terminal`` names
    the first construct that a final-state sampler cannot reproduce (a gate on a qubit after
    its measurement, ``reset``, or ``if``), or is None.
    """

    def __init__(self, qregs, cregs, measures, non_terminal, has_reset=False,
                 has_classical_control=False):
        self.qregs = list(qregs)
        self.cregs = list(cregs)
        self.qubits = [(n, i) for n, size in self.qregs for i in range(size)]
        self.clbits = [(n, i) for n, size in self.cregs for i in range(size)]
        self.measures = list(measures)
        self.non_terminal = non_terminal
        self.has_reset = has_reset
        self.has_classical_control = has_classical_control
        self._clbit_index = {bit: k for k, bit in enumerate(self.clbits)}

    @property
    def n_qubits(self):
        return len(self.qubits)

    @property
    def n_clbits(self):
        return len(self.clbits)

    @property
    def has_measurements(self):
        return bool(self.measures)

    def require_terminal(self, message: str = MID_CIRCUIT_ERROR):
        """Raise ValueError if the circuit measures mid-circuit, resets, or branches."""
        if self.non_terminal is not None:
            raise ValueError(f"{message} ({self.non_terminal}).")

    def clbit_sources(self) -> dict:
        """``{flat_clbit: flat_qubit}`` for every written classical bit; the last write wins."""
        return {c: q for q, c in self.measures}

    def implicit_measure_all(self, creg: str) -> "MeasurementLayout":
        """This layout plus a register ``creg`` after the declared ones, reading qubit k into
        ``creg[k]`` in declaration order (the declared classical bits stay, unwritten)."""
        offset = self.n_clbits
        return MeasurementLayout(
            self.qregs, self.cregs + [(creg, self.n_qubits)],
            [(q, offset + q) for q in range(self.n_qubits)], self.non_terminal,
            self.has_reset, self.has_classical_control)

    def key(self, bits, bit_order: str) -> str:
        """Key for ``bits`` indexed by flat classical bit."""
        text = "".join(str(int(b)) for b in bits)
        return text[::-1] if bit_order == "lsb" else text

    def key_from_named(self, named: dict, bit_order: str) -> str:
        """Key from ``{(register, index): bit}``; classical bits not present read 0."""
        bits = [0] * self.n_clbits
        for bit, value in named.items():
            k = self._clbit_index.get(bit)
            if k is not None:
                bits[k] = int(value)
        return self.key(bits, bit_order)

    def counts_from_named(self, items, bit_order: str) -> dict:
        """Counts from an iterable of ``({(register, index): bit}, count)`` pairs."""
        counts: dict = {}
        for named, count in items:
            key = self.key_from_named(named, bit_order)
            counts[key] = counts.get(key, 0) + int(count)
        return counts

    def qubit_positions(self, index_order: str, backend_qubits=None) -> list:
        """Bit position of each flat declared qubit inside a backend's basis-state index.

        ``backend_qubits`` is the backend's qubit order as ``(register, index)`` pairs
        (default: declaration order). ``index_order`` ``"msb"``: the backend's first qubit
        is the most significant index bit; ``"lsb"``: the least significant.
        """
        order = list(backend_qubits) if backend_qubits is not None else self.qubits
        if sorted(order) != sorted(self.qubits):
            raise ValueError(
                f"backend qubits {order} do not match the declared qubits {self.qubits}")
        n = len(order)
        position = {qb: (n - 1 - k if index_order == "msb" else k) for k, qb in enumerate(order)}
        return [position[qb] for qb in self.qubits]

    def counts_from_qubit_counts(self, qubit_counts: dict, positions, bit_order: str) -> dict:
        """Map ``{basis_state_index: count}`` over qubits to counts over classical bits."""
        sources = self.clbit_sources()
        clbit_positions = [
            positions[sources[c]] if c in sources else None for c in range(self.n_clbits)]
        counts: dict = {}
        for index, count in qubit_counts.items():
            index = int(index)
            bits = [0 if p is None else (index >> p) & 1 for p in clbit_positions]
            key = self.key(bits, bit_order)
            counts[key] = counts.get(key, 0) + int(count)
        return counts

    def counts_from_qubit_samples(self, samples, positions, bit_order: str) -> dict:
        """Map sampled basis-state indices over qubits to counts over classical bits."""
        return self.counts_from_qubit_counts(
            Counter(np.asarray(samples).ravel().tolist()), positions, bit_order)


def _expand(arg: str, sizes: dict):
    match = _ARG_RE.match(arg.strip())
    if not match:
        raise ValueError(f"cannot parse QASM operand {arg!r}")
    name, index = match.group(1), match.group(2)
    if name not in sizes:
        raise ValueError(f"QASM operand {arg!r} names an undeclared register")
    if index is None:
        return [(name, i) for i in range(sizes[name])]
    return [(name, int(index))]


def parse_measurement_layout(qasm: str) -> MeasurementLayout:
    """Parse registers and measure statements, and flag non-terminal measurement."""
    qregs, cregs, measures = [], [], []
    qsizes, csizes = {}, {}
    qubit_index, clbit_index = {}, {}
    measured = set()
    non_terminal = None
    has_reset = has_classical_control = False

    def flag(reason):
        nonlocal non_terminal
        if non_terminal is None:
            non_terminal = reason

    for stmt in _statements(qasm):
        if stmt.startswith(_SKIPPED_KEYWORDS):
            continue
        if m := _QREG_RE.match(stmt):
            name, size = m.group(1), int(m.group(2))
            for i in range(size):
                qubit_index[(name, i)] = len(qubit_index)
            qregs.append((name, size))
            qsizes[name] = size
            continue
        if m := _CREG_RE.match(stmt):
            name, size = m.group(1), int(m.group(2))
            for i in range(size):
                clbit_index[(name, i)] = len(clbit_index)
            cregs.append((name, size))
            csizes[name] = size
            continue
        if re.match(r"^if\s*\(", stmt):
            flag("classically controlled operation 'if'")
            has_classical_control = True
            continue
        if re.match(r"^reset\b", stmt):
            flag("reset")
            has_reset = True
            continue
        if m := _MEASURE_RE.match(stmt):
            qs, cs = _expand(m.group(1), qsizes), _expand(m.group(2), csizes)
            if len(qs) != len(cs):
                raise ValueError(f"measure operands differ in size: {stmt!r}")
            for qb, cb in zip(qs, cs):
                measures.append((qubit_index[qb], clbit_index[cb]))
                measured.add(qb)
            continue
        args = [a for a in _gate_args(stmt).split(",") if a.strip()]
        for arg in args:
            for qb in _expand(arg, qsizes):
                if qb in measured:
                    flag(f"'{_NAME_RE.match(stmt).group(1)}' acts on {qb[0]}[{qb[1]}] "
                         "after it is measured")
    return MeasurementLayout(qregs, cregs, measures, non_terminal, has_reset,
                             has_classical_control)


BROADCAST_NOTE = (
    "Gate calls with a whole-register operand expanded into one call per qubit (OpenQASM 2.0 "
    "broadcast: register operands have equal size and step together, indexed operands repeat "
    "in every call); {reason}. The expansion leaves the "
    "unitary unchanged. Required by the adapter, applied regardless of apply_preprocessing.")
PYTKET_BROADCAST_REASON = (
    "pytket's QASM parser applies a call that mixes indexed and register operands to the "
    "register's first qubit only")
_IF_PREFIX_RE = re.compile(r"^(if\s*\([^)]*\)\s*)(.*)$", re.S)
_NON_GATE_RE = re.compile(r"^(qreg|creg|measure|reset|OPENQASM|include|opaque|barrier)\b")


def _expand_call(stmt: str, qsizes: dict):
    """Indexed calls for a gate call with register operands, or None when it has none."""
    prefix, call = "", stmt
    if m := _IF_PREFIX_RE.match(stmt):
        prefix, call = m.group(1), m.group(2)
    if _NON_GATE_RE.match(call) or not _NAME_RE.match(call):
        return None
    args_text = _gate_args(call)
    head = call[:len(call) - len(args_text)].rstrip()
    operands = [_ARG_RE.match(a.strip()) for a in args_text.split(",")]
    if not all(operands) or any(op.group(1) not in qsizes for op in operands):
        return None
    sizes = {qsizes[op.group(1)] for op in operands if op.group(2) is None}
    if not sizes:
        return None
    if len(sizes) > 1:
        raise ValueError(f"register operands of different sizes in {stmt!r}")
    size = sizes.pop()
    return [
        prefix + head + " " + ", ".join(
            f"{op.group(1)}[{op.group(2) if op.group(2) is not None else i}]"
            for op in operands) + ";"
        for i in range(size)]


def expand_register_broadcasts(qasm: str, reason: str):
    """Expand gate calls on whole registers into indexed calls, per OpenQASM 2.0 broadcast.

    ``reason`` completes the preprocessing note: why the adapter's parser needs it.
    ``cx q[0], r;`` with ``qreg r[2]`` becomes ``cx q[0], r[0]; cx q[0], r[1];``. Gate
    definitions, measure, reset and barrier statements are kept as written. Returns
    ``(qasm, note)``; when nothing is expanded the input is returned unchanged with note None.
    """
    text = _strip_comments(qasm)
    qsizes, out, changed, pos = {}, [], False, 0

    def expand_segment(segment):
        nonlocal changed
        pieces = segment.split(";")
        for piece in pieces[:-1]:
            stmt = " ".join(piece.split())
            if m := _QREG_RE.match(stmt):
                qsizes[m.group(1)] = int(m.group(2))
            calls = _expand_call(stmt, qsizes) if stmt else None
            if calls is None:
                out.append(piece + ";")
            else:
                changed = True
                out.append(piece[:len(piece) - len(piece.lstrip())] + "\n".join(calls))
        out.append(pieces[-1])

    for m in _GATE_DEF_RE.finditer(text):
        expand_segment(text[pos:m.start()])
        out.append(m.group(0))
        pos = m.end()
    expand_segment(text[pos:])
    if not changed:
        return qasm, None
    return "".join(out), BROADCAST_NOTE.format(reason=reason)


def strip_measurements(qasm: str) -> str:
    """Remove every ``measure`` statement (comments are removed too)."""
    return _MEASURE_STMT_RE.sub("", _strip_comments(qasm))


def strip_identity_gates(qasm: str, names) -> tuple:
    """Remove calls to the named identity gates (qelib1 ``id``, ``u0``); comments go too.

    Returns ``(qasm, removed)`` with ``removed`` the names that occurred, in ``names`` order.
    """
    text = _strip_comments(qasm)
    removed = []
    for name in names:
        pattern = re.compile(rf"(^|[;{{}}])(\s*){name}\b\s*(?:\([^)]*\))?\s*[^;{{}}]*;", re.M)
        text, n = pattern.subn(r"\1\2", text)
        if n:
            removed.append(name)
    return text, removed


def prepare_statevector_qasm(qasm: str):
    """QASM with its terminal measurements removed, plus preprocessing notes.

    Raises ValueError when a measurement is not terminal or the circuit resets or branches.
    """
    layout = parse_measurement_layout(qasm)
    layout.require_terminal(STATEVECTOR_TERMINAL_ERROR)
    if not layout.has_measurements:
        return qasm, []
    return strip_measurements(qasm), [STRIP_MEASUREMENTS_NOTE]


def prepare_final_state_sampling(qasm: str):
    """For runners that draw shots from a final state: ``(stripped_qasm, layout, notes)``.

    Raises ValueError when a measurement is not terminal. A circuit without measure
    statements reads out every qubit into a register appended after the declared ones
    (``measure_all_register``), matching the circuit the API sends natively sampling runners.
    """
    layout = parse_measurement_layout(qasm)
    layout.require_terminal()
    if not layout.has_measurements:
        creg = measure_all_register(qasm)
        return (qasm, layout.implicit_measure_all(creg),
                [IMPLICIT_MEASURE_ALL_NOTE.format(creg=creg)])
    return strip_measurements(qasm), layout, [FINAL_STATE_SAMPLING_NOTE]


def named_bits_from_register_key(key: str, registers) -> dict:
    """``{(register, index): bit}`` from a key with one space-separated field per register.

    ``registers`` is ``[(name, size), ...]`` in the backend's register order; the key lists
    the last register leftmost and each field is little-endian (Qiskit Aer's format).
    """
    fields = key.split()
    if len(fields) != len(registers):
        raise ValueError(f"counts key {key!r} does not match registers {registers}")
    named = {}
    for (name, size), field in zip(reversed(registers), fields):
        for i in range(size):
            named[(name, i)] = int(field[size - 1 - i])
    return named


def unordered_qreg_note(layout: MeasurementLayout, parser: str = "pytket"):
    """Note for a parser that sorts quantum registers by name, when that changes the order."""
    names = [n for n, _ in layout.qregs]
    if len(names) > 1 and names != sorted(names):
        return (f"{parser} QASM parser orders quantum registers alphabetically "
                f"({', '.join(sorted(names))}) rather than in declaration order "
                f"({', '.join(names)}). The executed circuit and the recorded transpiled_qasm "
                "list qubits in the alphabetical order, flattened into one register where the "
                "backend compilation merges registers; the returned statevector and counts are "
                "mapped back to declaration order.")
    return None


def reorder_statevector(statevector, layout: MeasurementLayout, backend_qubits,
                        index_order: str):
    """Permute a statevector over ``backend_qubits`` into the declared qubit order.

    ``index_order`` is the backend's convention and is kept: ``"msb"`` makes declared qubit 0
    the most significant index bit, ``"lsb"`` the least. Returns ``(statevector, moved)``.
    """
    statevector = np.asarray(statevector)
    n = layout.n_qubits
    if statevector.size != 2 ** n:
        raise ValueError(
            f"statevector has {statevector.size} amplitudes; {n} declared qubits need {2 ** n}")
    positions = layout.qubit_positions(index_order, backend_qubits)
    targets = [n - 1 - j if index_order == "msb" else j for j in range(n)]
    if positions == targets:
        return statevector, False
    axes = [0] * n
    for source, target in zip(positions, targets):
        axes[n - 1 - target] = n - 1 - source
    return np.transpose(statevector.reshape([2] * n), axes).reshape(-1), True


def statevector_in_declaration_order(statevector, qasm: str, backend_qubits,
                                     index_order: str, notes: list):
    """``reorder_statevector`` for ``qasm``'s registers; appends the note when it moves."""
    statevector, moved = reorder_statevector(
        statevector, parse_measurement_layout(qasm), backend_qubits, index_order)
    if moved:
        notes.append(STATEVECTOR_REORDER_NOTE)
    return statevector


def counts_from_register_keys(layout: MeasurementLayout, counts: dict, registers,
                              bit_order: str) -> dict:
    """Re-key counts whose keys have one space-separated field per classical register."""
    return layout.counts_from_named(
        ((named_bits_from_register_key(k, registers), v) for k, v in counts.items()),
        bit_order)


def counts_from_pytket_result(layout: MeasurementLayout, result, compiled_bits, bits,
                              bit_order: str) -> dict:
    """Re-key a pytket ``BackendResult``'s counts over the declared classical bits.

    ``compiled_bits`` are the executed circuit's bits and ``bits`` the parsed circuit's
    ``(register, index)`` pairs, position for position. Only bits the result reads out are
    requested, so an unmeasured bit reads 0 instead of shifting its neighbours.
    """
    compiled_bits = list(compiled_bits)
    if len(compiled_bits) != len(bits):
        raise ValueError(
            f"backend compilation changed the number of classical bits "
            f"({len(bits)} declared, {len(compiled_bits)} compiled)")
    rename = dict(zip(compiled_bits, bits))
    read = [b for b in compiled_bits if b in result.c_bits]
    counts = result.get_counts(cbits=read)
    items = []
    for key, count in counts.items():
        if len(key) != len(read):
            raise ValueError(f"counts key {key} does not cover the bits read out {read}")
        items.append(({rename[b]: v for b, v in zip(read, key)}, count))
    return layout.counts_from_named(items, bit_order)


def unit_pairs(units) -> list:
    """``(register, index)`` pairs for pytket Qubit / Bit objects, in the given order."""
    return [(u.reg_name, u.index[0]) for u in units]
