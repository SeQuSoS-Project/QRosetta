"""Q-Synth compiler: Qiskit decomposes the circuit to u3 and cx, the gate set Q-Synth
takes, then Q-Synth's SAT-based peephole synthesis resynthesises each CNOT slice with the
fewest CNOTs or the smallest CNOT depth."""

import contextlib
import io
import os
import tempfile

from fastapi import FastAPI
from qiskit import QuantumCircuit, qasm2, transpile
from qiskit.quantum_info import Operator
from qsynth.api import peephole_synthesis

from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, with_sdk_versions

declare_sdk_packages("q-synth", "python-sat", "qiskit")

app = FastAPI(title="Q-Synth Compiler")

DECOMPOSITION_BASIS = ("u3", "cx")
SOLVER_TIME_LIMIT_SEC = 240
CHECKED_UP_TO_QUBITS = 10

_DECOMPOSE_NOTE = ("qiskit.transpile(basis_gates=['u3', 'cx'], optimization_level=0): basis "
                   "translation only, required by the adapter, since Q-Synth takes CNOT and "
                   "single-qubit gates.")
_LEVEL_NOTES = {
    0: "qsynth.api.peephole_synthesis(slicing='cnot', metric='cx-count'): each CNOT slice resynthesised with the fewest CNOTs (SAT, CaDiCaL 1.9 via pysat 'cd19').",
    1: "qsynth.api.peephole_synthesis(slicing='cnot', metric='cx-depth'): each CNOT slice resynthesised with the smallest CNOT depth (SAT, CaDiCaL 1.9 via pysat 'cd19').",
}
_INSTALL_NOTE = ("Q-Synth 5.1 pins python-sat 1.8.dev13, which is no longer on PyPI; this image "
                 "runs it with python-sat 1.8.dev14.")
_ENCODE_NOTE = "qiskit.qasm2.dumps(): the synthesised circuit as OpenQASM 2.0, registers as declared."


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output has the input's unitary up to global phase, both read by Qiskit."""
    source = QuantumCircuit.from_qasm_str(input_qasm).remove_final_measurements(inplace=False)
    output = QuantumCircuit.from_qasm_str(output_qasm).remove_final_measurements(inplace=False)
    return Operator(output).equiv(Operator(source), atol=1e-8)


def _pipeline(level: int):
    metric = "cx-count" if level == 0 else "cx-depth"

    def run(qasm: str):
        circuit = transpile(QuantumCircuit.from_qasm_str(qasm), basis_gates=list(DECOMPOSITION_BASIS),
                            optimization_level=0)
        unexpected = sorted({i.operation.name for i in circuit.data} - set(DECOMPOSITION_BASIS) - {"barrier"})
        if unexpected:
            raise ValueError(f"decomposition left gates Q-Synth cannot take: {unexpected}")
        home = os.getcwd()
        with tempfile.TemporaryDirectory() as workdir:
            os.chdir(workdir)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    result = peephole_synthesis(circuit, slicing="cnot", metric=metric,
                                                timeout=SOLVER_TIME_LIMIT_SEC, verbose=-1)
            finally:
                os.chdir(home)
        if result.timed_out:
            raise ValueError(f"Q-Synth reached its {SOLVER_TIME_LIMIT_SEC} s solver limit; a partial "
                             f"result would depend on machine speed, so none is reported")
        output = qasm2.dumps(result.circuit)
        if circuit.num_qubits <= CHECKED_UP_TO_QUBITS:
            if not equivalent(qasm, output):
                raise ValueError("Q-Synth's output does not have the input's unitary, so it is not reported")
            check = "Checked: the output has the input's unitary (Qiskit Operator equality up to global phase)."
        else:
            check = f"The output's unitary is not checked above {CHECKED_UP_TO_QUBITS} qubits."
        return output, [_DECOMPOSE_NOTE, _LEVEL_NOTES[level], _INSTALL_NOTE, _ENCODE_NOTE, check]
    return run


PIPELINES = {0: _pipeline(0), 1: _pipeline(1)}


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="qsynth", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "Q-Synth", levels=sorted(PIPELINES), equivalent=equivalent)
