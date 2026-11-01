"""Independent numpy reference for OpenQASM 2.0 circuits over every gate of qelib1.inc: each
gate's matrix is built from its qelib1.inc definition down to U and CX, so the reference rests
on the definitions alone and calls no backend SDK or pytket. Statevectors are in lsb order
(amplitude index = sum of b_k * 2**k, qubits flattened over the qreg declarations in
declaration order). Results agree with the definitions up to a global phase, which every
fidelity used here ignores."""

import ast
import copy
import math
import operator
import re
from pathlib import Path

import numpy as np

QELIB1 = Path(__file__).resolve().parents[2] / "shared" / "qrosetta_commons" / "qelib1_qiskit.inc"

_GATE_DEF = re.compile(r"gate\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(([^)]*)\))?\s*([^{]*)\{([^}]*)\}", re.S)
_CALL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*)\))?\s+(.+)$", re.S)
_DECL = re.compile(r"^(qreg|creg)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*(\d+)\s*\]$")
_OPERAND = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*(\d+)\s*\]$")
_MEASURE = re.compile(r"^measure\s+(.+?)\s*->\s*(.+)$")

_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_PREFIX = "qasm_"
_IDENT = re.compile(r"(?<![0-9.eE])\b[A-Za-z_][A-Za-z0-9_]*\b")
_FUNCTIONS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
              "ln": math.log, "sqrt": math.sqrt}


class ReferenceError(ValueError):
    """The circuit uses something the reference does not model."""


def evaluate(expression: str, names: dict) -> float:
    """An OpenQASM 2.0 parameter expression with ``pi`` and the given names. Identifiers are
    prefixed before Python parses the text, so Python keywords (``lambda``) are valid names."""
    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id.startswith(_PREFIX):
            name = node.id[len(_PREFIX):]
            if name == "pi":
                return math.pi
            if name in names:
                return names[name]
            raise ReferenceError(f"unknown name {name!r}")
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return _BINARY[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](walk(node.operand))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id[len(_PREFIX):] in _FUNCTIONS and len(node.args) == 1 and not node.keywords):
            return _FUNCTIONS[node.func.id[len(_PREFIX):]](walk(node.args[0]))
        raise ReferenceError(f"unsupported expression {expression!r}")
    try:
        source = _IDENT.sub(lambda m: _PREFIX + m.group(0), expression.replace("^", "**").strip())
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise ReferenceError(f"unparsable expression {expression!r}") from exc
    return float(walk(tree))


def _split_args(text: str) -> list:
    parts, depth, current = [], 0, ""
    for ch in text:
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


def u_matrix(theta: float, phi: float, lam: float) -> np.ndarray:
    """OpenQASM 2.0's U(theta, phi, lambda) = Rz(phi) Ry(theta) Rz(lambda), with the global
    phase that makes it equal to qelib1's u3."""
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -np.exp(1j * lam) * s],
                     [np.exp(1j * phi) * s, np.exp(1j * (phi + lam)) * c]], dtype=complex)


def _axis(qubit: int, n: int) -> int:
    return n - 1 - qubit


def apply(state: np.ndarray, matrix: np.ndarray, qubits, n: int) -> np.ndarray:
    """``matrix`` (lsb over its operands: operand j is bit j) applied to ``qubits`` of an
    lsb statevector of ``n`` qubits."""
    k = len(qubits)
    tensor = state.reshape([2] * n)
    gate = matrix.reshape([2] * (2 * k))
    in_axes = [_axis(qubits[k - 1 - i], n) for i in range(k)]
    out = np.tensordot(gate, tensor, axes=(list(range(k, 2 * k)), in_axes))
    return np.moveaxis(out, list(range(k)), in_axes).reshape(-1)


def _cx_matrix() -> np.ndarray:
    m = np.zeros((4, 4), dtype=complex)
    for index in range(4):
        control, target = index & 1, (index >> 1) & 1
        m[(control | ((target ^ control) << 1)), index] = 1
    return m


class GateLibrary:
    """Gate definitions (qelib1.inc plus any a circuit declares) and their matrices."""

    def __init__(self, text: str = None, overrides: dict = None):
        """``overrides``: gate name -> function(matrix, params) -> the matrix used instead of
        that gate's own; every other gate, and the matrix an override receives, are built from
        the definitions without overrides."""
        self.defs = {}
        self.overrides = dict(overrides or {})
        self.add_definitions(text if text is not None else QELIB1.read_text())

    def add_definitions(self, text: str):
        text = re.sub(r"//[^\n]*", "", text)
        for match in _GATE_DEF.finditer(text):
            name, params, qargs, body = match.groups()
            self.defs[name] = {
                "params": [p.strip() for p in (params or "").split(",") if p.strip()],
                "qubits": [q.strip() for q in qargs.split(",") if q.strip()],
                "body": [s.strip() for s in body.split(";") if s.strip()],
            }

    def arity(self, name: str) -> int:
        if name == "U":
            return 1
        if name == "CX":
            return 2
        return len(self.defs[name]["qubits"])

    def parameter_count(self, name: str) -> int:
        if name == "U":
            return 3
        if name == "CX":
            return 0
        return len(self.defs[name]["params"])

    def names(self) -> list:
        return sorted(self.defs)

    def matrix(self, name: str, params=()) -> np.ndarray:
        """The 2**k x 2**k matrix of gate ``name`` with numeric ``params``, lsb over its operands."""
        if name in self.overrides:
            return self.overrides[name](self._matrix(name, params), params)
        return self._matrix(name, params)

    def _sub(self, name, params):
        return self._matrix(name, params) if self.overrides else self.matrix(name, params)

    def _matrix(self, name, params):
        if name == "U":
            return u_matrix(*params)
        if name == "CX":
            return _cx_matrix()
        if name not in self.defs:
            raise ReferenceError(f"unknown gate {name!r}")
        d = self.defs[name]
        if len(params) != len(d["params"]):
            raise ReferenceError(f"{name} takes {len(d['params'])} parameters, got {len(params)}")
        names = dict(zip(d["params"], params, strict=True))
        index = {q: i for i, q in enumerate(d["qubits"])}
        k = len(d["qubits"])
        unitary = np.eye(2 ** k, dtype=complex)
        for statement in d["body"]:
            if statement.startswith("barrier"):
                continue
            call = _CALL.match(statement)
            if not call:
                raise ReferenceError(f"unparsable body statement {statement!r} in {name}")
            inner, raw, operands = call.groups()
            values = [evaluate(p, names) for p in _split_args(raw)] if raw else []
            targets = [index[o.strip()] for o in operands.split(",")]
            sub = self._sub(inner, values)
            unitary = np.column_stack([apply(unitary[:, j], sub, targets, k) for j in range(2 ** k)])
        return unitary


def reverse_operands(matrix: np.ndarray) -> np.ndarray:
    """The matrix with its operand order reversed (operand j becomes operand k-1-j)."""
    k = int(round(math.log2(matrix.shape[0])))
    index = [int(format(i, f"0{k}b")[::-1], 2) for i in range(2 ** k)]
    return matrix[np.ix_(index, index)]


def parse(qasm: str, library: GateLibrary = None) -> dict:
    """``{n_qubits, n_clbits, ops: [(name, params, qubits)], measures: [(qubit, clbit)],
    library}``; register indices flattened in declaration order. Gate definitions in the
    circuit are added to a copy of the library."""
    library = library or GateLibrary()
    own = copy.copy(library)
    own.defs = dict(library.defs)
    text = re.sub(r"//[^\n]*", "", qasm)
    own.add_definitions(text)
    text = _GATE_DEF.sub("", text)
    qregs, cregs, n_qubits, n_clbits, ops, measures = {}, {}, 0, 0, [], []

    def bit(operand, registers):
        match = _OPERAND.match(operand.strip())
        if not match or match.group(1) not in registers:
            raise ReferenceError(f"operand {operand!r} is not a declared single bit")
        offset, size = registers[match.group(1)]
        if int(match.group(2)) >= size:
            raise ReferenceError(f"index out of range in {operand!r}")
        return offset + int(match.group(2))

    for statement in [s.strip() for s in text.split(";") if s.strip()]:
        if statement.startswith("OPENQASM") or statement.startswith("include"):
            continue
        decl = _DECL.match(statement)
        if decl:
            kind, reg, size = decl.group(1), decl.group(2), int(decl.group(3))
            if kind == "qreg":
                qregs[reg] = (n_qubits, size)
                n_qubits += size
            else:
                cregs[reg] = (n_clbits, size)
                n_clbits += size
            continue
        if statement.startswith("barrier"):
            continue
        measure = _MEASURE.match(statement)
        if measure:
            measures.append((bit(measure.group(1), qregs), bit(measure.group(2), cregs)))
            continue
        call = _CALL.match(statement)
        if not call:
            raise ReferenceError(f"unparsable statement {statement!r}")
        name, raw, operands = call.groups()
        if name not in own.defs and name not in ("U", "CX"):
            raise ReferenceError(f"unknown gate {name!r}")
        params = tuple(evaluate(p, {}) for p in _split_args(raw)) if raw else ()
        qubits = tuple(bit(o, qregs) for o in operands.split(","))
        if len(qubits) != own.arity(name) or len(set(qubits)) != len(qubits):
            raise ReferenceError(f"wrong operands in {statement!r}")
        if any(q == m for q in qubits for m, _c in measures):
            raise ReferenceError("a gate after a measurement of its qubit is not modelled")
        ops.append((name, params, qubits))
    if n_qubits == 0:
        raise ReferenceError("no qreg declared")
    return {"n_qubits": n_qubits, "n_clbits": n_clbits, "ops": ops, "measures": measures, "library": own}


def statevector(qasm: str, library: GateLibrary = None) -> np.ndarray:
    """The lsb statevector of ``qasm`` on |0...0>, before any measurement."""
    circuit = parse(qasm, library)
    n = circuit["n_qubits"]
    state = np.zeros(2 ** n, dtype=complex)
    state[0] = 1
    cache = {}
    for name, params, qubits in circuit["ops"]:
        key = (name, params)
        if key not in cache:
            cache[key] = circuit["library"].matrix(name, params)
        state = apply(state, cache[key], qubits, n)
    return state


def clbit_distribution(qasm: str, library: GateLibrary = None) -> dict:
    """``{lsb key: probability}`` over the classical bits (creg declaration order, clbit 0
    rightmost) for a circuit whose measurements are all terminal."""
    circuit = parse(qasm, library)
    if circuit["n_clbits"] == 0:
        raise ReferenceError("no creg declared")
    state = statevector(qasm, library)
    out = {}
    for index, p in enumerate(np.abs(state) ** 2):
        if p < 1e-15:
            continue
        bits = [0] * circuit["n_clbits"]
        for qubit, clbit in circuit["measures"]:
            bits[clbit] = (index >> qubit) & 1
        key = "".join(str(b) for b in reversed(bits))
        out[key] = out.get(key, 0.0) + float(p)
    return out


def to_order(state: np.ndarray, ordering: str) -> np.ndarray:
    """An lsb statevector in ``ordering`` (lsb, or msb with qubit 0 most significant)."""
    if ordering == "lsb":
        return state
    if ordering != "msb":
        raise ValueError(f"unknown ordering {ordering!r}")
    n = int(round(math.log2(len(state))))
    return state.reshape([2] * n).transpose(tuple(reversed(range(n)))).reshape(-1)


def fidelity(expected, actual) -> float:
    """|<e|a>|^2 of the two vectors, each divided by its norm, clamped to [0, 1]."""
    e = np.asarray(expected, dtype=complex)
    a = np.asarray(actual, dtype=complex)
    e = e / np.linalg.norm(e)
    a = a / np.linalg.norm(a)
    return float(min(max(abs(np.vdot(e, a)) ** 2, 0.0), 1.0))
