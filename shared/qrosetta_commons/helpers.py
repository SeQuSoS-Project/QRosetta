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
