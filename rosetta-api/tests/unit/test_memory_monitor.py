# Tests for qrosetta_commons MemoryMonitor.

import sys
import os
import numpy as np
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
shared_dir = os.path.join(project_root, 'shared')
sys.path.insert(0, shared_dir)

from qrosetta_commons.helpers import MemoryMonitor

def test_memory_monitor_captures_spike():
    """MemoryMonitor captures a sudden allocation."""
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

def test_lifetime_peak_is_never_below_a_window_peak(monkeypatch):
    """A window peak above the VmHWM read afterwards is folded into the lifetime peak."""
    from qrosetta_commons import memory

    mib = 1024 * 1024
    status = {"VmHWM": 150 * mib, "VmRSS": 100 * mib}
    monkeypatch.setattr(memory, "_read_status_bytes", lambda field: status.get(field))
    monkeypatch.setattr(memory, "_lifetime_hwm_bytes", 0)

    monitor = memory.MemoryMonitor()
    monitor.method = "vmhwm"
    monitor.baseline_memory = 100 * mib
    monitor.peak_memory = 170 * mib
    monitor.__exit__(None, None, None)

    peak_mb, method = memory.lifetime_peak_rss()
    assert method == "vmhwm"
    assert peak_mb >= monitor.get_process_peak_mb() == 170


def test_lifetime_peak_fallback_includes_sampled_window(monkeypatch):
    from qrosetta_commons import memory

    monkeypatch.setattr(memory, "_read_status_bytes", lambda field: None)
    monkeypatch.setattr(memory, "_lifetime_hwm_bytes", 10 ** 13)
    peak_mb, method = memory.lifetime_peak_rss()
    assert method == "getrusage"
    assert peak_mb == 10 ** 13 / (1024 * 1024)


if __name__ == "__main__":
    test_memory_monitor_captures_spike()

    print("✅ All memory tests passed!")
