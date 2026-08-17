# Unit and integration tests.

import sys
import os
import numpy as np
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
shared_dir = os.path.join(project_root, 'shared')
sys.path.insert(0, shared_dir)

from qrosetta_commons.helpers import MemoryMonitor

def test_memory_monitor_captures_spike():
    """
    Tests if the MemoryMonitor can capture a sudden memory allocation.
    """
    print("Running Verification...")

    target_mb = 100

    with MemoryMonitor(interval=0.001) as monitor:

        print(f"Allocating {target_mb} MB...")
        arr = np.ones(int(target_mb * 1024 * 1024 / 8), dtype=np.float64)

        time.sleep(0.1)

        del arr

    measured_mb = monitor.get_peak_usage_mb()
    print(f"Actual Allocation: {target_mb} MB")
    print(f"Measured Peak:     {measured_mb:.2f} MB")

    assert abs(measured_mb - target_mb) < 5, "The monitor failed to capture the C++ memory spike."

if __name__ == "__main__":
    test_memory_monitor_captures_spike()

    print("✅ All memory tests passed!")
