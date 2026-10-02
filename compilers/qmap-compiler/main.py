"""MQT QMAP compiler: maps the circuit onto a linear nearest-neighbour chain of its own
qubit count, after Qiskit decomposes it to u3 and cx, the gate set QMAP maps."""

from fastapi import FastAPI
from mqt.core import load
from mqt.qmap.sc import Architecture, Configuration, Method, map_
from qiskit import QuantumCircuit

from qrosetta_commons.compile_errors import CompileRefused, OutputRejected
from qrosetta_commons.compile_service import (
    TRANSLATION_PROBES, register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, with_sdk_versions
from qrosetta_commons.qiskit_circuits import exact_qasm2_dumps, translate_to_basis, translation_note, unitary_of

declare_sdk_packages("mqt.qmap", "mqt.core", "qiskit")

app = FastAPI(title="MQT QMAP Compiler")

DECOMPOSITION_BASIS = ("u3", "cx")
CHECKED_UP_TO_QUBITS = 10

_DECOMPOSE_NOTE = (translation_note(DECOMPOSITION_BASIS) + " QMAP 3.10 rejects gates with more "
                   "than one control and turns other controlled two-qubit gates (cu3, cp) into cx "
                   "without an error, so it never receives them.")
_ENCODE_NOTE = ("QuantumComputation.qasm2_str(): the mapped circuit as OpenQASM 2.0. Its "
                "'// i' and '// o' comment lines give the physical qubit holding each logical "
                "qubit at input and at output.")


def _decompose(qasm: str) -> str:
    circuit = translate_to_basis(QuantumCircuit.from_qasm_str(qasm), DECOMPOSITION_BASIS)
    unexpected = sorted({inst.operation.name for inst in circuit.data} - set(DECOMPOSITION_BASIS)
                        - {"barrier"})
    if unexpected:
        raise CompileRefused(f"decomposition left gates QMAP cannot map: {unexpected}")
    used = {circuit.find_bit(q).index for inst in circuit.data if inst.operation.name != "barrier"
            for q in inst.qubits}
    idle = sorted(set(range(circuit.num_qubits)) - used)
    if idle:
        raise CompileRefused(f"qubit(s) {idle} have no gates; QMAP 3.10 then records a qubit layout "
                         f"that does not match its output, so the circuit is not mapped")
    return exact_qasm2_dumps(circuit)


def _check_output(decomposed: str, output: str, n_qubits: int) -> str:
    """Note on the run-time check of QMAP's output; ValueError when its layout lines are not
    full permutations of the qubits, or, up to CHECKED_UP_TO_QUBITS, when the output read
    through them does not have the decomposed input's unitary."""
    for tag in ("i", "o"):
        try:
            layout = _layout(output, tag)
        except StopIteration:
            raise OutputRejected(f"QMAP's output has no '// {tag}' layout line")
        if sorted(layout) != list(range(n_qubits)):
            raise OutputRejected(f"QMAP's '// {tag}' layout line {layout} is not a permutation of the "
                             f"{n_qubits} qubits, so the output's qubit layout is unknown")
    if n_qubits > CHECKED_UP_TO_QUBITS:
        return (f"Layout lines checked to be permutations of the qubits; the unitary is not checked "
                f"above {CHECKED_UP_TO_QUBITS} qubits.")
    if not equivalent(decomposed, output):
        raise OutputRejected("QMAP's output, read through its layout lines, does not have the input's "
                         "unitary, so it is not reported")
    return ("Checked: the output, read through its '// i' and '// o' lines, has the input's "
            "unitary (Qiskit Operator equality up to global phase).")


def _line(n_qubits: int) -> Architecture:
    edges = {(i, i + 1) for i in range(n_qubits - 1)} | {(i + 1, i) for i in range(n_qubits - 1)}
    return Architecture(n_qubits, edges, Architecture.Properties())


def _pipeline(method: Method, description: str):
    def run(qasm: str):
        decomposed = _decompose(qasm)
        computation = load(decomposed)
        n_qubits = computation.num_qubits
        if n_qubits < 2:
            raise CompileRefused("QMAP maps circuits of two or more qubits")
        config = Configuration()
        config.method = method
        config.add_measurements_to_mapped_circuit = False
        mapped, _results = map_(computation, _line(n_qubits), config)
        output = mapped.qasm2_str()
        check_note = _check_output(decomposed, output, n_qubits)
        map_note = (f"mqt.qmap.sc.map_ with method={method.name} ({description}) onto a linear "
                    f"chain of {n_qubits} qubits, qubit i coupled to i+1 in both directions, "
                    f"with QMAP's default pre- and post-mapping optimizations and no "
                    f"measurements added.")
        return output, [_DECOMPOSE_NOTE, map_note, _ENCODE_NOTE, check_note]
    return run


PIPELINES = {
    0: _pipeline(Method.heuristic, "A* search over SWAP insertions"),
    1: _pipeline(Method.exact, "SAT-based minimal SWAP insertion"),
}


def _layout(output_qasm: str, tag: str) -> list:
    line = next(line for line in output_qasm.splitlines() if line.startswith(f"// {tag} "))
    return [int(x) for x in line.split()[2:]]


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output, read through its '// i' and '// o' layout lines (entry k is the physical
    qubit holding logical qubit k), has the input's unitary; compared by Qiskit."""
    source = QuantumCircuit.from_qasm_str(input_qasm)
    mapped = QuantumCircuit.from_qasm_str(output_qasm)
    try:
        start, end = _layout(output_qasm, "i"), _layout(output_qasm, "o")
    except StopIteration:
        return False
    n = source.num_qubits
    if sorted(start) != list(range(n)) or sorted(end) != list(range(n)):
        return False
    logical = QuantumCircuit(n)
    wire_of_physical = {physical: k for k, physical in enumerate(start)}
    logical.compose(mapped.remove_final_measurements(inplace=False),
                    qubits=[wire_of_physical[p] for p in range(n)], inplace=True)
    holds = [None] * n
    for k, physical in enumerate(end):
        holds[wire_of_physical[physical]] = k
    for wire in range(n):
        while holds[wire] != wire:
            other = holds[wire]
            logical.swap(wire, other)
            holds[wire], holds[other] = holds[other], holds[wire]
    return unitary_of(logical).equiv(unitary_of(source), atol=1e-8)


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="qmap", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "MQT QMAP", levels=sorted(PIPELINES), equivalent=equivalent,
                          extra_probes=TRANSLATION_PROBES)
