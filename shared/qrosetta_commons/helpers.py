import numpy as np
from collections import Counter
import time
import psutil
import threading
import os
import logging
import sys

import base64

def get_logger(service_name: str) -> logging.Logger:
    """
    Configures a structured logger that outputs to stdout.
    Format: [Timestamp] [Level] [Service] Message
    """
    logger = logging.getLogger(service_name)
    
    # Prevent duplicate logs if get_logger is called multiple times
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
    # Ensure it's complex128
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
        # Fallback for legacy list-of-strings format if needed, or just re-raise
        raise ValueError(f"Failed to decode statevector: {e}")

def calculate_theoretical_memory_mb(num_qubits):
    """
    Calculates the theoretical memory required to store a statevector in MB.
    Formula: (2^num_qubits * 16) / (1024 * 1024), where 16 bytes are for complex128.
    """
    return (2**num_qubits * 16) / (1024 * 1024)

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
            # fast access to RSS (Resident Set Size)
            current_mem = self.process.memory_info().rss
            if current_mem > self.peak_memory:
                self.peak_memory = current_mem
            time.sleep(self.interval)

    def __enter__(self):
        # 1. Record baseline (what the server uses at rest)
        self.baseline_memory = self.process.memory_info().rss
        self.peak_memory = self.baseline_memory
        
        # 2. Start the background spy
        self.keep_measuring = True
        self.thread = threading.Thread(target=self._measure_loop)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 3. Stop measuring
        self.keep_measuring = False
        self.thread.join()

    def get_peak_usage_mb(self):
        # Peak usage is the highest point reached minus the baseline
        return (self.peak_memory - self.baseline_memory) / (1024 * 1024)

    def get_process_peak_mb(self):
        # Absolute peak RSS memory usage of the process
        return self.peak_memory / (1024 * 1024)