"""A minimal pytket-based runner for test_runner_self_test: exact statevector, sampled counts."""
import numpy as np
import pytket.qasm

from qrosetta_commons.counts import (
    prepare_final_state_sampling, prepare_statevector_qasm, statevector_in_declaration_order,
    unit_pairs,
)
from qrosetta_commons.helpers import (
    CompileResult, _draw_statevector_samples, declare_sdk_packages, run_measured_job,
    run_statevector_job, with_sdk_versions,
)

declare_sdk_packages("pytket", "numpy")


def _compile(payload):
    qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
    circ = pytket.qasm.circuit_from_qasm_str(qasm)
    return CompileResult(circuit=(circ, unit_pairs(circ.qubits)), n_qubits=circ.n_qubits,
                         preprocessing_applied=notes)


def _execute(compiled, _payload):
    return compiled.circuit[0].get_statevector()


@with_sdk_versions
def process_run(payload):
    def shape(sv, compiled, payload):
        return statevector_in_declaration_order(
            sv, payload["circuit_data"], compiled.circuit[1], "msb", compiled.preprocessing_applied)

    return run_statevector_job(
        simulator="fixture", payload=payload, compile_fn=_compile, execute_fn=_execute,
        postprocess_fn=shape, qubit_ordering="msb", precision="complex128")


def _compile_sampled(payload):
    qasm, layout, notes = prepare_final_state_sampling(payload["circuit_data"])
    circ = pytket.qasm.circuit_from_qasm_str(qasm)
    return CompileResult(circuit=(circ, layout, unit_pairs(circ.qubits)),
                         n_qubits=circ.n_qubits, preprocessing_applied=notes)


def _make_measured(seed_override=None, bit_order="msb"):
    @with_sdk_versions
    def process_run_measured(payload):
        def draw(compiled, payload):
            seed = payload.get("seed") if seed_override is None else seed_override
            return _draw_statevector_samples(
                np.asarray(compiled.circuit[0].get_statevector()), payload["n_shots"], seed)

        def shape(samples, compiled, _payload):
            _circ, layout, qubits = compiled.circuit
            positions = layout.qubit_positions("msb", qubits)
            return layout.counts_from_qubit_samples(samples, positions, bit_order), "sv_sample"

        return run_measured_job(
            simulator="fixture", payload=payload, compile_fn=_compile_sampled,
            execute_fn=draw, postprocess_fn=shape, qubit_ordering="msb",
            precision="complex128")
    return process_run_measured


process_run_measured = _make_measured()
process_run_measured_ignoring_seed = _make_measured(seed_override=7)
process_run_measured_wrong_label = _make_measured(bit_order="lsb")
