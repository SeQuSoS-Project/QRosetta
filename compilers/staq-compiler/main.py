"""staq compiler: runs softwareQ's staq command-line compiler (built from the pinned v3.5
release) at its optimization levels -O1, -O2 and -O3, without device mapping."""

import os
import re
import subprocess
import tempfile

import numpy as np
from fastapi import FastAPI

from qrosetta_commons.compile_checks import (
    process_infidelity, single_precision_angle_change, unitary_check_note,
)
from qrosetta_commons.compile_errors import CompileRefused
from qrosetta_commons.compile_service import (
    declare_native_component, register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import (
    declare_sdk_packages, get_num_qubits_from_qasm, strip_qasm_comments,
    with_sdk_versions,
)
from qrosetta_commons.qelib1 import add_qelib1_definitions, qelib1_definitions

declare_sdk_packages("qiskit")

app = FastAPI(title="staq Compiler")

STAQ_BINARY = "/usr/local/bin/staq"
STAQ_VERSION = os.getenv("STAQ_VERSION", "not recorded")
declare_native_component(
    "staq", STAQ_VERSION,
    source_url=f"https://github.com/softwareQinc/staq/archive/refs/tags/v{STAQ_VERSION}.tar.gz",
    source_sha256=os.getenv("STAQ_SHA256", "not recorded"),
    compiler_flags=os.getenv("STAQ_CXXFLAGS", "not recorded"))
MAX_PROCESS_INFIDELITY = 1e-8
MAX_LITERAL_ROUNDING = 1e-6
STAQ_GATES = frozenset({
    "u3", "u2", "u1", "cx", "id", "u0", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "r", "rx",
    "ry", "rz", "cz", "cy", "swap", "ch", "ccx", "cswap", "crz", "cu1", "cu3", "U", "CX",
})
_GATE_DEF = re.compile(r"gate\s+(\w+)\s*(?:\([^)]*\))?\s*[^{]*\{([^}]*)\}")
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


def _precision_note(qasm: str) -> str:
    return (f"staq 3.5 reads every real literal in single precision (std::stof in its lexer) and "
            f"evaluates the expression in double precision; literals it would change by more "
            f"than {MAX_LITERAL_ROUNDING:g} are refused before staq runs. The largest change to a "
            f"constant angle of this circuit is {single_precision_angle_change(qasm):.3g} rad.")


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output's process infidelity to the input is at most MAX_PROCESS_INFIDELITY, a
    tolerance that absorbs staq's single-precision angles."""
    return process_infidelity(input_qasm, output_qasm) <= MAX_PROCESS_INFIDELITY


def _add_missing_qelib1_definitions(qasm: str):
    """(qasm, names): the circuit with Qiskit's qelib1.inc definitions of the gates it calls
    that staq's library lacks, and of the gates those definitions call, inserted after the
    include line."""
    return add_qelib1_definitions(qasm, set(qelib1_definitions()) - STAQ_GATES)


def _refuse_library_name_clashes(qasm: str) -> None:
    """ValueError for a register or gate named r or cswap: staq's library adds these two gates
    to qelib1.inc and rejects a second declaration under either name."""
    text = strip_qasm_comments(qasm)
    declared = set(re.findall(r"\b(?:qreg|creg)\s+([A-Za-z_]\w*)", text))
    declared |= {m.group(1) for m in _GATE_DEF.finditer(text)}
    clashes = sorted(declared & {"r", "cswap"})
    if clashes:
        raise CompileRefused(f"{', '.join(clashes)} names a gate in staq's library, and staq rejects a "
                         f"register or gate declared under that name")


def _refuse_single_precision_losses(qasm: str) -> None:
    """ValueError for a numeric literal that staq's std::stof would move by more than
    MAX_LITERAL_ROUNDING or cannot represent (it then aborts)."""
    for literal in _NUMBER.findall(strip_qasm_comments(qasm)):
        value = float(literal)
        single = float(np.float32(value))
        if value != 0 and abs(value) < np.finfo(np.float32).tiny:
            raise CompileRefused(f"the literal {literal} is below single precision's smallest normal "
                             f"number; staq 3.5 reads literals with std::stof and cannot take it")
        if abs(single - value) > MAX_LITERAL_ROUNDING:
            raise CompileRefused(f"staq 3.5 reads literals in single precision, which would change "
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
        check = unitary_check_note("staq", qasm, output, get_num_qubits_from_qasm(qasm),
                                   MAX_PROCESS_INFIDELITY, "for single-precision angles")
        notes = [_BUILD_NOTE]
        if added:
            notes.append(f"staq's gate library lacks {', '.join(added)}; their definitions from "
                         f"Qiskit's qelib1.inc were added to the circuit given to staq.")
        return output, notes + [_LEVEL_NOTES[level], _precision_note(qasm), check]
    return run


PIPELINES = {level: _pipeline(level) for level in (1, 2, 3)}


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="staq", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "staq", levels=sorted(PIPELINES), equivalent=equivalent)
