"""PyZX compiler: converts the circuit to a ZX-diagram, simplifies it with full_reduce and
extracts a circuit, optionally followed by PyZX's gate-level basic_optimization."""

import math
import re
from decimal import Decimal

from fastapi import FastAPI
import pyzx as zx
from pyzx.circuit.qasmparser import QASMParser

from qrosetta_commons.compile_checks import process_infidelity, unitary_check_note
from qrosetta_commons.compile_errors import CompileRefused
from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import (
    declare_sdk_packages, get_num_qubits_from_qasm, strip_qasm_comments, with_sdk_versions,
)
from qrosetta_commons.qelib1 import add_qelib1_definitions
from qrosetta_commons.qasm_expressions import (
    ParameterExpressionError, evaluate_constant_expression, gate_parameter_lists,
)

declare_sdk_packages("pyzx", "qiskit")

app = FastAPI(title="PyZX Compiler")

PYZX_PARSER_LACKS = frozenset({"c3x", "c3sqrtx", "c4x", "rccx", "rc3x", "u0"})
MAX_PROCESS_INFIDELITY = 1e-8

_PARSE_NOTE = "pyzx.Circuit.from_qasm(): PyZX's OpenQASM 2.0 parser."
_CREG_NOTE = ("creg declarations removed before parsing, required by the adapter: PyZX reads each "
              "classical bit as an extra qubit wire. The compile input has no measurement, reset "
              "or classical control, so no operation is dropped.")
_COMMENTS_NOTE = "Comments removed before parsing."
_CREG_RE = re.compile(r"\bcreg\s+\w+\s*\[\s*\d+\s*\]\s*;")
_CLASSICAL_RE = re.compile(r"\b(measure|reset)\b|\bif\s*\(")
_REDUCE_NOTE = ("circuit.to_graph(), pyzx.full_reduce(graph), pyzx.extract_circuit(graph): "
                "ZX-calculus simplification and circuit extraction.")
_BASIC_NOTE = ("pyzx.basic_optimization(extracted.to_basic_gates()): gate cancellation and "
               "commutation on the extracted circuit only. PyZX 0.10.6's basic_optimization "
               "changes the unitary of some input circuits (an X or S followed by an X or Y "
               "rotation), so it is never applied to the input directly.")
_ENCODE_NOTE = "Circuit.to_qasm(): the output circuit as OpenQASM 2.0, one register q."
_EXPONENT_RE = re.compile(r"(?<![\w.])(?:\d+\.?\d*|\.\d+)[eE][-+]?\d+")
_EXPONENT_NOTE = ("Numbers in scientific notation rewritten as plain decimals with the same value "
                  "({examples}), required by the adapter: PyZX 0.10.6's parser reads the e as a "
                  "variable and rejects the circuit.")


def _phase_note(qasm: str) -> str:
    """How far PyZX's rational phases move the circuit's constant angles, read through
    PyZX's own parameter parser."""
    parser = QASMParser()
    worst = 0.0
    for _name, params in gate_parameter_lists(qasm):
        for text in params:
            try:
                value = evaluate_constant_expression(text)
                stored = float(parser.parse_phase_arg(text)) * math.pi
            except (ParameterExpressionError, TypeError):
                continue
            worst = max(worst, abs(stored - value))
    return (f"PyZX stores each phase as a fraction of pi with denominator at most "
            f"{zx.settings.float_to_fraction_max_denominator} "
            f"(pyzx.settings.float_to_fraction_max_denominator); the largest change to a constant "
            f"angle of this circuit is {worst:.3g} rad.")


def _plain_decimals(qasm: str):
    """``(qasm, examples)`` with every number in scientific notation written as a plain decimal."""
    examples = []

    def plain(match):
        text = format(Decimal(match.group(0)), "f")
        if len(examples) < 3:
            examples.append(f"{match.group(0)} -> {text}")
        return text

    return _EXPONENT_RE.sub(plain, qasm), examples


def _quantum_only(qasm: str):
    """``(qasm without creg declarations, notes)``, with qelib1.inc definitions of the gates
    PyZX's parser lacks; CompileRefused for a circuit with classical operations, which PyZX
    cannot represent."""
    code = strip_qasm_comments(qasm)
    if _CLASSICAL_RE.search(code):
        raise CompileRefused("PyZX compiles unitary circuits only; this circuit has measure, reset or if")
    stripped = _CREG_RE.sub("", code)
    notes = [_COMMENTS_NOTE] if code != qasm else []
    notes += [_CREG_NOTE] if stripped != code else []
    stripped, examples = _plain_decimals(stripped)
    if examples:
        notes.append(_EXPONENT_NOTE.format(examples=", ".join(examples)))
    stripped, added = add_qelib1_definitions(stripped, PYZX_PARSER_LACKS)
    if added:
        notes.append(f"PyZX 0.10.6's parser lacks {', '.join(added)}; their definitions from "
                     f"Qiskit's qelib1.inc were added to the circuit given to PyZX.")
    return stripped, notes


def _parse(qasm: str):
    """PyZX's reading of the circuit; CompileRefused for a statement its parser rejects."""
    try:
        return zx.Circuit.from_qasm(qasm)
    except TypeError as exc:
        raise CompileRefused(f"PyZX 0.10.6's OpenQASM 2.0 parser does not read this circuit ({exc})")


def _check(qasm: str, output: str) -> str:
    return unitary_check_note("PyZX", qasm, output, get_num_qubits_from_qasm(qasm),
                              MAX_PROCESS_INFIDELITY, "for PyZX's rational phases")


def _extract(qasm: str):
    graph = _parse(qasm).to_graph()
    zx.full_reduce(graph)
    return zx.extract_circuit(graph.copy())


def _full_reduce(qasm: str):
    unitary, notes = _quantum_only(qasm)
    output = _extract(unitary).to_qasm()
    return output, notes + [_PARSE_NOTE, _phase_note(unitary), _REDUCE_NOTE, _ENCODE_NOTE, _check(qasm, output)]


def _full_reduce_then_basic(qasm: str):
    unitary, notes = _quantum_only(qasm)
    output = zx.basic_optimization(_extract(unitary).to_basic_gates()).to_qasm()
    return output, notes + [_PARSE_NOTE, _phase_note(unitary), _REDUCE_NOTE, _BASIC_NOTE, _ENCODE_NOTE,
                            _check(qasm, output)]


PIPELINES = {1: _full_reduce, 2: _full_reduce_then_basic}


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output's process infidelity to the input, both read by Qiskit, is at most
    MAX_PROCESS_INFIDELITY."""
    return process_infidelity(input_qasm, output_qasm) <= MAX_PROCESS_INFIDELITY


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="pyzx", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "PyZX", levels=sorted(PIPELINES), equivalent=equivalent)
