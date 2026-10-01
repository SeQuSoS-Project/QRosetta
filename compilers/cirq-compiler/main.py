"""Cirq compiler: imports the circuit with Cirq's own OpenQASM 2.0 parser and compiles it to
Cirq's CZ target gate set with optimize_for_target_gateset, optionally followed by Cirq's
eject and cleanup transformers."""

import ast
import math
import re

import cirq
from cirq.contrib.qasm_import import circuit_from_qasm
from fastapi import FastAPI
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, strip_qasm_comments, with_sdk_versions

declare_sdk_packages("cirq-core", "qiskit")

app = FastAPI(title="Cirq Compiler")

QASM_PRECISION = 16
CHECKED_UP_TO_QUBITS = 10

_PARSE_NOTE = "cirq.contrib.qasm_import.circuit_from_qasm(): Cirq's OpenQASM 2.0 parser."
_LEVEL0_NOTE = ("cirq.optimize_for_target_gateset(circuit, gateset=cirq.CZTargetGateset()): "
                "decomposes to CZ and single-qubit PhasedXZ gates and merges neighbouring "
                "single- and two-qubit operations.")
_LEVEL1_NOTE = ("then cirq.eject_phased_paulis, cirq.eject_z, cirq.drop_negligible_operations and "
                "cirq.drop_empty_moments.")
_ENCODE_NOTE = (f"Circuit.to_qasm(qubit_order=<declared qubits in register order>, precision="
                f"{QASM_PRECISION}): the output as OpenQASM 2.0, one register q in declaration "
                f"order; gates Cirq has no qelib1 name for are written as their u3/cx form.")

_QREG = re.compile(r"\bqreg\s+(\w+)\s*\[\s*(\d+)\s*\]\s*;")
_FUNCTIONS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp,
              "ln": math.log, "sqrt": math.sqrt}


def _value(expression: str):
    """The value of an OpenQASM 2.0 parameter expression without variables, else None."""
    try:
        tree = ast.parse(expression.replace("^", "**").strip(), mode="eval")
    except SyntaxError:
        return None

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id == "pi":
            return math.pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = walk(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            left, right = walk(node.left), walk(node.right)
            return {ast.Add: left + right, ast.Sub: left - right, ast.Mult: left * right,
                    ast.Div: left / right if right else math.nan, ast.Pow: left ** right}[type(node.op)]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS
                and len(node.args) == 1 and not node.keywords):
            return _FUNCTIONS[node.func.id](walk(node.args[0]))
        raise ValueError("not a constant expression")

    try:
        result = walk(tree)
    except (ValueError, OverflowError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) else None


def _first_argument(statement: str) -> str:
    depth, start = 0, statement.index("(") + 1
    for i in range(start, len(statement)):
        ch = statement[i]
        if ch == "(":
            depth += 1
        elif ch == ")" and depth == 0 or ch == "," and depth == 0:
            return statement[start:i]
        elif ch == ")":
            depth -= 1
    return statement[start:]


def _refuse_misimported_cu3(qasm: str) -> None:
    """ValueError for a cu3 that cirq-core 1.7.0 imports with the wrong unitary: theta with
    floor(theta / 2 pi) odd (for example any small negative theta), or a theta that cannot be
    evaluated (a gate-body parameter) when the output cannot be checked."""
    for statement in strip_qasm_comments(qasm).split(";"):
        text = statement.strip()
        if not re.match(r"cu3\s*\(", text):
            continue
        theta = _value(_first_argument(text))
        if theta is not None and math.floor(theta / (2 * math.pi)) % 2 == 1:
            raise ValueError(
                f"'{text};' has theta = {theta:g}; cirq-core 1.7.0 imports cu3 with theta mod 4 pi "
                f"in [2 pi, 4 pi) as a different unitary (a phase of -1 on the control's |1> "
                f"branch), so the circuit is not compiled")


def _declared_qubits(qasm: str) -> list:
    return [cirq.NamedQubit(f"{name}_{i}") for name, size in _QREG.findall(strip_qasm_comments(qasm))
            for i in range(int(size))]


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output has the input's unitary up to global phase, both read by Qiskit."""
    source = QuantumCircuit.from_qasm_str(input_qasm).remove_final_measurements(inplace=False)
    output = QuantumCircuit.from_qasm_str(output_qasm).remove_final_measurements(inplace=False)
    return Operator(output).equiv(Operator(source), atol=1e-8)


def _check(qasm: str, output: str, n_qubits: int) -> str:
    if n_qubits > CHECKED_UP_TO_QUBITS:
        return f"The output's unitary is not checked above {CHECKED_UP_TO_QUBITS} qubits."
    if not equivalent(qasm, output):
        raise ValueError("Cirq's output does not have the input's unitary, so it is not reported")
    return ("Checked: the output has the input's unitary (Qiskit Operator equality up to "
            "global phase).")


def _pipeline(cleanup: bool):
    def run(qasm: str):
        _refuse_misimported_cu3(qasm)
        qubits = _declared_qubits(qasm)
        circuit = cirq.optimize_for_target_gateset(circuit_from_qasm(qasm), gateset=cirq.CZTargetGateset())
        notes = [_PARSE_NOTE, _LEVEL0_NOTE]
        if cleanup:
            for transformer in (cirq.eject_phased_paulis, cirq.eject_z, cirq.drop_negligible_operations,
                                cirq.drop_empty_moments):
                circuit = transformer(circuit)
            notes.append(_LEVEL1_NOTE)
        output = circuit.to_qasm(qubit_order=qubits, precision=QASM_PRECISION)
        return output, notes + [_ENCODE_NOTE, _check(qasm, output, len(qubits))]
    return run


PIPELINES = {0: _pipeline(False), 1: _pipeline(True)}


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="cirq-transformers", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "Cirq", levels=sorted(PIPELINES), equivalent=equivalent)
