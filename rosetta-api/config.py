import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Category 1: Native Samplers
    PYTKET_QISKIT_RUNNER_URL: str = "http://pytket-qiskit-runner:8000"
    PYTKET_CIRQ_RUNNER_URL: str = "http://pytket-cirq-runner:8000"
    PYTKET_QULACS_RUNNER_URL: str = "http://pytket-qulacs-runner:8000"
    PYTKET_BRAKET_RUNNER_URL: str = "http://pytket-braket-runner:8000"

    # Category 2: Statevector Samplers
    PYTKET_PROJECTQ_RUNNER_URL: str = "http://pytket-projectq-runner:8000"
    PYTKET_QUEST_RUNNER_URL: str = "http://pytket-quest-runner:8000"
    PENNYLANE_LIGHTNING_RUNNER_URL: str = "http://pennylane-lightning-runner:8000"
    PENNYLANE_DEFAULT_RUNNER_URL: str = "http://pennylane-default-runner:8000"
    QSIM_CIRQ_RUNNER_URL: str = "http://qsim-cirq-runner:8000"
    QIBO_RUNNER_URL: str = "http://qibo-runner:8000"
    QRISP_RUNNER_URL: str = "http://qrisp-runner:8000"
    MYQLM_RUNNER_URL: str = "http://myqlm-runner:8000"
    PYQUIL_RUNNER_URL: str = "http://pyquil-runner:8000"
    TORCHQUANTUM_RUNNER_URL: str = "http://torch-quantum-runner:8000"
    QUIMB_RUNNER_URL: str = "http://quimb-runner:8000"
    CUQUANTUM_RUNNER_URL: str = "http://cuquantum-runner:8000"

    # Timeouts
    RUNNER_TIMEOUT_SEC: int = 60

    # Storage Configuration
    STORAGE_MODE: str = os.getenv("STORAGE_MODE", "local")  # Options: 'local', 's3'
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "minioadmin")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "qrosetta-runs")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")

    # Safeguards
    MAX_QUBITS_STATEVECTOR: int = 18
    MAX_QUBITS_MEASURED: int = 24

    class Config:
        env_file = ".env"

    def get_runner_services(self):
        return {
            # Category 1: Native Samplers (work with our modified QASM)
            "qiskit": {
                "base_url": self.PYTKET_QISKIT_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            },
            "cirq":   {
                "base_url": self.PYTKET_CIRQ_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            },
            "qulacs": {
                "base_url": self.PYTKET_QULACS_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            },
            "braket": {
                "base_url": self.PYTKET_BRAKET_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": False  # Consistent errors — set True to re-enable
            },

            # Category 2: Statevector Samplers (need original QASM)
            "projectq": {
                "base_url": self.PYTKET_PROJECTQ_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": False  # Consistent errors — set True to re-enable
            },
            "quest":  {
                "base_url": self.PYTKET_QUEST_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True
            },
            "pennylane-lightning":  {
                "base_url": self.PENNYLANE_LIGHTNING_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True
            },
            "pennylane-default":  {
                "base_url": self.PENNYLANE_DEFAULT_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True
            },
            "qsim-cirq": {
                "base_url": self.QSIM_CIRQ_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            },
            "qibo": {
                "base_url": self.QIBO_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            },
            "qrisp": {
                "base_url": self.QRISP_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            },
            "myqlm": {
                "base_url": self.MYQLM_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            },
            "pyquil": {
                "base_url": self.PYQUIL_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            },
            "torchquantum": {
                "base_url": self.TORCHQUANTUM_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True
            },
            "quimb": {
                "base_url": self.QUIMB_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            },
            "cuquantum": {
                "base_url": self.CUQUANTUM_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True
            }
        }

settings = Settings()
