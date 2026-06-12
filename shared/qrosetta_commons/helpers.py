# Shared common utilities for the Rosetta ecosystem.

import numpy as np
from collections import Counter
import time
import psutil
import threading
import os
import logging
import sys
import functools
import importlib.metadata

import base64

MAX_QUBITS_STATEVECTOR = int(os.getenv("MAX_QUBITS_STATEVECTOR", "18"))
MAX_QUBITS_MEASURED = int(os.getenv("MAX_QUBITS_MEASURED", "24"))

def get_logger(service_name: str) -> logging.Logger:
    """
    Configures a structured logger that outputs to stdout.
    Format: [Timestamp] [Level] [Service] Message
    """
    logger = logging.getLogger(service_name)

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

def encode_statevector(statevector: np.ndarray) -> str:
    """
    Serializes a NumPy array (complex128) to a Base64 string.
    """

    if statevector.dtype != np.complex128:
        statevector = statevector.astype(np.complex128)
    return base64.b64encode(statevector.tobytes()).decode('utf-8')

def decode_statevector(encoded_str: str) -> np.ndarray:
    """
    Deserializes a Base64 string back to a NumPy array (complex128).
    """
    try:
        bytes_data = base64.b64decode(encoded_str)
        return np.frombuffer(bytes_data, dtype=np.complex128)
    except Exception as e:

        raise ValueError(f"Failed to decode statevector: {e}")

def _sample_from_statevector(statevector, n_shots, n_qubits):
    """
    Manually samples from a statevector's probability distribution.
    """

    probabilities = np.abs(statevector)**2

    samples = np.random.choice(
        range(len(statevector)),
        size=n_shots,
        p=probabilities
    )

    sample_counts = Counter(samples)

    counts_dict = {
        format(k, f'0{n_qubits}b'): v
        for k, v in sample_counts.items()
    }
    return counts_dict

class MemoryMonitor:
    def __init__(self, interval=0.001):
        """
        interval: Sampling rate in seconds.
        0.001 (1ms) is fast enough to catch C++ spikes
        without slowing down the simulation significantly.
        """
        self.interval = interval
        self.process = psutil.Process(os.getpid())
        self.keep_measuring = True
        self.peak_memory = 0
        self.start_memory = 0
        self.baseline_memory = 0

    def _measure_loop(self):
        while self.keep_measuring:

            current_mem = self.process.memory_info().rss
            if current_mem > self.peak_memory:
                self.peak_memory = current_mem
            time.sleep(self.interval)

    def __enter__(self):

        self.baseline_memory = self.process.memory_info().rss
        self.peak_memory = self.baseline_memory

        self.keep_measuring = True
        self.thread = threading.Thread(target=self._measure_loop)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        self.keep_measuring = False
        self.thread.join()

    def get_peak_usage_mb(self):

        return (self.peak_memory - self.baseline_memory) / (1024 * 1024)

    def get_process_peak_mb(self):

        return self.peak_memory / (1024 * 1024)

def theoretical_statevector_mb(n_qubits: int) -> float:
    """
    Minimum memory to store a full statevector for n_qubits in complex128.
    = 2^N amplitudes × 16 bytes each.
    This is a lower-bound reference; actual runtime usage is always higher
    due to working buffers, compilation state, and intermediate tensors.
    Not meaningful for tensor-network simulators (report None for those).
    """
    return (2 ** n_qubits * 16) / (1024 ** 2)

def get_num_qubits_from_qasm(qasm_string: str) -> int:
    """
    Parses QASM string to find the size of the 'qreg'.
    Returns 0 if not found (or raises error if strict).
    """
    for line in qasm_string.split('\n'):
        if line.strip().startswith("qreg"):
            try:

                return int(line.split('[')[1].split(']')[0])
            except Exception:
                pass
    return 0

def strip_barriers_from_qasm(qasm_string: str) -> str:
    """Remove barrier instructions from QASM before simulation.
    Barriers are visual hints only — they don't affect the statevector.
    Some C++ backends (lightning.qubit) raise errors on qml.Barrier at larger wire counts."""
    return '\n'.join(
        line for line in qasm_string.split('\n')
        if not line.strip().startswith('barrier')
    )

def check_qubits_limit(qasm_string: str, max_qubits: int = 24):
    """
    Raises ValueError if the circuit has more qubits than allowed.
    24 qubits ~ 268 MB statevector (complex128).
    25 qubits ~ 536 MB statevector (OOM on 512 MiB local container,
    fits within 1 GiB K8s runner pod).
    """
    n_qubits = get_num_qubits_from_qasm(qasm_string)
    if n_qubits > max_qubits:
        raise ValueError(f"Circuit has {n_qubits} qubits, which exceeds the limit of {max_qubits} for this runner.")


# Distribution-name substrings that identify the quantum SDK packages worth recording
# for provenance. A runner's image is isolated and only contains its own stack, so
# scanning installed distributions for these yields exactly that runner's quantum
# dependencies (e.g. pytket + pytket-qiskit + qiskit + qiskit-aer for the qiskit runner).
_SDK_VERSION_KEYWORDS = (
    "qiskit", "cirq", "qulacs", "pennylane", "qibo", "pytket", "cuquantum",
    "custatevec", "torch", "quimb", "myqlm", "qat", "qrisp", "pyquil",
    "braket", "projectq",
)

_sdk_versions_cache = None

def get_sdk_versions() -> dict:
    """Return {distribution_name: version} for the quantum SDK packages installed in
    this process, read from importlib.metadata at runtime.

    This is ground truth — the exact versions that executed the circuit — not a
    declared pin scraped from a requirements.txt. It is the version coordinate the
    cross-simulator compatibility matrix and RO-Crate provenance attribute outcomes to.
    Versions are fixed for a process's lifetime, so the scan is cached after first call.
    """
    global _sdk_versions_cache
    if _sdk_versions_cache is not None:
        return dict(_sdk_versions_cache)
    versions = {}
    try:
        for dist in importlib.metadata.distributions():
            try:
                name = dist.metadata["Name"]
            except Exception:
                name = None
            if name and any(k in name.lower() for k in _SDK_VERSION_KEYWORDS):
                versions[name] = dist.version
    except Exception:
        pass
    _sdk_versions_cache = versions
    return dict(versions)

def with_sdk_versions(func):
    """Decorator for a runner's process_run / process_run_measured.

    Attaches the executed SDK versions (get_sdk_versions) to the returned result dict
    under 'sdk_versions'. Wrapping the function rather than each return statement means
    both the success and the error paths carry the version — and the error path is the
    one the compatibility matrix cares about most (which version rejected which gate).
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, dict) and "sdk_versions" not in result:
            result["sdk_versions"] = get_sdk_versions()
        return result
    return wrapper