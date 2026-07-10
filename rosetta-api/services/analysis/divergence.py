# Quantum state and performance analysis utilities.

from itertools import permutations

from qrosetta_commons.helpers import get_logger, decode_statevector
import numpy as np
from scipy.spatial.distance import jensenshannon
from scipy.stats import chi2 as _chi2_dist, chi2_contingency, ncx2
from scipy.optimize import brentq

logger = get_logger(__name__)

MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS = 6

# Parameters for the pairwise shot-noise statistical test.
STAT_TEST_ALPHA = 0.05          # significance level per pairwise test
STAT_TEST_TARGET_POWER = 0.8    # target power for the shot-budget recommendation
STAT_TEST_DELTA_TV = 0.05       # total-variation effect size the budget is sized to detect


def parse_statevector(sv_data):
    """Converts a statevector (Base64 string or list) into a numpy array."""
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


def _json_float(value):
    """Convert numpy scalar values to JSON-safe floats."""
    if value is None:
        return None
    return float(value)


def _statevector_invalid_reason(sv):
    """Return a not-comparable reason for a degenerate statevector, else None.

    Guards against inputs that would otherwise inject non-finite values (NaN/Inf)
    into the report — e.g. an empty vector, a vector containing NaN/Inf, or an
    all-zero vector whose normalization divides by zero. These are reported as
    explicit not-comparable evidence rather than silently normalized/repaired.
    """
    if sv.size == 0:
        return "empty_statevector"
    if not np.all(np.isfinite(sv)):
        return "nonfinite_statevector"
    if np.linalg.norm(sv) == 0:
        return "zero_norm_statevector"
    return None


def _normalize_statevector(sv):
    norm = np.linalg.norm(sv)
    return sv / norm, norm


def _statevector_inner_metrics(sv_i_norm, sv_j_norm, fidelity_tolerance, phase_tolerance):
    inner_product = np.dot(np.conjugate(sv_i_norm), sv_j_norm)
    fidelity = np.abs(inner_product)**2
    relative_phase = np.angle(inner_product)

    if np.isclose(fidelity, 1.0, atol=fidelity_tolerance):
        fidelity = 1.0
    if np.isclose(relative_phase, 0.0, atol=phase_tolerance):
        relative_phase = 0.0

    return fidelity, relative_phase


def _statevector_qubit_count(sv):
    size = len(sv)
    if size == 0 or size & (size - 1):
        raise ValueError(f"statevector length {size} is not a power of two")
    return int(np.log2(size))


def _permute_statevector(sv, permutation):
    """Return sv with computational-basis bit positions permuted."""
    n_qubits = _statevector_qubit_count(sv)
    permuted_sv = np.empty_like(sv)
    for index, amplitude in enumerate(sv):
        bits = format(index, f"0{n_qubits}b")
        permuted_bits = "".join(bits[source] for source in permutation)
        permuted_sv[int(permuted_bits, 2)] = amplitude
    return permuted_sv


def _bit_reversed_statevector(sv):
    """Return a copy of sv with computational-basis index bits reversed."""
    n_qubits = _statevector_qubit_count(sv)
    return _permute_statevector(sv, tuple(reversed(range(n_qubits))))


def _best_statevector_qubit_permutation_metrics(sv_i_norm, sv_j_norm, fidelity_tolerance, phase_tolerance):
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


def _pair_provenance(res_i, res_j, mode):
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    provenance = {
        "qubit_ordering": {
            sim_i: res_i.get("qubit_ordering"),
            sim_j: res_j.get("qubit_ordering"),
        },
        "sdk_versions": {
            sim_i: res_i.get("sdk_versions", {}),
            sim_j: res_j.get("sdk_versions", {}),
        },
        "preprocessing_applied": {
            sim_i: res_i.get("preprocessing_applied", []),
            sim_j: res_j.get("preprocessing_applied", []),
        },
    }
    if mode == "measured":
        provenance["seed"] = {
            sim_i: res_i.get("seed"),
            sim_j: res_j.get("seed"),
        }
        provenance["sampling_method"] = {
            sim_i: res_i.get("sampling_method"),
            sim_j: res_j.get("sampling_method"),
        }
    return provenance


def _run_status(res):
    return "error" if "error" in res else "completed"


def _statevector_not_comparable_record(res_i, res_j, reason, details=None):
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    return {
        "simulators": [sim_i, sim_j],
        "mode": "statevector",
        "run_status": {
            sim_i: _run_status(res_i),
            sim_j: _run_status(res_j),
        },
        "agreement": "not_comparable",
        "registered_transform": None,
        "transform_effect": None,
        "metrics": {
            "reason": reason,
            "details": details or {},
        },
        "provenance": _pair_provenance(res_i, res_j, "statevector"),
    }


def _classify_statevector_pair(
    res_i,
    res_j,
    fidelity,
    relative_phase,
    bit_reversed_fidelity,
    bit_reversed_relative_phase,
    qubit_permutation_metrics,
    norm_i,
    norm_j,
    is_cross_group,
    fidelity_tolerance,
    phase_tolerance,
):
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    phase_agrees = np.isclose(relative_phase, 0.0, atol=phase_tolerance)
    fidelity_agrees = fidelity >= (1.0 - fidelity_tolerance)
    bit_reversal_agrees = bit_reversed_fidelity >= (1.0 - fidelity_tolerance)
    qubit_permutation_fidelity = qubit_permutation_metrics.get("fidelity")
    qubit_permutation_agrees = (
        qubit_permutation_metrics.get("attempted")
        and qubit_permutation_fidelity is not None
        and qubit_permutation_fidelity >= (1.0 - fidelity_tolerance)
    )

    if fidelity_agrees and phase_agrees:
        agreement = "agree_directly"
        registered_transform = "identity"
        transform_effect = {
            "fidelity_delta": 0.0,
            "relative_phase_delta_rad": 0.0,
        }
    elif fidelity_agrees:
        agreement = "agree_up_to_global_phase"
        registered_transform = "global_phase_alignment"
        transform_effect = {
            "fidelity_delta": 0.0,
            "relative_phase_delta_rad": _json_float(-relative_phase),
            "relative_phase_after_alignment_rad": 0.0,
        }
    elif bit_reversal_agrees:
        agreement = "agree_after_bit_reversal"
        registered_transform = "bit_reversal"
        transform_effect = {
            "fidelity_delta": _json_float(bit_reversed_fidelity - fidelity),
            "fidelity_after_transform": _json_float(bit_reversed_fidelity),
            "relative_phase_after_transform_rad": _json_float(bit_reversed_relative_phase),
        }
    elif qubit_permutation_agrees:
        agreement = "agree_after_qubit_permutation"
        registered_transform = "qubit_permutation"
        transform_effect = {
            "permutation": qubit_permutation_metrics["permutation"],
            "fidelity_delta": _json_float(qubit_permutation_fidelity - fidelity),
            "fidelity_after_transform": _json_float(qubit_permutation_fidelity),
            "relative_phase_after_transform_rad": _json_float(
                qubit_permutation_metrics.get("relative_phase")
            ),
        }
    else:
        agreement = "residual_disagreement"
        registered_transform = None
        transform_effect = None

    return {
        "simulators": [sim_i, sim_j],
        "mode": "statevector",
        "run_status": {
            sim_i: _run_status(res_i),
            sim_j: _run_status(res_j),
        },
        "agreement": agreement,
        "registered_transform": registered_transform,
        "transform_effect": transform_effect,
        "metrics": {
            "direct_fidelity": _json_float(fidelity),
            "direct_relative_phase_rad": _json_float(relative_phase),
            "bit_reversed_fidelity": _json_float(bit_reversed_fidelity),
            "bit_reversed_relative_phase_rad": _json_float(bit_reversed_relative_phase),
            "qubit_permutation": {
                "attempted": bool(qubit_permutation_metrics.get("attempted")),
                "reason": qubit_permutation_metrics.get("reason"),
                "n_qubits": qubit_permutation_metrics.get("n_qubits"),
                "max_qubits": qubit_permutation_metrics.get("max_qubits"),
                "permutation": qubit_permutation_metrics.get("permutation"),
                "fidelity": _json_float(qubit_permutation_metrics.get("fidelity")),
                "relative_phase_rad": _json_float(
                    qubit_permutation_metrics.get("relative_phase")
                ),
            },
            "norms": {
                sim_i: _json_float(norm_i),
                sim_j: _json_float(norm_j),
            },
            "fidelity_tolerance": fidelity_tolerance,
            "phase_tolerance": phase_tolerance,
            "is_cross_group": bool(is_cross_group),
        },
        "provenance": _pair_provenance(res_i, res_j, "statevector"),
    }


def _counts_not_comparable_record(res_i, res_j, reason, details=None):
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    return {
        "simulators": [sim_i, sim_j],
        "mode": "measured",
        "run_status": {
            sim_i: _run_status(res_i),
            sim_j: _run_status(res_j),
        },
        "agreement": "not_comparable",
        "registered_transform": None,
        "transform_effect": None,
        "metrics": {
            "reason": reason,
            "details": details or {},
        },
        "provenance": _pair_provenance(res_i, res_j, "measured"),
    }


def _classify_counts_pair(
    res_i,
    res_j,
    js_div,
    h_dist,
    bit_reversed_js_div,
    bit_reversed_h_dist,
    qubit_permutation_metrics,
    is_cross_group,
    js_threshold,
    hellinger_threshold,
    n_shots,
):
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    direct_agrees = js_div <= js_threshold and h_dist <= hellinger_threshold
    bit_reversal_agrees = (
        bit_reversed_js_div <= js_threshold
        and bit_reversed_h_dist <= hellinger_threshold
    )
    qubit_permutation_js = qubit_permutation_metrics.get("js_divergence")
    qubit_permutation_h = qubit_permutation_metrics.get("hellinger_distance")
    qubit_permutation_agrees = (
        qubit_permutation_metrics.get("attempted")
        and qubit_permutation_js is not None
        and qubit_permutation_h is not None
        and qubit_permutation_js <= js_threshold
        and qubit_permutation_h <= hellinger_threshold
    )

    if direct_agrees:
        agreement = "distance_within_threshold"
        registered_transform = "identity_threshold_check"
        transform_effect = {
            "js_divergence_delta": 0.0,
            "hellinger_distance_delta": 0.0,
        }
    elif bit_reversal_agrees:
        agreement = "agree_after_bit_reversal"
        registered_transform = "bit_reversal"
        transform_effect = {
            "js_divergence_delta": _json_float(bit_reversed_js_div - js_div),
            "hellinger_distance_delta": _json_float(bit_reversed_h_dist - h_dist),
            "js_divergence_after_transform": _json_float(bit_reversed_js_div),
            "hellinger_distance_after_transform": _json_float(bit_reversed_h_dist),
        }
    elif qubit_permutation_agrees:
        agreement = "agree_after_qubit_permutation"
        registered_transform = "qubit_permutation"
        transform_effect = {
            "permutation": qubit_permutation_metrics["permutation"],
            "js_divergence_delta": _json_float(qubit_permutation_js - js_div),
            "hellinger_distance_delta": _json_float(qubit_permutation_h - h_dist),
            "js_divergence_after_transform": _json_float(qubit_permutation_js),
            "hellinger_distance_after_transform": _json_float(qubit_permutation_h),
        }
    else:
        agreement = "distance_exceeds_threshold"
        registered_transform = "identity_threshold_check"
        transform_effect = {
            "js_divergence_delta": 0.0,
            "hellinger_distance_delta": 0.0,
        }

    return {
        "simulators": [sim_i, sim_j],
        "mode": "measured",
        "run_status": {
            sim_i: _run_status(res_i),
            sim_j: _run_status(res_j),
        },
        "agreement": agreement,
        "registered_transform": registered_transform,
        "transform_effect": transform_effect,
        "metrics": {
            "js_divergence": _json_float(js_div),
            "hellinger_distance": _json_float(h_dist),
            "bit_reversed_js_divergence": _json_float(bit_reversed_js_div),
            "bit_reversed_hellinger_distance": _json_float(bit_reversed_h_dist),
            "qubit_permutation": {
                "attempted": bool(qubit_permutation_metrics.get("attempted")),
                "reason": qubit_permutation_metrics.get("reason"),
                "n_qubits": qubit_permutation_metrics.get("n_qubits"),
                "max_qubits": qubit_permutation_metrics.get("max_qubits"),
                "permutation": qubit_permutation_metrics.get("permutation"),
                "js_divergence": _json_float(qubit_permutation_metrics.get("js_divergence")),
                "hellinger_distance": _json_float(
                    qubit_permutation_metrics.get("hellinger_distance")
                ),
            },
            "js_threshold": js_threshold,
            "hellinger_threshold": hellinger_threshold,
            "n_shots": n_shots,
            "is_cross_group": bool(is_cross_group),
        },
        "provenance": _pair_provenance(res_i, res_j, "measured"),
    }


def create_divergence_report(results_list, thresholds=None):
    """
    Generates a full report including fidelity and phase.
    Optimized for memory: Parses statevectors ONLY when needed and compares sequentially.

    thresholds: optional dict overriding the agreement tolerances. Recognized keys:
    ``fidelity_tolerance`` and ``phase_tolerance`` (defaults = 1e-12, numerical-precision
    tolerances for exact — shot-noise-free — statevectors). Absent/None keeps the defaults.
    """
    import gc

    ordering_map = {}
    for res in results_list:
        if "error" not in res and "qubit_ordering" in res:
            ordering_map[res.get("simulator", "unknown")] = res["qubit_ordering"]
    lsb_sims = [s for s, o in ordering_map.items() if o == "lsb"]
    msb_sims = [s for s, o in ordering_map.items() if o == "msb"]
    qubit_ordering_warning = None
    if lsb_sims and msb_sims:
        qubit_ordering_warning = (
            f"Mixed qubit-ordering conventions detected. "
            f"LSB (qubit-0 = bit-0): {lsb_sims}. "
            f"MSB (qubit-0 = most-significant): {msb_sims}. "
            "Fidelity comparisons across groups may be misleading."
        )
        logger.warning(qubit_ordering_warning)

    valid_results = [res for res in results_list if "error" not in res and "statevector" in res]
    simulators = [res.get('simulator', 'unknown') for res in results_list]

    sim_to_valid_idx = {}
    for i, res in enumerate(valid_results):
        sim_to_valid_idx[res.get('simulator')] = i

    n_total = len(simulators)

    fidelity_matrix = np.full((n_total, n_total), -1.0)
    phase_matrix = np.zeros((n_total, n_total))

    divergences_found = []
    pairwise_agreement = []

    _t = thresholds or {}
    fidelity_tolerance = _t.get("fidelity_tolerance", 1e-12)
    phase_tolerance = _t.get("phase_tolerance", 1e-12)
    normalization_tolerance = 1e-9  # numerical only; not user-facing

    logger.info("Starting sequential divergence comparison...")

    for i in range(n_total):
        sim_i_name = simulators[i]
        res_i_raw = results_list[i]

        if sim_i_name not in sim_to_valid_idx:
            for j in range(i + 1, n_total):
                pairwise_agreement.append(
                    _statevector_not_comparable_record(
                        res_i_raw,
                        results_list[j],
                        "missing_statevector",
                    )
                )
            continue

        try:
            res_i = valid_results[sim_to_valid_idx[sim_i_name]]
            sv_i = parse_statevector(res_i["statevector"])

            invalid_reason_i = _statevector_invalid_reason(sv_i)
            if invalid_reason_i is not None:
                for j in range(i + 1, n_total):
                    pairwise_agreement.append(
                        _statevector_not_comparable_record(
                            res_i_raw,
                            results_list[j],
                            invalid_reason_i,
                            {sim_i_name: invalid_reason_i},
                        )
                    )
                continue

            sv_i_norm, norm_i = _normalize_statevector(sv_i)

            if not np.isclose(norm_i, 1.0, atol=normalization_tolerance):
                 divergences_found.append({
                    "type": "Normalization",
                    "simulator": sim_i_name,
                    "norm": float(norm_i)
                })

        except Exception as e:
            logger.error(f"Failed to load statevector for {sim_i_name}: {e}")
            for j in range(i + 1, n_total):
                pairwise_agreement.append(
                    _statevector_not_comparable_record(
                        res_i_raw,
                        results_list[j],
                        "statevector_parse_error",
                        {sim_i_name: str(e)},
                    )
                )
            continue

        for j in range(i + 1, n_total):
            sim_j_name = simulators[j]

            if sim_j_name not in sim_to_valid_idx:
                pairwise_agreement.append(
                    _statevector_not_comparable_record(
                        res_i,
                        results_list[j],
                        "missing_statevector",
                    )
                )
                continue

            try:
                res_j = valid_results[sim_to_valid_idx[sim_j_name]]
                sv_j = parse_statevector(res_j["statevector"])

                invalid_reason_j = _statevector_invalid_reason(sv_j)
                if invalid_reason_j is not None:
                    pairwise_agreement.append(
                        _statevector_not_comparable_record(
                            res_i,
                            res_j,
                            invalid_reason_j,
                            {sim_j_name: invalid_reason_j},
                        )
                    )
                    del sv_j
                    continue

                if sv_i.shape != sv_j.shape:
                    fidelity_matrix[i, j] = 0.0
                    fidelity_matrix[j, i] = 0.0
                    divergences_found.append({
                        "type": "Shape Mismatch",
                        "simulators": [sim_i_name, sim_j_name],
                        "shapes": [sv_i.shape, sv_j.shape]
                    })
                    pairwise_agreement.append(
                        _statevector_not_comparable_record(
                            res_i,
                            res_j,
                            "shape_mismatch",
                            {
                                sim_i_name: list(sv_i.shape),
                                sim_j_name: list(sv_j.shape),
                            },
                        )
                    )
                    del sv_j
                    continue

                sv_j_norm, norm_j = _normalize_statevector(sv_j)
                fidelity, relative_phase = _statevector_inner_metrics(
                    sv_i_norm,
                    sv_j_norm,
                    fidelity_tolerance,
                    phase_tolerance,
                )
                sv_j_bit_reversed_norm = _bit_reversed_statevector(sv_j_norm)
                bit_reversed_fidelity, bit_reversed_relative_phase = _statevector_inner_metrics(
                    sv_i_norm,
                    sv_j_bit_reversed_norm,
                    fidelity_tolerance,
                    phase_tolerance,
                )
                qubit_permutation_metrics = _best_statevector_qubit_permutation_metrics(
                    sv_i_norm,
                    sv_j_norm,
                    fidelity_tolerance,
                    phase_tolerance,
                )

                fidelity_matrix[i, j] = fidelity
                fidelity_matrix[j, i] = fidelity
                phase_matrix[i, j] = relative_phase
                phase_matrix[j, i] = -relative_phase

                is_cross_group = (lsb_sims and msb_sims and
                                 ((sim_i_name in lsb_sims and sim_j_name in msb_sims) or
                                  (sim_i_name in msb_sims and sim_j_name in lsb_sims)))

                pairwise_agreement.append(
                    _classify_statevector_pair(
                        res_i,
                        res_j,
                        fidelity,
                        relative_phase,
                        bit_reversed_fidelity,
                        bit_reversed_relative_phase,
                        qubit_permutation_metrics,
                        norm_i,
                        norm_j,
                        is_cross_group,
                        fidelity_tolerance,
                        phase_tolerance,
                    )
                )

                if fidelity < (1.0 - fidelity_tolerance):
                    divergences_found.append({
                        "type": "Fidelity",
                        "simulators": [sim_i_name, sim_j_name],
                        "fidelity": float(fidelity),
                        "relative_phase": float(relative_phase),
                        "is_cross_group": is_cross_group
                    })
                elif relative_phase != 0.0:
                    divergences_found.append({
                        "type": "Phase",
                        "simulators": [sim_i_name, sim_j_name],
                        "fidelity": 1.0,
                        "relative_phase": float(relative_phase),
                        "is_cross_group": is_cross_group
                    })

                del sv_j
                del sv_j_norm
                del sv_j_bit_reversed_norm

            except Exception as e:
                logger.error(f"Error comparing {sim_i_name} vs {sim_j_name}: {e}")
                fidelity_matrix[i, j] = -1.0
                fidelity_matrix[j, i] = -1.0
                pairwise_agreement.append(
                    _statevector_not_comparable_record(
                        res_i,
                        results_list[j],
                        "comparison_error",
                        {"error": str(e)},
                    )
                )

        del sv_i
        del sv_i_norm
        gc.collect()

    report = {
        "simulators": simulators,
        "fidelity_matrix": fidelity_matrix.tolist(),
        "relative_phase_matrix": phase_matrix.tolist(),
        "divergences_found": divergences_found,
        "pairwise_agreement": pairwise_agreement,
        "qubit_ordering_warning": qubit_ordering_warning,
        "ordering_map": ordering_map
    }

    return report


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


def _shots_per_backend_for_target_power(alpha, target_power, delta_tv):
    """Shots per backend needed to detect a total-variation difference of ``delta_tv``.

    Prospective shot budget under a deliberately conservative two-outcome alternative:
    two outcomes carry all the probability mass and differ by +/- delta_tv between the
    two backends, so the pooled cell probabilities are 0.5 each and Cohen's w reduces to
    exactly ``delta_tv`` on a single degree of freedom. This is the *largest* shot budget
    among alternatives with the same total-variation distance (smallest w), so it does not
    under-state the required shots. Deterministic; scipy-only.
    """
    if delta_tv <= 0:
        return None
    crit = _chi2_dist.ppf(1 - alpha, 1)
    # Required noncentrality lambda so that power == target_power at df=1.
    lam_required = brentq(
        lambda lam: ncx2.cdf(crit, 1, lam) - (1 - target_power),
        0.0,
        1.0e6,
    )
    n_total = lam_required / (delta_tv ** 2)  # lambda = N * w^2, w = delta_tv
    return int(np.ceil(n_total / 2.0))


def _statistical_agreement_test(
    counts_i,
    counts_j,
    basis,
    sim_i,
    sim_j,
    alpha=STAT_TEST_ALPHA,
    target_power=STAT_TEST_TARGET_POWER,
    delta_tv=STAT_TEST_DELTA_TV,
):
    """Shot-noise-aware homogeneity test between two count distributions.

    ``counts_j`` is already aligned to the registered transform named by ``basis`` (direct
    counts, bit-reversed keys, or permuted keys), so the statistical verdict is computed on
    the same basis the explained-cause label selected. Returns descriptive metrics plus raw
    chi-square and G-test p-values; family-wise correction and the final verdict are filled
    in a second pass over all pairs.
    """
    outcomes = sorted(set(counts_i) | set(counts_j))
    row_i = np.array([float(counts_i.get(o, 0)) for o in outcomes])
    row_j = np.array([float(counts_j.get(o, 0)) for o in outcomes])
    n_i = float(row_i.sum())
    n_j = float(row_j.sum())

    p_i = row_i / n_i
    p_j = row_j / n_j
    total_variation = float(0.5 * np.abs(p_i - p_j).sum())

    block = {
        "basis": basis,
        "n_shots": {sim_i: int(round(n_i)), sim_j: int(round(n_j))},
        "alpha": alpha,
        "effect_size": {
            "total_variation": total_variation,
            "cramers_v": None,
        },
        "power": {
            "delta_tv": delta_tv,
            "target_power": target_power,
            "model": "two_outcome_conservative (Cohen's w = delta_tv, df=1)",
            "power_to_detect_delta_at_observed_shots": None,
            "shots_per_backend_for_target_power": _shots_per_backend_for_target_power(
                alpha, target_power, delta_tv
            ),
        },
        "chi2": {
            "statistic": None,
            "dof": None,
            "p_value": None,
            "p_value_bh": None,
            "p_value_bonferroni": None,
            "significant_bh": None,
        },
        "g_test": {
            "statistic": None,
            "dof": None,
            "p_value": None,
            "p_value_bh": None,
            "p_value_bonferroni": None,
            "significant_bh": None,
        },
        "low_count_warning": False,
        "verdict": None,
    }

    # Prospective sensitivity: with the shots actually used, power to detect a delta_tv
    # difference (same conservative df=1 model). Not post-hoc/observed-effect power.
    n_total = n_i + n_j
    crit_ref = _chi2_dist.ppf(1 - alpha, 1)
    lam_at_observed = n_total * (delta_tv ** 2)
    block["power"]["power_to_detect_delta_at_observed_shots"] = float(
        1 - ncx2.cdf(crit_ref, 1, lam_at_observed)
    )

    # A single shared outcome (K < 2) is a degenerate contingency table (df 0): the two
    # backends put all mass on the same bitstring, so they are trivially consistent.
    if len(outcomes) < 2:
        block["chi2"].update({"statistic": 0.0, "dof": 0, "p_value": 1.0})
        block["g_test"].update({"statistic": 0.0, "dof": 0, "p_value": 1.0})
        block["effect_size"]["cramers_v"] = 0.0
        return block

    table = np.vstack([row_i, row_j])
    chi2_stat, chi2_p, dof, expected = chi2_contingency(table, correction=False)
    g_stat, g_p, _, _ = chi2_contingency(table, lambda_="log-likelihood")

    block["low_count_warning"] = bool((expected < 5).any())
    block["effect_size"]["cramers_v"] = float(np.sqrt(chi2_stat / n_total))
    block["chi2"].update({
        "statistic": float(chi2_stat),
        "dof": int(dof),
        "p_value": float(chi2_p),
    })
    block["g_test"].update({
        "statistic": float(g_stat),
        "dof": int(dof),
        "p_value": float(g_p),
    })
    return block


def _bh_adjust(pvalues):
    """Benjamini-Hochberg step-up adjusted p-values, aligned to input order."""
    m = len(pvalues)
    if m == 0:
        return []
    pvals = np.asarray(pvalues, dtype=float)
    order = np.argsort(pvals)
    ranked = pvals[order] * m / np.arange(1, m + 1)
    # Enforce monotonicity (step-up): each adjusted value is the running min from the top.
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    ranked = np.clip(ranked, 0.0, 1.0)
    adjusted = np.empty(m)
    adjusted[order] = ranked
    return adjusted.tolist()


def _apply_multiple_comparison_correction(stat_records, alpha=STAT_TEST_ALPHA):
    """Fill BH/Bonferroni-adjusted p-values and verdicts across the pairwise family.

    ``stat_records`` is the list of ``statistical_test`` blocks (one per comparable pair).
    Correction is applied per test (chi-square and G-test) across all pairs, so the fleet's
    many pairwise comparisons do not inflate the false-discovery rate.
    """
    m = len(stat_records)
    if m == 0:
        return {
            "family_size": 0,
            "alpha": alpha,
            "correction": ["benjamini_hochberg", "bonferroni"],
            "verdict_counts": {},
            "n_significant_bh": {"chi2": 0, "g_test": 0},
        }

    for test in ("chi2", "g_test"):
        raw = [rec[test]["p_value"] for rec in stat_records]
        bh = _bh_adjust(raw)
        for rec, p_raw, p_bh in zip(stat_records, raw, bh):
            p_bonf = min(p_raw * m, 1.0)
            rec[test]["p_value_bh"] = float(p_bh)
            rec[test]["p_value_bonferroni"] = float(p_bonf)
            rec[test]["significant_bh"] = bool(p_bh < alpha)

    verdict_counts = {}
    n_sig = {"chi2": 0, "g_test": 0}
    for rec in stat_records:
        chi2_sig = rec["chi2"]["significant_bh"]
        g_sig = rec["g_test"]["significant_bh"]
        n_sig["chi2"] += int(bool(chi2_sig))
        n_sig["g_test"] += int(bool(g_sig))
        if rec["low_count_warning"]:
            verdict = "inconclusive_low_shots"
        elif chi2_sig and g_sig:
            verdict = "distinguishable"
        elif not chi2_sig and not g_sig:
            verdict = "consistent"
        else:
            verdict = "ambiguous"
        rec["verdict"] = verdict
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    return {
        "family_size": m,
        "alpha": alpha,
        "correction": ["benjamini_hochberg", "bonferroni"],
        "verdict_counts": verdict_counts,
        "n_significant_bh": n_sig,
    }


def create_counts_report(results_list, n_shots, thresholds=None):
    """
    Generates a full report on the statistical divergence
    between counts distributions using JS Divergence AND Hellinger Distance.

    thresholds: optional dict overriding the descriptive distance thresholds. Recognized
    keys: ``js_threshold`` (default 0.01) and ``hellinger_threshold`` (default 0.1). Both
    are heuristic, shot-count-dependent cut-offs; the statistical_test block carries the
    shot-noise-aware verdict. Absent/None keeps the defaults; the effective values are
    recorded per pair in the pairwise_agreement records.
    """

    simulators = [res.get('simulator', 'unknown') for res in results_list]

    # Per-simulator counts validity: None if comparable, else a not-comparable reason.
    counts_validity = []
    for res in results_list:
        if "counts" not in res:
            counts_validity.append("missing_counts")
        else:
            counts_validity.append(_counts_invalid_reason(res["counts"]))

    all_bitstrings = set()
    for res, reason in zip(results_list, counts_validity):
        if reason is None:
            all_bitstrings.update(res["counts"].keys())

    all_bitstrings = sorted(list(all_bitstrings))

    prob_vectors = []
    for res, reason in zip(results_list, counts_validity):
        if reason is None:
            prob_vectors.append(
                _counts_probability_vector(res["counts"], all_bitstrings, n_shots)
            )
        else:
            prob_vectors.append(None)

    n = len(simulators)

    js_matrix = np.zeros((n, n))
    hellinger_matrix = np.zeros((n, n))

    divergences_found = []
    pairwise_agreement = []
    stat_test_records = []

    _t = thresholds or {}
    js_threshold = _t.get("js_threshold", 0.01)
    hellinger_threshold = _t.get("hellinger_threshold", 0.1)

    lsb_sims = [res.get('simulator') for res in results_list if res.get('qubit_ordering') == 'lsb']
    msb_sims = [res.get('simulator') for res in results_list if res.get('qubit_ordering') == 'msb']

    for i in range(n):
        for j in range(i + 1, n):
            sim_i = simulators[i]
            sim_j = simulators[j]
            pv_i = prob_vectors[i]
            pv_j = prob_vectors[j]

            if pv_i is not None and pv_j is not None:

                js_div, h_dist = _counts_distance_metrics(pv_i, pv_j)

                bit_reversed_counts_j = _bit_reversed_counts(results_list[j]["counts"])
                bit_reversed_outcomes = sorted(
                    set(results_list[i]["counts"].keys()) | set(bit_reversed_counts_j.keys())
                )
                pv_i_for_bit_reversal = _counts_probability_vector(
                    results_list[i]["counts"], bit_reversed_outcomes, n_shots
                )
                pv_j_bit_reversed = _counts_probability_vector(
                    bit_reversed_counts_j, bit_reversed_outcomes, n_shots
                )
                bit_reversed_js_div, bit_reversed_h_dist = _counts_distance_metrics(
                    pv_i_for_bit_reversal, pv_j_bit_reversed
                )
                qubit_permutation_metrics = _best_counts_qubit_permutation_metrics(
                    results_list[i]["counts"],
                    results_list[j]["counts"],
                    n_shots,
                    js_threshold,
                    hellinger_threshold,
                )

                js_matrix[i, j] = js_div
                js_matrix[j, i] = js_div

                hellinger_matrix[i, j] = h_dist
                hellinger_matrix[j, i] = h_dist

                is_cross_group = False

                if (sim_i in lsb_sims and sim_j in msb_sims) or (sim_i in msb_sims and sim_j in lsb_sims):
                    is_cross_group = True

                record = _classify_counts_pair(
                    results_list[i],
                    results_list[j],
                    js_div,
                    h_dist,
                    bit_reversed_js_div,
                    bit_reversed_h_dist,
                    qubit_permutation_metrics,
                    is_cross_group,
                    js_threshold,
                    hellinger_threshold,
                    n_shots,
                )

                # Shot-noise statistical test, computed on the same registered-transform
                # basis the descriptive label selected.
                if record["agreement"] == "agree_after_bit_reversal":
                    basis = "bit_reversal"
                    counts_j_aligned = _bit_reversed_counts(results_list[j]["counts"])
                elif record["agreement"] == "agree_after_qubit_permutation":
                    basis = "qubit_permutation"
                    counts_j_aligned = _permute_counts(
                        results_list[j]["counts"],
                        record["transform_effect"]["permutation"],
                    )
                else:
                    basis = "direct"
                    counts_j_aligned = results_list[j]["counts"]

                stat_block = _statistical_agreement_test(
                    results_list[i]["counts"],
                    counts_j_aligned,
                    basis,
                    sim_i,
                    sim_j,
                )
                record["metrics"]["statistical_test"] = stat_block
                stat_test_records.append(stat_block)

                pairwise_agreement.append(record)

                if js_div > js_threshold or h_dist > hellinger_threshold:
                    divergences_found.append({
                        "type": "Distribution Divergence",
                        "simulators": [sim_i, sim_j],
                        "js_divergence": js_div,
                        "hellinger_distance": h_dist,
                        "is_cross_group": is_cross_group
                    })
            else:
                js_matrix[i, j] = -1.0
                js_matrix[j, i] = -1.0
                hellinger_matrix[i, j] = -1.0
                hellinger_matrix[j, i] = -1.0
                reason_i = counts_validity[i]
                reason_j = counts_validity[j]
                reason = reason_i or reason_j
                details = {}
                if reason_i:
                    details[sim_i] = reason_i
                if reason_j:
                    details[sim_j] = reason_j
                pairwise_agreement.append(
                    _counts_not_comparable_record(
                        results_list[i],
                        results_list[j],
                        reason,
                        details,
                    )
                )

    # Family-wise correction across every comparable pair, applied per test, then verdicts.
    statistical_test_summary = _apply_multiple_comparison_correction(stat_test_records)

    ordering_map = {res.get('simulator'): res.get('qubit_ordering') for res in results_list if "qubit_ordering" in res}
    return {
        "simulators": simulators,
        "statistical_distance_matrix (js_divergence)": js_matrix.tolist(),
        "hellinger_distance_matrix": hellinger_matrix.tolist(),
        "divergences_found": divergences_found,
        "pairwise_agreement": pairwise_agreement,
        "statistical_test_summary": statistical_test_summary,
        "all_outcomes_observed": all_bitstrings,
        "ordering_map": ordering_map
    }
