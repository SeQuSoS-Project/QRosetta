"""Measured mode, no measure statements: sampled and native runners produce the same keys."""

import pytest

from qrosetta_commons.counts import (
    counts_from_register_keys, measure_all_register, parse_measurement_layout,
    prepare_final_state_sampling,
)
from services.circuit_resolver import prepare_measured_dispatch

H = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
CASES = [
    H + "qreg q[2];\ncreg c[2];\nx q[0];\n",
    H + "qreg q[2];\ncreg meas[1];\nx q[0];\n",
    H + "qreg b[1];\nqreg a[2];\ncreg c[2];\ncreg d[1];\nx a[0];\n",
]


@pytest.mark.parametrize("qasm", CASES)
@pytest.mark.parametrize("preprocessing", [False, True])
def test_sampled_layout_matches_native_dispatch(qasm, preprocessing):
    circuits = prepare_measured_dispatch(qasm, preprocessing)
    native = parse_measurement_layout(circuits["measured_native"]["qasm"])
    _, sampled, notes = prepare_final_state_sampling(circuits["measured_sampled"]["qasm"])
    assert sampled.cregs == native.cregs
    assert sampled.measures == native.measures
    assert f"'{measure_all_register(circuits['measured_sampled']['qasm'])}'" in notes[0]


def test_fresh_register_name_avoids_declared_names():
    assert measure_all_register(CASES[0]) == "meas"
    assert measure_all_register(CASES[1]) == "meas0"
    assert measure_all_register(H + "qreg meas[1];\ncreg meas0[1];\n") == "meas1"
    assert measure_all_register(H + "qreg q[1]; // meas\n") == "meas"


@pytest.mark.parametrize("preprocessing", [False, True])
def test_aer_keys_equal_sampled_keys(preprocessing):
    qasm2 = pytest.importorskip("qiskit.qasm2")
    aer = pytest.importorskip("qiskit_aer")
    circuits = prepare_measured_dispatch(CASES[0], preprocessing)
    native_qasm = circuits["measured_native"]["qasm"]
    circ = qasm2.loads(native_qasm)
    raw = aer.AerSimulator(method="statevector").run(circ, shots=16, seed_simulator=1).result()
    layout = parse_measurement_layout(native_qasm)
    registers = [(r.name, r.size) for r in circ.cregs]
    native = counts_from_register_keys(layout, raw.get_counts(), registers, "lsb")

    _, sampled, _ = prepare_final_state_sampling(circuits["measured_sampled"]["qasm"])
    sampled_counts = sampled.counts_from_qubit_counts(
        {0b10: 16}, sampled.qubit_positions("msb"), "lsb")
    assert native == sampled_counts == {"0100": 16}
