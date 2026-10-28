"""Hypothesis strategy for OpenQASM 2.0 programs: several registers, nested gate definitions
with parameters, parameter expressions (+ - * / ^, unary minus, functions, pi), indexed and
whole-register (broadcast) operands, barriers, measurements, reset and if.

``programs()`` draws a ``Program``; ``Program.text(barriers=...)`` writes it.
"""

from dataclasses import dataclass, field

from hypothesis import strategies as st

QELIB1 = {
    "x": (0, 1), "y": (0, 1), "z": (0, 1), "h": (0, 1), "s": (0, 1), "sdg": (0, 1),
    "t": (0, 1), "tdg": (0, 1), "sx": (0, 1), "id": (0, 1), "rx": (1, 1), "ry": (1, 1),
    "rz": (1, 1), "p": (1, 1), "u1": (1, 1), "u2": (2, 1), "u3": (3, 1), "u": (3, 1),
    "U": (3, 1), "cx": (0, 2), "CX": (0, 2), "cy": (0, 2), "cz": (0, 2), "ch": (0, 2),
    "swap": (0, 2), "crx": (1, 2), "cry": (1, 2), "crz": (1, 2), "cp": (1, 2), "cu1": (1, 2),
    "cu3": (3, 2), "rxx": (1, 2), "rzz": (1, 2), "ccx": (0, 3), "cswap": (0, 3),
}
FUNCTIONS = ["sin", "cos", "tan", "exp", "ln", "sqrt"]


@dataclass
class Program:
    qregs: list
    cregs: list
    gates: list = field(default_factory=list)
    body: list = field(default_factory=list)

    def text(self, barriers: bool = True) -> str:
        lines = ["OPENQASM 2.0;", 'include "qelib1.inc";']
        lines += [f"qreg {name}[{size}];" for name, size in self.qregs]
        lines += [f"creg {name}[{size}];" for name, size in self.cregs]
        for name, params, args, inner in self.gates:
            head = f"gate {name}" + (f"({', '.join(params)})" if params else "")
            stmts = " ".join(s for s in inner if barriers or not s.startswith("barrier"))
            lines.append(f"{head} {', '.join(args)} {{ {stmts} }}")
        lines += [s for s in self.body if barriers or not s.startswith("barrier")]
        return "\n".join(lines) + "\n"


def expressions(names, depth=3):
    """Constant or parameter expressions over ``names``, small enough to stay finite."""
    leaves = [st.sampled_from(["pi", "0", "1", "2", "0.5", "1e-3", "3.25e1", ".75", "1."])]
    leaves.append(st.floats(-10, 10, allow_nan=False).map(lambda x: repr(round(x, 6))))
    if names:
        leaves.append(st.sampled_from(sorted(names)))
    leaf = st.one_of(*leaves)
    if depth == 0:
        return leaf
    inner = expressions(names, depth - 1)
    return st.one_of(
        leaf,
        st.tuples(inner, st.sampled_from(["+", "-", "*", "/"]), inner).map(
            lambda t: f"{t[0]} {t[1]} {t[2]}" if t[1] != "/" else f"{t[0]} / ({t[2]} + 7)"),
        inner.map(lambda e: f"-({e})"),
        inner.map(lambda e: f"({e})"),
        st.tuples(st.sampled_from(["sin", "cos"]), inner).map(lambda t: f"{t[0]}({t[1]})"),
        st.tuples(st.sampled_from(["exp", "sqrt", "ln"]), inner).map(
            lambda t: f"{t[0]}(cos({t[1]}) + 2)"),
        st.tuples(inner, st.sampled_from(["2", "0.5", "3"])).map(lambda t: f"(cos({t[0]}) + 2)^{t[1]}"),
    )


@st.composite
def gate_calls(draw, signatures, operands_for, names, allow_user=True):
    choices = sorted(n for n in signatures if allow_user or n in QELIB1)
    op = draw(st.sampled_from(choices))
    n_params, n_qubits = signatures[op]
    params = [draw(expressions(names, 2)) for _ in range(n_params)]
    operands = draw(operands_for(n_qubits))
    if operands is None:
        return None
    head = op + (f"({', '.join(params)})" if n_params else "")
    return f"{head} {', '.join(operands)};"


@st.composite
def programs(draw, max_qregs=3, max_size=3, max_gates=4, max_statements=12, measured=True):
    n_qregs = draw(st.integers(1, max_qregs))
    qregs = [(f"q{i}" if i else "q", draw(st.integers(1, max_size))) for i in range(n_qregs)]
    cregs = []
    if measured:
        cregs = [(f"c{i}" if i else "c", draw(st.integers(1, max_size)))
                 for i in range(draw(st.integers(0, 2)))]
    signatures = dict(QELIB1)
    program = Program(qregs, cregs)
    for g in range(draw(st.integers(0, max_gates))):
        name = f"g{g}"
        params = [f"t{k}" for k in range(draw(st.integers(0, 3)))]
        args = [f"a{k}" for k in range(draw(st.integers(1, 3)))]

        def body_operands(n, args=args):
            if n > len(args):
                return st.none()
            return st.permutations(args).map(lambda p, n=n: list(p[:n]))
        inner = []
        for _ in range(draw(st.integers(0, 4))):
            if draw(st.integers(0, 9)) == 0:
                inner.append(f"barrier {', '.join(args)};")
                continue
            call = draw(gate_calls(signatures, body_operands, set(params)))
            if call:
                inner.append(call)
        program.gates.append((name, params, args, inner))
        signatures[name] = (len(params), len(args))

    def top_operands(n):
        sizes = {}
        for name, size in qregs:
            sizes.setdefault(size, []).append(name)

        @st.composite
        def pick(draw):
            if draw(st.booleans()):
                size = draw(st.sampled_from(sorted(sizes)))
                regs = sizes[size]
                if len(regs) >= n:
                    return list(draw(st.permutations(regs)))[:n]
            qubits = [(name, i) for name, size in qregs for i in range(size)]
            if len(qubits) < n:
                return None
            chosen = draw(st.permutations(qubits))[:n]
            return [f"{name}[{i}]" for name, i in chosen]
        return pick()
    for _ in range(draw(st.integers(0, max_statements))):
        kind = draw(st.integers(0, 19))
        if kind == 0:
            reg = draw(st.sampled_from(qregs))
            program.body.append(f"barrier {reg[0]};")
        elif kind == 1 and measured:
            reg = draw(st.sampled_from(qregs))
            program.body.append(f"reset {reg[0]}[{draw(st.integers(0, reg[1] - 1))}];")
        elif kind == 2 and measured and cregs:
            creg = draw(st.sampled_from(cregs))
            call = draw(gate_calls(signatures, top_operands, set()))
            if call:
                program.body.append(f"if({creg[0]}=={draw(st.integers(0, 2 ** creg[1] - 1))}) {call}")
        else:
            call = draw(gate_calls(signatures, top_operands, set()))
            if call:
                program.body.append(call)
    if measured and cregs:
        for name, size in qregs:
            same = [c for c, s in cregs if s == size]
            if same and draw(st.booleans()):
                program.body.append(f"measure {name} -> {draw(st.sampled_from(same))};")
            else:
                creg, csize = draw(st.sampled_from(cregs))
                program.body.append(
                    f"measure {name}[{draw(st.integers(0, size - 1))}] -> "
                    f"{creg}[{draw(st.integers(0, csize - 1))}];")
    return program
