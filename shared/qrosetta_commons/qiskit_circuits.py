"""Qiskit helpers: final measurements split off and restored and basis translation that makes
no assumption about the qubits' initial state (compile-only adapters), the output permutation
of a transpiled circuit made explicit (``restore_final_layout``), and OpenQASM 2.0 export that
keeps every angle (``exact_qasm2_dumps``)."""

import re

from qiskit import QuantumCircuit, transpile

from qrosetta_commons.compile_errors import CompileRefused

_CONTROL_FLOW = {"if_else", "while_loop", "for_loop", "switch_case", "box"}


def split_final_measurements(circuit: QuantumCircuit, compiler: str):
    """(circuit without its final measurements, [(qubit, clbit), ...] in circuit order).
    CompileRefused for a measurement followed by a gate on its qubit, reset or classical control."""
    later = set()
    finals = []
    body = []
    for inst in reversed(circuit.data):
        name = inst.operation.name
        qubits = [circuit.find_bit(q).index for q in inst.qubits]
        if name in _CONTROL_FLOW:
            raise CompileRefused(f"classically controlled operations are refused; {compiler} rewrites unitary circuits")
        if name == "reset":
            raise CompileRefused(f"reset is refused; {compiler} rewrites unitary circuits")
        if name == "measure":
            if qubits[0] in later:
                raise CompileRefused(f"mid-circuit measurement is refused; {compiler} rewrites unitary circuits")
            finals.append((qubits[0], circuit.find_bit(inst.clbits[0]).index))
            later.add(qubits[0])
            continue
        if name != "barrier":
            later.update(qubits)
        body.append(inst)
    unitary = circuit.copy_empty_like()
    for inst in reversed(body):
        unitary.append(inst.operation, inst.qubits, inst.clbits)
    return unitary, list(reversed(finals))


def translate_to_basis(circuit: QuantumCircuit, basis) -> QuantumCircuit:
    """Basis translation with optimization_level=0 and qubits_initially_zero=False, so that no
    qubit is used as a clean ancilla when a multi-controlled gate is decomposed."""
    return transpile(circuit, basis_gates=list(basis), optimization_level=0, qubits_initially_zero=False)


def translation_note(basis) -> str:
    names = ", ".join(f"'{b}'" for b in basis)
    return (f"qiskit.transpile(basis_gates=[{names}], optimization_level=0, "
            f"qubits_initially_zero=False): basis translation only, required by the adapter; no "
            f"qubit is assumed to start in |0>, so the translation keeps the unitary.")


def unitary_of(circuit: QuantumCircuit):
    """Qiskit Operator of the circuit, built from its u3/cx translation so that nested gate
    definitions are flattened first."""
    from qiskit.quantum_info import Operator
    return Operator(translate_to_basis(circuit, ("u3", "cx")))


def swaps_restoring(final_positions) -> list:
    """Swaps ``(a, b)`` that move the qubit ending at ``final_positions[v]`` back to ``v``."""
    holder = {p: v for v, p in enumerate(final_positions)}
    position = list(final_positions)
    swaps = []
    for target in range(len(position)):
        source = position[target]
        if source == target:
            continue
        swaps.append((target, source))
        displaced = holder[target]
        holder[target], holder[source] = target, displaced
        position[target], position[displaced] = target, source
    return swaps


def restore_final_layout(circuit: QuantumCircuit):
    """(circuit, swaps appended): a transpiled circuit whose ``layout`` records an output
    permutation (ElidePermutations deletes swap gates and records them only there) gets the
    swap gates that put each qubit's final state back on its input position; the layout is
    then cleared, since the gates realise the permutation."""
    layout = circuit.layout
    if layout is None:
        return circuit, []
    swaps = swaps_restoring(layout.final_index_layout())
    if swaps:
        for a, b in swaps:
            circuit.swap(a, b)
        circuit._layout = None
    return circuit, swaps


def final_layout_note(swaps) -> str:
    pairs = "; ".join(f"{a},{b}" for a, b in swaps)
    return (f"Output permutation: the Qiskit transpiler removed swap gates and recorded the "
            f"permutation only in the circuit's layout (final_layout, ElidePermutations at "
            f"levels 2 and 3); swap gates on qubit positions {pairs} (0-based, circuit qubit "
            f"order) are appended after transpilation, inside compilation_time, so the final "
            f"state is in the input's qubit order.")


def qasm_real(value: float) -> str:
    """Shortest text that reads back as ``value``, always with a decimal point (OpenQASM 2.0
    real literals need one)."""
    text = repr(float(value))
    mantissa, _, exponent = text.partition("e")
    if "." not in mantissa:
        mantissa += ".0"
    return mantissa + ("e" + exponent if exponent else "")


def exact_qasm2_dumps(circuit: QuantumCircuit) -> str:
    """``qiskit.qasm2.dumps`` with every numeric gate parameter written as ``qasm_real`` and
    generated gate names numbered (``_numbered_generated_names``).
    Qiskit's exporter formats parameters with ``pi_check(eps=1e-12)``, which writes a
    magnitude below 1e-12 as 0 and a value within 1e-12 of a simple multiple of pi as that
    multiple; symbolic parameters (inside gate definitions) keep Qiskit's formatting."""
    import math
    from qiskit import qasm2
    from qiskit.qasm2 import export

    original = export.pi_check

    def exact(value, *args, **kwargs):
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return qasm_real(value)
        return original(value, *args, **kwargs)

    export.pi_check = exact
    try:
        text = qasm2.dumps(circuit)
    finally:
        export.pi_check = original
    return _numbered_generated_names(text)


_GENERATED_NAME = re.compile(r"\b([A-Za-z_]\w*?)_(\d{9,})\b")


def _numbered_generated_names(text: str) -> str:
    """Qiskit names a gate it defines ``<name>_<id(operation)>``, a memory address that
    differs between processes; number those suffixes by first appearance instead."""
    numbers = {}

    def number(match):
        key = match.group(0)
        if key not in numbers:
            numbers[key] = f"{match.group(1)}_q{len(numbers)}"
        return numbers[key]

    return _GENERATED_NAME.sub(number, text)
