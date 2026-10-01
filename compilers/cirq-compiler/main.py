"""Cirq compiler: imports the circuit with Cirq's own OpenQASM 2.0 parser and compiles it to
Cirq's CZ target gate set with optimize_for_target_gateset, optionally followed by Cirq's
eject and cleanup transformers."""

import math
import re

import cirq
from cirq.contrib.qasm_import import circuit_from_qasm
from fastapi import FastAPI
from qiskit import QuantumCircuit
from qiskit.circuit.library import get_standard_gate_name_mapping

from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, strip_qasm_comments, with_sdk_versions
from qrosetta_commons.qiskit_circuits import unitary_of

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

_STANDARD_GATES = set(get_standard_gate_name_mapping())
_QREG = re.compile(r"\bqreg\s+(\w+)\s*\[\s*(\d+)\s*\]\s*;")


def _cu3_thetas(circuit: QuantumCircuit):
    """theta of every cu3 call in the circuit, including those inside user gate definitions."""
    for inst in circuit.data:
        operation = inst.operation
        if operation.name == "cu3":
            yield float(operation.params[0])
        elif operation.name not in _STANDARD_GATES and getattr(operation, "definition", None) is not None:
            yield from _cu3_thetas(operation.definition)


def _refuse_misimported_cu3(qasm: str) -> None:
    """ValueError for a cu3, at top level or in a gate body, that cirq-core 1.7.0 imports with
    the wrong unitary: theta with floor(theta / 2 pi) odd, for example any small negative theta."""
    for theta in _cu3_thetas(QuantumCircuit.from_qasm_str(qasm)):
        if math.floor(theta / (2 * math.pi)) % 2 == 1:
            raise ValueError(
                f"the compile input has a cu3 with theta = {theta:g}; cirq-core 1.7.0 imports cu3 "
                f"with theta mod 4 pi in [2 pi, 4 pi) as a different unitary (a phase of -1 on the "
                f"control's |1> branch), so the circuit is not compiled")


def _declared_qubits(qasm: str) -> list:
    return [cirq.NamedQubit(f"{name}_{i}") for name, size in _QREG.findall(strip_qasm_comments(qasm))
            for i in range(int(size))]


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output has the input's unitary up to global phase, both read by Qiskit."""
    source = QuantumCircuit.from_qasm_str(input_qasm).remove_final_measurements(inplace=False)
    output = QuantumCircuit.from_qasm_str(output_qasm).remove_final_measurements(inplace=False)
    return unitary_of(output).equiv(unitary_of(source), atol=1e-8)


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
