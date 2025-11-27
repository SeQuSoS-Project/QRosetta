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

    class Config:
        env_file = ".env"

    def get_runner_services(self):
        return {
            # Category 1: Native Samplers (work with our modified QASM)
            "pytket-qiskit-runner": {
                "base_url": self.PYTKET_QISKIT_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"]
            },
            "pytket-cirq-runner":   {
                "base_url": self.PYTKET_CIRQ_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"]
            },
            "pytket-qulacs-runner": {
                "base_url": self.PYTKET_QULACS_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"]
            },
            "pytket-braket-runner": {
                "base_url": self.PYTKET_BRAKET_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"]
            },
            
            # Category 2: Statevector Samplers (need original QASM)
            "pytket-projectq-runner": {
                "base_url": self.PYTKET_PROJECTQ_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"]
            },
            "pytket-quest-runner":  {
                "base_url": self.PYTKET_QUEST_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"]
            },
            "pennylane-lightning-runner":  {
                "base_url": self.PENNYLANE_LIGHTNING_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"]
            },
            "pennylane-default-runner":  {
                "base_url": self.PENNYLANE_DEFAULT_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"]
            }
        }

settings = Settings()
