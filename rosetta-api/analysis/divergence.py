from qrosetta_commons.helpers import get_logger, decode_statevector
import numpy as np
from scipy.spatial.distance import jensenshannon

logger = get_logger(__name__)

def parse_statevector(sv_data):
    """Converts a statevector (Base64 string or list) into a numpy array."""
    if sv_data is None:
        return np.array([])
    
    if isinstance(sv_data, str):
        # New format: Base64 string
        return decode_statevector(sv_data)
    elif isinstance(sv_data, list):
        # Legacy format: List of strings
        if not sv_data:
            return np.array([])
        return np.array([complex(s) for s in sv_data])
    else:
        raise ValueError(f"Unknown statevector format: {type(sv_data)}")

def create_divergence_report(results_list):
    """
    Generates a full report including fidelity and phase.
    Optimized for memory: Parses statevectors ONLY when needed and compares sequentially.
    """
    import gc

    # --- 0. Qubit ordering consistency check ---
    # Warn if results mix LSB and MSB conventions — fidelity comparisons between
    # simulators with different orderings are mathematically meaningless.
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

    # --- 1. Filter & Setup ---
    # Only keep valid results
    valid_results = [res for res in results_list if "error" not in res and "statevector" in res]
    simulators = [res.get('simulator', 'unknown') for res in results_list]  # All simulators (for the matrix headers)
    
    # Map simulator name to its result index in valid_results (if it exists)
    sim_to_valid_idx = {}
    for i, res in enumerate(valid_results):
        sim_to_valid_idx[res.get('simulator')] = i

    n_total = len(simulators)
    
    # Initialize matrices with -1 (Error/Skip)
    fidelity_matrix = np.full((n_total, n_total), -1.0)
    phase_matrix = np.zeros((n_total, n_total))
    
    divergences_found = []
    
    # Tolerances
    fidelity_tolerance = 1e-12
    phase_tolerance = 1e-12
    normalization_tolerance = 1e-9

    # --- 2. Pairwise Comparison (Memory Optimized) ---
    logger.info("Starting sequential divergence comparison...")

    for i in range(n_total):
        sim_i_name = simulators[i]
        
        # Check if sim_i has a valid result
        if sim_i_name not in sim_to_valid_idx:
            continue
            
        # Load Statevector I (On-Demand)
        try:
            res_i = valid_results[sim_to_valid_idx[sim_i_name]]
            sv_i = parse_statevector(res_i["statevector"])
            norm_i = np.linalg.norm(sv_i)
            
            # Check Norm I
            if not np.isclose(norm_i, 1.0, atol=normalization_tolerance):
                 divergences_found.append({
                    "type": "Normalization",
                    "simulator": sim_i_name,
                    "norm": float(norm_i)
                })
            
            # Normalize I to save repeated calc
            sv_i_norm = sv_i / norm_i
            
        except Exception as e:
            logger.error(f"Failed to load statevector for {sim_i_name}: {e}")
            continue

        # Valid I loaded. Now compare against J > i
        for j in range(i + 1, n_total):
            sim_j_name = simulators[j]
            
            if sim_j_name not in sim_to_valid_idx:
                continue

            # Load Statevector J (On-Demand)
            try:
                res_j = valid_results[sim_to_valid_idx[sim_j_name]]
                sv_j = parse_statevector(res_j["statevector"])
                
                # Check Shape Mismatch
                if sv_i.shape != sv_j.shape:
                    fidelity_matrix[i, j] = 0.0
                    fidelity_matrix[j, i] = 0.0
                    divergences_found.append({
                        "type": "Shape Mismatch",
                        "simulators": [sim_i_name, sim_j_name],
                        "shapes": [sv_i.shape, sv_j.shape]
                    })
                    del sv_j # Free J immediately
                    continue

                norm_j = np.linalg.norm(sv_j)
                
                sv_j_norm = sv_j / norm_j
                
                # --- CALCULATION ---
                inner_product = np.dot(np.conjugate(sv_i_norm), sv_j_norm)
                fidelity = np.abs(inner_product)**2
                relative_phase = np.angle(inner_product)

                # Clamp
                if np.isclose(fidelity, 1.0, atol=fidelity_tolerance): fidelity = 1.0
                if np.isclose(relative_phase, 0.0, atol=phase_tolerance): relative_phase = 0.0

                # Store
                fidelity_matrix[i, j] = fidelity
                fidelity_matrix[j, i] = fidelity
                phase_matrix[i, j] = relative_phase
                phase_matrix[j, i] = -relative_phase
                
                # Divergence Reports
                is_cross_group = (lsb_sims and msb_sims and 
                                 ((sim_i_name in lsb_sims and sim_j_name in msb_sims) or 
                                  (sim_i_name in msb_sims and sim_j_name in lsb_sims)))
                
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
                
                # Free J immediately
                del sv_j
                del sv_j_norm
                
            except Exception as e:
                logger.error(f"Error comparing {sim_i_name} vs {sim_j_name}: {e}")
                fidelity_matrix[i, j] = -1.0
                fidelity_matrix[j, i] = -1.0
        
        # Free I after inner loop
        del sv_i
        del sv_i_norm
        gc.collect() # Aggressive GC

    report = {
        "simulators": simulators,
        "fidelity_matrix": fidelity_matrix.tolist(),
        "relative_phase_matrix": phase_matrix.tolist(),
        "divergences_found": divergences_found,
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
    
    # Get all bitstring outcomes observed by *any* simulator
    all_bitstrings = set()
    for res in results_list:
        if "counts" in res:
            all_bitstrings.update(res["counts"].keys())
    
    # Create a sorted, canonical list of all possible outcomes
    all_bitstrings = sorted(list(all_bitstrings))
    n_outcomes = len(all_bitstrings)
    
    # Create aligned probability vectors for each simulator
    prob_vectors = []
    for res in results_list:
        if "counts" in res:
            prob_vec = np.zeros(n_outcomes)
            # Normalize the raw counts to get a probability distribution
            norm_counts = _normalize_counts(res["counts"], n_shots)
            
            # Map the simulator's probabilities to the canonical list
            for i, bitstring in enumerate(all_bitstrings):
                prob_vec[i] = norm_counts.get(bitstring, 0.0)
            
            prob_vectors.append(prob_vec)
        else:
            prob_vectors.append(None) # For failed simulators

    n = len(simulators)
    
    # Initialize matrices
    js_matrix = np.zeros((n, n))
    hellinger_matrix = np.zeros((n, n))
    
    divergences_found = []
    
    # Thresholds
    js_threshold = 0.01 
    hellinger_threshold = 0.1 # Hellinger is more sensitive

    for i in range(n):
        for j in range(i + 1, n):
            sim_i = simulators[i]
            sim_j = simulators[j]
            pv_i = prob_vectors[i]
            pv_j = prob_vectors[j]
            
            # Only compare if both simulators returned valid counts
            if pv_i is not None and pv_j is not None:
                # 1. JS Divergence
                js_div = (jensenshannon(pv_i, pv_j))**2
                if np.isnan(js_div): js_div = 0.0
                
                # 2. Hellinger Distance
                h_dist = calculate_hellinger_distance(pv_i, pv_j)
                if np.isnan(h_dist): h_dist = 0.0

                # Populate Matrices
                js_matrix[i, j] = js_div
                js_matrix[j, i] = js_div
                
                hellinger_matrix[i, j] = h_dist
                hellinger_matrix[j, i] = h_dist
                
                # Check thresholds
                is_cross_group = False 
                # Re-calculate split if needed or just pass it in
                lsb_sims = [res.get('simulator') for res in results_list if res.get('qubit_ordering') == 'lsb']
                msb_sims = [res.get('simulator') for res in results_list if res.get('qubit_ordering') == 'msb']
                if (sim_i in lsb_sims and sim_j in msb_sims) or (sim_i in msb_sims and sim_j in lsb_sims):
                    is_cross_group = True

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
                
    ordering_map = {res.get('simulator'): res.get('qubit_ordering') for res in results_list if "qubit_ordering" in res}
    return {
        "simulators": simulators,
        "statistical_distance_matrix (js_divergence)": js_matrix.tolist(),
        "hellinger_distance_matrix": hellinger_matrix.tolist(),
        "divergences_found": divergences_found,
        "all_outcomes_observed": all_bitstrings,
        "ordering_map": ordering_map
    }
