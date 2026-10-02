"""The statevector and counts report builders that walk every backend pair."""

import gc
import math

from .common import (
    ANALYSIS_VERSION, DEFAULT_FIDELITY_TOLERANCE, DEFAULT_HELLINGER_THRESHOLD,
    DEFAULT_JS_THRESHOLD, DEFAULT_NORM_TOLERANCE, DEFAULT_PHASE_TOLERANCE, JS_DIVERGENCE_UNIT,
    STAT_TEST_ALPHA, STAT_TEST_DELTA_TV, STAT_TEST_TARGET_POWER, _threshold, logger,
)
from .classification import (
    _classify_counts_pair, _classify_statevector_pair, _counts_not_comparable_record,
    _statevector_not_comparable_record,
)
from .counts import (
    _best_counts_qubit_permutation_metrics, _bit_reversed_counts, _counts_distance_metrics,
    _counts_invalid_reason, _counts_probability_vector, _counts_total,
)
from .statevector import (
    _best_statevector_qubit_permutation_metrics, _bit_reversed_statevector,
    _normalize_statevector, _statevector_inner_metrics,
    _statevector_invalid_reason, parse_statevector,
)
from .marginals import apply_marginal_correction, marginal_block
from .statistics import (
    _apply_multiple_comparison_correction,
    _statistical_agreement_test,
)


def _measured_assessment(record):
    """Combined measured-mode reading of a pair from its statistical verdict.

    consistent -> consistent_within_shot_noise; distinguishable, ambiguous and
    inconclusive_low_shots pass through; a not_comparable pair is not_comparable. A pair
    without a verdict falls back to its distance label.
    """
    if record.get("agreement") == "not_comparable":
        return "not_comparable"
    verdict = ((record.get("metrics") or {}).get("statistical_test") or {}).get("verdict")
    if verdict == "consistent":
        return "consistent_within_shot_noise"
    if verdict in ("distinguishable", "ambiguous", "inconclusive_low_shots"):
        return verdict
    if record.get("agreement") == "distance_exceeds_threshold":
        return "distinguishable"
    return "consistent_within_shot_noise"


def create_divergence_report(results_list, thresholds=None):
    """Build the statevector divergence report: fidelity/phase matrices and pair records.

    Each statevector is decoded and normalised once and reused across pairs. ``thresholds``
    may override ``fidelity_tolerance`` (default 1e-5), ``phase_tolerance`` (default 1e-6 rad)
    and ``norm_tolerance`` (default 1e-4); an absent or None key keeps the default.

    Matrix cells are None for pairs that were not compared; a diagonal cell holds the
    exact self-value (fidelity 1.0, global phase offset 0.0) when that backend's statevector
    is usable, else None.
    """

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
            "Pairs across the two groups are labelled in the bit-reversed basis; the raw "
            "fidelity matrix compares amplitudes as reported."
        )
        logger.warning(qubit_ordering_warning)

    valid_results = [res for res in results_list if "error" not in res and "statevector" in res]
    simulators = [res.get('simulator', 'unknown') for res in results_list]

    sim_to_valid_idx = {}
    for i, res in enumerate(valid_results):
        sim_to_valid_idx[res.get('simulator')] = i

    n_total = len(simulators)

    fidelity_matrix = _empty_matrix(n_total)
    phase_matrix = _empty_matrix(n_total)

    divergences_found = []
    pairwise_agreement = []

    fidelity_tolerance = _threshold(thresholds, "fidelity_tolerance", DEFAULT_FIDELITY_TOLERANCE)
    phase_tolerance = _threshold(thresholds, "phase_tolerance", DEFAULT_PHASE_TOLERANCE)
    norm_tolerance = _threshold(thresholds, "norm_tolerance", DEFAULT_NORM_TOLERANCE)

    logger.info("Starting sequential divergence comparison...")

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
            fidelity_matrix[i][i] = 1.0
            phase_matrix[i][i] = 0.0

            if abs(float(norm_i) - 1.0) > norm_tolerance:
                divergences_found.append({
                    "type": "Normalization",
                    "simulators": [sim_i_name],
                    "norm": float(norm_i),
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

                fidelity_matrix[i][j] = fidelity_matrix[j][i] = float(fidelity)
                phase_matrix[i][j] = float(relative_phase)
                phase_matrix[j][i] = float(-relative_phase)

                is_cross_group = bool(
                    (sim_i_name in lsb_sims and sim_j_name in msb_sims)
                    or (sim_i_name in msb_sims and sim_j_name in lsb_sims)
                )
                basis, basis_source = _statevector_label_aligned_basis(
                    res_i, res_j, len(sv_j_norm))

                record = _classify_statevector_pair(
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
                    norm_tolerance,
                    label_aligned_basis=basis,
                    basis_source=basis_source,
                )
                pairwise_agreement.append(record)
                divergence = _statevector_divergence_entry(record, is_cross_group)
                if divergence is not None:
                    divergences_found.append(divergence)

                del sv_j
                del sv_j_norm
                del sv_j_bit_reversed_norm

            except Exception as e:
                logger.error(f"Error comparing {sim_i_name} vs {sim_j_name}: {e}")
                fidelity_matrix[i][j] = fidelity_matrix[j][i] = None
                phase_matrix[i][j] = phase_matrix[j][i] = None
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
        "analysis_version": ANALYSIS_VERSION,
        "agreement_thresholds": {
            "fidelity_tolerance": fidelity_tolerance,
            "phase_tolerance": phase_tolerance,
            "norm_tolerance": norm_tolerance,
        },
        "simulators": simulators,
        "fidelity_matrix": fidelity_matrix,
        "relative_phase_matrix": phase_matrix,
        "divergences_found": divergences_found,
        "pairwise_agreement": pairwise_agreement,
        "qubit_ordering_warning": qubit_ordering_warning,
        "ordering_map": ordering_map
    }

    return report


_DECLARED_ORDERS = ("lsb", "msb")

DISAGREEMENT_GROUPS = {
    "residual_disagreement": "disagreement: not explained by the declared qubit orderings",
    "unaligned_basis_match": ("disagreement: agrees only in the basis the declared qubit "
                              "orderings do not imply"),
    "agree_after_qubit_permutation": ("disagreement: agrees only after an undeclared qubit "
                                      "permutation"),
}


def _label_aligned_basis(res_i, res_j):
    """"bit_reversal" when the two results declare different counts bit orders, else "direct"."""
    order_i = res_i.get("qubit_ordering")
    order_j = res_j.get("qubit_ordering")
    if order_i in _DECLARED_ORDERS and order_j in _DECLARED_ORDERS and order_i != order_j:
        return "bit_reversal"
    return "direct"


def _statevector_label_aligned_basis(res_i, res_j, length):
    """(basis, basis_source) for a statevector pair of ``length`` amplitudes.

    One qubit: bit reversal is the identity, so ("direct", "single_qubit"). Both orderings
    declared: the basis they imply. Otherwise ("direct", "undeclared_qubit_ordering").
    """
    if length <= 2:
        return "direct", "single_qubit"
    if (res_i.get("qubit_ordering") in _DECLARED_ORDERS
            and res_j.get("qubit_ordering") in _DECLARED_ORDERS):
        return _label_aligned_basis(res_i, res_j), "declared_qubit_ordering"
    return "direct", "undeclared_qubit_ordering"


def _statevector_divergence_entry(record, is_cross_group):
    """divergences_found entry for a disagreeing pair ("Fidelity") or an agreeing pair with a
    global phase offset in the label-aligned basis ("Phase"); None otherwise."""
    metrics = record["metrics"]
    agreement = record["agreement"]
    entry = {
        "simulators": record["simulators"],
        "basis": metrics["label_aligned_basis"],
        "fidelity": metrics["label_aligned_fidelity"],
        "direct_fidelity": metrics["direct_fidelity"],
        "relative_phase": metrics["label_aligned_relative_phase_rad"],
        "agreement": agreement,
        "is_cross_group": is_cross_group,
    }
    if metrics.get("unaligned_basis_match"):
        entry.update({"type": "Fidelity", "group": DISAGREEMENT_GROUPS["unaligned_basis_match"],
                      "unaligned_basis_match": metrics["unaligned_basis_match"]})
        return entry
    if agreement in ("residual_disagreement", "agree_after_qubit_permutation"):
        entry.update({"type": "Fidelity", "group": DISAGREEMENT_GROUPS[agreement]})
        return entry
    if agreement != "not_comparable" and metrics["label_aligned_relative_phase_rad"] != 0.0:
        entry["type"] = "Phase"
        return entry
    return None


def _empty_matrix(n):
    """n×n list of None."""
    return [[None] * n for _ in range(n)]


def _as_number(total):
    """Return an integral float as int, otherwise the float."""
    return int(total) if float(total).is_integer() else float(total)


def _shot_total_mismatch(sim_i, total_i, sim_j, total_j, n_shots):
    """Return {"observed": {...}, "requested": n_shots} if a total differs from n_shots."""
    if n_shots is None or (total_i == n_shots and total_j == n_shots):
        return None
    return {
        "observed": {sim_i: _as_number(total_i), sim_j: _as_number(total_j)},
        "requested": n_shots,
    }


def _compare_counts_pair(res_i, res_j, is_cross_group, js_threshold, hellinger_threshold, n_shots):
    """Return (record, statistical_test block or None, distances or None) for one pair.

    ``distances`` is (direct js, direct hellinger, label-aligned js, label-aligned
    hellinger). The statistical test runs in the label-aligned basis.
    """
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    counts_i = res_i["counts"]
    counts_j = res_j["counts"]

    outcomes = sorted(set(counts_i) | set(counts_j))
    js_div, h_dist = _counts_distance_metrics(
        _counts_probability_vector(counts_i, outcomes),
        _counts_probability_vector(counts_j, outcomes),
    )

    bit_reversed_counts_j = _bit_reversed_counts(counts_j)
    bit_reversed_outcomes = sorted(set(counts_i) | set(bit_reversed_counts_j))
    bit_reversed_js_div, bit_reversed_h_dist = _counts_distance_metrics(
        _counts_probability_vector(counts_i, bit_reversed_outcomes),
        _counts_probability_vector(bit_reversed_counts_j, bit_reversed_outcomes),
    )

    nonfinite = {
        name: value for name, value in (
            ("js_divergence", js_div),
            ("hellinger_distance", h_dist),
            ("bit_reversed_js_divergence", bit_reversed_js_div),
            ("bit_reversed_hellinger_distance", bit_reversed_h_dist),
        ) if not math.isfinite(value)
    }
    if nonfinite:
        return (
            _counts_not_comparable_record(
                res_i, res_j, "nonfinite_metric", {name: str(v) for name, v in nonfinite.items()}
            ),
            None,
            None,
        )

    qubit_permutation_metrics = _best_counts_qubit_permutation_metrics(counts_i, counts_j)
    shot_total_mismatch = _shot_total_mismatch(
        sim_i, _counts_total(counts_i), sim_j, _counts_total(counts_j), n_shots
    )

    basis = _label_aligned_basis(res_i, res_j)
    record = _classify_counts_pair(
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
        shot_total_mismatch,
        label_aligned_basis=basis,
    )

    counts_j_aligned = bit_reversed_counts_j if basis == "bit_reversal" else counts_j
    stat_block = _statistical_agreement_test(
        counts_i, counts_j_aligned, basis, sim_i, sim_j, res_i=res_i, res_j=res_j
    )
    record["metrics"]["statistical_test"] = stat_block
    record["metrics"]["marginal_test"] = marginal_block(
        counts_i, counts_j_aligned, res_i.get("qubit_ordering"))
    metrics = record["metrics"]
    return record, stat_block, (
        js_div, h_dist,
        metrics["label_aligned_js_divergence"], metrics["label_aligned_hellinger_distance"],
    )


def create_counts_report(results_list, n_shots, thresholds=None):
    """Build the measured report: JS/Hellinger matrices, pair records and shot-noise tests.

    Each backend's distribution is normalised by its observed total. JS divergence is in
    nats (maximum ln 2). ``thresholds`` may override ``js_threshold`` (default 0.01) and
    ``hellinger_threshold`` (default 0.1); an absent or None key keeps the default. A pair
    whose comparison raises is recorded as not_comparable with reason ``comparison_error``.
    """
    simulators = [res.get('simulator', 'unknown') for res in results_list]

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
    all_bitstrings = sorted(all_bitstrings)

    n = len(simulators)
    js_matrix = _empty_matrix(n)
    hellinger_matrix = _empty_matrix(n)
    for k, reason in enumerate(counts_validity):
        if reason is None:
            js_matrix[k][k] = hellinger_matrix[k][k] = 0.0

    divergences_found = []
    pairwise_agreement = []
    stat_test_records = []

    js_threshold = _threshold(thresholds, "js_threshold", DEFAULT_JS_THRESHOLD)
    hellinger_threshold = _threshold(thresholds, "hellinger_threshold", DEFAULT_HELLINGER_THRESHOLD)

    lsb_sims = [res.get('simulator') for res in results_list if res.get('qubit_ordering') == 'lsb']
    msb_sims = [res.get('simulator') for res in results_list if res.get('qubit_ordering') == 'msb']

    for i in range(n):
        for j in range(i + 1, n):
            sim_i = simulators[i]
            sim_j = simulators[j]
            reason_i = counts_validity[i]
            reason_j = counts_validity[j]

            distances = None
            if reason_i is None and reason_j is None:
                is_cross_group = bool(
                    (sim_i in lsb_sims and sim_j in msb_sims)
                    or (sim_i in msb_sims and sim_j in lsb_sims)
                )
                try:
                    record, stat_block, distances = _compare_counts_pair(
                        results_list[i], results_list[j], is_cross_group,
                        js_threshold, hellinger_threshold, n_shots,
                    )
                except Exception as e:
                    logger.error(f"Error comparing counts {sim_i} vs {sim_j}: {e}")
                    record = _counts_not_comparable_record(
                        results_list[i], results_list[j], "comparison_error", {"error": str(e)}
                    )
                    stat_block = None
                pairwise_agreement.append(record)
                if stat_block is not None:
                    stat_test_records.append(stat_block)
            else:
                details = {}
                if reason_i:
                    details[sim_i] = reason_i
                if reason_j:
                    details[sim_j] = reason_j
                pairwise_agreement.append(
                    _counts_not_comparable_record(
                        results_list[i], results_list[j], reason_i or reason_j, details
                    )
                )

            if distances is None:
                continue

            js_div, h_dist, aligned_js, aligned_h = distances
            js_matrix[i][j] = js_matrix[j][i] = float(js_div)
            hellinger_matrix[i][j] = hellinger_matrix[j][i] = float(h_dist)
            if aligned_js > js_threshold or aligned_h > hellinger_threshold:
                entry = {
                    "type": "Distribution Divergence",
                    "simulators": [sim_i, sim_j],
                    "basis": record["metrics"]["label_aligned_basis"],
                    "js_divergence": aligned_js,
                    "hellinger_distance": aligned_h,
                    "agreement": record["agreement"],
                    "is_cross_group": is_cross_group,
                }
                if record["agreement"] == "agree_after_qubit_permutation":
                    entry["group"] = DISAGREEMENT_GROUPS["agree_after_qubit_permutation"]
                divergences_found.append(entry)

    statistical_test_summary = _apply_multiple_comparison_correction(stat_test_records)
    assessment_counts = {}
    for record in pairwise_agreement:
        record["measured_assessment"] = _measured_assessment(record)
        assessment_counts[record["measured_assessment"]] = (
            assessment_counts.get(record["measured_assessment"], 0) + 1)
    statistical_test_summary["measured_assessment_counts"] = assessment_counts
    marginal_blocks = [b for b in ((r.get("metrics") or {}).get("marginal_test") for r in pairwise_agreement) if b]
    statistical_test_summary["marginal_test_summary"] = apply_marginal_correction(marginal_blocks)
    for record in pairwise_agreement:
        block = (record.get("metrics") or {}).get("marginal_test")
        record["marginal_assessment"] = block["assessment"] if block else "not_applicable"

    ordering_map = {res.get('simulator'): res.get('qubit_ordering') for res in results_list if "qubit_ordering" in res}
    return {
        "analysis_version": ANALYSIS_VERSION,
        "agreement_thresholds": {
            "js_threshold": js_threshold,
            "hellinger_threshold": hellinger_threshold,
            "stat_test_alpha": STAT_TEST_ALPHA,
            "stat_test_target_power": STAT_TEST_TARGET_POWER,
            "stat_test_delta_tv": STAT_TEST_DELTA_TV,
        },
        "simulators": simulators,
        "statistical_distance_matrix (js_divergence)": js_matrix,
        "hellinger_distance_matrix": hellinger_matrix,
        "js_divergence_unit": JS_DIVERGENCE_UNIT,
        "divergences_found": divergences_found,
        "pairwise_agreement": pairwise_agreement,
        "statistical_test_summary": statistical_test_summary,
        "all_outcomes_observed": all_bitstrings,
        "ordering_map": ordering_map
    }
