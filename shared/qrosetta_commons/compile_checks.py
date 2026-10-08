"""Run-time checks of a compile-only service's output: the process infidelity of output and
input read by Qiskit (up to CHECKED_UP_TO_QUBITS), the largest change single-precision
reading makes to a constant angle, and the qubit-count limits of pipelines that do not
finish at larger widths."""

import re

from qrosetta_commons.compile_errors import CompileRefused, OutputRejected
from qrosetta_commons.helpers import strip_qasm_comments
from qrosetta_commons.qasm_expressions import (
    ParameterExpressionError, evaluate_constant_expression, gate_parameter_lists,
)

CHECKED_UP_TO_QUBITS = 10
_NUMBER = re.compile(r"(?<![\w.])(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def process_infidelity(input_qasm: str, output_qasm: str) -> float:
    """1 - |Tr(U_in^dagger U_out)| / 2^n, both unitaries read by Qiskit after final
    measurements are removed; 0 means equal up to global phase."""
    import numpy as np
    from qiskit import QuantumCircuit
    from qrosetta_commons.qiskit_circuits import unitary_of

    source = unitary_of(QuantumCircuit.from_qasm_str(input_qasm).remove_final_measurements(inplace=False))
    output = unitary_of(QuantumCircuit.from_qasm_str(output_qasm).remove_final_measurements(inplace=False))
    if source.dim != output.dim:
        return 1.0
    return max(0.0, 1.0 - abs(np.trace(source.data.conj().T @ output.data)) / source.dim[0])


def unitary_check_note(compiler: str, input_qasm: str, output_qasm: str, n_qubits: int,
                       max_infidelity: float, tolerance_reason: str) -> str:
    """The pass line recording the output check: process infidelity to the input up to
    CHECKED_UP_TO_QUBITS, else that the unitary is not checked. OutputRejected when the
    infidelity exceeds ``max_infidelity``."""
    if n_qubits > CHECKED_UP_TO_QUBITS:
        return f"The output's unitary is not checked above {CHECKED_UP_TO_QUBITS} qubits."
    infidelity = process_infidelity(input_qasm, output_qasm)
    if infidelity > max_infidelity:
        raise OutputRejected(f"{compiler}'s output has process infidelity {infidelity:.2g} to the "
                             f"input (more than {max_infidelity:g}), so it is not reported")
    return (f"Checked with Qiskit: process infidelity to the input {infidelity:.2g} (at most "
            f"{max_infidelity:g} accepted, {tolerance_reason}).")


def single_precision_angle_change(qasm: str) -> float:
    """Largest change, in rad, to a constant gate parameter (top level or inside a gate
    definition) when each numeric literal is read in single precision and the expression is
    then evaluated in double precision, as staq 3.5 reads it."""
    import numpy as np

    def single(match):
        return repr(float(np.float32(float(match.group(0)))))

    worst = 0.0
    for _name, params in gate_parameter_lists(strip_qasm_comments(qasm)):
        for text in params:
            try:
                exact = evaluate_constant_expression(text)
                read = evaluate_constant_expression(_NUMBER.sub(single, text))
            except ParameterExpressionError:
                continue
            worst = max(worst, abs(read - exact))
    return worst


def refuse_above_qubits(n_qubits: int, limit: int, compiler: str, what: str, evidence: str) -> None:
    """CompileRefused for a circuit wider than ``limit`` qubits at a pipeline that does not
    finish at larger widths (``what`` names the pipeline, ``evidence`` says what happens)."""
    if n_qubits > limit:
        raise CompileRefused(f"{compiler} {what} is offered up to {limit} qubits and this circuit "
                             f"has {n_qubits}: {evidence}")
