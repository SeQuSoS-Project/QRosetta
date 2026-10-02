"""Q-Synth compiler: Qiskit decomposes the circuit to u3 and cx, the gate set Q-Synth
takes, then Q-Synth's SAT-based peephole synthesis resynthesises each CNOT slice with the
fewest CNOTs or the smallest CNOT depth."""

import contextlib
import io
import os
import sys
import tempfile
import time

from fastapi import FastAPI
from qiskit import QuantumCircuit, QuantumRegister
from qsynth.api import peephole_synthesis

from qrosetta_commons.compile_errors import CompileRefused, OutputRejected
from qrosetta_commons.compile_service import (
    TRANSLATION_PROBES, register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, with_sdk_versions
from qrosetta_commons.qiskit_circuits import (
    exact_qasm2_dumps, split_final_measurements, translate_to_basis, translation_note, unitary_of,
)

declare_sdk_packages("q-synth", "python-sat", "qiskit")

app = FastAPI(title="Q-Synth Compiler")

DECOMPOSITION_BASIS = ("u3", "cx")
SOLVER_TIME_LIMIT_SEC = 240
CHECKED_UP_TO_QUBITS = 10

_LEVEL_NOTES = {
    0: "qsynth.api.peephole_synthesis(slicing='cnot', metric='cx-count'): each CNOT slice resynthesised with the fewest CNOTs (SAT, CaDiCaL 1.9 via pysat 'cd19').",
    1: "qsynth.api.peephole_synthesis(slicing='cnot', metric='cx-depth'): each CNOT slice resynthesised with the smallest CNOT depth (SAT, CaDiCaL 1.9 via pysat 'cd19').",
}
_INSTALL_NOTE = ("Q-Synth 5.1 pins python-sat 1.8.dev13, which is no longer on PyPI; this image "
                 "runs it with python-sat 1.8.dev14.")
_REGISTER_NOTE = ("Q-Synth is given the qubits as one register q in declaration order; its output "
                  "is composed back onto the input's registers, with the input's final "
                  "measurements in their original order.")
_ENCODE_NOTE = ("qrosetta_commons.qiskit_circuits.exact_qasm2_dumps(): the output as OpenQASM "
                "2.0, every numeric angle written as the shortest literal that reads back as "
                "the same double.")


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output has the input's unitary up to global phase and the same final measurements,
    both read by Qiskit."""
    source, source_measures = split_final_measurements(QuantumCircuit.from_qasm_str(input_qasm), "Q-Synth")
    output, output_measures = split_final_measurements(QuantumCircuit.from_qasm_str(output_qasm), "Q-Synth")
    return source_measures == output_measures and unitary_of(output).equiv(unitary_of(source), atol=1e-8)


def _synthesise(circuit: QuantumCircuit, metric: str) -> QuantumCircuit:
    """peephole_synthesis with a record of every slice's last solver call; ValueError when a
    slice was still timed out at the end or the time budget ran out, since Q-Synth then keeps
    that slice's original gates and the result depends on machine speed."""
    module = sys.modules["qsynth.peephole_synthesis"]
    original = module.optimize_single_slice
    last_timed_out = {}

    def recording(args, slice, coupling_graph, current_slice_time):
        circuit_out, timed_out = original(args, slice, coupling_graph, current_slice_time)
        last_timed_out[id(slice)] = timed_out
        return circuit_out, timed_out

    home = os.getcwd()
    module.optimize_single_slice = recording
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory() as workdir:
            os.chdir(workdir)
            with contextlib.redirect_stdout(io.StringIO()):
                result = peephole_synthesis(circuit, slicing="cnot", metric=metric,
                                            timeout=SOLVER_TIME_LIMIT_SEC, verbose=-1)
    finally:
        os.chdir(home)
        module.optimize_single_slice = original
    elapsed = time.monotonic() - started
    unsolved = sum(1 for timed_out in last_timed_out.values() if timed_out)
    if result.timed_out or unsolved or elapsed >= SOLVER_TIME_LIMIT_SEC - 1:
        raise ValueError(f"Q-Synth did not solve every CNOT slice within its {SOLVER_TIME_LIMIT_SEC} s "
                         f"solver budget ({unsolved} slice(s) timed out, {elapsed:.0f} s); it keeps "
                         f"such slices unchanged, so the result would depend on machine speed and "
                         f"none is reported")
    return result.circuit


def _pipeline(level: int):
    metric = "cx-count" if level == 0 else "cx-depth"

    def run(qasm: str):
        original = QuantumCircuit.from_qasm_str(qasm)
        unitary, measures = split_final_measurements(original, "Q-Synth")
        translated = translate_to_basis(unitary, DECOMPOSITION_BASIS)
        unexpected = sorted({i.operation.name for i in translated.data} - set(DECOMPOSITION_BASIS) - {"barrier"})
        if unexpected:
            raise CompileRefused(f"decomposition left gates Q-Synth cannot take: {unexpected}")
        flat = QuantumCircuit(QuantumRegister(original.num_qubits, "q"))
        flat.compose(translated, qubits=list(range(original.num_qubits)), inplace=True)
        synthesised = _synthesise(flat, metric)
        output_circuit = original.copy_empty_like()
        output_circuit.global_phase = 0
        output_circuit.compose(synthesised, qubits=list(range(original.num_qubits)), inplace=True)
        for qubit, clbit in measures:
            output_circuit.measure(qubit, clbit)
        output = exact_qasm2_dumps(output_circuit)
        if original.num_qubits <= CHECKED_UP_TO_QUBITS:
            if not equivalent(qasm, output):
                raise OutputRejected("Q-Synth's output does not have the input's unitary, so it is not reported")
            check = "Checked: the output has the input's unitary (Qiskit Operator equality up to global phase)."
        else:
            check = f"The output's unitary is not checked above {CHECKED_UP_TO_QUBITS} qubits."
        notes = [translation_note(DECOMPOSITION_BASIS), _LEVEL_NOTES[level], _INSTALL_NOTE, _REGISTER_NOTE,
                 _ENCODE_NOTE, check]
        return output, notes
    return run


PIPELINES = {0: _pipeline(0), 1: _pipeline(1)}


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="qsynth", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "Q-Synth", levels=sorted(PIPELINES), equivalent=equivalent,
                          extra_probes=TRANSLATION_PROBES)
