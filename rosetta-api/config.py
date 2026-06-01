# Application configuration and environment variables.

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    PYTKET_QISKIT_RUNNER_URL: str = "http://pytket-qiskit-runner:8000"
    PYTKET_CIRQ_RUNNER_URL: str = "http://pytket-cirq-runner:8000"
    PYTKET_QULACS_RUNNER_URL: str = "http://pytket-qulacs-runner:8000"
    PYTKET_BRAKET_RUNNER_URL: str = "http://pytket-braket-runner:8000"

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

    RUNNER_TIMEOUT_SEC: int = 300
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    STORAGE_MODE: str = os.getenv("STORAGE_MODE", "local")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "minioadmin")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "qrosetta-runs")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")

    MAX_QUBITS_STATEVECTOR: int = 18
    MAX_QUBITS_MEASURED: int = 24
    MAX_QASM_SIZE: int = 1_000_000
    MAX_QASM_GATES: int = 10_000

    # Multi-run (self-comparison) fan-out caps. One request expands to one job per
    # configured run; without these a crafted request could spawn unbounded httpx
    # calls (local) or K8s Job pods (Rahti) and blow up the O(n^2) divergence analysis.
    MAX_RUNS_PER_RUNNER: int = 16
    MAX_TOTAL_RUNS: int = 48

    class Config:
        env_file = ".env"

    def get_runner_services(self):
        return {

            "qiskit": {
                "base_url": self.PYTKET_QISKIT_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Aer transpiler level 1: basic gate cancellation",
                    2: "Aer transpiler level 2: unitary synthesis + gate cancellation",
                    3: "Aer transpiler level 3: heavy optimization, fewest gates (slowest compile)",
                }
            },
            "cirq":   {
                "base_url": self.PYTKET_CIRQ_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "qulacs": {
                "base_url": self.PYTKET_QULACS_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "braket": {
                "base_url": self.PYTKET_BRAKET_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": False,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },

            "projectq": {
                "base_url": self.PYTKET_PROJECTQ_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": False,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "quest":  {
                "base_url": self.PYTKET_QUEST_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "pennylane-lightning":  {
                "base_url": self.PENNYLANE_LIGHTNING_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Cancel inverse gate pairs",
                    2: "Cancel inverses + merge consecutive rotation gates",
                    3: "Commute gates through controls, then cancel inverses + merge rotations",
                }
            },
            "pennylane-default":  {
                "base_url": self.PENNYLANE_DEFAULT_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Cancel inverse gate pairs",
                    2: "Cancel inverses + merge consecutive rotation gates",
                    3: "Commute gates through controls, then cancel inverses + merge rotations",
                }
            },
            "qsim-cirq": {
                "base_url": self.QSIM_CIRQ_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Drop empty moments + align left",
                    2: "Eject Z/phased-Paulis, merge single-qubit gates to PhasedXZ",
                }
            },
            "qibo": {
                "base_url": self.QIBO_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Gate fusion: merge runs of single-qubit gates into one unitary",
                    2: "Gate fusion: merge up to 2-qubit blocks into one unitary",
                }
            },
            "qrisp": {
                "base_url": self.QRISP_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization (Qrisp's optimizer targets high-level programs, not post-QASM gate passes)",
                }
            },
            "myqlm": {
                "base_url": self.MYQLM_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization (PyLinalg does not expose circuit-level optimization passes)",
                }
            },
            "pyquil": {
                "base_url": self.PYQUIL_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "Barrier removal only",
                    1: "Pytket PeepholeOptimise2Q: cancel redundant 2Q gates, merge 1Q sequences",
                    2: "Pytket FullPeepholeOptimise: full 1Q merging + KAK-based 2Q reduction",
                }
            },
            "torchquantum": {
                "base_url": self.TORCHQUANTUM_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Qiskit transpiler level 1: single-qubit gate consolidation, basic cancellation",
                    2: "Qiskit transpiler level 2: unitary synthesis + gate cancellation",
                }
            },
            "quimb": {
                "base_url": self.QUIMB_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization (quimb tensor-network contraction path is managed internally)",
                }
            },
            "cuquantum": {
                "base_url": self.CUQUANTUM_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Qiskit transpiler level 1: basic gate cancellation, 1Q consolidation",
                    2: "Qiskit transpiler level 2: unitary synthesis + gate cancellation",
                    3: "Qiskit transpiler level 3: heavy optimization, fewest gates (slowest compile)",
                }
            }
        }

settings = Settings()
