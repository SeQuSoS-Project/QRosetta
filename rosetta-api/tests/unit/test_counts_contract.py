"""Counts keys over classical bits: the measurement layout parser and the key mapping."""
import re
from pathlib import Path

import numpy as np
import pytest

from qrosetta_commons.counts import (
    MID_CIRCUIT_ERROR, STATEVECTOR_TERMINAL_ERROR, counts_from_register_keys,
    named_bits_from_register_key, parse_measurement_layout, prepare_final_state_sampling,
    prepare_statevector_qasm, strip_measurements, unordered_qreg_note,
)

H = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'

MID_CIRCUIT = H + "qreg q[1]; creg c[2]; h q[0]; measure q[0]->c[0]; h q[0]; measure q[0]->c[1];"
SUBSET = H + "qreg q[3]; creg c[1]; x q[2]; h q[0]; measure q[0]->c[0];"
SWAPPED = H + "qreg q[4]; creg c[2]; x q[0]; x q[3]; measure q[0]->c[1]; measure q[3]->c[0];"
ASYMMETRIC = H + "qreg q[2]; creg c[2]; x q[0]; measure q[0]->c[0]; measure q[1]->c[1];"


def _msb_index(bits):
    """Basis-state index with qubit 0 most significant."""
    return int("".join(map(str, bits)), 2)


def test_flat_clbit_index_follows_creg_declaration_order():
    layout = parse_measurement_layout(H + "qreg q[2]; creg a[2]; creg b[1]; measure q -> a;")
    assert layout.clbits == [("a", 0), ("a", 1), ("b", 0)]
    assert layout.measures == [(0, 0), (1, 1)]


def test_register_broadcast_measure_with_multiple_qregs():
    layout = parse_measurement_layout(
        H + "qreg m[1]; qreg a[2]; creg c[1]; creg d[2]; measure m -> c; measure a -> d;")
    assert layout.qubits == [("m", 0), ("a", 0), ("a", 1)]
    assert layout.measures == [(0, 0), (1, 1), (2, 2)]
    assert layout.non_terminal is None


def test_comments_and_gate_bodies_are_ignored():
    layout = parse_measurement_layout(
        H + "gate g(t) x, y { cx x, y; u3(t, sin(t), 0) y; }\n"
        "qreg q[2]; creg c[2];\n// measure q[0] -> c[1];\n/* h q[0]; */\n"
        "g(pi/2) q[0], q[1];\nmeasure q[0] -> c[0];\nbarrier q;\n")
    assert layout.measures == [(0, 0)]
    assert layout.non_terminal is None


@pytest.mark.parametrize("body, reason", [
    ("qreg q[1]; creg c[2]; h q[0]; measure q[0]->c[0]; h q[0]; measure q[0]->c[1];", "'h'"),
    ("qreg q[2]; creg c[1]; measure q[0]->c[0]; cx q[0],q[1];", "'cx'"),
    ("qreg q[2]; creg c[1]; measure q[0]->c[0]; cx q,q;", "'cx'"),
    ("qreg q[1]; creg c[1]; x q[0]; reset q[0]; measure q[0]->c[0];", "reset"),
    ("qreg q[2]; creg c[1]; measure q[0]->c[0]; if(c==1) x q[1];", "'if'"),
])
def test_non_terminal_constructs_are_flagged(body, reason):
    layout = parse_measurement_layout(H + body)
    assert layout.non_terminal is not None and reason in layout.non_terminal
    with pytest.raises(ValueError, match=MID_CIRCUIT_ERROR):
        layout.require_terminal()


@pytest.mark.parametrize("body", [
    "qreg q[2]; creg c[2]; h q[0]; measure q[0]->c[0]; x q[1]; measure q[1]->c[1];",
    "qreg q[2]; creg c[2]; measure q[0]->c[0]; barrier q; measure q[0]->c[1];",
    "qreg q[2]; creg c[2]; h q[0]; measure q -> c;",
])
def test_terminal_measurements_are_not_flagged(body):
    assert parse_measurement_layout(H + body).non_terminal is None


def test_key_order_labels():
    layout = parse_measurement_layout(ASYMMETRIC)
    assert layout.key([1, 0], "lsb") == "01"
    assert layout.key([1, 0], "msb") == "10"


@pytest.mark.parametrize("qasm, qubit_state, expected", [
    (SUBSET, (1, 0, 1), {"lsb": "1", "msb": "1"}),
    (SUBSET, (0, 0, 1), {"lsb": "0", "msb": "0"}),
    (SWAPPED, (1, 0, 0, 1), {"lsb": "11", "msb": "11"}),
    (ASYMMETRIC, (1, 0), {"lsb": "01", "msb": "10"}),
])
def test_qubit_samples_map_to_classical_keys(qasm, qubit_state, expected):
    layout = parse_measurement_layout(qasm)
    samples = np.full(5, _msb_index(qubit_state))
    for order, key in expected.items():
        counts = layout.counts_from_qubit_samples(samples, layout.qubit_positions("msb"), order)
        assert counts == {key: 5}


def test_lsb_backend_index_and_reordered_backend_qubits():
    layout = parse_measurement_layout(
        H + "qreg m[1]; qreg a[2]; creg c[3]; x m[0]; measure m[0]->c[0]; "
        "measure a[0]->c[1]; measure a[1]->c[2];")
    # A backend ordering registers alphabetically (a[0], a[1], m[0]), qubit 0 least significant.
    backend = [("a", 0), ("a", 1), ("m", 0)]
    index = 1 << 2
    positions = layout.qubit_positions("lsb", backend)
    assert layout.counts_from_qubit_counts({index: 7}, positions, "msb") == {"100": 7}
    assert layout.counts_from_qubit_counts({index: 7}, positions, "lsb") == {"001": 7}


def test_unmeasured_classical_bits_read_zero():
    layout = parse_measurement_layout(
        H + "qreg q[2]; creg c[2]; creg d[1]; x q[0]; x q[1]; measure q[0]->c[0];")
    counts = layout.counts_from_qubit_counts({0b11: 3}, layout.qubit_positions("msb"), "msb")
    assert counts == {"100": 3}


def test_last_measurement_into_a_clbit_wins():
    layout = parse_measurement_layout(
        H + "qreg q[2]; creg c[2]; x q[1]; measure q[0]->c[0]; measure q[1]->c[0];")
    counts = layout.counts_from_qubit_counts({0b01: 4}, layout.qubit_positions("msb"), "lsb")
    assert counts == {"01": 4}


def test_aer_register_keys():
    assert named_bits_from_register_key("1 01", [("a", 2), ("b", 1)]) == {
        ("a", 0): 1, ("a", 1): 0, ("b", 0): 1}
    layout = parse_measurement_layout(
        H + "qreg q[2]; creg b[1]; creg a[1]; measure q[0]->b[0]; measure q[1]->a[0];")
    # Aer through pytket sees registers alphabetically: [a, b], so its key is "b a".
    counts = counts_from_register_keys(layout, {"1 0": 9}, [("a", 1), ("b", 1)], "lsb")
    assert counts == {"01": 9}


def test_strip_and_prepare():
    qasm, notes = prepare_statevector_qasm(ASYMMETRIC)
    assert "measure" not in qasm and notes
    assert prepare_statevector_qasm(H + "qreg q[1]; h q[0];") == (H + "qreg q[1]; h q[0];", [])
    with pytest.raises(ValueError, match=STATEVECTOR_TERMINAL_ERROR):
        prepare_statevector_qasm(MID_CIRCUIT)
    with pytest.raises(ValueError, match=MID_CIRCUIT_ERROR):
        prepare_final_state_sampling(MID_CIRCUIT)
    stripped, layout, _ = prepare_final_state_sampling(SWAPPED)
    assert "measure" not in stripped and "creg c[2]" in stripped and layout.n_clbits == 2
    assert "measure" not in strip_measurements(H + "qreg q[1]; creg c[1]; measure q -> c;")


def test_circuit_without_measurements_reads_every_qubit():
    _, layout, _ = prepare_final_state_sampling(H + "qreg a[1]; qreg b[2]; x b[1];")
    counts = layout.counts_from_qubit_counts({0b001: 2}, layout.qubit_positions("msb"), "msb")
    assert counts == {"001": 2}


def test_unordered_qreg_note_only_when_order_changes():
    assert unordered_qreg_note(parse_measurement_layout(H + "qreg a[1]; qreg b[1];")) is None
    assert "alphabetically" in unordered_qreg_note(
        parse_measurement_layout(H + "qreg b[1]; qreg a[1];"))


_RUNNERS = Path(__file__).resolve().parents[3] / "runners"


@pytest.mark.skipif(not _RUNNERS.exists(), reason="runner sources not present")
def test_every_runner_keys_counts_over_classical_bits():
    """Each runner's measured path goes through the classical-bit layout."""
    markers = re.compile(r"parse_measurement_layout|prepare_final_state_sampling")
    missing = [p.parent.name for p in sorted(_RUNNERS.glob("*/main.py"))
               if not markers.search(p.read_text())]
    assert not missing, f"runners not keying counts over classical bits: {missing}"


def test_api_round_trip_keeps_register_declaration_order():
    from services.circuit_resolver import prepare_measured_dispatch, prepare_statevector_dispatch
    qasm = H + ("qreg r[1]; qreg b[1]; creg w[2]; creg a[1]; x b[0]; "
                "measure r[0] -> w[1]; measure b[0] -> a[0];")
    original = parse_measurement_layout(qasm).clbits
    for group in ("measured_native", "measured_sampled"):
        sent = prepare_measured_dispatch(qasm, True)[group]["qasm"]
        assert parse_measurement_layout(sent).clbits == original
    sent = prepare_statevector_dispatch(qasm, True)["qasm"]
    assert [n for n, _ in parse_measurement_layout(sent).cregs] == ["w", "a"]


def test_restore_register_order_leaves_mismatched_declarations_alone():
    from services.circuit_resolver import _restore_register_order
    emitted = "qreg q[1];\ncreg a[1];\ncreg b[1];\n"
    assert _restore_register_order(emitted, H + "qreg q[1]; creg b[1]; creg a[1];") == (
        "qreg q[1];\ncreg b[1];\ncreg a[1];\n")
    assert _restore_register_order(emitted, H + "qreg q[1]; creg b[1];") == emitted
