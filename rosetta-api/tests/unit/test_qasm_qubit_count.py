"""Unit tests for the shared qreg-counting helper and the runner-side qubit guard."""

import pytest

from qrosetta_commons.helpers import (
    check_qubits_limit,
    get_num_qubits_from_qasm,
    strip_qasm_comments,
)


def test_single_register():
    assert get_num_qubits_from_qasm("OPENQASM 2.0;\nqreg q[5];\n") == 5


def test_no_register_declared():
    assert get_num_qubits_from_qasm("OPENQASM 2.0;\n") == 0


def test_sums_multiple_registers():
    qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[9];\nqreg flag[1];\n'
    assert get_num_qubits_from_qasm(qasm) == 10


def test_sums_registers_declared_on_one_line():
    assert get_num_qubits_from_qasm("qreg a[2]; qreg b[3];") == 5


def test_tolerates_whitespace_in_declaration():
    assert get_num_qubits_from_qasm("qreg  q [ 7 ] ;") == 7


def test_ignores_commented_out_registers():
    qasm = "// qreg ghost[7];\n/* qreg other[9]; */\nqreg q[3];\n"
    assert get_num_qubits_from_qasm(qasm) == 3


def test_creg_is_not_counted():
    assert get_num_qubits_from_qasm("qreg q[4];\ncreg c[4];\n") == 4


def test_runner_guard_rejects_multi_register_circuit_over_limit():
    """Splitting a circuit across registers must not slip past the runner's cap."""
    qasm = "OPENQASM 2.0;\nqreg a[2];\nqreg b[28];\nh a[0];\n"
    with pytest.raises(ValueError, match="30 qubits"):
        check_qubits_limit(qasm, max_qubits=24)


def test_runner_guard_allows_multi_register_circuit_within_limit():
    check_qubits_limit("qreg q[6];\nqreg anc[4];\n", max_qubits=24)


def test_strip_qasm_comments_removes_both_comment_forms():
    assert strip_qasm_comments("a; // trailing\n/* block */b;").split() == ["a;", "b;"]
