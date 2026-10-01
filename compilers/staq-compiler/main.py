"""staq compiler: runs softwareQ's staq command-line compiler (built from the pinned v3.5
release) at its optimization levels -O1, -O2 and -O3, without device mapping."""

import os
import re
import subprocess
import tempfile

import numpy as np
from fastapi import FastAPI
from qiskit import QuantumCircuit

from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import (
    declare_sdk_packages, get_num_qubits_from_qasm, get_sdk_versions, strip_qasm_comments,
    with_sdk_versions,
)
from qrosetta_commons.qiskit_circuits import unitary_of

declare_sdk_packages("qiskit")

app = FastAPI(title="staq Compiler")

STAQ_BINARY = "/usr/local/bin/staq"
STAQ_VERSION = os.getenv("STAQ_VERSION", "not recorded")
CHECKED_UP_TO_QUBITS = 10
MAX_PROCESS_INFIDELITY = 1e-8
MAX_LITERAL_ROUNDING = 1e-6
STAQ_GATES = frozenset({
    "u3", "u2", "u1", "cx", "id", "u0", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "r", "rx",
    "ry", "rz", "cz", "cy", "swap", "ch", "ccx", "cswap", "crz", "cu1", "cu3", "U", "CX",
})
_KEYWORDS = frozenset({"OPENQASM", "include", "qreg", "creg", "gate", "opaque", "measure",
                       "barrier", "reset", "if"})
_GATE_DEF = re.compile(r"gate\s+(\w+)\s*(?:\([^)]*\))?\s*[^{]*\{([^}]*)\}")
_STATEMENT_NAME = re.compile(r"(?:^|[;{}])\s*(?:if\s*\([^)]*\)\s*)?([A-Za-z_]\w*)")
_NUMBER = re.compile(r"(?<![\w.])(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

_LEVEL_NOTES = {
    1: "staq -O1: rotation folding, then simplification.",
    2: ("staq -O2: inline every gate except x, y, z, h, s, sdg, t, tdg, rx, ry, rz, cz, cy, swap, "
        "cx and u1 (staq's default overrides), then simplification, rotation folding, simplification."),
    3: "staq -O3: -O2 followed by CNOT resynthesis and simplification.",
}
_BUILD_NOTE = (f"staq {STAQ_VERSION} built from the release source with USE_OPENQASM2_SPECS=false: "
               f"its gate library is the OpenQASM 2.0 qelib1 gates plus r and cswap, with Qiskit's "
               f"cu3 and rz definitions; no device mapping.")
_PRECISION_NOTE = (f"staq 3.5 reads every real literal in single precision (std::stof in its "
                   f"lexer), so angles in the output differ from the input from about the eighth "
                   f"significant digit; literals it would change by more than "
                   f"{MAX_LITERAL_ROUNDING:g} are refused before staq runs.")


def process_infidelity(input_qasm: str, output_qasm: str) -> float:
    """1 - |Tr(U_in^dagger U_out)| / 2^n, both unitaries read by Qiskit; 0 means equal up to
    global phase."""
    source = unitary_of(QuantumCircuit.from_qasm_str(input_qasm).remove_final_measurements(inplace=False))
    output = unitary_of(QuantumCircuit.from_qasm_str(output_qasm).remove_final_measurements(inplace=False))
    if source.dim != output.dim:
        return 1.0
    return max(0.0, 1.0 - abs(np.trace(source.data.conj().T @ output.data)) / source.dim[0])


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output's process infidelity to the input is at most MAX_PROCESS_INFIDELITY, a
    tolerance that absorbs staq's single-precision angles."""
    return process_infidelity(input_qasm, output_qasm) <= MAX_PROCESS_INFIDELITY


def _qiskit_qelib1() -> dict:
    """Gate name -> definition text, from the qelib1.inc shipped with Qiskit."""
    import qiskit
    path = os.path.join(os.path.dirname(qiskit.__file__), "qasm", "libs", "qelib1.inc")
    with open(path) as fh:
        text = strip_qasm_comments(fh.read())
    return {m.group(1): m.group(0) for m in _GATE_DEF.finditer(text)}


def _called_names(text: str) -> set:
    return {name for name in _STATEMENT_NAME.findall(text) if name not in _KEYWORDS}


def _add_missing_qelib1_definitions(qasm: str):
    """(qasm, names): the circuit with Qiskit's qelib1.inc definitions of the gates it calls
    that staq's library lacks, and of the gates those definitions call, inserted after the
    include line."""
    text = strip_qasm_comments(qasm)
    defined = {m.group(1) for m in _GATE_DEF.finditer(text)}
    library = _qiskit_qelib1()
    order = []

    def visit(name):
        if name in order or name in defined or name in STAQ_GATES or name not in library:
            return
        for dependency in sorted(_called_names(library[name].split("{", 1)[1])):
            visit(dependency)
        order.append(name)

    for name in sorted(_called_names(text)):
        visit(name)
    if not order:
        return qasm, []
    definitions = "\n".join(library[name] for name in order)
    match = re.search(r'include\s+"qelib1\.inc"\s*;', qasm)
    if match is None:
        return qasm, []
    return qasm[:match.end()] + "\n" + definitions + qasm[match.end():], sorted(order)


def _refuse_library_name_clashes(qasm: str) -> None:
    """ValueError for a register or gate named r or cswap: staq's library adds these two gates
    to qelib1.inc and rejects a second declaration under either name."""
    text = strip_qasm_comments(qasm)
    declared = set(re.findall(r"\b(?:qreg|creg)\s+([A-Za-z_]\w*)", text))
    declared |= {m.group(1) for m in _GATE_DEF.finditer(text)}
    clashes = sorted(declared & {"r", "cswap"})
    if clashes:
        raise ValueError(f"{', '.join(clashes)} names a gate in staq's library, and staq rejects a "
                         f"register or gate declared under that name")


def _refuse_single_precision_losses(qasm: str) -> None:
    """ValueError for a numeric literal that staq's std::stof would move by more than
    MAX_LITERAL_ROUNDING or cannot represent (it then aborts)."""
    for literal in _NUMBER.findall(strip_qasm_comments(qasm)):
        value = float(literal)
        single = float(np.float32(value))
        if value != 0 and abs(value) < np.finfo(np.float32).tiny:
            raise ValueError(f"the literal {literal} is below single precision's smallest normal "
                             f"number; staq 3.5 reads literals with std::stof and cannot take it")
        if abs(single - value) > MAX_LITERAL_ROUNDING:
            raise ValueError(f"staq 3.5 reads literals in single precision, which would change "
                             f"{literal} by {abs(single - value):.2g}; literals that change by more "
                             f"than {MAX_LITERAL_ROUNDING:g} are refused")


def _staq(qasm: str, level: int) -> str:
    with tempfile.TemporaryDirectory() as workdir:
        path = os.path.join(workdir, "input.qasm")
        with open(path, "w") as fh:
            fh.write(qasm)
        run = subprocess.run([STAQ_BINARY, f"-O{level}", "input.qasm"], capture_output=True,
                             text=True, timeout=None, cwd=workdir)
    if run.returncode != 0 or not run.stdout.strip():
        message = run.stderr.replace(workdir + os.sep, "").strip()[:500]
        raise ValueError(f"staq exited with status {run.returncode}: {message}")
    return run.stdout


def _pipeline(level: int):
    def run(qasm: str):
        _refuse_library_name_clashes(qasm)
        _refuse_single_precision_losses(qasm)
        given, added = _add_missing_qelib1_definitions(qasm)
        output = _staq(given, level)
        n_qubits = get_num_qubits_from_qasm(qasm)
        if n_qubits > CHECKED_UP_TO_QUBITS:
            check = f"The output's unitary is not checked above {CHECKED_UP_TO_QUBITS} qubits."
        else:
            infidelity = process_infidelity(qasm, output)
            if infidelity > MAX_PROCESS_INFIDELITY:
                raise ValueError(f"staq's output has process infidelity {infidelity:.2g} to the input "
                                 f"(more than {MAX_PROCESS_INFIDELITY:g}), so it is not reported")
            check = (f"Checked with Qiskit: process infidelity to the input {infidelity:.2g} "
                     f"(at most {MAX_PROCESS_INFIDELITY:g} accepted, for single-precision angles).")
        notes = [_BUILD_NOTE]
        if added:
            notes.append(f"staq's gate library lacks {', '.join(added)}; their definitions from "
                         f"Qiskit's qelib1.inc were added to the circuit given to staq.")
        return output, notes + [_LEVEL_NOTES[level], _PRECISION_NOTE, check]
    return run


PIPELINES = {level: _pipeline(level) for level in (1, 2, 3)}


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    result = run_compile_job(compiler="staq", payload=payload, pipelines=PIPELINES)
    if isinstance(result, dict):
        result["sdk_versions"] = {**get_sdk_versions(), "staq": STAQ_VERSION}
    return result


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "staq", levels=sorted(PIPELINES), equivalent=equivalent)
