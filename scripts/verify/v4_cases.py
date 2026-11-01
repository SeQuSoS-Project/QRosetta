"""V4 cases: OpenQASM 2.0 circuits with known answers, generated from fixed seeds.

gate-*      every qelib1 gate on a random product state, operands in several orders
relabel-*   a random circuit and the same circuit with its qubit indices permuted (pairs)
inverse-*   a random circuit followed by its inverse (expected |0...0>)
split-*     one circuit on qreg q[4] and on qreg a[2]; qreg b[2] (pairs)

Each case is ``{name, family, n_qubits, qasm, ...}``; a relabelled case carries
``pair`` (the original's name) and ``perm`` (original qubit i -> perm[i])."""

import math
import random

import qelib1_reference as ref

SEED = 20261101
HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'

# Gates with a closed-form inverse: name -> function(params) -> (name, params).
INVERSES = {
    "x": lambda p: ("x", ()), "y": lambda p: ("y", ()), "z": lambda p: ("z", ()), "h": lambda p: ("h", ()),
    "s": lambda p: ("sdg", ()), "sdg": lambda p: ("s", ()), "t": lambda p: ("tdg", ()), "tdg": lambda p: ("t", ()),
    "sx": lambda p: ("sxdg", ()), "sxdg": lambda p: ("sx", ()), "id": lambda p: ("id", ()),
    "rx": lambda p: ("rx", (-p[0],)), "ry": lambda p: ("ry", (-p[0],)), "rz": lambda p: ("rz", (-p[0],)),
    "p": lambda p: ("p", (-p[0],)), "u1": lambda p: ("u1", (-p[0],)),
    "u3": lambda p: ("u3", (-p[0], -p[2], -p[1])), "u": lambda p: ("u", (-p[0], -p[2], -p[1])),
    "cx": lambda p: ("cx", ()), "cy": lambda p: ("cy", ()), "cz": lambda p: ("cz", ()), "ch": lambda p: ("ch", ()),
    "swap": lambda p: ("swap", ()), "ccx": lambda p: ("ccx", ()), "cswap": lambda p: ("cswap", ()),
    "crx": lambda p: ("crx", (-p[0],)), "cry": lambda p: ("cry", (-p[0],)), "crz": lambda p: ("crz", (-p[0],)),
    "cu1": lambda p: ("cu1", (-p[0],)), "cp": lambda p: ("cp", (-p[0],)),
    "cu3": lambda p: ("cu3", (-p[0], -p[2], -p[1])),
    "rxx": lambda p: ("rxx", (-p[0],)), "rzz": lambda p: ("rzz", (-p[0],)),
    "c3x": lambda p: ("c3x", ()), "c4x": lambda p: ("c4x", ()),
}


def fmt(value: float) -> str:
    return repr(float(value))


def statement(name: str, params, qubits, reg="q") -> str:
    args = f"({','.join(fmt(p) for p in params)})" if params else ""
    return f"{name}{args} {','.join(f'{reg}[{q}]' for q in qubits)};"


def circuit(n: int, ops, measure=False, regs=None, measured=None) -> str:
    """Text of ``ops`` [(name, params, qubits)] on ``qreg q[n]`` (or ``regs``, a list of
    (name, size) whose flat indices the ops use), with a final ``measure`` of qubit
    ``measured[i]`` (default i) into c[i]."""
    regs = regs or [("q", n)]
    lines = [HEADER.rstrip("\n")] + [f"qreg {r}[{s}];" for r, s in regs]
    if measure:
        lines.append(f"creg c[{n}];")
    where = []
    for r, s in regs:
        where += [(r, i) for i in range(s)]
    for name, params, qubits in ops:
        args = f"({','.join(fmt(p) for p in params)})" if params else ""
        lines.append(f"{name}{args} {','.join(f'{where[q][0]}[{where[q][1]}]' for q in qubits)};")
    if measure:
        targets = measured or list(range(n))
        lines += [f"measure {where[q][0]}[{where[q][1]}] -> c[{i}];" for i, q in enumerate(targets)]
    return "\n".join(lines) + "\n"


def _angle(rng) -> float:
    return rng.uniform(-math.pi, math.pi)


def _product_state(rng, n) -> list:
    ops = []
    for q in range(n):
        ops += [("ry", (_angle(rng),), (q,)), ("rz", (_angle(rng),), (q,))]
    return ops


def _orders(rng, k, n, count) -> list:
    """``count`` operand tuples of ``k`` distinct qubits out of ``n``; for k = 2 the first two
    are one pair in both orientations."""
    out = []
    if k == 2:
        a, b = rng.sample(range(n), 2)
        out += [(a, b), (b, a)]
    while len(out) < count:
        out.append(tuple(rng.sample(range(n), k)))
    return out


def gate_cases(library, rng) -> list:
    cases = []
    for name in library.names():
        k, m = library.arity(name), library.parameter_count(name)
        count = 3 if k == 1 else 4
        n = k + 1 if k >= 4 else max(k, rng.randint(2, 4))
        for i, operands in enumerate(_orders(rng, k, n, count)):
            params = tuple(_angle(rng) for _ in range(m))
            ops = _product_state(rng, n) + [(name, params, operands)]
            cases.append({"name": f"gate-{name}-{i}", "family": "gate", "gate": name, "n_qubits": n,
                          "ops": ops})
    return cases


def random_ops(library, rng, n, length, names=None) -> list:
    names = [g for g in (names or library.names()) if library.arity(g) <= n]
    ops = []
    for _ in range(length):
        g = rng.choice(names)
        ops.append((g, tuple(_angle(rng) for _ in range(library.parameter_count(g))),
                    tuple(rng.sample(range(n), library.arity(g)))))
    return ops


def relabel_cases(library, rng, pairs=15) -> list:
    cases = []
    for i in range(pairs):
        n = rng.randint(3, 5)
        ops = _product_state(rng, n) + random_ops(library, rng, n, rng.randint(12, 20))
        perm = list(range(n))
        while perm == list(range(n)):
            rng.shuffle(perm)
        moved = [(g, p, tuple(perm[q] for q in qs)) for g, p, qs in ops]
        cases.append({"name": f"relabel-{i}-a", "family": "relabel", "n_qubits": n, "ops": ops})
        cases.append({"name": f"relabel-{i}-b", "family": "relabel", "n_qubits": n, "ops": moved,
                      "pair": f"relabel-{i}-a", "perm": perm})
    return cases


def inverse_cases(library, rng, count=10) -> list:
    cases = []
    for i in range(count):
        n = rng.randint(2, 5)
        ops = random_ops(library, rng, n, rng.randint(10, 20), names=sorted(INVERSES))
        undo = [(*INVERSES[g](p), qs) for g, p, qs in reversed(ops)]
        cases.append({"name": f"inverse-{i}", "family": "inverse", "n_qubits": n, "ops": ops + undo})
    return cases


def split_cases(library, rng, count=6) -> list:
    cases = []
    for i in range(count):
        ops = _product_state(rng, 4) + random_ops(library, rng, 4, rng.randint(10, 16))
        cases.append({"name": f"split-{i}-a", "family": "split", "n_qubits": 4, "ops": ops})
        cases.append({"name": f"split-{i}-b", "family": "split", "n_qubits": 4, "ops": ops,
                      "regs": [("a", 2), ("b", 2)], "pair": f"split-{i}-a", "perm": [0, 1, 2, 3]})
    return cases


def build(measure: bool = False, seed: int = SEED) -> list:
    """Every case with its QASM text and lsb reference statevector (and, measured, the
    reference distribution of its classical bits)."""
    library = ref.GateLibrary()
    rng = random.Random(seed)  # noqa: S311 (a fixed seed makes the cases reproducible)
    cases = (gate_cases(library, rng) + relabel_cases(library, rng) + inverse_cases(library, rng)
             + split_cases(library, rng))
    for case in cases:
        case["qasm"] = circuit(case["n_qubits"], case["ops"], measure, case.get("regs"), case.get("perm"))
        case["expected"] = ref.statevector(case["qasm"], library)
        if measure:
            case["distribution"] = ref.clbit_distribution(case["qasm"], library)
        del case["ops"]
    return cases
