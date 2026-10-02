"""Quartz compiler: Qiskit decomposes the circuit to h, x, rz and cx (Nam's gate set), then
Quartz rewrites it greedily with an ECC set of verified equivalent subcircuits generated when
the image is built, applying cost-reducing rewrites until none applies."""

import ctypes
import math
import os
import re
import signal
import subprocess
from fractions import Fraction

from fastapi import FastAPI
from qiskit import QuantumCircuit

from qrosetta_commons.compile_errors import CompileRefused, OutputRejected
from qrosetta_commons.compile_service import (
    TRANSLATION_PROBES, declare_native_component, register_compiler_endpoint, run_compile_job,
    run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, with_sdk_versions
from qrosetta_commons.qiskit_circuits import (
    split_final_measurements, translate_to_basis, translation_note, unitary_of,
)

declare_sdk_packages("qiskit")

app = FastAPI(title="Quartz Compiler")

QUARTZ_BINARY = "/usr/local/bin/quartz-greedy"
QUARTZ_VERSION = os.getenv("QUARTZ_VERSION", "not recorded")
ECC_SET = os.getenv("QUARTZ_ECC_SET", "/usr/local/share/quartz/Nam_complete_ECC_set.json")
ECC_MAX_GATES = os.getenv("QUARTZ_ECC_MAX_GATES", "not recorded")
ECC_SHA256 = os.getenv("QUARTZ_ECC_SHA256", "not recorded")
declare_native_component(
    "quartz", QUARTZ_VERSION,
    source_url=f"https://github.com/quantum-compiler/quartz/archive/refs/tags/v{QUARTZ_VERSION}.tar.gz",
    source_sha256=os.getenv("QUARTZ_SHA256", "not recorded"),
    patches=["shift10-normalise.patch"],
    built_with=["gen_nam_ecc.cpp", "quartz_greedy.cpp"],
    ecc_set="Nam_complete_ECC_set.json", ecc_set_sha256=ECC_SHA256,
    ecc_set_max_gates=ECC_MAX_GATES)
DECOMPOSITION_BASIS = ("h", "x", "rz", "cx")
CHECKED_UP_TO_QUBITS = 10
_QUARTZ_GATE = re.compile(r"^(h|x|cx|rz\(pi\*-?\d+(?:/\d+)?\)|rz\(0\)) q\[(\d+)\](?:,q\[(\d+)\])?;$")

_BARRIER_NOTE = ("Barriers removed before Quartz, which reads them but rewrites across them; "
                 "the output has none.")
_ANGLE_NOTE = ("Each rz angle given to Quartz as an exact fraction times pi (the shortest decimal "
               "of angle/pi that reads back as the same double); Quartz computes with exact "
               "rationals and writes its angles the same way, so the output angles are exact.")
_ENCODE_NOTE = ("Output: Quartz's gate lines as Quartz wrote them, its qubits q[i] renamed to the "
                "input's registers in declaration order, with the input's qreg and creg "
                "declarations.")
_MEASURE_NOTE = ("Final measurements removed before Quartz, whose reader drops them, and written "
                 "back after its gate lines in their original order.")


def _build_note() -> str:
    return (f"Quartz {QUARTZ_VERSION} built from the release source with exact rational "
            f"parameters (upstream default) and one fix to its big-integer code "
            f"(shift10-normalise.patch: a zero remainder kept a leading zero limb, so gcd never "
            f"ended). ECC set: Nam gate set, 3 qubits, 2 symbolic parameters, circuits of up to "
            f"{ECC_MAX_GATES} gates, generated and verified at image build, sha256 {ECC_SHA256}.")


def _greedy_note() -> str:
    return ("quartz::Graph::greedy_optimize with the ECC set: every rewrite that lowers the gate "
            "count is applied until none applies; no search, so the output depends only on the "
            "input and the ECC set. Quartz's time-bounded search (Graph::optimize) is not offered.")


def _quartz_input(circuit: QuantumCircuit) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{circuit.num_qubits}];"]
    for inst in circuit.data:
        name = inst.operation.name
        if name == "barrier":
            continue
        if name not in DECOMPOSITION_BASIS:
            raise CompileRefused(f"decomposition left a gate Quartz cannot take: {name}")
        wires = ",".join(f"q[{circuit.find_bit(q).index}]" for q in inst.qubits)
        if name == "rz":
            turns = Fraction(repr(float(inst.operation.params[0]) / math.pi))
            lines.append(f"rz(pi*{turns.numerator}/{turns.denominator}) {wires};")
        else:
            lines.append(f"{name} {wires};")
    return "\n".join(lines) + "\n"


def _die_with_parent() -> None:
    """Quartz gets SIGKILL when the worker process that started it ends (prctl
    PR_SET_PDEATHSIG), so a timed-out compile does not keep running."""
    ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGKILL)


def _quartz(text: str) -> str:
    run = subprocess.run([QUARTZ_BINARY, ECC_SET], input=text, capture_output=True, text=True,
                         timeout=None, preexec_fn=_die_with_parent)
    if run.returncode != 0 or not run.stdout.strip():
        raise ValueError(f"Quartz exited with status {run.returncode}: {run.stderr.strip()[:500]}")
    return run.stdout


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output has the input's unitary up to global phase and the same final measurements,
    both read by Qiskit."""
    source, source_measures = split_final_measurements(QuantumCircuit.from_qasm_str(input_qasm), "Quartz")
    output, output_measures = split_final_measurements(QuantumCircuit.from_qasm_str(output_qasm), "Quartz")
    if source_measures != output_measures:
        return False
    return unitary_of(output).equiv(unitary_of(source), atol=1e-8)


def _register_names(circuit: QuantumCircuit):
    names = []
    for bit in circuit.qubits:
        register, index = circuit.find_bit(bit).registers[0]
        names.append(f"{register.name}[{index}]")
    return names


def _clbit_name(circuit: QuantumCircuit, index: int) -> str:
    register, local = circuit.find_bit(circuit.clbits[index]).registers[0]
    return f"{register.name}[{local}]"


def _encode(original: QuantumCircuit, quartz_output: str, measures) -> str:
    """Quartz's gate lines on the input's registers, with the input's declarations and final
    measurements; ValueError on any line other than the header and h, x, rz, cx gates."""
    lines = [line.strip() for line in quartz_output.splitlines() if line.strip()]
    header = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{original.num_qubits}];"]
    if lines[:3] != header:
        raise ValueError(f"Quartz's output starts with {lines[:3]}, expected {header}")
    wires = _register_names(original)
    out = ["OPENQASM 2.0;", 'include "qelib1.inc";']
    out += [f"qreg {r.name}[{r.size}];" for r in original.qregs]
    out += [f"creg {r.name}[{r.size}];" for r in original.cregs]
    for line in lines[3:]:
        match = _QUARTZ_GATE.match(line)
        if not match:
            raise ValueError(f"Quartz wrote a line the adapter does not read: {line[:200]}")
        gate, first, second = match.groups()
        if (gate == "cx") != (second is not None):
            raise ValueError(f"Quartz wrote a gate with the wrong number of qubits: {line[:200]}")
        operands = wires[int(first)] + (f",{wires[int(second)]}" if second is not None else "")
        out.append(f"{gate} {operands};")
    for qubit, clbit in measures:
        out.append(f"measure {wires[qubit]} -> {_clbit_name(original, clbit)};")
    return "\n".join(out) + "\n"


def _compile(qasm: str):
    original = QuantumCircuit.from_qasm_str(qasm)
    unitary, measures = split_final_measurements(original, "Quartz")
    decomposed = translate_to_basis(unitary, DECOMPOSITION_BASIS)
    text = _encode(original, _quartz(_quartz_input(decomposed)), measures)
    notes = [translation_note(DECOMPOSITION_BASIS), _build_note(), _ANGLE_NOTE, _greedy_note()]
    if any(inst.operation.name == "barrier" for inst in original.data):
        notes.append(_BARRIER_NOTE)
    if measures:
        notes.append(_MEASURE_NOTE)
    notes.append(_ENCODE_NOTE)
    if original.num_qubits > CHECKED_UP_TO_QUBITS:
        notes.append(f"The output's unitary is not checked above {CHECKED_UP_TO_QUBITS} qubits.")
    elif not equivalent(qasm, text):
        raise OutputRejected("Quartz's output does not have the input's unitary, so it is not reported")
    else:
        notes.append("Checked: the output has the input's unitary (Qiskit Operator equality up to "
                     "global phase)" + (" and the same final measurements." if measures else "."))
    return text, notes


PIPELINES = {0: _compile}


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="quartz", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "Quartz", levels=sorted(PIPELINES), equivalent=equivalent,
                          extra_probes=TRANSLATION_PROBES)
