"""OpenQASM 2.0 constant parameter expressions, and the gate parameters tket moves when it
builds a circuit (a parameter within TKET_PARAMETER_EPS half-turns of a multiple of 1/4
half-turn, i.e. of pi/4, is set to that multiple; pytket 1.33)."""

import ast
import math
import re

from qrosetta_commons.helpers import strip_qasm_comments

TKET_PARAMETER_EPS = 1e-11


class ParameterExpressionError(ValueError):
    """A gate parameter expression that is not a finite OpenQASM 2.0 constant expression."""


_QASM_FUNCTIONS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
                   "ln": math.log, "sqrt": math.sqrt}
_BINARY_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
               ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
               ast.Pow: lambda a, b: a ** b}
_NON_QASM_NUMBER_RE = re.compile(r"\b0[xXoObB]|\d_|_\d|\d[jJ]\b")


def _eval_node(node, env=None):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Name) and env and node.id in env:
        return env[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id == "pi":
        return math.pi
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval_node(node.operand, env)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        return _BINARY_OPS[type(node.op)](_eval_node(node.left, env), _eval_node(node.right, env))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _QASM_FUNCTIONS and len(node.args) == 1 and not node.keywords):
        return _QASM_FUNCTIONS[node.func.id](_eval_node(node.args[0], env))
    raise ParameterExpressionError("only numbers, pi, + - * / ^, unary minus and "
                                   "sin/cos/tan/exp/ln/sqrt are allowed")


def evaluate_constant_expression(text: str, env: dict = None) -> float:
    """Value of an OpenQASM 2.0 constant expression (numbers, pi, + - * / ^, unary minus,
    sin cos tan exp ln sqrt), computed in floating point. Raises
    ParameterExpressionError for anything else or a non-finite value."""
    if "**" in text or _NON_QASM_NUMBER_RE.search(text):
        raise ParameterExpressionError(
            "only OpenQASM 2.0 numbers (decimal, optional exponent) and '^' for powers are allowed")
    try:
        tree = ast.parse(text.replace("^", "**").strip(), mode="eval")
        value = _eval_node(tree, env)
    except ParameterExpressionError:
        raise
    except RecursionError:
        raise ParameterExpressionError("the expression is nested too deeply")
    except OverflowError:
        raise ParameterExpressionError("the value is too large")
    except ZeroDivisionError:
        raise ParameterExpressionError("division by zero")
    except (SyntaxError, ValueError) as exc:
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


def tket_rounded_parameters(qasm: str) -> list:
    """[(gate, parameter text, value in rad, value tket stores in rad)] for every constant
    gate parameter tket moves when it builds the circuit. Parameters written in terms of a
    gate definition's arguments are not evaluated."""
    moved = []
    for name, params in gate_parameter_lists(qasm):
        for text in params:
            try:
                value = evaluate_constant_expression(text)
            except ParameterExpressionError:
                continue
            half_turns = value / math.pi
            nearest = round(4 * half_turns) / 4
            if 0 < abs(half_turns - nearest) < TKET_PARAMETER_EPS:
                moved.append((name, text, value, nearest * math.pi))
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
            f"multiple when it builds the circuit: {shown}{more}.")
