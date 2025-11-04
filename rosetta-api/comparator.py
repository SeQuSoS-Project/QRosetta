import numpy as np
import cmath

def parse_statevector(sv_str_list):
    """Converts a list of complex number strings into a numpy array."""
    return np.array([complex(s) for s in sv_str_list])

def calculate_fidelity(sv1, sv2):
    """
    Calculates the fidelity between two statevectors.
    Fidelity = |<sv1|sv2>|^2
    """
    if sv1.shape != sv2.shape:
        return 0.0
        
    sv1_norm = sv1 / np.linalg.norm(sv1)
    sv2_norm = sv2 / np.linalg.norm(sv2)
    
    inner_product = np.dot(np.conjugate(sv1_norm), sv2_norm)
    
    # --- FIX 1: Clamp fidelity to a max of 1.0 ---
    # This prevents floating-point errors like 1.000...04
    fidelity = min(1.0, np.abs(inner_product)**2)
    
    return fidelity

def create_divergence_report(results_list):
    """
    Takes the 'results' list from our API and generates a
    fidelity matrix and a list of divergences.
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
    divergences_found = []
    
    for i in range(n):
        for j in range(i + 1, n):
            sim_i = simulators[i]
            sim_j = simulators[j]
            sv_i = statevectors[i]
            sv_j = statevectors[j]
            
            if sv_i is not None and sv_j is not None:
                fidelity = calculate_fidelity(sv_i, sv_j)
                fidelity_matrix[i, j] = fidelity
                fidelity_matrix[j, i] = fidelity
                
                # --- FIX 2: Make the tolerance extremely small ---
                # We catch any deviation beyond the 16th decimal.
                if not np.isclose(fidelity, 1.0, rtol=1e-17, atol=1e-17):
                # --- END OF FIX ---
                    divergences_found.append({
                        "simulators": [sim_i, sim_j],
                        "fidelity": fidelity,
                        "is_divergent": True
                    })
            else:
                fidelity_matrix[i, j] = 0.0 
                fidelity_matrix[j, i] = 0.0
                
    report = {
        "simulators": simulators,
        "fidelity_matrix": fidelity_matrix.tolist(),
        "divergences_found": divergences_found
    }
    
    return report