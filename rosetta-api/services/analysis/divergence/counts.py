# Counts primitives: validation, normalisation, bit-order transforms, distances.

from itertools import permutations

import numpy as np
from scipy.spatial.distance import jensenshannon

from .common import MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS


def _counts_invalid_reason(counts):
    """Return a not-comparable reason for malformed counts, else None.

    Guards against inputs that would otherwise inject non-finite values (NaN/Inf)
    into the report or be silently coerced toward agreement — empty counts,
    non-string/empty bitstring keys, or values that are non-numeric, non-finite,
    or negative. Malformed counts are reported as explicit not-comparable evidence
    rather than repaired.
    """
    if not counts:
        return "empty_counts"
    for key, value in counts.items():
        if not isinstance(key, str) or not key:
            return "invalid_bitstring_key"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "noninteger_counts"
        if not np.isfinite(numeric):
            return "nonfinite_counts"
        if numeric < 0:
            return "negative_counts"
    return None


def _normalize_counts(counts, n_shots):
    """Converts a {bitstring: count} dict to a {bitstring: prob} dict."""
    if n_shots == 0:
        return {}
    return {k: v / n_shots for k, v in counts.items()}


def _bit_reversed_counts(counts):
    """Return counts with each bitstring key reversed, aggregating collisions."""
    reversed_counts = {}
    for bitstring, count in counts.items():
        reversed_key = bitstring[::-1]
        reversed_counts[reversed_key] = reversed_counts.get(reversed_key, 0) + count
    return reversed_counts


def _counts_bit_length(counts):
    lengths = {len(bitstring) for bitstring in counts}
    if len(lengths) != 1:
        return None
    return lengths.pop()


def _permute_counts(counts, permutation):
    permuted_counts = {}
    for bitstring, count in counts.items():
        permuted_key = "".join(bitstring[source] for source in permutation)
        permuted_counts[permuted_key] = permuted_counts.get(permuted_key, 0) + count
    return permuted_counts


def _best_counts_qubit_permutation_metrics(counts_i, counts_j, n_shots, js_threshold, hellinger_threshold):
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
        outcomes = sorted(set(counts_i.keys()) | set(permuted_counts_j.keys()))
        pv_i = _counts_probability_vector(counts_i, outcomes, n_shots)
        pv_j = _counts_probability_vector(permuted_counts_j, outcomes, n_shots)
        js_div, h_dist = _counts_distance_metrics(pv_i, pv_j)
        score = js_div + h_dist
        if score < best_score:
            best_score = score
            best.update({
                "permutation": list(permutation),
                "js_divergence": js_div,
                "hellinger_distance": h_dist,
            })
        if js_div <= js_threshold and h_dist <= hellinger_threshold:
            break
    return best


def _counts_probability_vector(counts, outcomes, n_shots):
    probabilities = np.zeros(len(outcomes))
    normalized = _normalize_counts(counts, n_shots)
    for index, bitstring in enumerate(outcomes):
        probabilities[index] = normalized.get(bitstring, 0.0)
    return probabilities


def _counts_distance_metrics(pv_i, pv_j):
    js_div = (jensenshannon(pv_i, pv_j))**2
    if np.isnan(js_div):
        js_div = 0.0

    h_dist = calculate_hellinger_distance(pv_i, pv_j)
    if np.isnan(h_dist):
        h_dist = 0.0

    return js_div, h_dist


def calculate_hellinger_distance(p, q):
    """
    Calculates the Hellinger distance between two probability distributions.
    """
    return np.linalg.norm(np.sqrt(p) - np.sqrt(q)) / np.sqrt(2)
