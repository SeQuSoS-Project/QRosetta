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
    """The result's dispatch_status when it is timeout/offline, "error" if it carries an
    error, else "completed"."""
    if res.get("dispatch_status") in ("timeout", "offline"):
        return res["dispatch_status"]
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


_STATEVECTOR_AGREEING = ("agree_directly", "agree_up_to_global_phase", "agree_after_bit_reversal")


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
    label_aligned_basis="direct",
    basis_source="declared_qubit_ordering",
):
    """Label a statevector pair in the basis its declared qubit orderings imply.

    ``label_aligned_basis`` is "bit_reversal" for an lsb x msb pair and "direct" otherwise.
    A pair agrees when the fidelity in that basis is >= 1 - fidelity_tolerance:
    agree_directly / agree_up_to_global_phase in the direct basis, agree_after_bit_reversal
    in the bit-reversed one (``transform_effect.global_phase_aligned`` marks a phase offset).
    A pair that matches only in the other basis is residual_disagreement with
    ``metrics.unaligned_basis_match`` naming that basis. agree_after_qubit_permutation
    (an undeclared permutation) is a disagreement class. If either input norm differs
    from 1 by more than ``norm_tolerance``, an agreeing pair is labelled
    ``agree_after_normalization`` and its label is kept in ``metrics.normalized_agreement``.
    """
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    if norm_tolerance is None:
        norm_tolerance = DEFAULT_NORM_TOLERANCE
    unnormalized_input = bool(
        abs(float(norm_i) - 1.0) > norm_tolerance or abs(float(norm_j) - 1.0) > norm_tolerance
    )
    direct_agrees = fidelity >= (1.0 - fidelity_tolerance)
    bit_reversal_agrees = bit_reversed_fidelity >= (1.0 - fidelity_tolerance)
    qubit_permutation_fidelity = qubit_permutation_metrics.get("fidelity")
    qubit_permutation_agrees = (
        qubit_permutation_metrics.get("attempted")
        and qubit_permutation_fidelity is not None
        and qubit_permutation_fidelity >= (1.0 - fidelity_tolerance)
    )
    reversed_basis = label_aligned_basis == "bit_reversal"
    aligned_fidelity = bit_reversed_fidelity if reversed_basis else fidelity
    aligned_phase = bit_reversed_relative_phase if reversed_basis else relative_phase
    aligned_agrees = bit_reversal_agrees if reversed_basis else direct_agrees
    unaligned_agrees = direct_agrees if reversed_basis else bit_reversal_agrees
    phase_agrees = abs(aligned_phase) <= phase_tolerance
    unaligned_basis_match = None

    if aligned_agrees and not reversed_basis and phase_agrees:
        agreement = "agree_directly"
        registered_transform = "identity"
        transform_effect = {
            "fidelity_delta": 0.0,
            "relative_phase_delta_rad": 0.0,
        }
    elif aligned_agrees and not reversed_basis:
        agreement = "agree_up_to_global_phase"
        registered_transform = "global_phase_alignment"
        transform_effect = {
            "fidelity_delta": 0.0,
            "relative_phase_delta_rad": _json_float(-relative_phase),
            "relative_phase_after_alignment_rad": 0.0,
        }
    elif aligned_agrees:
        agreement = "agree_after_bit_reversal"
        registered_transform = "bit_reversal"
        transform_effect = {
            "fidelity_delta": _json_float(bit_reversed_fidelity - fidelity),
            "fidelity_after_transform": _json_float(bit_reversed_fidelity),
            "relative_phase_after_transform_rad": _json_float(bit_reversed_relative_phase),
            "global_phase_aligned": not phase_agrees,
        }
    elif unaligned_agrees:
        agreement = "residual_disagreement"
        registered_transform = None
        transform_effect = None
        unaligned_basis_match = "direct" if reversed_basis else "bit_reversal"
    elif qubit_permutation_agrees:
        agreement = "agree_after_qubit_permutation"
        registered_transform = "qubit_permutation"
        transform_effect = {
            "permutation": qubit_permutation_metrics["permutation"],
            "fidelity_delta": _json_float(qubit_permutation_fidelity - aligned_fidelity),
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
    if unnormalized_input and agreement in _STATEVECTOR_AGREEING:
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
            "label_aligned_basis": label_aligned_basis,
            "basis_source": basis_source,
            "label_aligned_fidelity": _json_float(aligned_fidelity),
            "label_aligned_relative_phase_rad": _json_float(aligned_phase),
            "unaligned_basis_match": unaligned_basis_match,
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
    label_aligned_basis="direct",
    basis_source="declared_qubit_ordering",
):
    """Label a measured pair from its direct, bit-reversed and permuted JS/Hellinger distances.

    The label is a descriptive threshold check; ``metrics.statistical_test`` is added by the
    report builder. Only ``label_aligned_basis`` ("direct" or "bit_reversal", from the
    declared counts bit orders; "direct" for keys of one bit, recorded in
    ``metrics.basis_source``) can give a within-threshold label: a pair within the
    thresholds only in the other basis is distance_exceeds_threshold with
    ``metrics.unaligned_basis_match`` naming that basis, as in statevector mode; otherwise
    qubit permutations are checked.
    ``shot_total_mismatch`` is recorded when an observed total differs from the requested
    ``n_shots``.
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

    direct_label = (
        "distance_within_threshold",
        "identity_threshold_check",
        {"js_divergence_delta": 0.0, "hellinger_distance_delta": 0.0},
    )
    reversal_label = (
        "agree_after_bit_reversal",
        "bit_reversal",
        {
            "js_divergence_delta": _json_float(bit_reversed_js_div - js_div),
            "hellinger_distance_delta": _json_float(bit_reversed_h_dist - h_dist),
            "js_divergence_after_transform": _json_float(bit_reversed_js_div),
            "hellinger_distance_after_transform": _json_float(bit_reversed_h_dist),
        },
    )
    reversed_basis = label_aligned_basis == "bit_reversal"
    aligned_agrees = bit_reversal_agrees if reversed_basis else direct_agrees
    unaligned_agrees = direct_agrees if reversed_basis else bit_reversal_agrees
    unaligned_basis_match = None

    if aligned_agrees:
        agreement, registered_transform, transform_effect = (
            reversal_label if reversed_basis else direct_label)
    elif unaligned_agrees:
        agreement = "distance_exceeds_threshold"
        registered_transform = "identity_threshold_check"
        transform_effect = {
            "js_divergence_delta": 0.0,
            "hellinger_distance_delta": 0.0,
        }
        unaligned_basis_match = "direct" if reversed_basis else "bit_reversal"
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
            "label_aligned_basis": label_aligned_basis,
            "basis_source": basis_source,
            "label_aligned_js_divergence": _json_float(
                bit_reversed_js_div if label_aligned_basis == "bit_reversal" else js_div
            ),
            "label_aligned_hellinger_distance": _json_float(
                bit_reversed_h_dist if label_aligned_basis == "bit_reversal" else h_dist
            ),
            "unaligned_basis_match": unaligned_basis_match,
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
