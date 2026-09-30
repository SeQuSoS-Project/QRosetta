"""Statevector primitives: parsing, validation, normalisation, and bit-order transforms."""

from itertools import permutations

import numpy as np
from qrosetta_commons.helpers import decode_statevector

from .common import MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS


def parse_statevector(sv_data):
    """Convert a statevector (Base64 string or list) into a numpy array."""
    if sv_data is None:
        return np.array([])

    if isinstance(sv_data, str):
        return decode_statevector(sv_data)
    elif isinstance(sv_data, list):
        if not sv_data:
            return np.array([])
        return np.array([complex(s) for s in sv_data])
    else:
        raise ValueError(f"Unknown statevector format: {type(sv_data)}")


def _statevector_invalid_reason(sv):
    """Return a not-comparable reason for an empty, non-finite or zero-norm vector, else None."""
    if sv.size == 0:
        return "empty_statevector"
    if not np.all(np.isfinite(sv)):
        return "nonfinite_statevector"
    if np.linalg.norm(sv) == 0:
        return "zero_norm_statevector"
    return None


def _normalize_statevector(sv):
    """Return (sv / ||sv||, ||sv||)."""
    norm = np.linalg.norm(sv)
    return sv / norm, norm


def _statevector_inner_metrics(sv_i_norm, sv_j_norm, fidelity_tolerance, phase_tolerance):
    """Return (fidelity, global phase offset arg<i|j>) of two normalised vectors.

    Fidelity is |<i|j>|^2 clamped to [0, 1]; it is never rounded toward 1. A phase offset
    within ``phase_tolerance`` of 0 is reported as 0. ``fidelity_tolerance`` is accepted for
    signature compatibility and does not alter the returned fidelity.
    """
    inner_product = np.dot(np.conjugate(sv_i_norm), sv_j_norm)
    fidelity = float(min(max(np.abs(inner_product) ** 2, 0.0), 1.0))
    relative_phase = float(np.angle(inner_product))

    if abs(relative_phase) <= phase_tolerance:
        relative_phase = 0.0

    return fidelity, relative_phase


def _statevector_qubit_count(sv):
    """Return log2(len(sv)); raise ValueError if the length is not a power of two."""
    size = len(sv)
    if size == 0 or size & (size - 1):
        raise ValueError(f"statevector length {size} is not a power of two")
    return int(np.log2(size))


def _permute_statevector(sv, permutation):
    """Return sv with computational-basis bit positions permuted.

    The 2^n amplitudes are viewed as an n-dimensional array indexed by the bits (axis 0 is
    the most significant), and permuting bit positions is transposing those axes.
    """
    n_qubits = _statevector_qubit_count(sv)
    return np.asarray(sv).reshape([2] * n_qubits).transpose(permutation).reshape(-1)


def _bit_reversed_statevector(sv):
    """Return a copy of sv with computational-basis index bits reversed."""
    n_qubits = _statevector_qubit_count(sv)
    return _permute_statevector(sv, tuple(reversed(range(n_qubits))))


def _best_statevector_qubit_permutation_metrics(sv_i_norm, sv_j_norm, fidelity_tolerance, phase_tolerance):
    """Search every non-identity, non-reversal qubit permutation for the highest fidelity.

    Ties keep the lexicographically first permutation. Above the qubit cap the search is
    not attempted and the result says so.
    """
    n_qubits = _statevector_qubit_count(sv_j_norm)
    if n_qubits > MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS:
        return {
            "attempted": False,
            "reason": "too_many_qubits",
            "n_qubits": n_qubits,
            "max_qubits": MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS,
            "permutation": None,
            "fidelity": None,
            "relative_phase": None,
        }

    identity = tuple(range(n_qubits))
    bit_reversal = tuple(reversed(range(n_qubits)))
    best = {
        "attempted": True,
        "reason": None,
        "n_qubits": n_qubits,
        "max_qubits": MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS,
        "permutation": None,
        "fidelity": -1.0,
        "relative_phase": 0.0,
    }
    for permutation in permutations(range(n_qubits)):
        if permutation in (identity, bit_reversal):
            continue
        permuted = _permute_statevector(sv_j_norm, permutation)
        fidelity, relative_phase = _statevector_inner_metrics(
            sv_i_norm, permuted, fidelity_tolerance, phase_tolerance
        )
        if fidelity > best["fidelity"]:
            best.update({
                "permutation": list(permutation),
                "fidelity": fidelity,
                "relative_phase": relative_phase,
            })
    if best["permutation"] is None:
        best.update({"fidelity": None, "relative_phase": None})
    return best
