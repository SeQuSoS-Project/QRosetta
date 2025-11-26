
import sys
import os
import numpy as np
import time

# Add the 'shared' directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
shared_dir = os.path.join(project_root, 'shared')
sys.path.insert(0, shared_dir)

from qrosetta_commons.helpers import MemoryMonitor, calculate_theoretical_memory_mb

def test_memory_monitor_captures_spike():
    """
    Tests if the MemoryMonitor can capture a sudden memory allocation.
    """
    print("Running Verification...")
    
    # We will allocate 100 MB of doubles (8 bytes each) -> ~12.5 million items
    # 100 MB = 100 * 1024 * 1024 bytes
    target_mb = 100
    
    with MemoryMonitor(interval=0.001) as monitor:
        # 1. Allocate 100MB in C++ (numpy backend)
        print(f"Allocating {target_mb} MB...")
        arr = np.ones(int(target_mb * 1024 * 1024 / 8), dtype=np.float64)
        
        # 2. Sleep briefly to ensure the 1ms poll catches it
        time.sleep(0.1) 
        
        # 3. Free it
        del arr
        
    measured_mb = monitor.get_peak_usage_mb()
    print(f"Actual Allocation: {target_mb} MB")
    print(f"Measured Peak:     {measured_mb:.2f} MB")

    assert abs(measured_mb - target_mb) < 5, "The monitor failed to capture the C++ memory spike."

def test_theoretical_memory_calculation():
    """
    Tests the theoretical memory calculation for a few qubit sizes.
    """
    # Test case 1: 10 qubits
    # (2^10 * 16) / (1024*1024) = (1024 * 16) / (1024*1024) = 16/1024 = 0.015625
    assert abs(calculate_theoretical_memory_mb(10) - 0.015625) < 1e-9

    # Test case 2: 20 qubits
    # (2^20 * 16) / (1024*1024) = (1024*1024 * 16) / (1024*1024) = 16
    assert abs(calculate_theoretical_memory_mb(20) - 16.0) < 1e-9

    # Test case 3: 24 qubits
    # (2^24 * 16) / (1024*1024) = (16 * 1024 * 1024 * 16) / (1024*1024) = 256
    assert abs(calculate_theoretical_memory_mb(24) - 256.0) < 1e-9

if __name__ == "__main__":
    test_memory_monitor_captures_spike()
    test_theoretical_memory_calculation()
    print("✅ All memory tests passed!")
