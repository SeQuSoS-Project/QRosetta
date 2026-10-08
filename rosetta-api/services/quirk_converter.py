"""OpenQASM 2.0 -> Quirk circuit URL. The circuit is merged into one register and parsed by
pytket; every gate becomes Quirk gates with the same matrix up to a global phase, or the
request is refused (QuirkUnsupported) naming the statement Quirk cannot show."""

import cmath
import json
import math
import urllib.parse

from services.circuit_resolver import (
    _classical_width, check_round_trip_integrity, evaluate_caret_parameters, flatten_qregs,
    normalise_index_spacing,
)
from services.pytket_lock import PYTKET_LOCK
from qrosetta_commons.helpers import get_num_qubits_from_qasm, strip_qasm_comments
from qrosetta_commons.qasm_expressions import tket_parameter_note

QUIRK_MAX_QUBITS = 16
QUIRK_MAX_COLUMNS = 1000
QUIRK_URL = "https://quirk-e.dev/#circuit="

_FIXED_1Q = {"H": "H", "X": "X", "Y": "Y", "Z": "Z", "S": "Z^½", "Sdg": "Z^-½", "T": "Z^¼",
             "Tdg": "Z^-¼", "SX": "X^½", "SXdg": "X^-½"}
_ROTATIONS = {"Rz": "Z^ft", "U1": "Z^ft", "Rx": "X^ft", "Ry": "Y^ft"}
_CONTROLLED = {"CX": "X", "CY": "Y", "CZ": "Z", "CH": "H", "CCX": "X", "CnX": "X",
               "CnY": "Y", "CnZ": "Z"}
_NO_EFFECT = {"noop", "Phase"}


class QuirkUnsupported(ValueError):
    """A circuit the visualizer cannot draw as the same circuit in Quirk."""


def _formula(half_turns: float):
    """Quirk formula text of an exponent in half-turns, reduced to (-1, 1]; None for 0."""
    value = math.remainder(half_turns, 2.0)
    if value == -1.0:
        value = 1.0
    text = f"{value:.17f}".rstrip("0").rstrip(".")
    return None if text in ("0", "-0") else text


def _zyz(matrix) -> list:
    """(Quirk id, exponent in half-turns) in time order: Z^l, Y^t, Z^p with
    U = e^{ia} Rz(p) Ry(t) Rz(l)."""
    det = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    root = cmath.sqrt(det)
    a, b = matrix[0][0] / root, matrix[1][0] / root
    theta = 2 * math.atan2(abs(b), abs(a))
    total = -2 * cmath.phase(a) if abs(a) > 1e-12 else 0.0
    diff = 2 * cmath.phase(b) if abs(b) > 1e-12 else 0.0
    phi, lam = (total + diff) / 2, (total - diff) / 2
    return [("Z^ft", lam / math.pi), ("Y^ft", theta / math.pi), ("Z^ft", phi / math.pi)]


class _Columns:
    """Quirk columns: single-qubit gates share columns; a multi-qubit gate gets a column of
    its own, because Quirk applies the controls of a column to every gate in it. Quirk draws
    as many wires as the last occupied one, so an idle last qubit gets Quirk's spacer gate
    ("…", no effect)."""

    def __init__(self, n_qubits: int):
        self.n, self.cols, self.multi, self.depth = n_qubits, [], [], [0] * n_qubits

    def _new(self, multi: bool) -> int:
        self.cols.append([1] * self.n)
        self.multi.append(multi)
        return len(self.cols) - 1

    def final(self, placed: dict) -> None:
        """A new last column holding ``placed`` (qubit -> gate)."""
        c = self._new(False)
        for q, gate in placed.items():
            self.cols[c][q] = gate

    def single(self, qubit: int, gate) -> None:
        for c in range(self.depth[qubit], len(self.cols)):
            if not self.multi[c] and self.cols[c][qubit] == 1:
                break
        else:
            c = self._new(False)
        self.cols[c][qubit] = gate
        self.depth[qubit] = c + 1

    def multiple(self, placed: dict) -> None:
        start = max(self.depth[q] for q in placed)
        for c in range(start, len(self.cols)):
            if all(cell == 1 for cell in self.cols[c]):
                self.multi[c] = True
                break
        else:
            c = self._new(True)
        for q, gate in placed.items():
            self.cols[c][q] = gate
            self.depth[q] = c + 1


def _single_gate(cols, qubit, quirk_id, half_turns=None):
    if half_turns is None:
        cols.single(qubit, quirk_id)
        return
    text = _formula(half_turns)
    if text is not None:
        cols.single(qubit, {"id": quirk_id, "arg": text})


def _place(cols, op, qubits, redrawn) -> None:
    """Add one pytket operation acting on ``qubits`` (indices) to ``cols``."""
    from pytket.circuit import Circuit
    from pytket.passes import DecomposeMultiQubitsCX

    name = op.type.name
    if name in _NO_EFFECT:
        return
    if len(qubits) == 1:
        q = qubits[0]
        if name in _FIXED_1Q:
            _single_gate(cols, q, _FIXED_1Q[name])
        elif name in _ROTATIONS:
            _single_gate(cols, q, _ROTATIONS[name], float(op.params[0]))
        else:
            sub = Circuit(1)
            sub.add_gate(op, [0])
            for quirk_id, half_turns in _zyz(sub.get_unitary()):
                _single_gate(cols, q, quirk_id, half_turns)
            redrawn.add(name)
        return
    if name in _CONTROLLED:
        placed = {q: "•" for q in qubits[:-1]}
        placed[qubits[-1]] = _CONTROLLED[name]
        cols.multiple(placed)
        return
    if name == "SWAP":
        cols.multiple({qubits[0]: "Swap", qubits[1]: "Swap"})
        return
    if name == "CSWAP":
        cols.multiple({qubits[0]: "•", qubits[1]: "Swap", qubits[2]: "Swap"})
        return
    sub = Circuit(len(qubits))
    sub.add_gate(op, list(range(len(qubits))))
    DecomposeMultiQubitsCX().apply(sub)
    for cmd in sub.get_commands():
        inner = [qubits[a.index[0]] for a in cmd.args]
        if cmd.op.type.name == name:
            raise QuirkUnsupported(f"the visualizer cannot draw the gate '{name.lower()}' in Quirk")
        _place(cols, cmd.op, inner, redrawn)
    redrawn.add(name)


def _prepared_text(qasm: str):
    notes = []
    text, note = normalise_index_spacing(qasm)
    text, merged = flatten_qregs(text)
    if merged:
        notes.append(f"Registers drawn as one: {merged.removeprefix('API: ')}.")
    text, _ = evaluate_caret_parameters(text)
    return strip_qasm_comments(text), notes


def quirk_columns(qasm: str):
    """``(columns, notes)``: Quirk's ``cols`` for ``qasm`` and what the drawing changed.
    Raises QuirkUnsupported for more than QUIRK_MAX_QUBITS qubits or QUIRK_MAX_COLUMNS
    columns, reset, classical control, or a gate on a qubit after it was measured."""
    n_qubits = get_num_qubits_from_qasm(qasm)
    if n_qubits > QUIRK_MAX_QUBITS:
        raise QuirkUnsupported(
            f"the visualizer opens circuits of at most {QUIRK_MAX_QUBITS} qubits, Quirk's limit; "
            f"this circuit declares {n_qubits}")
    text, notes = _prepared_text(qasm)
    with PYTKET_LOCK:
        import pytket.qasm
        from pytket.passes import DecomposeBoxes

        circ = pytket.qasm.circuit_from_qasm_str(text, maxwidth=_classical_width(text))
        check_round_trip_integrity(circ, text)
        DecomposeBoxes().apply(circ)
        cols, measured, redrawn, barriers = _Columns(circ.n_qubits), set(), set(), False
        index = {qubit: k for k, qubit in enumerate(circ.qubits)}
        for cmd in circ.get_commands():
            name = cmd.op.type.name
            qubits = [index[a] for a in cmd.args if a in index]
            if name == "Barrier":
                barriers = True
                continue
            if name in ("Reset", "Conditional"):
                raise QuirkUnsupported(
                    "the visualizer draws gates and final measurements; this circuit uses "
                    f"{'reset' if name == 'Reset' else 'classically controlled gates (if)'}")
            if set(qubits) & measured:
                raise QuirkUnsupported(
                    "the visualizer draws gates and final measurements; this circuit applies a "
                    "gate to a qubit after measuring it")
            if name == "Measure":
                measured.add(qubits[0])
                continue
            _place(cols, cmd.op, qubits, redrawn)
            if len(cols.cols) > QUIRK_MAX_COLUMNS:
                raise QuirkUnsupported(f"the drawing needs more than {QUIRK_MAX_COLUMNS} columns, "
                                       f"the most the visualizer draws")
    if measured:
        cols.final({q: "Measure" for q in measured})
    if circ.n_qubits and cols.depth[-1] == 0 and circ.n_qubits - 1 not in measured:
        cols.single(circ.n_qubits - 1, "…")
    if len(cols.cols) > QUIRK_MAX_COLUMNS:
        raise QuirkUnsupported(f"the drawing needs more than {QUIRK_MAX_COLUMNS} columns, the "
                               f"most the visualizer draws")
    if redrawn:
        notes.append(
            "Drawn with other Quirk gates, same matrix up to a global phase (pytket's gate "
            "names): "
            + ", ".join(sorted(n.lower() for n in redrawn))
            + " (multi-qubit gates as cx and single-qubit rotations, single-qubit gates as "
              "Z^t, Y^t, Z^t).")
    if barriers:
        notes.append("Barriers are not drawn; they do not change the state.")
    tket_note = tket_parameter_note(text, "tket, which parses the circuit for the visualizer,")
    if tket_note:
        notes.append(tket_note)
    return cols.cols, notes


def quirk_url(qasm: str):
    """``(url, notes)`` opening ``qasm`` in Quirk."""
    cols, notes = quirk_columns(qasm)
    payload = json.dumps({"cols": cols}, ensure_ascii=False, separators=(",", ":"))
    return QUIRK_URL + urllib.parse.quote(payload, safe=""), notes

