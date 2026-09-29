"""Checks the transpose form of _permute_statevector against a per-amplitude reference.

An inverted axis order would not crash but would report the wrong permutation in the
pairwise agreement taxonomy, so the two forms are compared exhaustively for n = 1..6.
"""
from itertools import permutations

import numpy as np
import pytest

from services.analysis.divergence import _permute_statevector


def _reference_permute(sv, permutation):
    """Per-amplitude scatter: gather each index's bits through the permutation."""
    n_qubits = int(np.log2(len(sv)))
    out = np.empty_like(sv)
    for index, amplitude in enumerate(sv):
        bits = format(index, f"0{n_qubits}b")
        permuted_bits = "".join(bits[source] for source in permutation)
        out[int(permuted_bits, 2)] = amplitude
    return out


@pytest.mark.parametrize("n_qubits", [1, 2, 3, 4, 5, 6])
def test_matches_reference_for_every_permutation(n_qubits):
    rng = np.random.default_rng(1234 + n_qubits)
    size = 2 ** n_qubits
    sv = (rng.normal(size=size) + 1j * rng.normal(size=size)).astype(np.complex128)

    for permutation in permutations(range(n_qubits)):
        expected = _reference_permute(sv, permutation)
        actual = _permute_statevector(sv, permutation)
        assert np.array_equal(actual, expected), f"n={n_qubits} permutation={permutation}"


def test_identity_permutation_is_a_no_op():
    sv = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.complex128)
    assert np.array_equal(_permute_statevector(sv, (0, 1)), sv)


def test_permutation_preserves_norm_and_multiset_of_amplitudes():
    rng = np.random.default_rng(7)
    sv = (rng.normal(size=8) + 1j * rng.normal(size=8)).astype(np.complex128)
    permuted = _permute_statevector(sv, (2, 0, 1))
    assert np.isclose(np.linalg.norm(permuted), np.linalg.norm(sv))
    assert sorted(permuted.tolist(), key=lambda z: (z.real, z.imag)) == \
        sorted(sv.tolist(), key=lambda z: (z.real, z.imag))


def test_two_qubit_swap_moves_the_expected_basis_state():
    """|01> under a bit swap becomes |10>."""
    sv = np.zeros(4, dtype=np.complex128)
    sv[0b01] = 1.0
    permuted = _permute_statevector(sv, (1, 0))
    assert permuted[0b10] == 1.0
    assert permuted[0b01] == 0.0
