"""Tests for the stdlib-only QASM gate-count/depth metric."""

from qrosetta_commons.helpers import count_qasm_gates_and_depth


def test_empty_circuit():
    assert count_qasm_gates_and_depth("") == (0, 0)


def test_bell_state_chained_depth():
    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
"""
    assert count_qasm_gates_and_depth(qasm) == (2, 2)


def test_parallel_gates_share_a_layer():
    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
h q[1];
"""
    assert count_qasm_gates_and_depth(qasm) == (2, 1)


def test_ghz_chain_depth_grows_with_length():
    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
"""
    assert count_qasm_gates_and_depth(qasm) == (3, 3)


def test_barrier_measure_creg_qreg_are_not_gates():
    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
barrier q[0],q[1];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""
    assert count_qasm_gates_and_depth(qasm) == (2, 2)


def test_comments_are_ignored():
    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
// h q[0]; this comment must not be counted
h q[0]; // trailing comment
"""
    assert count_qasm_gates_and_depth(qasm) == (1, 1)


def test_gate_definition_bodies_are_not_counted():
    qasm = """OPENQASM 2.0;
include "qelib1.inc";
gate bell a,b { h a; cx a,b; }
qreg q[2];
bell q[0],q[1];
"""
    gate_count, depth = count_qasm_gates_and_depth(qasm)
    assert gate_count == 1
    assert depth == 1
