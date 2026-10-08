"""BQSKit compiler: bqskit.compile partitions the circuit into blocks and resynthesises
them numerically, at BQSKit optimization levels 1 to 3."""

from fastapi import FastAPI
from bqskit import compile as bqskit_compile
from bqskit.compiler import Compiler
from bqskit.ir import Circuit
from bqskit.ir.gates import CircuitGate
from bqskit.ir.lang.qasm2 import OPENQASM2Language

from qrosetta_commons.compile_checks import (
    process_infidelity, unitary_check_note,
)
from qrosetta_commons.compile_errors import CompileRefused
from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, with_sdk_versions
from qrosetta_commons.qelib1 import QELIB1_SOURCE, renamed_qelib1_definitions

declare_sdk_packages("bqskit", "bqskitrs", "qiskit")

app = FastAPI(title="BQSKit Compiler")

SEED = 0
MAX_SYNTHESIS_SIZE = 3
SYNTHESIS_EPSILON = 1e-8
MAX_PROCESS_INFIDELITY = 1e-6
BQSKIT_READS_DIFFERENTLY = frozenset({"c3x", "c3sqrtx", "c4x", "rc3x", "u0"})

_PARSE_NOTE = "bqskit.ir.lang.qasm2.OPENQASM2Language().decode(): BQSKit's OpenQASM 2.0 parser."
_ENCODE_NOTE = "OPENQASM2Language().encode(): the output circuit as OpenQASM 2.0, one register q."
_APPROXIMATION_NOTE = (f"BQSKit's synthesis is approximate: each resynthesised block is accepted "
                       f"when its Hilbert-Schmidt cost to the block it replaces is below "
                       f"synthesis_epsilon ({SYNTHESIS_EPSILON:g}), and the errors of the blocks "
                       f"add up, so the output approximates the input unitary.")


def _qelib1_gates(qasm: str):
    """(qasm, notes): calls of the gates BQSKit reads differently from qelib1.inc (c3x,
    c3sqrtx, c4x and rc3x as single gates on 4 or 5 qubits, u0 without its parameter)
    replaced by their qelib1.inc definitions under new names."""
    text, renames = renamed_qelib1_definitions(qasm, BQSKIT_READS_DIFFERENTLY)
    if not renames:
        return qasm, []
    listed = ", ".join(f"{name} as {new}" for name, new in renames.items())
    return text, [f"BQSKit 1.2.1's parser reads c3x, c3sqrtx, c4x and rc3x as single gates on "
                  f"more qubits than its blocks hold (max_synthesis_size {MAX_SYNTHESIS_SIZE}) "
                  f"and its u0 takes no parameter; the definitions from {QELIB1_SOURCE} were "
                  f"added to the circuit given to BQSKit under new names, so that its parser "
                  f"reads them as gates defined in the circuit, and the calls renamed with them "
                  f"({listed})."]


def _wide_definition(op) -> bool:
    return isinstance(op.gate, CircuitGate) and op.num_qudits > MAX_SYNTHESIS_SIZE


def _unfold_wide_definitions(circuit):
    """(circuit, number replaced): every gate defined in the circuit that acts on more than
    MAX_SYNTHESIS_SIZE qubits replaced by its body, until none is left. The circuit is
    rebuilt in operation order as Circuit.unfold_all does; Circuit.unfold(point) of BQSKit
    1.2.1 changes the unitary of a circuit with gates before the unfolded one."""
    unfolded = 0
    while any(_wide_definition(op) for op in circuit):
        rebuilt = Circuit(circuit.num_qudits, circuit.radixes)
        for op in circuit:
            if _wide_definition(op):
                body = op.gate._circuit.copy()
                body.set_params(op.params)
                rebuilt.append_circuit(body, op.location)
                unfolded += 1
            else:
                rebuilt.append(op)
        circuit = rebuilt
    return circuit, unfolded


def _decode(qasm: str):
    """(circuit, notes): BQSKit's reading of the circuit; CompileRefused when its parser
    rejects the circuit or a gate on more qubits than BQSKit's blocks hold remains."""
    text, notes = _qelib1_gates(qasm)
    try:
        circuit = OPENQASM2Language().decode(text)
    except Exception as exc:
        raise CompileRefused(f"BQSKit 1.2.1's OpenQASM 2.0 parser does not read this circuit ({exc})")
    circuit, unfolded = _unfold_wide_definitions(circuit)
    if unfolded:
        notes.append(f"Gates defined in the circuit that act on more than {MAX_SYNTHESIS_SIZE} "
                     f"qubits replaced by their bodies, required by the adapter: "
                     f"BQSKit cannot place a gate on more qubits than its blocks hold.")
    wide = sorted({f"{_gate_label(op.gate)} ({op.num_qudits} qubits)" for op in circuit
                   if op.num_qudits > MAX_SYNTHESIS_SIZE})
    if wide:
        raise CompileRefused(
            f"BQSKit partitions the circuit into blocks of at most {MAX_SYNTHESIS_SIZE} qubits "
            f"(max_synthesis_size) and cannot place a gate on more qubits: {', '.join(wide)}")
    return circuit, notes


def _gate_label(gate) -> str:
    if isinstance(gate, CircuitGate):
        return "a gate defined in the circuit"
    try:
        return gate.qasm_name
    except Exception:
        return gate.name


def _pipeline(level: int):
    def run(qasm: str):
        circuit, notes = _decode(qasm)
        with Compiler(num_workers=1) as compiler:
            output = bqskit_compile(circuit, optimization_level=level, seed=SEED,
                                    max_synthesis_size=MAX_SYNTHESIS_SIZE,
                                    synthesis_epsilon=SYNTHESIS_EPSILON, compiler=compiler)
        text = OPENQASM2Language().encode(output)
        compile_note = (f"bqskit.compile(optimization_level={level}, "
                        f"max_synthesis_size={MAX_SYNTHESIS_SIZE}, "
                        f"synthesis_epsilon={SYNTHESIS_EPSILON}, seed={SEED}) with one "
                        f"worker and no machine model (all-to-all, BQSKit's default gate set).")
        check = unitary_check_note("BQSKit", qasm, text, circuit.num_qudits,
                                   MAX_PROCESS_INFIDELITY, "for approximate synthesis")
        return text, notes + [_PARSE_NOTE, compile_note, _APPROXIMATION_NOTE, _ENCODE_NOTE, check]
    return run


PIPELINES = {level: _pipeline(level) for level in (1, 2, 3)}


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output's process infidelity to the input, both read by Qiskit, is at most
    MAX_PROCESS_INFIDELITY."""
    return process_infidelity(input_qasm, output_qasm) <= MAX_PROCESS_INFIDELITY


# bqskit.compiler.Compiler binds fixed ports (7472 and 7474) for its runtime server and
# workers, so two compiles in one container collide.
SINGLE_COMPILE = 1

@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="bqskit", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile, max_concurrent=SINGLE_COMPILE)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "BQSKit", levels=sorted(PIPELINES), equivalent=equivalent)
