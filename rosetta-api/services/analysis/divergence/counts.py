"""Counts primitives: validation, normalisation, bit-order transforms, and distances.

Distributions are normalised by each backend's observed total, sum(counts). The
Jensen-Shannon divergence is the squared scipy Jensen-Shannon distance with the natural
logarithm, so it is in nats and bounded by ln 2.
"""

import numbers
import re
from functools import cache
from itertools import permutations

import numpy as np
from scipy.spatial.distance import jensenshannon

from .common import MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS

_BINARY_KEY = re.compile(r"[01]+")


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


@cache
def _key_permutation_table(n_bits):
    """Return (permutations, table) for every non-identity, non-reversal key permutation.

    Permutations are in ``itertools.permutations`` order. ``table[r, x]`` is the integer
    value of key ``x`` (first character most significant) after ``_permute_counts`` with
    permutation ``r``.
    """
    identity = tuple(range(n_bits))
    bit_reversal = tuple(reversed(range(n_bits)))
    perms = [p for p in permutations(range(n_bits)) if p not in (identity, bit_reversal)]
    keys = np.arange(2 ** n_bits)
    shifts = n_bits - 1 - np.arange(n_bits)
    bits = (keys[None, :] >> shifts[:, None]) & 1
    table = np.zeros((len(perms), 2 ** n_bits), dtype=np.intp)
    if perms:
        sources = np.array(perms)
        for position in range(n_bits):
            table += bits[sources[:, position]] << shifts[position]
    table.setflags(write=False)
    return perms, table


def _dense_probabilities(counts, n_bits):
    """Return (probabilities, present) over all 2^n keys, normalised as ``_normalize_counts``."""
    probabilities = np.zeros(2 ** n_bits)
    present = np.zeros(2 ** n_bits, dtype=bool)
    for bitstring, probability in _normalize_counts(counts).items():
        index = int(bitstring, 2)
        probabilities[index] = probability
        present[index] = True
    for bitstring in counts:
        present[int(bitstring, 2)] = True
    return probabilities, present


def _permutation_scores(counts_i, counts_j, n_bits):
    """Return (js, hellinger) arrays, one entry per row of ``_key_permutation_table``.

    Each entry is computed on the same vectors, in the same operation order, as
    ``_counts_distance_metrics`` on the sorted outcome union of that permutation, so the
    values are identical to the per-permutation loop.
    """
    _, table = _key_permutation_table(n_bits)
    n_rows = table.shape[0]
    dense_i, present_i = _dense_probabilities(counts_i, n_bits)
    dense_j, present_j = _dense_probabilities(counts_j, n_bits)
    permuted_j = np.zeros(table.shape)
    permuted_present_j = np.zeros(table.shape, dtype=bool)
    np.put_along_axis(permuted_j, table, np.broadcast_to(dense_j, table.shape), axis=1)
    np.put_along_axis(permuted_present_j, table, np.broadcast_to(present_j, table.shape), axis=1)
    union = present_i[None, :] | permuted_present_j
    sizes = union.sum(axis=1)
    js = np.empty(n_rows)
    hellinger = np.empty(n_rows)
    for size in np.unique(sizes):
        rows = np.flatnonzero(sizes == size)
        mask = union[rows]
        pv_i = np.broadcast_to(dense_i, mask.shape)[mask].reshape(len(rows), size)
        pv_j = permuted_j[rows][mask].reshape(len(rows), size)
        js[rows] = [distance ** 2 for distance in jensenshannon(pv_i, pv_j, axis=1)]
        difference = np.sqrt(pv_i) - np.sqrt(pv_j)
        hellinger[rows] = [_norm(row.copy()) / np.sqrt(2) for row in difference]
    return js, hellinger


def _norm(vector):
    """Return ``np.linalg.norm(vector)`` for a 1-D float vector by the same BLAS dot."""
    return np.sqrt(vector.dot(vector))


def _best_counts_qubit_permutation_metrics(counts_i, counts_j):
    """Search every non-identity, non-reversal key permutation for the lowest JS + Hellinger.

    The whole search space is scanned; ties keep the lexicographically first permutation.
    Permutations whose metrics are not finite are skipped. Keys made of 0 and 1 only are
    scored in one array pass; other keys go through the per-permutation loop.
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
    if all(_BINARY_KEY.fullmatch(key) for key in (*counts_i, *counts_j)):
        perms, _ = _key_permutation_table(n_qubits_i)
        if not perms:
            return best
        js, hellinger = _permutation_scores(counts_i, counts_j, n_qubits_i)
        scores = js + hellinger
        finite = np.isfinite(scores)
        if finite.any():
            row = int(np.argmin(np.where(finite, scores, np.inf)))
            best.update({
                "permutation": list(perms[row]),
                "js_divergence": float(js[row]),
                "hellinger_distance": float(hellinger[row]),
            })
        return best

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
    lookup = _normalize_counts(counts).get
    return np.fromiter((lookup(bitstring, 0.0) for bitstring in outcomes), dtype=float, count=len(outcomes))


def _counts_distance_metrics(pv_i, pv_j):
    """Return (JS divergence in nats, Hellinger distance); either may be NaN."""
    js_div = float(jensenshannon(pv_i, pv_j) ** 2)
    h_dist = float(calculate_hellinger_distance(pv_i, pv_j))
    return js_div, h_dist


def calculate_hellinger_distance(p, q):
    """Return the Hellinger distance between two probability vectors."""
    return np.linalg.norm(np.sqrt(p) - np.sqrt(q)) / np.sqrt(2)
