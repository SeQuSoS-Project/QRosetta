"""Counts primitives: validation, normalisation, bit-order transforms, and distances.

Distributions are normalised by each backend's observed total, sum(counts). The
Jensen-Shannon divergence is the squared scipy Jensen-Shannon distance with the natural
logarithm, so it is in nats and bounded by ln 2.
"""

import numbers
from itertools import permutations

import numpy as np
from scipy.spatial.distance import jensenshannon

from .common import MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS


def _counts_invalid_reason(counts):
    """Return a not-comparable reason for malformed counts, else None.

    Rejects empty counts, non-string or empty keys, values that are not real numbers
    (strings and booleans included), non-finite or negative values, and a total <= 0.
    """
    if not counts:
        return "empty_counts"
    total = 0.0
    for key, value in counts.items():
        if not isinstance(key, str) or not key:
            return "invalid_bitstring_key"
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            return "non_numeric_counts"
        numeric = float(value)
        if not np.isfinite(numeric):
            return "nonfinite_counts"
        if numeric < 0:
            return "negative_counts"
        total += numeric
    if total <= 0:
        return "zero_total_counts"
    return None


def _counts_total(counts):
    """Return sum(counts.values()) as a float."""
    return float(sum(counts.values()))


def _normalize_counts(counts):
    """Convert a {bitstring: count} dict to {bitstring: probability} by its observed total."""
    total = _counts_total(counts)
    if total <= 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def _bit_reversed_counts(counts):
    """Return counts with each bitstring key reversed, aggregating collisions."""
    reversed_counts = {}
    for bitstring, count in counts.items():
        reversed_key = bitstring[::-1]
        reversed_counts[reversed_key] = reversed_counts.get(reversed_key, 0) + count
    return reversed_counts


def _counts_bit_length(counts):
    """Return the common bitstring length, or None if keys have different lengths."""
    lengths = {len(bitstring) for bitstring in counts}
    if len(lengths) != 1:
        return None
    return lengths.pop()


def _permute_counts(counts, permutation):
    """Return counts with bit positions of every key gathered through ``permutation``."""
    permuted_counts = {}
    for bitstring, count in counts.items():
        permuted_key = "".join(bitstring[source] for source in permutation)
        permuted_counts[permuted_key] = permuted_counts.get(permuted_key, 0) + count
    return permuted_counts


def _best_counts_qubit_permutation_metrics(counts_i, counts_j):
    """Search every non-identity, non-reversal key permutation for the lowest JS + Hellinger.

    The whole search space is scanned; ties keep the lexicographically first permutation.
    Permutations whose metrics are not finite are skipped.
    """
    n_qubits_i = _counts_bit_length(counts_i)
    n_qubits_j = _counts_bit_length(counts_j)
    if n_qubits_i is None or n_qubits_j is None or n_qubits_i != n_qubits_j:
        return {
            "attempted": False,
            "reason": "inconsistent_bitstring_lengths",
            "n_qubits": None,
            "max_qubits": MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS,
            "permutation": None,
            "js_divergence": None,
            "hellinger_distance": None,
        }
    if n_qubits_i > MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS:
        return {
            "attempted": False,
            "reason": "too_many_qubits",
            "n_qubits": n_qubits_i,
            "max_qubits": MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS,
            "permutation": None,
            "js_divergence": None,
            "hellinger_distance": None,
        }

    identity = tuple(range(n_qubits_i))
    bit_reversal = tuple(reversed(range(n_qubits_i)))
    best = {
        "attempted": True,
        "reason": None,
        "n_qubits": n_qubits_i,
        "max_qubits": MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS,
        "permutation": None,
        "js_divergence": None,
        "hellinger_distance": None,
    }
    best_score = float("inf")
    for permutation in permutations(range(n_qubits_i)):
        if permutation in (identity, bit_reversal):
            continue
        permuted_counts_j = _permute_counts(counts_j, permutation)
        outcomes = sorted(set(counts_i) | set(permuted_counts_j))
        pv_i = _counts_probability_vector(counts_i, outcomes)
        pv_j = _counts_probability_vector(permuted_counts_j, outcomes)
        js_div, h_dist = _counts_distance_metrics(pv_i, pv_j)
        score = js_div + h_dist
        if np.isfinite(score) and score < best_score:
            best_score = score
            best.update({
                "permutation": list(permutation),
                "js_divergence": js_div,
                "hellinger_distance": h_dist,
            })
    return best


def _counts_probability_vector(counts, outcomes):
    """Return the probability of each outcome in ``outcomes``, normalised by sum(counts)."""
    probabilities = np.zeros(len(outcomes))
    normalized = _normalize_counts(counts)
    for index, bitstring in enumerate(outcomes):
        probabilities[index] = normalized.get(bitstring, 0.0)
    return probabilities


def _counts_distance_metrics(pv_i, pv_j):
    """Return (JS divergence in nats, Hellinger distance); either may be NaN."""
    js_div = float(jensenshannon(pv_i, pv_j) ** 2)
    h_dist = float(calculate_hellinger_distance(pv_i, pv_j))
    return js_div, h_dist


def calculate_hellinger_distance(p, q):
    """Return the Hellinger distance between two probability vectors."""
    return np.linalg.norm(np.sqrt(p) - np.sqrt(q)) / np.sqrt(2)
