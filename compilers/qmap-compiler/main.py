"""MQT QMAP compiler: maps the circuit onto a linear nearest-neighbour chain of its own
qubit count, after Qiskit decomposes it to u3 and cx, the gate set QMAP maps."""

from fastapi import FastAPI
from mqt.core import load
from mqt.qmap.sc import Architecture, Configuration, Method, map_
import itertools

from qiskit import QuantumCircuit, qasm2, transpile
from qiskit.circuit.library import PermutationGate
from qiskit.quantum_info import Operator

from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, with_sdk_versions

declare_sdk_packages("mqt.qmap", "mqt.core", "qiskit")

app = FastAPI(title="MQT QMAP Compiler")

DECOMPOSITION_BASIS = ("u3", "cx")

_DECOMPOSE_NOTE = ("qiskit.transpile(basis_gates=['u3', 'cx'], optimization_level=0): basis "
                   "translation only, required by the adapter. QMAP 3.10 rejects gates with "
                   "more than one control and turns other controlled two-qubit gates (cu3, "
                   "cp) into cx without an error, so it never receives them.")
_ENCODE_NOTE = ("QuantumComputation.qasm2_str(): the mapped circuit as OpenQASM 2.0. Its "
                "'// i' and '// o' comment lines give the physical qubit holding each logical "
                "qubit at input and at output.")


def _decompose(qasm: str) -> str:
    circuit = transpile(QuantumCircuit.from_qasm_str(qasm), basis_gates=list(DECOMPOSITION_BASIS),
                        optimization_level=0)
    unexpected = sorted({inst.operation.name for inst in circuit.data} - set(DECOMPOSITION_BASIS)
                        - {"barrier"})
    if unexpected:
        raise ValueError(f"decomposition left gates QMAP cannot map: {unexpected}")
    return qasm2.dumps(circuit)


def _line(n_qubits: int) -> Architecture:
    edges = {(i, i + 1) for i in range(n_qubits - 1)} | {(i + 1, i) for i in range(n_qubits - 1)}
    return Architecture(n_qubits, edges, Architecture.Properties())


def _pipeline(method: Method, description: str):
    def run(qasm: str):
        decomposed = _decompose(qasm)
        computation = load(decomposed)
        n_qubits = computation.num_qubits
        if n_qubits < 2:
            raise ValueError("QMAP maps circuits of two or more qubits")
        config = Configuration()
        config.method = method
        config.add_measurements_to_mapped_circuit = False
        mapped, _results = map_(computation, _line(n_qubits), config)
        map_note = (f"mqt.qmap.sc.map_ with method={method.name} ({description}) onto a linear "
                    f"chain of {n_qubits} qubits, qubit i coupled to i+1 in both directions, "
                    f"with QMAP's default pre- and post-mapping optimizations and no "
                    f"measurements added.")
        return mapped.qasm2_str(), [_DECOMPOSE_NOTE, map_note, _ENCODE_NOTE]
    return run


PIPELINES = {
    0: _pipeline(Method.heuristic, "A* search over SWAP insertions"),
    1: _pipeline(Method.exact, "SAT-based minimal SWAP insertion"),
}


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """Output unitary equal to the input's up to a qubit relabelling at input and at output
    (the layouts QMAP chose), compared by Qiskit; for small probe circuits only."""
    target = Operator(QuantumCircuit.from_qasm_str(input_qasm))
    mapped = Operator(QuantumCircuit.from_qasm_str(output_qasm))
    labels = list(itertools.permutations(range(target.num_qubits)))
    return any((Operator(PermutationGate(list(after))) @ mapped @ Operator(PermutationGate(list(before))))
               .equiv(target, atol=1e-8) for before in labels for after in labels)


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="qmap", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "MQT QMAP", levels=sorted(PIPELINES), equivalent=equivalent)
