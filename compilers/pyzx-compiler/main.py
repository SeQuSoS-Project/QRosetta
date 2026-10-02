"""PyZX compiler: converts the circuit to a ZX-diagram, simplifies it with full_reduce and
extracts a circuit, optionally followed by PyZX's gate-level basic_optimization."""

import math
import re
from decimal import Decimal

from fastapi import FastAPI
import pyzx as zx
from pyzx.circuit.qasmparser import QASMParser

from qrosetta_commons.compile_errors import CompileRefused
from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, strip_qasm_comments, with_sdk_versions
from qrosetta_commons.qasm_expressions import (
    ParameterExpressionError, evaluate_constant_expression, gate_parameter_lists,
)

declare_sdk_packages("pyzx")

app = FastAPI(title="PyZX Compiler")

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
    """``(qasm without creg declarations, notes)``; ValueError for a circuit with classical
    operations, which PyZX cannot represent."""
    code = strip_qasm_comments(qasm)
    if _CLASSICAL_RE.search(code):
        raise CompileRefused("PyZX compiles unitary circuits only; this circuit has measure, reset or if")
    stripped = _CREG_RE.sub("", code)
    notes = [_COMMENTS_NOTE] if code != qasm else []
    notes += [_CREG_NOTE] if stripped != code else []
    stripped, examples = _plain_decimals(stripped)
    if examples:
        notes.append(_EXPONENT_NOTE.format(examples=", ".join(examples)))
    return stripped, notes


def _extract(qasm: str):
    graph = zx.Circuit.from_qasm(qasm).to_graph()
    zx.full_reduce(graph)
    return zx.extract_circuit(graph.copy())


def _full_reduce(qasm: str):
    unitary, notes = _quantum_only(qasm)
    return _extract(unitary).to_qasm(), notes + [_PARSE_NOTE, _phase_note(unitary), _REDUCE_NOTE, _ENCODE_NOTE]


def _full_reduce_then_basic(qasm: str):
    unitary, notes = _quantum_only(qasm)
    circuit = zx.basic_optimization(_extract(unitary).to_basic_gates())
    return circuit.to_qasm(), notes + [_PARSE_NOTE, _phase_note(unitary), _REDUCE_NOTE, _BASIC_NOTE, _ENCODE_NOTE]


PIPELINES = {1: _full_reduce, 2: _full_reduce_then_basic}


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """PyZX's tensor comparison of the two circuits, up to a global scalar."""
    return zx.compare_tensors(zx.Circuit.from_qasm(_quantum_only(input_qasm)[0]),
                              zx.Circuit.from_qasm(output_qasm), preserve_scalar=False)


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="pyzx", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "PyZX", levels=sorted(PIPELINES), equivalent=equivalent)
