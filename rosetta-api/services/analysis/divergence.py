# Quantum state and performance analysis utilities.

from qrosetta_commons.helpers import get_logger, decode_statevector
import numpy as np
from scipy.spatial.distance import jensenshannon

logger = get_logger(__name__)


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


def _bit_reversed_statevector(sv):
    """Return a copy of sv with computational-basis index bits reversed."""
    size = len(sv)
    if size == 0 or size & (size - 1):
        raise ValueError(f"statevector length {size} is not a power of two")

    n_qubits = int(np.log2(size))
    reversed_sv = np.empty_like(sv)
    for index, amplitude in enumerate(sv):
        reversed_index = int(format(index, f"0{n_qubits}b")[::-1], 2)
        reversed_sv[reversed_index] = amplitude
    return reversed_sv


def _pair_provenance(res_i, res_j, mode):
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    provenance = {
        "qubit_ordering": {
            sim_i: res_i.get("qubit_ordering"),
            sim_j: res_j.get("qubit_ordering"),
        },
        "seed": {
            sim_i: res_i.get("seed"),
            sim_j: res_j.get("seed"),
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


def _classify_counts_pair(res_i, res_j, js_div, h_dist, is_cross_group, js_threshold, hellinger_threshold, n_shots):
    sim_i = res_i.get("simulator", "unknown")
    sim_j = res_j.get("simulator", "unknown")
    agreement = "distance_within_threshold"
    if js_div > js_threshold or h_dist > hellinger_threshold:
        agreement = "distance_exceeds_threshold"

    return {
        "simulators": [sim_i, sim_j],
        "mode": "measured",
        "run_status": {
            sim_i: _run_status(res_i),
            sim_j: _run_status(res_j),
        },
        "agreement": agreement,
        "registered_transform": "identity_threshold_check",
        "transform_effect": {
            "js_divergence_delta": 0.0,
            "hellinger_distance_delta": 0.0,
        },
        "metrics": {
            "js_divergence": _json_float(js_div),
            "hellinger_distance": _json_float(h_dist),
            "js_threshold": js_threshold,
            "hellinger_threshold": hellinger_threshold,
            "n_shots": n_shots,
            "is_cross_group": bool(is_cross_group),
        },
        "provenance": _pair_provenance(res_i, res_j, "measured"),
    }


def create_divergence_report(results_list):
    """
    Generates a full report including fidelity and phase.
    Optimized for memory: Parses statevectors ONLY when needed and compares sequentially.
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

    fidelity_tolerance = 1e-12
    phase_tolerance = 1e-12
    normalization_tolerance = 1e-9

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


def _normalize_counts(counts, n_shots):
    """Converts a {bitstring: count} dict to a {bitstring: prob} dict."""
    if n_shots == 0:
        return {}
    return {k: v / n_shots for k, v in counts.items()}


def calculate_hellinger_distance(p, q):
    """
    Calculates the Hellinger distance between two probability distributions.
    """
    return np.linalg.norm(np.sqrt(p) - np.sqrt(q)) / np.sqrt(2)


def create_counts_report(results_list, n_shots):
    """
    Generates a full report on the statistical divergence
    between counts distributions using JS Divergence AND Hellinger Distance.
    """

    simulators = [res.get('simulator', 'unknown') for res in results_list]

    all_bitstrings = set()
    for res in results_list:
        if "counts" in res:
            all_bitstrings.update(res["counts"].keys())

    all_bitstrings = sorted(list(all_bitstrings))
    n_outcomes = len(all_bitstrings)

    prob_vectors = []
    for res in results_list:
        if "counts" in res:
            prob_vec = np.zeros(n_outcomes)

            norm_counts = _normalize_counts(res["counts"], n_shots)

            for i, bitstring in enumerate(all_bitstrings):
                prob_vec[i] = norm_counts.get(bitstring, 0.0)

            prob_vectors.append(prob_vec)
        else:
            prob_vectors.append(None)

    n = len(simulators)

    js_matrix = np.zeros((n, n))
    hellinger_matrix = np.zeros((n, n))

    divergences_found = []
    pairwise_agreement = []

    js_threshold = 0.01
    hellinger_threshold = 0.1

    lsb_sims = [res.get('simulator') for res in results_list if res.get('qubit_ordering') == 'lsb']
    msb_sims = [res.get('simulator') for res in results_list if res.get('qubit_ordering') == 'msb']

    for i in range(n):
        for j in range(i + 1, n):
            sim_i = simulators[i]
            sim_j = simulators[j]
            pv_i = prob_vectors[i]
            pv_j = prob_vectors[j]

            if pv_i is not None and pv_j is not None:

                js_div = (jensenshannon(pv_i, pv_j))**2
                if np.isnan(js_div): js_div = 0.0

                h_dist = calculate_hellinger_distance(pv_i, pv_j)
                if np.isnan(h_dist): h_dist = 0.0

                js_matrix[i, j] = js_div
                js_matrix[j, i] = js_div

                hellinger_matrix[i, j] = h_dist
                hellinger_matrix[j, i] = h_dist

                is_cross_group = False

                if (sim_i in lsb_sims and sim_j in msb_sims) or (sim_i in msb_sims and sim_j in lsb_sims):
                    is_cross_group = True

                pairwise_agreement.append(
                    _classify_counts_pair(
                        results_list[i],
                        results_list[j],
                        js_div,
                        h_dist,
                        is_cross_group,
                        js_threshold,
                        hellinger_threshold,
                        n_shots,
                    )
                )

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
                pairwise_agreement.append(
                    _counts_not_comparable_record(
                        results_list[i],
                        results_list[j],
                        "missing_counts",
                    )
                )

    ordering_map = {res.get('simulator'): res.get('qubit_ordering') for res in results_list if "qubit_ordering" in res}
    return {
        "simulators": simulators,
        "statistical_distance_matrix (js_divergence)": js_matrix.tolist(),
        "hellinger_distance_matrix": hellinger_matrix.tolist(),
        "divergences_found": divergences_found,
        "pairwise_agreement": pairwise_agreement,
        "all_outcomes_observed": all_bitstrings,
        "ordering_map": ordering_map
    }
