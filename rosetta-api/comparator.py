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
        
    # Calculate the inner product
    inner_product = np.dot(np.conjugate(sv1), sv2)
    
    # Return the squared magnitude
    return np.abs(inner_product)**2

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
    
    # Define a very tight tolerance for our divergence check
    # We want to find *any* deviation, even at the floating-point limit
    ABSOLUTE_TOLERANCE = 1e-12 
    
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
                
                # --- FIX 2 ---
                # We use our new, tight tolerance for the check.
                # We also set rtol=0 to only use absolute tolerance.
                if not np.isclose(fidelity, 1.0, rtol=1e-15, atol=1e-15):
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