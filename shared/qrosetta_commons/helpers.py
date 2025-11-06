# ./shared/helpers.py
import numpy as np
from collections import Counter
from pytket.circuit import Circuit


def _sample_from_statevector(statevector, n_shots, n_qubits):
    """
    Manually samples from a statevector's probability distribution.
    """
    # 1. Get probabilities
    probabilities = np.abs(statevector)**2
    
    # 2. Get samples
    samples = np.random.choice(
        range(len(statevector)), 
        size=n_shots, 
        p=probabilities
    )
    
    # 3. Count the samples
    sample_counts = Counter(samples)
    
    # 4. Convert integer keys (e.g., 3) to bitstring keys (e.g., "11")
    counts_dict = {
        format(k, f'0{n_qubits}b'): v 
        for k, v in sample_counts.items()
    }
    return counts_dict

def ensure_circuit_is_measurable(tk_circ: Circuit) -> Circuit:
    """
    Checks if a circuit has a classical register 'c' and
    measurements, adding them if they are missing.
    
    This is the logic moved from the rosetta-api.
    """
    n_qubits = tk_circ.n_qubits
    c_reg_name = "c"

    # 1. Add the classical register if it doesn't exist
    if c_reg_name not in [reg.name for reg in tk_circ.c_registers]:
        tk_circ.add_c_register(c_reg_name, n_qubits)

    # 2. Add the measurements
    all_qubits = tk_circ.qubits
    c_register = tk_circ.get_c_register(c_reg_name)
    
    # This loop is what was in the rosetta-api [cite: 114]
    for i in range(n_qubits):
        tk_circ.Measure(all_qubits[i], c_register[i])
        
    return tk_circ