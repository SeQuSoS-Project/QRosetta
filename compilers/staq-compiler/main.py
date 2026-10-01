"""staq compiler: runs softwareQ's staq command-line compiler (built from the pinned v3.5
release) at its optimization levels -O1, -O2 and -O3, without device mapping."""

import os
import subprocess
import tempfile

from fastapi import FastAPI
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import (
    declare_sdk_packages, get_num_qubits_from_qasm, get_sdk_versions, with_sdk_versions,
)

declare_sdk_packages("qiskit")

app = FastAPI(title="staq Compiler")

STAQ_BINARY = "/usr/local/bin/staq"
STAQ_VERSION = os.getenv("STAQ_VERSION", "not recorded")
CHECKED_UP_TO_QUBITS = 10

_LEVEL_NOTES = {
    1: "staq -O1: rotation folding, then simplification.",
    2: "staq -O2: inline all gates, simplification, rotation folding, simplification.",
    3: "staq -O3: -O2 followed by CNOT resynthesis and simplification.",
}
_BUILD_NOTE = (f"staq {STAQ_VERSION} built from the release source with Qiskit's qelib1 gate "
               f"definitions (USE_OPENQASM2_SPECS=false); no device mapping.")
_PRECISION_NOTE = ("staq 3.5 reads every real literal in single precision (std::stof in its "
                   "lexer), so angles in the output differ from the input from about the eighth "
                   "significant digit.")


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output has the input's unitary up to global phase (Qiskit Operator.equiv with its
    default tolerances, which absorb staq's single-precision angles)."""
    source = QuantumCircuit.from_qasm_str(input_qasm).remove_final_measurements(inplace=False)
    output = QuantumCircuit.from_qasm_str(output_qasm).remove_final_measurements(inplace=False)
    return Operator(output).equiv(Operator(source))


def _staq(qasm: str, level: int) -> str:
    with tempfile.TemporaryDirectory() as workdir:
        path = os.path.join(workdir, "input.qasm")
        with open(path, "w") as fh:
            fh.write(qasm)
        run = subprocess.run([STAQ_BINARY, f"-O{level}", path], capture_output=True, text=True,
                             timeout=None, cwd=workdir)
    if run.returncode != 0 or not run.stdout.strip():
        raise ValueError(f"staq exited with status {run.returncode}: {run.stderr.strip()[:500]}")
    return run.stdout


def _pipeline(level: int):
    def run(qasm: str):
        output = _staq(qasm, level)
        n_qubits = get_num_qubits_from_qasm(qasm)
        if n_qubits > CHECKED_UP_TO_QUBITS:
            check = f"The output's unitary is not checked above {CHECKED_UP_TO_QUBITS} qubits."
        elif not equivalent(qasm, output):
            raise ValueError("staq's output does not have the input's unitary, so it is not reported")
        else:
            check = "Checked: the output has the input's unitary (Qiskit Operator equality up to global phase)."
        return output, [_BUILD_NOTE, _LEVEL_NOTES[level], _PRECISION_NOTE, check]
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
