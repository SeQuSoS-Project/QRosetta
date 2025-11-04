import numpy as np

def parse_statevector(sv_str_list):
    """Converts a list of complex number strings into a numpy array."""
    if not sv_str_list:
        return np.array([])
    return np.array([complex(s) for s in sv_str_list])

def create_divergence_report(results_list):
    """
    Generates a full report including fidelity, phase,
    and a list of all divergence types (Normalization, Fidelity, Phase).
    
    Args:
        results_list (list): The "raw_results" list from main.py, where
                             each item is a dict from a runner.
                             
    Returns:
        dict: A full divergence report.
    """
    
    # --- 1. Data Preparation ---
    
    simulators = []
    statevectors = []
    
    for res in results_list:
        simulators.append(res.get('simulator', 'unknown'))
        if "statevector" in res:
            try:
                statevectors.append(parse_statevector(res["statevector"]))
            except Exception as e:
                print(f"Error parsing statevector from {res.get('simulator')}: {e}")
                statevectors.append(None) # Add None to keep lists in sync
        else:
            statevectors.append(None) # Add None if simulator failed

    n = len(simulators)
    
    # Initialize matrices
    fidelity_matrix = np.ones((n, n))
    phase_matrix = np.zeros((n, n))
    
    # List to hold all found divergences
    divergences_found = []
    
    # Define our strict tolerances for comparison
    fidelity_tolerance = 1e-12
    phase_tolerance = 1e-12
    normalization_tolerance = 1e-9 # A bit looser for the initial norm check

    # --- 2. Pairwise Comparison ---

    for i in range(n):
        for j in range(i + 1, n):
            sim_i = simulators[i]
            sim_j = simulators[j]
            sv_i = statevectors[i]
            sv_j = statevectors[j]
            
            # Mark as -1 (Error/Skip) if either vector is missing
            if sv_i is None or sv_j is None or sv_i.size == 0 or sv_j.size == 0:
                fidelity_matrix[i, j] = -1.0
                fidelity_matrix[j, i] = -1.0
                continue
                
            if sv_i.shape != sv_j.shape:
                fidelity_matrix[i, j] = 0.0 # Vectors are different shapes
                fidelity_matrix[j, i] = 0.0
                divergences_found.append({
                    "type": "Shape Mismatch",
                    "simulators": [sim_i, sim_j],
                    "shapes": [sv_i.shape, sv_j.shape]
                })
                continue

            # --- 3. Analysis ---
            
            try:
                # A. Check for Normalization Divergence (on raw vectors)
                norm_i = np.linalg.norm(sv_i)
                norm_j = np.linalg.norm(sv_j)
                
                if not np.isclose(norm_i, 1.0, atol=normalization_tolerance):
                    divergences_found.append({
                        "type": "Normalization",
                        "simulator": sim_i,
                        "norm": norm_i
                    })
                
                if not np.isclose(norm_j, 1.0, atol=normalization_tolerance):
                    divergences_found.append({
                        "type": "Normalization",
                        "simulator": sim_j,
                        "norm": norm_j
                    })

                # B. Calculate Fidelity and Phase (on normalized vectors)
                # This is the correct way: normalize FIRST, then compare.
                # This prevents floating point norm errors from polluting fidelity.
                sv_i_norm = sv_i / norm_i
                sv_j_norm = sv_j / norm_j
                
                # Use the normalized vectors for the one, true inner product
                inner_product = np.dot(np.conjugate(sv_i_norm), sv_j_norm)
                
                # Fidelity is the squared magnitude of the normalized inner product
                fidelity = np.abs(inner_product)**2
                
                # Relative phase is the angle of that same inner product
                relative_phase = np.angle(inner_product)

                # Clamp fidelity near 1.0 for floating point precision
                if np.isclose(fidelity, 1.0, atol=fidelity_tolerance):
                    fidelity = 1.0
                
                # Clamp phase near 0.0 for floating point precision
                if np.isclose(relative_phase, 0.0, atol=phase_tolerance):
                    relative_phase = 0.0

                # C. Populate matrices and report divergences
                fidelity_matrix[i, j] = fidelity
                fidelity_matrix[j, i] = fidelity
                phase_matrix[i, j] = relative_phase
                phase_matrix[j, i] = -relative_phase
                
                # Check for a *Fidelity* divergence (physically different states)
                if fidelity < (1.0 - fidelity_tolerance):
                    divergences_found.append({
                        "type": "Fidelity",
                        "simulators": [sim_i, sim_j],
                        "fidelity": fidelity,
                        "relative_phase": relative_phase
                    })
                # Check for a *Phase-only* divergence (physically same state, different convention)
                elif relative_phase != 0.0:
                    divergences_found.append({
                        "type": "Phase",
                        "simulators": [sim_i, sim_j],
                        "fidelity": 1.0, # We know it's 1.0 from the 'elif'
                        "relative_phase": relative_phase
                    })

            except Exception as e:
                print(f"Error comparing {sim_i} and {sim_j}: {e}")
                fidelity_matrix[i, j] = -1.0 # Mark as Error
                fidelity_matrix[j, i] = -1.0

    # --- 4. Final Report Assembly ---
    
    report = {
        "simulators": simulators,
        "fidelity_matrix": fidelity_matrix.tolist(),
        "relative_phase_matrix": phase_matrix.tolist(),
        "divergences_found": divergences_found
    }
    
    return report