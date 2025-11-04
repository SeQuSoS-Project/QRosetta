import numpy as np

def parse_statevector(sv_str_list):
    """Converts a list of complex number strings into a numpy array."""
    return np.array([complex(s) for s in sv_str_list])

def calculate_inner_product(sv1, sv2):
    """
    Calculates the complex inner product of two statevectors.
    We do NOT re-normalize, as this hides fidelity errors.
    """
    if sv1.shape != sv2.shape:
        return complex(0, 0)
        
    # --- THIS IS THE FIX ---
    # We calculate the inner product on the RAW vectors.
    inner_product = np.dot(np.conjugate(sv1), sv2)
    # --- END OF FIX ---
    
    return inner_product

def create_divergence_report(results_list):
    """
    Generates a full report including fidelity, phase,
    and a list of all divergence types.
    """
    simulators = [res.get('simulator', 'unknown') for res in results_list]
    statevectors = []
    
    for res in results_list:
        if "statevector" in res:
            try:
                statevectors.append(parse_statevector(res["statevector"]))
            except Exception as e:
                statevectors.append(None)
        else:
            statevectors.append(None)
            
    n = len(simulators)
    fidelity_matrix = np.ones((n, n))
    phase_matrix = np.zeros((n, n))
    divergences_found = []
    
    # Define our strict tolerances
    fidelity_tolerance = 1e-15
    phase_tolerance = 1e-15
    
    for i in range(n):
        for j in range(i + 1, n):
            sim_i = simulators[i]
            sim_j = simulators[j]
            sv_i = statevectors[i]
            sv_j = statevectors[j]
            
            if sv_i is not None and sv_j is not None:
                inner_product = calculate_inner_product(sv_i, sv_j)
                
                # Fidelity is the squared magnitude of the raw inner product
                fidelity = min(1.0, np.abs(inner_product)**2)
                
                # We calculate phase *after* normalizing,
                # as phase is only meaningful for unit vectors.
                sv1_norm = sv_i / np.linalg.norm(sv_i)
                sv2_norm = sv_j / np.linalg.norm(sv_j)
                norm_inner_product = np.dot(np.conjugate(sv1_norm), sv2_norm)
                relative_phase = np.angle(norm_inner_product)
                
                fidelity_matrix[i, j] = fidelity
                fidelity_matrix[j, i] = fidelity
                phase_matrix[i, j] = relative_phase
                phase_matrix[j, i] = -relative_phase
                
                # Check for a fidelity divergence
                if not np.isclose(fidelity, 1.0, atol=fidelity_tolerance):
                    divergences_found.append({
                        "type": "Fidelity",
                        "simulators": [sim_i, sim_j],
                        "fidelity": fidelity,
                        "relative_phase": relative_phase
                    })
                # Check for a phase-only divergence
                elif not np.isclose(relative_phase, 0.0, atol=phase_tolerance):
                    divergences_found.append({
                        "type": "Phase",
                        "simulators": [sim_i, sim_j],
                        "fidelity": fidelity,
                        "relative_phase": relative_phase
                    })
                    
            else:
                fidelity_matrix[i, j] = -1.0 
                fidelity_matrix[j, i] = -1.0
                
    report = {
        "simulators": simulators,
        "fidelity_matrix": fidelity_matrix.tolist(),
        "relative_phase_matrix": phase_matrix.tolist(),
        "divergences_found": divergences_found
    }
    
    return report