"""Application settings, runner registry, and build/provenance identifiers."""

import json
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "local")

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

    PLATFORM_VERSION: str = os.getenv("QROSETTA_VERSION", "1.0.0")

    RUN_RATE_LIMIT: str = os.getenv("QROSETTA_RUN_RATE_LIMIT", "10/minute")

    RUNNER_TIMEOUT_SEC: int = 300
    MIN_TIMEOUT_SEC: int = 10
    MIN_SHOTS: int = 1
    MAX_SHOTS: int = 1_000_000
    RUNNER_CONNECT_TIMEOUT_SEC: int = 10
    RUNNER_DEADLINE_BUFFER_SEC: int = 15
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

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
    MAX_UPLOAD_BYTES: int = 1_048_576

    CORS_ALLOW_ORIGINS: str = os.getenv("CORS_ALLOW_ORIGINS", "")

    MAX_RUNS_PER_RUNNER: int = 16
    MAX_TOTAL_RUNS: int = 48

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def max_qubits_for_mode(self, mode: str) -> int:
        """Qubit cap for a run mode: statevector runs are capped lower than measured runs."""
        return self.MAX_QUBITS_STATEVECTOR if mode == "statevector" else self.MAX_QUBITS_MEASURED

    def get_cors_origins(self) -> list:
        origins = ["http://localhost", "http://127.0.0.1"]
        origins += [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]
        return origins

    def get_runner_services(self):
        """Canonical runner id -> base_url, capabilities, enabled flag, optimization levels.

        ``honours_seed`` is False for a runner whose backend ignores the sampling seed it
        is passed; it defaults to True when absent.
        """
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
                    0: "Backend default rebase only: pytket default_compilation_pass level 0 (DecomposeBoxes, FlattenRegisters, AutoRebase to the backend gate set), no optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "qulacs": {
                "base_url": self.PYTKET_QULACS_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "optimization_levels": {
                    0: "Backend default rebase only: pytket default_compilation_pass level 0 (DecomposeBoxes, FlattenRegisters, AutoRebase to the backend gate set), no optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "braket": {
                "base_url": self.PYTKET_BRAKET_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": False,
                "honours_seed": False,
                "optimization_levels": {
                    0: "Backend default rebase only: pytket default_compilation_pass level 0 (DecomposeBoxes, FlattenRegisters, AutoRebase to the backend gate set), no optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },

            "projectq": {
                "base_url": self.PYTKET_PROJECTQ_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": False,
                "optimization_levels": {
                    0: "Backend default rebase only: pytket default_compilation_pass level 0 (DecomposeBoxes, FlattenRegisters, AutoRebase to the backend gate set), no optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "quest":  {
                "base_url": self.PYTKET_QUEST_RUNNER_URL,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True,
                "optimization_levels": {
                    0: "Backend default rebase only: pytket default_compilation_pass level 0 (DecomposeBoxes, FlattenRegisters, AutoRebase to the backend gate set), no optimization",
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
                # NumpyWavefunctionSimulator has no shot sampler; the runner samples the statevector.
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True,
                "optimization_levels": {
                    0: "No optimization pass: barriers removed and gates rebased to CX/Rz/Rx (with apply_preprocessing=false, single-qubit Rz/Rx rebase only)",
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


def server_git_sha() -> str:
    """Git SHA injected at build time via QROSETTA_GIT_SHA (or GIT_SHA); 'unknown' if unset."""
    return (os.getenv("QROSETTA_GIT_SHA") or os.getenv("GIT_SHA") or "").strip() or "unknown"


def server_image_digests() -> dict:
    """Deployed image digests from the QROSETTA_IMAGE_DIGESTS JSON env var, or {}."""
    raw = os.getenv("QROSETTA_IMAGE_DIGESTS")
    if not raw:
        return {}
    try:
        val = json.loads(raw)
    except ValueError:
        return {}
    return val if isinstance(val, dict) else {}


def runner_registry_snapshot(runner_services: dict = None) -> dict:
    """JSON-safe copy of the runner registry fields that describe a run's configuration."""
    services = runner_services if runner_services is not None else settings.get_runner_services()
    return {
        name: {
            "enabled": svc.get("enabled", True),
            "capabilities": list(svc.get("capabilities", [])),
            "optimization_levels": {str(k): v for k, v in svc.get("optimization_levels", {}).items()},
            "honours_seed": svc.get("honours_seed", True),
        }
        for name, svc in services.items()
    }
