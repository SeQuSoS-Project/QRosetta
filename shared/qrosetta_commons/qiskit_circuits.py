"""Qiskit helpers for compile-only adapters: final measurements split off and restored, and
basis translation that makes no assumption about the qubits' initial state."""

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
