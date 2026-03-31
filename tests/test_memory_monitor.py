
import sys
import os
import numpy as np
import time

# Add the 'shared' directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
shared_dir = os.path.join(project_root, 'shared')
sys.path.insert(0, shared_dir)

from qrosetta_commons.helpers import MemoryMonitor

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



if __name__ == "__main__":
    test_memory_monitor_captures_spike()

    print("✅ All memory tests passed!")
