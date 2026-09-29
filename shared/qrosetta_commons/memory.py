"""Process memory measurement: kernel high-water mark (VmHWM) with a sampling fallback."""

import os
import resource
import threading
import time

import psutil

_MIB = 1024 * 1024
_STATUS_PATH = "/proc/self/status"
_CLEAR_REFS_PATH = "/proc/self/clear_refs"

_lifetime_hwm_bytes = 0


def _read_status_bytes(field):
    """Return a ``/proc/self/status`` kB field (e.g. ``VmHWM``) in bytes, or None."""
    try:
        with open(_STATUS_PATH) as fh:
            for line in fh:
                if line.startswith(field + ":"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _reset_hwm():
    """Reset this process's VmHWM to its current RSS. Returns False if unsupported.

    The high-water mark reached so far is kept in ``_lifetime_hwm_bytes`` first, so
    ``lifetime_peak_rss`` still covers the whole process life.
    """
    global _lifetime_hwm_bytes
    hwm = _read_status_bytes("VmHWM")
    if hwm is None:
        return False
    try:
        with open(_CLEAR_REFS_PATH, "w") as fh:
            fh.write("5")
    except OSError:
        return False
    _lifetime_hwm_bytes = max(_lifetime_hwm_bytes, hwm)
    return True


def lifetime_peak_rss():
    """Peak RSS of this process over its whole life, as ``(mib, method)``.

    Never lower than any MemoryMonitor window peak recorded in this process.
    ``method`` is ``"vmhwm"`` (kernel high-water mark, adjusted for resets done by
    MemoryMonitor) or ``"getrusage"`` (ru_maxrss, which in a spawned child also
    includes the parent's peak).
    """
    hwm = _read_status_bytes("VmHWM")
    if hwm is not None:
        return max(hwm, _lifetime_hwm_bytes) / _MIB, "vmhwm"
    maxrss_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return max(maxrss_mib, _lifetime_hwm_bytes / _MIB), "getrusage"


class MemoryMonitor:
    """Peak RSS of the current process inside a ``with`` block.

    Uses the kernel high-water mark when ``/proc/self/clear_refs`` is writable
    (``method == "vmhwm"``), else a background thread sampling RSS every
    ``interval`` seconds (``method == "sampled_<N>ms"``).
    """

    def __init__(self, interval=0.001):
        self.interval = interval
        self.process = psutil.Process(os.getpid())
        self.method = None
        self.baseline_memory = 0
        self.peak_memory = 0
        self._keep_measuring = False
        self._thread = None

    def _sample(self):
        current = self.process.memory_info().rss
        if current > self.peak_memory:
            self.peak_memory = current

    def _measure_loop(self):
        while self._keep_measuring:
            self._sample()
            time.sleep(self.interval)

    def __enter__(self):
        if _reset_hwm():
            self.method = "vmhwm"
            self.baseline_memory = _read_status_bytes("VmRSS")
            self.peak_memory = self.baseline_memory
            return self

        self.method = f"sampled_{round(self.interval * 1000)}ms"
        self.baseline_memory = self.process.memory_info().rss
        self.peak_memory = self.baseline_memory
        self._keep_measuring = True
        self._thread = threading.Thread(target=self._measure_loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _lifetime_hwm_bytes
        if self.method == "vmhwm":
            hwm = _read_status_bytes("VmHWM")
            if hwm is not None:
                self.peak_memory = max(self.peak_memory, hwm)
        else:
            self._keep_measuring = False
            self._thread.join()
            self._sample()
        _lifetime_hwm_bytes = max(_lifetime_hwm_bytes, self.peak_memory)

    def get_peak_usage_mb(self):
        """Peak RSS inside the block minus RSS at entry, in MiB."""
        return (self.peak_memory - self.baseline_memory) / _MIB

    def get_process_peak_mb(self):
        """Peak RSS inside the block, in MiB."""
        return self.peak_memory / _MIB
