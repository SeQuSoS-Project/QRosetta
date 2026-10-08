"""OpenQASM 2.0 constant parameter expressions, and the gate parameters tket moves when it
builds a circuit (a parameter within TKET_PARAMETER_EPS half-turns of a multiple of 1/4
half-turn, i.e. of pi/4, is set to that multiple; pytket 1.33)."""

import math
import re

from qrosetta_commons.helpers import strip_qasm_comments

TKET_PARAMETER_EPS = 1e-11


class ParameterExpressionError(ValueError):
    """A gate parameter expression that is not a finite OpenQASM 2.0 constant expression."""


_QASM_FUNCTIONS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
                   "ln": math.log, "sqrt": math.sqrt}
_ALLOWED = ("only numbers, pi, + - * / ^, unary minus and sin/cos/tan/exp/ln/sqrt are allowed")
_NUMBERS_ONLY = ("only OpenQASM 2.0 numbers (decimal, optional exponent) and '^' for powers "
                 "are allowed")
_TOKEN_RE = re.compile(r"\s*(?:(?P<number>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)"
                       r"|(?P<name>[A-Za-z_]\w*)|(?P<op>[-+*/^()]))")
_MAX_DEPTH = 200


def _tokens(text: str) -> list:
    """[(kind, text)] of ``text``; raises ParameterExpressionError for any other character,
    a number run into a letter or digit (``0x1``, ``1j``, ``1_0``) or ``**``."""
    tokens, pos, end = [], 0, len(text.rstrip())
    while pos < end:
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ParameterExpressionError(_ALLOWED)
        pos = m.end()
        kind = m.lastgroup
        value = m.group(kind)
        if kind == "number":
            if pos < len(text) and (text[pos].isalnum() or text[pos] == "_"):
                raise ParameterExpressionError(_NUMBERS_ONLY)
            if re.fullmatch(r"0+[1-9]\d*", value):
                raise ParameterExpressionError(_NUMBERS_ONLY)
        if kind == "op" and value == "*" and tokens and tokens[-1] == ("op", "*"):
            raise ParameterExpressionError(_NUMBERS_ONLY)
        tokens.append((kind, value))
    return tokens


class _Parser:
    """Recursive descent over the OpenQASM 2.0 expression grammar: + - lowest, then * /,
    then unary minus, then right-associative ^ (so -2^2 = -4 and 2^-1 = 0.5)."""

    def __init__(self, tokens, env):
        self.tokens, self.pos, self.env, self.depth = tokens, 0, env or {}, 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self, value=None):
        token = self.peek()
        if token[0] is None or (value is not None and token[1] != value):
            raise ParameterExpressionError(_ALLOWED)
        self.pos += 1
        return token

    def expression(self):
        self.depth += 1
        if self.depth > _MAX_DEPTH:
            raise ParameterExpressionError("the expression is nested too deeply")
        value = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            right = self.term()
            value = value + right if op == "+" else value - right
        self.depth -= 1
        return value

    def term(self):
        value = self.unary()
        while self.peek() in (("op", "*"), ("op", "/")):
            op = self.take()[1]
            right = self.unary()
            if op == "*":
                value = value * right
            elif right == 0:
                raise ParameterExpressionError("division by zero")
            else:
                value = value / right
        return value

    def unary(self):
        if self.peek() in (("op", "-"), ("op", "+")):
            op = self.take()[1]
            self.depth += 1
            if self.depth > _MAX_DEPTH:
                raise ParameterExpressionError("the expression is nested too deeply")
            value = self.unary()
            self.depth -= 1
            return -value if op == "-" else value
        return self.power()

    def power(self):
        base = self.atom()
        if self.peek() != ("op", "^"):
            return base
        self.take()
        self.depth += 1
        if self.depth > _MAX_DEPTH:
            raise ParameterExpressionError("the expression is nested too deeply")
        exponent = self.unary()
        self.depth -= 1
        value = base ** exponent
        if isinstance(value, complex):
            raise ParameterExpressionError("the value is not a real number")
        return value

    def atom(self):
        kind, text = self.take()
        if kind == "number":
            return float(text)
        if kind == "op" and text == "(":
            value = self.expression()
            self.take(")")
            return value
        if kind == "name":
            if text in _QASM_FUNCTIONS and self.peek() == ("op", "("):
                self.take("(")
                argument = self.expression()
                self.take(")")
                return _QASM_FUNCTIONS[text](argument)
            if text in self.env:
                return float(self.env[text])
            if text == "pi":
                return math.pi
        raise ParameterExpressionError(_ALLOWED)


def evaluate_constant_expression(text: str, env: dict = None) -> float:
    """Value of an OpenQASM 2.0 constant expression (numbers, pi, + - * / ^, unary minus,
    sin cos tan exp ln sqrt), computed in floating point; names in ``env`` (gate parameters,
    any identifier, ``lambda`` included) take their values from it. Raises
    ParameterExpressionError for anything else or a non-finite value."""
    if "**" in text:
        raise ParameterExpressionError(_NUMBERS_ONLY)
    try:
        parser = _Parser(_tokens(text), env)
        value = parser.expression()
        if parser.pos != len(parser.tokens):
            raise ParameterExpressionError(_ALLOWED)
    except ParameterExpressionError:
        raise
    except RecursionError:
        raise ParameterExpressionError("the expression is nested too deeply")
    except OverflowError:
        raise ParameterExpressionError("the value is too large")
    except ZeroDivisionError:
        raise ParameterExpressionError("division by zero")
    except (TypeError, ValueError) as exc:
        raise ParameterExpressionError(str(exc) or type(exc).__name__)
    if not math.isfinite(value):
        raise ParameterExpressionError("the value is not finite")
    return value




_SKIPPED = ("gate", "opaque", "qreg", "creg", "OPENQASM", "include", "measure", "barrier", "reset")
_CALL_RE = re.compile(r"^(?:if\s*\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(")


def gate_parameter_lists(qasm: str):
    """(gate name, [parameter text, ...]) for every gate call with a parameter list, at top
    level and inside gate bodies."""
    for fragment in re.split(r"[;{}]", strip_qasm_comments(qasm)):
        text = fragment.strip()
        if not text or text.startswith(_SKIPPED):
            continue
        m = _CALL_RE.match(text)
        if not m:
            continue
        depth, start, params = 0, m.end(), []
        for k in range(m.end() - 1, len(text)):
            depth += text[k] == "("
            depth -= text[k] == ")"
            if depth == 0:
                inner = text[start:k]
                break
        else:
            continue
        level, buf = 0, []
        for ch in inner:
            level += ch == "("
            level -= ch == ")"
            if ch == "," and level == 0:
                params.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        params.append("".join(buf))
        yield m.group(1), [p.strip() for p in params if p.strip()]


_GATE_DEF_RE = re.compile(r"gate\s+([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?[^{]*\{([^}]*)\}")


def _moved(name, text, value, out):
    half_turns = value / math.pi
    nearest = round(4 * half_turns) / 4
    if 0 < abs(half_turns - nearest) < TKET_PARAMETER_EPS:
        out.append((name, text, value, nearest * math.pi))


def tket_rounded_parameters(qasm: str) -> list:
    """[(gate, parameter text, value in rad, value tket stores in rad)] for every gate
    parameter tket moves when it builds the circuit: constant parameters at top level, and
    parameters inside user gate definitions with the values each call passes. Parameters
    tket derives itself while rebasing (such as the half-angles of cu1 or crz) are not
    predicted."""
    code = strip_qasm_comments(qasm)
    definitions = {}
    for m in _GATE_DEF_RE.finditer(code):
        names = [p.strip() for p in (m.group(2) or "").split(",") if p.strip()]
        definitions[m.group(1)] = (names, m.group(3))
    top_level = _GATE_DEF_RE.sub("", code)
    moved, seen = [], set()

    def visit(name, values, depth):
        key = (name, tuple(values))
        if name not in definitions or key in seen or depth > 64 or len(seen) > 10000:
            return
        seen.add(key)
        names, body = definitions[name]
        env = dict(zip(names, values))
        for inner, params in gate_parameter_lists(body):
            inner_values = []
            for text in params:
                try:
                    value = evaluate_constant_expression(text, env)
                except ParameterExpressionError:
                    inner_values = None
                    break
                _moved(inner, text, value, moved)
                inner_values.append(value)
            if inner_values is not None:
                visit(inner, inner_values, depth + 1)
        for call in re.findall(r"(?:^|;)\s*([A-Za-z_]\w*)\s+[A-Za-z_]", body):
            visit(call, [], depth + 1)

    for name, params in gate_parameter_lists(top_level):
        values = []
        for text in params:
            try:
                value = evaluate_constant_expression(text)
            except ParameterExpressionError:
                values = None
                break
            _moved(name, text, value, moved)
            values.append(value)
        if values is not None:
            visit(name, values, 0)
    for call in re.findall(r"(?:^|;)\s*([A-Za-z_]\w*)\s+[A-Za-z_]", top_level):
        visit(call, [], 0)
    return moved


def tket_parameter_note(qasm: str, who: str, limit: int = 5):
    """A preprocessing note naming the parameters tket moves in ``qasm`` (``who`` says where
    tket builds the circuit), or None when it moves none."""
    moved = tket_rounded_parameters(qasm)
    if not moved:
        return None
    shown = ", ".join(f"{name}({text}) -> {stored:.17g} (moved {stored - value:.3g} rad)"
                      for name, text, value, stored in moved[:limit])
    more = f", and {len(moved) - limit} more" if len(moved) > limit else ""
    return (f"{who} sets a gate parameter within {TKET_PARAMETER_EPS:g} half-turns "
            f"(about {TKET_PARAMETER_EPS * math.pi:.2g} rad) of a multiple of pi/4 to that "
            f"multiple when it builds the circuit: {shown}{more}. Parameters tket derives while "
            f"rebasing (such as the half-angles of cu1 or crz) are rounded the same way and are "
            f"not listed.")
