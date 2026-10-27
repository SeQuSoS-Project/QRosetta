"""The self-test's numpy reference against states computed by hand, and its refusals."""
import math

import numpy as np
import pytest

from services.selftest import reference

HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
R = 1 / math.sqrt(2)


def _sv(body: str) -> np.ndarray:
    return reference.statevector(HEADER + body)


def _basis(n: int, index: int) -> np.ndarray:
    state = np.zeros(2 ** n, dtype=complex)
    state[index] = 1
    return state


@pytest.mark.parametrize("body,expected", [
    ("qreg q[3];", _basis(3, 0)),
    ("qreg q[3]; x q[0];", _basis(3, 0b001)),
    ("qreg q[3]; x q[2];", _basis(3, 0b100)),
    ("qreg q[2]; x q[0]; cx q[0],q[1];", _basis(2, 0b11)),
    ("qreg q[2]; x q[1]; cx q[0],q[1];", _basis(2, 0b10)),
    ("qreg q[2]; x q[1]; cx q[1],q[0];", _basis(2, 0b11)),
    ("qreg q[3]; x q[2]; cx q[2],q[0];", _basis(3, 0b101)),
    ("qreg q[1]; h q[0];", np.array([R, R])),
    ("qreg q[1]; x q[0]; h q[0];", np.array([R, -R])),
    ("qreg q[2]; h q[1];", np.array([R, 0, R, 0])),
    ("qreg q[2]; h q[0]; cx q[0],q[1];", np.array([R, 0, 0, R])),
    ("qreg q[3]; h q[0]; cx q[0],q[1]; cx q[1],q[2];", np.array([R, 0, 0, 0, 0, 0, 0, R])),
    ("qreg a[1]; qreg b[2]; x b[0];", _basis(3, 0b010)),
])
def test_hand_computed_states(body, expected):
    np.testing.assert_allclose(_sv(body), expected, atol=1e-15)


def test_ry_and_rz_follow_the_qelib1_matrices():
    theta, phi = 0.37, 1.23
    np.testing.assert_allclose(_sv(f"qreg q[1]; ry({theta}) q[0];"),
                               [math.cos(theta / 2), math.sin(theta / 2)], atol=1e-15)
    np.testing.assert_allclose(_sv(f"qreg q[1]; h q[0]; rz({phi}) q[0];"),
                               [R, R * complex(math.cos(phi), math.sin(phi))], atol=1e-15)
    np.testing.assert_allclose(_sv(f"qreg q[2]; ry({theta}) q[1];"),
                               [math.cos(theta / 2), 0, math.sin(theta / 2), 0], atol=1e-15)


def test_ry_cx_chain_matches_a_basis_state_sum():
    """A product of ry states through cx q0,q1; cx q1,q2 and rz on q2, built here by
    enumerating input basis states instead of tensor contractions."""
    a, b, c, phi = 0.3, 0.7, 1.1, 0.5
    single = [(math.cos(t / 2), math.sin(t / 2)) for t in (a, b, c)]
    expected = np.zeros(8, dtype=complex)
    for b0 in (0, 1):
        for b1 in (0, 1):
            for b2 in (0, 1):
                amp = single[0][b0] * single[1][b1] * single[2][b2]
                o1 = b1 ^ b0
                o2 = b2 ^ o1
                phase = complex(math.cos(phi), math.sin(phi)) if o2 else 1
                expected[b0 | (o1 << 1) | (o2 << 2)] += amp * phase
    got = _sv(f"qreg q[3]; ry({a}) q[0]; ry({b}) q[1]; ry({c}) q[2]; "
              f"cx q[0],q[1]; cx q[1],q[2]; rz({phi}) q[2];")
    np.testing.assert_allclose(got, expected, atol=1e-15)


def test_msb_is_the_bit_reversed_index():
    lsb = _sv("qreg q[3]; x q[0];")
    assert np.argmax(np.abs(reference.to_msb(lsb))) == 0b100


@pytest.mark.parametrize("body,key", [
    ("qreg q[3]; creg c[3]; x q[0]; measure q[0] -> c[0]; measure q[1] -> c[1]; measure q[2] -> c[2];", "001"),
    ("qreg q[2]; creg b[1]; creg a[1]; x q[0]; measure q[0] -> b[0]; measure q[1] -> a[0];", "01"),
    ("qreg q[2]; creg a[2]; creg b[1]; x q[1]; measure q[0] -> a[0]; measure q[1] -> b[0];", "100"),
    ("qreg q[2]; creg c[2]; measure q[1] -> c[1]; x q[0]; measure q[0] -> c[0];", "01"),
])
def test_deterministic_counts_keys(body, key):
    assert reference.deterministic_counts_key(HEADER + body) == {"lsb": key, "msb": key[::-1]}


@pytest.mark.parametrize("body", [
    "qreg q[2]; cu1(0.1) q[0],q[1];",
    "qreg q[1]; rz(pi/2) q[0];",
    "qreg q[1]; x q[1];",
    "qreg q[2]; cx q[0],q[0];",
    "qreg q[1]; creg c[1]; measure q[0] -> c[0]; x q[0];",
    "qreg q[1]; reset q[0];",
    "creg c[1];",
])
def test_refuses_what_it_does_not_model(body):
    with pytest.raises(reference.ReferenceError):
        reference.statevector(HEADER + body)


def test_counts_key_needs_a_single_basis_state():
    with pytest.raises(reference.ReferenceError):
        reference.deterministic_counts_key(HEADER + "qreg q[1]; creg c[1]; h q[0]; measure q[0] -> c[0];")


def test_fidelity_normalises_and_ignores_global_phase():
    state = np.array([0.6, 0.8j])
    assert reference.fidelity(state, 2 * np.exp(0.4j) * state) == pytest.approx(1.0, abs=1e-15)
    assert reference.fidelity(np.array([1, 0]), np.array([0, 1])) == 0.0
