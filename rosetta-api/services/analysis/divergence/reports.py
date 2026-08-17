# The two report builders that walk every backend pair.


import numpy as np

from .common import (
    logger,
)
from .classification import (
    _classify_counts_pair, _classify_statevector_pair, _counts_not_comparable_record,
    _statevector_not_comparable_record,
)
from .counts import (
    _best_counts_qubit_permutation_metrics, _bit_reversed_counts,
    _counts_distance_metrics, _counts_invalid_reason, _counts_probability_vector,
    _permute_counts,
)
from .statevector import (
    _best_statevector_qubit_permutation_metrics, _bit_reversed_statevector,
    _normalize_statevector, _statevector_inner_metrics,
    _statevector_invalid_reason, parse_statevector,
)
from .statistics import (
    _apply_multiple_comparison_correction,
    _statistical_agreement_test,
)


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

    # Decode + normalize each runner's statevector once and reuse across every pair. The
    # cached values are identical to recomputing them per pair (parse_statevector and
    # _normalize_statevector are pure); this only removes the O(N^2) re-decode of the same
    # Base64 vector. Parse-error and invalid-statevector handling stays inline below.
    _parsed_sv = {}
    _normalized_sv = {}

    def _get_parsed_sv(sim_name, res):
        sv = _parsed_sv.get(sim_name)
        if sv is None:
            sv = parse_statevector(res["statevector"])
            _parsed_sv[sim_name] = sv
        return sv

    def _get_normalized_sv(sim_name, sv):
        nn = _normalized_sv.get(sim_name)
        if nn is None:
            nn = _normalize_statevector(sv)
            _normalized_sv[sim_name] = nn
        return nn

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
            sv_i = _get_parsed_sv(sim_i_name, res_i)

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

            sv_i_norm, norm_i = _get_normalized_sv(sim_i_name, sv_i)

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
                sv_j = _get_parsed_sv(sim_j_name, res_j)

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

                sv_j_norm, norm_j = _get_normalized_sv(sim_j_name, sv_j)
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

    _parsed_sv.clear()
    _normalized_sv.clear()
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
