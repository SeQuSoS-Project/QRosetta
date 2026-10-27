"""Independent numpy reference for the self-test's expected answers: a statevector simulator
for the qelib1 gates the self-test circuits use (x, h, ry, rz, cx) and the counts key of a
deterministic measured circuit. It calls no backend SDK and no pytket; each gate is built
from its qelib1.inc matrix.

Statevectors are in "lsb" order: amplitude index = sum of b_k * 2**k over qubits k, with
qubits flattened over the qreg declarations in declaration order.
"""

import math
import re

import numpy as np

_H = 1 / math.sqrt(2)

SINGLE_QUBIT_GATES = {
    "x": lambda: np.array([[0, 1], [1, 0]], dtype=complex),
    "h": lambda: np.array([[_H, _H], [_H, -_H]], dtype=complex),
    "ry": lambda theta: np.array([[math.cos(theta / 2), -math.sin(theta / 2)],
                                  [math.sin(theta / 2), math.cos(theta / 2)]], dtype=complex),
    "rz": lambda phi: np.array([[1, 0], [0, complex(math.cos(phi), math.sin(phi))]], dtype=complex),
}
PARAMETER_COUNTS = {"x": 0, "h": 0, "ry": 1, "rz": 1, "cx": 0}

_DECL = re.compile(r"^(qreg|creg)\s+([a-z][A-Za-z0-9_]*)\s*\[\s*(\d+)\s*\]$")
_GATE = re.compile(r"^([a-z][a-z0-9]*)\s*(?:\(([^)]*)\))?\s+(.+)$")
_OPERAND = re.compile(r"^([a-z][A-Za-z0-9_]*)\s*\[\s*(\d+)\s*\]$")
_MEASURE = re.compile(r"^measure\s+(.+?)\s*->\s*(.+)$")
_FLOAT = re.compile(r"^-?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?$")


class ReferenceError(ValueError):
    """The circuit uses something outside the reference's subset."""


def _statements(qasm: str) -> list:
    text = re.sub(r"//[^\n]*", "", qasm)
    return [s.strip() for s in text.split(";") if s.strip()]


def parse_circuit(qasm: str) -> dict:
    """``{n_qubits, n_clbits, gates: [(name, params, qubits)], measures: [(qubit, clbit)]}``
    with register indices flattened in declaration order. Accepts the OPENQASM 2.0 header,
    the qelib1 include, qreg/creg declarations, the gates of ``PARAMETER_COUNTS`` with
    decimal parameters, and ``measure`` of single bits, after which a measured qubit takes no
    gate; anything else raises ReferenceError."""
    qregs, cregs, n_qubits, n_clbits = {}, {}, 0, 0
    gates, measures = [], []

    def operand(text, registers):
        match = _OPERAND.match(text.strip())
        if not match or match.group(1) not in registers:
            raise ReferenceError(f"operand {text!r} is not a declared single bit")
        offset, size = registers[match.group(1)]
        index = int(match.group(2))
        if index >= size:
            raise ReferenceError(f"index {index} out of range in {text!r}")
        return offset + index

    for statement in _statements(qasm):
        if statement == "OPENQASM 2.0" or statement == 'include "qelib1.inc"':
            continue
        decl = _DECL.match(statement)
        if decl:
            kind, name, size = decl.group(1), decl.group(2), int(decl.group(3))
            if name in qregs or name in cregs:
                raise ReferenceError(f"register {name} declared twice")
            if kind == "qreg":
                qregs[name] = (n_qubits, size)
                n_qubits += size
            else:
                cregs[name] = (n_clbits, size)
                n_clbits += size
            continue
        measure = _MEASURE.match(statement)
        if measure:
            measures.append((operand(measure.group(1), qregs), operand(measure.group(2), cregs)))
            continue
        gate = _GATE.match(statement)
        if not gate or gate.group(1) not in PARAMETER_COUNTS:
            raise ReferenceError(f"statement {statement!r} is outside the reference subset")
        name = gate.group(1)
        raw = [p.strip() for p in gate.group(2).split(",")] if gate.group(2) is not None else []
        if len(raw) != PARAMETER_COUNTS[name] or not all(_FLOAT.match(p) for p in raw):
            raise ReferenceError(f"{name} needs {PARAMETER_COUNTS[name]} decimal parameter(s)")
        qubits = [operand(o, qregs) for o in gate.group(3).split(",")]
        if len(qubits) != (2 if name == "cx" else 1) or len(set(qubits)) != len(qubits):
            raise ReferenceError(f"{name} has the wrong operands in {statement!r}")
        if any(q == measured for q in qubits for measured, _clbit in measures):
            raise ReferenceError("a gate on a measured qubit is outside the reference subset")
        gates.append((name, tuple(float(p) for p in raw), tuple(qubits)))
    if n_qubits == 0:
        raise ReferenceError("no qreg declared")
    return {"n_qubits": n_qubits, "n_clbits": n_clbits, "gates": gates, "measures": measures}


def _axis(qubit: int, n_qubits: int) -> int:
    return n_qubits - 1 - qubit


def apply_single(state: np.ndarray, matrix: np.ndarray, qubit: int, n_qubits: int) -> np.ndarray:
    """``matrix`` applied to ``qubit`` of an lsb-ordered statevector."""
    tensor = state.reshape([2] * n_qubits)
    axis = _axis(qubit, n_qubits)
    tensor = np.moveaxis(np.tensordot(matrix, tensor, axes=([1], [axis])), 0, axis)
    return tensor.reshape(-1)


def apply_cx(state: np.ndarray, control: int, target: int, n_qubits: int) -> np.ndarray:
    """cx with ``control`` and ``target`` on an lsb-ordered statevector: the target's bit is
    flipped on the half of the amplitudes whose control bit is 1."""
    tensor = state.reshape([2] * n_qubits).copy()
    c_axis, t_axis = _axis(control, n_qubits), _axis(target, n_qubits)
    index = [slice(None)] * n_qubits
    index[c_axis] = 1
    sub = tensor[tuple(index)]
    t_sub_axis = t_axis if t_axis < c_axis else t_axis - 1
    tensor[tuple(index)] = np.flip(sub, axis=t_sub_axis)
    return tensor.reshape(-1)


def simulate_gates(n_qubits: int, gates: list) -> np.ndarray:
    """Statevector (lsb) of ``gates`` applied to |0...0>."""
    state = np.zeros(2 ** n_qubits, dtype=complex)
    state[0] = 1
    for name, params, qubits in gates:
        if name == "cx":
            state = apply_cx(state, qubits[0], qubits[1], n_qubits)
        else:
            state = apply_single(state, SINGLE_QUBIT_GATES[name](*params), qubits[0], n_qubits)
    return state


def statevector(qasm: str) -> np.ndarray:
    """The lsb statevector of ``qasm`` before any measurement."""
    circuit = parse_circuit(qasm)
    return simulate_gates(circuit["n_qubits"], circuit["gates"])


def to_msb(state: np.ndarray) -> np.ndarray:
    """An lsb statevector with qubit 0 moved to the most significant index bit."""
    n_qubits = int(round(math.log2(len(state))))
    return state.reshape([2] * n_qubits).transpose(tuple(reversed(range(n_qubits)))).reshape(-1)


def deterministic_counts_key(qasm: str) -> dict:
    """``{"lsb": key, "msb": key}`` for a circuit whose state before measurement is one basis
    state. Keys hold every classical bit in creg declaration order (flat clbit 0 rightmost
    under lsb, leftmost under msb); a bit no measure writes reads 0. Raises ReferenceError
    when the state is not a single basis state or there is no classical bit."""
    circuit = parse_circuit(qasm)
    if circuit["n_clbits"] == 0:
        raise ReferenceError("no creg declared")
    state = simulate_gates(circuit["n_qubits"], circuit["gates"])
    probabilities = np.abs(state) ** 2
    index = int(np.argmax(probabilities))
    if not math.isclose(probabilities[index], 1.0, abs_tol=1e-12):
        raise ReferenceError("the state before measurement is not a single basis state")
    bits = [0] * circuit["n_clbits"]
    for qubit, clbit in circuit["measures"]:
        bits[clbit] = (index >> qubit) & 1
    lsb = "".join(str(b) for b in reversed(bits))
    return {"lsb": lsb, "msb": lsb[::-1]}


def fidelity(expected: np.ndarray, actual: np.ndarray) -> float:
    """|<e|a>|^2 of the two vectors after each is divided by its norm, clamped to [0, 1]."""
    e = np.asarray(expected, dtype=complex)
    a = np.asarray(actual, dtype=complex)
    e = e / np.linalg.norm(e)
    a = a / np.linalg.norm(a)
    return float(min(max(abs(np.vdot(e, a)) ** 2, 0.0), 1.0))
