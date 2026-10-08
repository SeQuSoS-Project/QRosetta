"""The Quirk visualizer draws every gate with the circuit's own matrix (up to a global phase)
or refuses the circuit. Quirk's gates are modelled from its source (Strilanc/Quirk
src/gates: Z^t = fromPauliRotation(0, 0, t/2), the same rotation sense for X and Y; X^½ etc.
fixed powers; '•' controls every gate of its column)."""
import json
import math
import random
import urllib.parse

import numpy as np
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("pytket")

from services.quirk_converter import QUIRK_URL, QuirkUnsupported, quirk_columns, quirk_url

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
_H = np.array([[1, 1], [1, -1]]) / math.sqrt(2)
_S = np.diag([1, 1j])


def _z(t):
    return np.diag([1, np.exp(1j * math.pi * t)])


def _x(t):
    return _H @ _z(t) @ _H


def _y(t):
    return _S @ _x(t) @ _S.conj().T


_FIXED = {"H": _H, "X": _x(1), "Y": _y(1), "Z": _z(1), "Z^½": _z(0.5), "Z^-½": _z(-0.5),
          "Z^¼": _z(0.25), "Z^-¼": _z(-0.25), "X^½": _x(0.5), "X^-½": _x(-0.5), "…": np.eye(2),
          "Measure": np.eye(2)}
_FORMULA = {"Z^ft": _z, "X^ft": _x, "Y^ft": _y}


def _gate(cell):
    if isinstance(cell, dict):
        return _FORMULA[cell["id"]](float(cell["arg"]))
    return _FIXED[cell]


def _apply(state, matrix, qubit, n, controls=()):
    """Apply a 2x2 ``matrix`` to ``qubit`` (qubit 0 most significant, pytket's order)."""
    out = state.copy()
    for index in range(2 ** n):
        bit = (index >> (n - 1 - qubit)) & 1
        if bit or any(not (index >> (n - 1 - c)) & 1 for c in controls):
            continue
        partner = index | (1 << (n - 1 - qubit))
        a, b = state[index], state[partner]
        out[index] = matrix[0, 0] * a + matrix[0, 1] * b
        out[partner] = matrix[1, 0] * a + matrix[1, 1] * b
    return out


def _swap(state, a, b, n, controls=()):
    out = state.copy()
    for index in range(2 ** n):
        if any(not (index >> (n - 1 - c)) & 1 for c in controls):
            continue
        ba, bb = (index >> (n - 1 - a)) & 1, (index >> (n - 1 - b)) & 1
        if ba != bb:
            out[index ^ (1 << (n - 1 - a)) ^ (1 << (n - 1 - b))] = state[index]
    return out


def _quirk_unitary(cols, n):
    columns = []
    for k in range(2 ** n):
        state = np.zeros(2 ** n, dtype=complex)
        state[k] = 1
        for col in cols:
            controls = [q for q, cell in enumerate(col) if cell == "•"]
            swaps = [q for q, cell in enumerate(col) if cell == "Swap"]
            if swaps:
                state = _swap(state, swaps[0], swaps[1], n, controls)
            for q, cell in enumerate(col):
                if cell not in (1, "•", "Swap"):
                    state = _apply(state, _gate(cell), q, n, controls)
        columns.append(state)
    return np.array(columns).T


def _same_up_to_phase(a, b):
    k = np.unravel_index(np.argmax(abs(b)), b.shape)
    phase = a[k] / b[k]
    return abs(abs(phase) - 1) < 1e-9 and np.allclose(a, phase * b, atol=1e-9)


def _circuit_unitary(qasm):
    from pytket.passes import DecomposeBoxes
    from pytket.qasm import circuit_from_qasm_str
    from services.circuit_resolver import flatten_qregs
    circ = circuit_from_qasm_str(flatten_qregs(qasm)[0])
    DecomposeBoxes().apply(circ)
    return circ.get_unitary(), circ.n_qubits


_GATES_1Q = ["h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx", "sxdg", "id"]
_GATES_1Q_P = {"rx": 1, "ry": 1, "rz": 1, "u1": 1, "p": 1, "u2": 2, "u3": 3, "u": 3}
_GATES_2Q = ["cx", "cy", "cz", "ch", "swap", "csx"]
_GATES_2Q_P = {"crx": 1, "cry": 1, "crz": 1, "cu1": 1, "cp": 1, "cu3": 3, "rzz": 1, "rxx": 1, "cu": 4}
_GATES_3Q = ["ccx", "cswap", "rccx"]


def _random_circuit(rng, n, length):
    lines = [f"qreg q[{n}];"]
    for _ in range(length):
        kind = rng.random()
        qs = rng.sample(range(n), 3 if n >= 3 else n)
        angle = lambda: f"{rng.uniform(-7, 7):.6f}"
        if kind < 0.3:
            lines.append(f"{rng.choice(_GATES_1Q)} q[{qs[0]}];")
        elif kind < 0.55:
            g = rng.choice(sorted(_GATES_1Q_P))
            lines.append(f"{g}({','.join(angle() for _ in range(_GATES_1Q_P[g]))}) q[{qs[0]}];")
        elif kind < 0.7:
            lines.append(f"{rng.choice(_GATES_2Q)} q[{qs[0]}],q[{qs[1]}];")
        elif kind < 0.9:
            g = rng.choice(sorted(_GATES_2Q_P))
            lines.append(f"{g}({','.join(angle() for _ in range(_GATES_2Q_P[g]))}) q[{qs[0]}],q[{qs[1]}];")
        elif n >= 3:
            lines.append(f"{rng.choice(_GATES_3Q)} q[{qs[0]}],q[{qs[1]}],q[{qs[2]}];")
    return HEAD + "\n".join(lines) + "\n"


@pytest.mark.parametrize("seed", range(40))
def test_random_qelib1_circuits_are_drawn_with_their_own_unitary(seed):
    rng = random.Random(seed)
    qasm = _random_circuit(rng, rng.randint(2, 4), rng.randint(1, 25))
    cols, _notes = quirk_columns(qasm)
    expected, n = _circuit_unitary(qasm)
    assert _same_up_to_phase(_quirk_unitary(cols, n), expected), qasm


@pytest.mark.parametrize("body", [
    "qreg q[2];\nry(0.5) q[0];\ncx q[0],q[1];\n",
    "gate g(a) x, y { cu3(a, a/2, -a) x, y; rz(a) y; }\nqreg q[2];\ng(0.7) q[1], q[0];\n",
    "qreg a[1];\nqreg b[2];\nh a[0];\ncx a[0], b[1];\ncrz(0.3) b[1], b[0];\n",
    "qreg q[5];\nc3x q[0],q[1],q[2],q[3];\nc4x q[4],q[0],q[1],q[2],q[3];\n",
    "qreg q[3];\n// TODO; x q[1]\nh q[0];\n",
])
def test_reported_circuits_are_drawn_exactly(body):
    qasm = HEAD + body
    cols, _ = quirk_columns(qasm)
    expected, n = _circuit_unitary(qasm)
    assert _same_up_to_phase(_quirk_unitary(cols, n), expected)


def test_a_comment_does_not_add_a_gate():
    cols, _ = quirk_columns(HEAD + "qreg q[2];\n// TODO; x q[1]\nh q[0];\n")
    assert cols == [["H", "…"]]


def test_named_gates_keep_their_quirk_symbols():
    cols, notes = quirk_columns(HEAD + "qreg q[3];\nh q[0];\ns q[1];\ntdg q[2];\ncx q[0],q[1];\n"
                                       "ccx q[0],q[1],q[2];\nswap q[0],q[2];\nrz(pi/2) q[0];\n")
    assert cols[0] == ["H", "Z^½", "Z^-¼"]
    assert ["•", "X", 1] in cols and ["•", "•", "X"] in cols and ["Swap", 1, "Swap"] in cols
    assert {"id": "Z^ft", "arg": "0.5"} in cols[-1]
    assert notes == []


def test_redrawn_gates_registers_and_barriers_are_listed():
    _, notes = quirk_columns(HEAD + "qreg a[1];\nqreg b[1];\ncrz(0.2) a[0],b[0];\nbarrier a,b;\n"
                                    "u3(0.1,0.2,0.3) b[0];\n")
    text = " ".join(notes)
    assert "Registers drawn as one" in text and "crz" in text and "u3" in text
    assert "Barriers are not drawn" in text


def test_final_measurements_are_drawn():
    cols, _ = quirk_columns(HEAD + "qreg q[2];\ncreg c[2];\nh q[0];\nmeasure q -> c;\n")
    assert cols == [["H", 1], ["Measure", "Measure"]]


@pytest.mark.parametrize("body,message", [
    ("qreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];\nh q[0];\n", "after measuring it"),
    ("qreg q[1];\nreset q[0];\n", "uses reset"),
    ("qreg q[1];\ncreg c[1];\nif(c==1) x q[0];\n", "classically controlled"),
    ("qreg q[17];\nh q[0];\n", "at most 16 qubits"),
])
def test_circuits_quirk_cannot_show_are_refused(body, message):
    with pytest.raises(QuirkUnsupported, match=message):
        quirk_columns(HEAD + body)


def test_a_drawing_wider_than_the_column_limit_is_refused(monkeypatch):
    import services.quirk_converter as converter
    monkeypatch.setattr(converter, "QUIRK_MAX_COLUMNS", 3)
    with pytest.raises(QuirkUnsupported, match="more than 3 columns"):
        quirk_columns(HEAD + "qreg q[2];\n" + "cx q[0],q[1];\n" * 4)
    assert len(quirk_columns(HEAD + "qreg q[2];\n" + "cx q[0],q[1];\n" * 3)[0]) == 3


def test_idle_qubits_are_drawn_as_wires():
    cols, _ = quirk_columns(HEAD + "qreg q[4];\nh q[0];\n")
    assert cols == [["H", 1, 1, "…"]]


def test_url_carries_the_columns():
    url, _ = quirk_url(HEAD + "qreg q[2];\nh q[0];\ncx q[0],q[1];\n")
    assert url.startswith(QUIRK_URL)
    assert json.loads(urllib.parse.unquote(url[len(QUIRK_URL):])) == {"cols": [["H", 1], ["•", "X"]]}


@pytest.fixture()
def client():
    from main import app
    return TestClient(app)


@pytest.mark.parametrize("body,status,expected", [
    ("qreg q[20];\nh q[0];\n", 400, "The visualizer opens circuits of at most 16 qubits, Quirk's limit; this circuit declares 20."),
    ("qreg q[1];\nreset q[0];\n", 400, "Cannot draw this circuit in Quirk: the visualizer draws gates and final measurements"),
    ("qreg q[1];\ng q[0];\n", 400, "Line 4: unknown gate 'g'"),
    ("qreg a[1];\nqreg b[1];\ncx a[0],b[0];\n", 200, None),
])
def test_endpoint(client, body, status, expected):
    r = client.post("/visualize/quirk", json={"qasm_string": HEAD + body})
    assert r.status_code == status, r.text
    if expected:
        assert r.json()["detail"].startswith(expected)
    else:
        assert r.json()["url"].startswith(QUIRK_URL) and r.json()["notes"]
