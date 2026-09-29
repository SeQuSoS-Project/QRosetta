"""Turning one backend pair's metrics into an explained-cause agreement record."""

from .common import DEFAULT_NORM_TOLERANCE, _json_float


def _pair_provenance(res_i, res_j, mode):
    """Copy ordering, SDK, preprocessing and (measured) seed/sampling provenance per backend."""
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
        provenance["runner_seed"] = {
            sim_i: res_i.get("runner_seed"),
            sim_j: res_j.get("runner_seed"),
        }
        provenance["sampling_method"] = {
            sim_i: res_i.get("sampling_method"),
            sim_j: res_j.get("sampling_method"),
        }
    return provenance


def _run_status(res):
    """Return "error" if the result carries an error, else "completed"."""
    return "error" if "error" in res else "completed"


def _statevector_not_comparable_record(res_i, res_j, reason, details=None):
    """Build a not_comparable statevector record with ``reason``."""
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
    norm_tolerance=None,
):
    """Label a statevector pair from its direct, bit-reversed and permuted fidelities.

    Fidelities are computed on normalised vectors. A pair agrees when fidelity >=
    1 - fidelity_tolerance. If either input norm differs from 1 by more than
    ``norm_tolerance``, an agreeing pair is labelled ``agree_after_normalization`` and the
    label it would otherwise have received is kept in ``metrics.normalized_agreement``.
    """
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    if norm_tolerance is None:
        norm_tolerance = DEFAULT_NORM_TOLERANCE
    unnormalized_input = bool(
        abs(float(norm_i) - 1.0) > norm_tolerance or abs(float(norm_j) - 1.0) > norm_tolerance
    )
    phase_agrees = abs(relative_phase) <= phase_tolerance
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

    normalized_agreement = None
    if unnormalized_input and agreement != "residual_disagreement":
        normalized_agreement = agreement
        agreement = "agree_after_normalization"

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
            "unnormalized_input": unnormalized_input,
            "normalized_agreement": normalized_agreement,
            "fidelity_tolerance": fidelity_tolerance,
            "phase_tolerance": phase_tolerance,
            "norm_tolerance": norm_tolerance,
            "is_cross_group": bool(is_cross_group),
        },
        "provenance": _pair_provenance(res_i, res_j, "statevector"),
    }


def _counts_not_comparable_record(res_i, res_j, reason, details=None):
    """Build a not_comparable measured record with ``reason``."""
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
    shot_total_mismatch=None,
):
    """Label a measured pair from its direct, bit-reversed and permuted JS/Hellinger distances.

    The label is a descriptive threshold check; ``metrics.statistical_test`` is added by the
    report builder. ``shot_total_mismatch`` is recorded when an observed total differs from
    the requested ``n_shots``.
    """
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
            "shot_total_mismatch": shot_total_mismatch,
            "is_cross_group": bool(is_cross_group),
        },
        "provenance": _pair_provenance(res_i, res_j, "measured"),
    }
