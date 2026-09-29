"""Counts keys over a circuit's classical bits.

A counts key holds every declared classical bit, with no separators. The flat classical-bit
index follows creg declaration order (``creg a[2]; creg b[1]`` gives a[0]=0, a[1]=1, b[0]=2).
Bit order ``"lsb"`` puts flat clbit 0 rightmost; ``"msb"`` puts it leftmost. A classical bit
that no ``measure`` statement writes reads 0.
"""

import re
from collections import Counter

import numpy as np

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

IMPLICIT_MEASURE_ALL_NOTE = (
    "The circuit has no measure statements, so every qubit is read out: counts keys hold one "
    "bit per declared qubit in declaration order.")

_QREG_RE = re.compile(r"^qreg\s+(\w+)\s*\[\s*(\d+)\s*\]$")
_CREG_RE = re.compile(r"^creg\s+(\w+)\s*\[\s*(\d+)\s*\]$")
_GATE_DEF_RE = re.compile(r"\b(?:gate)\s+[^{;]*\{[^}]*\}", re.S)
_MEASURE_RE = re.compile(r"^measure\s+(.+?)\s*->\s*(.+)$", re.S)
_MEASURE_STMT_RE = re.compile(r"\bmeasure\b[^;]*;")
_ARG_RE = re.compile(r"^(\w+)\s*(?:\[\s*(\d+)\s*\])?$")
_NAME_RE = re.compile(r"^([A-Za-z_]\w*)")
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_SKIPPED_KEYWORDS = ("OPENQASM", "include", "opaque", "barrier")


def _strip_comments(qasm: str) -> str:
    return _LINE_COMMENT_RE.sub("", _BLOCK_COMMENT_RE.sub("", qasm))


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

    def implicit_measure_all(self) -> "MeasurementLayout":
        """A layout reading every qubit into its own classical bit, in declaration order."""
        return MeasurementLayout(
            self.qregs, [("meas", self.n_qubits)],
            [(q, q) for q in range(self.n_qubits)], self.non_terminal, self.has_reset,
            self.has_classical_control)

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


def strip_measurements(qasm: str) -> str:
    """Remove every ``measure`` statement (comments are removed too)."""
    return _MEASURE_STMT_RE.sub("", _strip_comments(qasm))


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
    statements reads out every qubit.
    """
    layout = parse_measurement_layout(qasm)
    layout.require_terminal()
    if not layout.has_measurements:
        return qasm, layout.implicit_measure_all(), [IMPLICIT_MEASURE_ALL_NOTE]
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
                f"({', '.join(names)}); the executed circuit's qubit order follows it.")
    return None


def counts_from_register_keys(layout: MeasurementLayout, counts: dict, registers,
                              bit_order: str) -> dict:
    """Re-key counts whose keys have one space-separated field per classical register."""
    return layout.counts_from_named(
        ((named_bits_from_register_key(k, registers), v) for k, v in counts.items()),
        bit_order)


def unit_pairs(units) -> list:
    """``(register, index)`` pairs for pytket Qubit / Bit objects, in the given order."""
    return [(u.reg_name, u.index[0]) for u in units]
