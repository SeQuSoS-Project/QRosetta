"""Application settings, runner registry, and build/provenance identifiers."""

import json
import os
from pydantic import Field, field_validator
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

    BQSKIT_COMPILER_URL: str = "http://bqskit-compiler:8000"
    PYZX_COMPILER_URL: str = "http://pyzx-compiler:8000"
    QMAP_COMPILER_URL: str = "http://qmap-compiler:8000"
    CIRQ_COMPILER_URL: str = "http://cirq-compiler:8000"
    STAQ_COMPILER_URL: str = "http://staq-compiler:8000"
    QSYNTH_COMPILER_URL: str = "http://qsynth-compiler:8000"
    QUARTZ_COMPILER_URL: str = "http://quartz-compiler:8000"
    SYNTHETIQ_COMPILER_URL: str = "http://synthetiq-compiler:8000"

    PLATFORM_VERSION: str = os.getenv("QROSETTA_VERSION", "1.0.0")
    REPOSITORY_URL: str = os.getenv("QROSETTA_REPOSITORY_URL",
                                    "https://github.com/SeQuSoS-Project/QRosetta").rstrip("/")

    RUN_RATE_LIMIT: str = os.getenv("QROSETTA_RUN_RATE_LIMIT", "10/minute")

    RUNNER_TIMEOUT_SEC: int = 300
    MIN_TIMEOUT_SEC: int = 10
    DEFAULT_TIMEOUT_SEC: int = 60
    MAX_TIMING_REPEATS: int = 10
    MAX_EXPANDED_GATES: int = int(os.getenv("QROSETTA_MAX_EXPANDED_GATES", "200000"))
    MAX_NESTED_GATE_CALLS: int = int(os.getenv("QROSETTA_MAX_NESTED_GATE_CALLS", "4096"))
    EXCLUSIVE_ENABLED: bool = os.getenv("QROSETTA_EXCLUSIVE_ENABLED", "true").lower() == "true"
    EXCLUSIVE_MAX_WAIT_SEC: float = float(os.getenv("QROSETTA_EXCLUSIVE_MAX_WAIT_SEC", "600"))
    MIN_SHOTS: int = 1
    MAX_SHOTS: int = 1_000_000
    DEFAULT_SHOTS: int = 8200
    RUNNER_CONNECT_TIMEOUT_SEC: int = 10
    RUNNER_DEADLINE_BUFFER_SEC: int = 15
    RUNNER_QUEUE_MAX_WAIT_SEC: int = int(os.getenv("RUNNER_QUEUE_MAX_WAIT_SEC", "1800"))
    K8S_MAX_CONCURRENT_JOBS: int = Field(default=3, validation_alias="QROSETTA_K8S_MAX_CONCURRENT_JOBS")
    GPU_AVAILABLE: bool = os.getenv("QROSETTA_GPU_AVAILABLE", "false").strip().lower() in ("1", "true", "yes")
    NOT_DEPLOYED: frozenset = frozenset(
        s.strip() for s in os.getenv("QROSETTA_NOT_DEPLOYED", "").split(",") if s.strip())
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    PROXY_TOKEN: str = Field(default="", validation_alias="QROSETTA_PROXY_TOKEN")

    STORAGE_MODE: str = os.getenv("STORAGE_MODE", "local")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "minioadmin")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "qrosetta-runs")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")

    MAX_QUBITS_STATEVECTOR: int = 18
    MAX_QUBITS_MEASURED: int = 24
    MAX_QUBITS_COMPILE: int = 24
    MAX_QASM_SIZE: int = 1_000_000
    MAX_QASM_GATES: int = 10_000
    MAX_UPLOAD_BYTES: int = 1_048_576

    CORS_ALLOW_ORIGINS: str = os.getenv("CORS_ALLOW_ORIGINS", "")

    MAX_RUNS_PER_RUNNER: int = 16
    MAX_TOTAL_RUNS: int = 48
    MAX_EXPERIMENT_CELLS: int = 200
    MAX_EXPORT_ITEMS: int = 60
    MAX_LABEL_LENGTH: int = 200

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("K8S_MAX_CONCURRENT_JOBS", mode="after")
    @classmethod
    def _at_least_one_slot(cls, value: int) -> int:
        return max(1, value)

    def max_qubits_for_mode(self, mode: str) -> int:
        """Qubit cap for a run mode ("statevector", "measured" or "compile" for a compile-only
        run): statevector runs are capped lower than measured runs."""
        if mode == "compile":
            return self.MAX_QUBITS_COMPILE
        return self.MAX_QUBITS_STATEVECTOR if mode == "statevector" else self.MAX_QUBITS_MEASURED

    def get_cors_origins(self) -> list:
        origins = ["http://localhost", "http://127.0.0.1"]
        origins += [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]
        return origins

    def get_runner_services(self):
        """Canonical runner id -> base_url, capabilities, enabled flag, optimization levels.

        Every entry sets ``honours_seed`` explicitly: False for a runner whose backend ignores
        the sampling seed it is passed (results then record ``seed_honoured: false``).
        ``requires_gpu`` marks a runner that is unavailable unless the deployment has a GPU
        (see ``services.availability``).
        """
        return {

            "qiskit": {
                "base_url": self.PYTKET_QISKIT_RUNNER_URL,
                "builds_with_tket": True,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "honours_seed": True,
                "optimization_levels": {
                    0: "No transpiler optimization (Aer still fuses gates during simulation; see gate_fusion)",
                    1: "Aer transpiler level 1: basic gate cancellation",
                    2: "Aer transpiler level 2: unitary synthesis + gate cancellation",
                    3: "Aer transpiler level 3: heavy optimization, fewest gates (slowest compile)",
                }
            },
            "cirq":   {
                "base_url": self.PYTKET_CIRQ_RUNNER_URL,
                "builds_with_tket": True,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "honours_seed": True,
                "optimization_levels": {
                    0: "Backend default rebase only: pytket default_compilation_pass level 0 (DecomposeBoxes, FlattenRegisters, AutoRebase to the backend gate set), no optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "qulacs": {
                "base_url": self.PYTKET_QULACS_RUNNER_URL,
                "builds_with_tket": True,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "honours_seed": True,
                "optimization_levels": {
                    0: "Backend default rebase only: pytket default_compilation_pass level 0 (DecomposeBoxes, FlattenRegisters, AutoRebase to the backend gate set), no optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "braket": {
                "base_url": self.PYTKET_BRAKET_RUNNER_URL,
                "builds_with_tket": True,
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
                "builds_with_tket": True,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": False,
                "honours_seed": True,
                "optimization_levels": {
                    0: "Backend default rebase only: pytket default_compilation_pass level 0 (DecomposeBoxes, FlattenRegisters, AutoRebase to the backend gate set), no optimization",
                    1: "Pytket light: fast peephole rewrites, remove redundant gates",
                    2: "Pytket heavy: full KAK-based 2Q reduction + 1Q sequence merging",
                }
            },
            "quest":  {
                "base_url": self.PYTKET_QUEST_RUNNER_URL,
                "builds_with_tket": True,
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True,
                "honours_seed": True,
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
                "honours_seed": True,
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
                "honours_seed": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Cancel inverse gate pairs",
                    2: "Cancel inverses + merge consecutive rotation gates",
                    3: "Commute gates through controls, then cancel inverses + merge rotations",
                }
            },
            "qsim-cirq": {
                "base_url": self.QSIM_CIRQ_RUNNER_URL,
                "builds_with_tket": True,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "honours_seed": True,
                "optimization_levels": {
                    0: "No optimization pass (qsim still fuses gates into 2-qubit blocks during simulation)",
                    1: "Drop empty moments + align left",
                    2: "Eject Z/phased-Paulis, merge single-qubit gates to PhasedXZ",
                }
            },
            "qibo": {
                "base_url": self.QIBO_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "honours_seed": True,
                "optimization_levels": {
                    0: "No optimization",
                    1: "Gate fusion of single-qubit runs: merge runs of single-qubit gates into one unitary",
                    2: "Gate fusion of 2-qubit blocks: merge up to 2-qubit blocks into one unitary",
                }
            },
            "qrisp": {
                "base_url": self.QRISP_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "honours_seed": True,
                "optimization_levels": {
                    0: "No optimization (Qrisp's optimizer targets high-level programs, not post-QASM gate passes)",
                }
            },
            "myqlm": {
                "base_url": self.MYQLM_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "honours_seed": True,
                "optimization_levels": {
                    0: "No optimization (PyLinalg does not expose circuit-level optimization passes)",
                }
            },
            "pyquil": {
                "base_url": self.PYQUIL_RUNNER_URL,
                "builds_with_tket": True,
                # NumpyWavefunctionSimulator has no shot sampler; the runner samples the statevector.
                "capabilities": ["statevector", "measured_sampled"],
                "enabled": True,
                "honours_seed": True,
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
                "honours_seed": True,
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
                "honours_seed": True,
                "optimization_levels": {
                    0: "No optimization (quimb tensor-network contraction path is managed internally)",
                }
            },
            "cuquantum": {
                "base_url": self.CUQUANTUM_RUNNER_URL,
                "capabilities": ["statevector", "measured_native"],
                "enabled": True,
                "honours_seed": True,
                "requires_gpu": True,
                "optimization_levels": {
                    0: "No transpiler optimization (Aer still fuses gates during simulation; see gate_fusion)",
                    1: "Qiskit transpiler level 1: basic gate cancellation, 1Q consolidation",
                    2: "Qiskit transpiler level 2: unitary synthesis + gate cancellation",
                    3: "Qiskit transpiler level 3: heavy optimization, fewest gates (slowest compile)",
                }
            }
        }

    def max_compile_jobs(self) -> int:
        """Compile jobs one circuit may request: every level of every enabled compiler once."""
        return sum(len(c["optimization_levels"])
                   for c in self.get_compiler_services().values() if c.get("enabled", True))

    def get_compiler_services(self):
        """Canonical compile-only service id -> base_url, display name, enabled flag and
        optimization levels. Compilers produce circuit text only: they are not runners,
        are never simulated and never enter the pairwise comparison."""
        return {
            "bqskit": {
                "base_url": self.BQSKIT_COMPILER_URL,
                "name": "BQSKit",
                "enabled": True,
                "optimization_levels": {
                    1: "bqskit.compile level 1: partition into 3-qubit blocks and resynthesise each numerically",
                    2: "bqskit.compile level 2: level 1 with more resynthesis passes",
                    3: "bqskit.compile level 3: heavier resynthesis (slow beyond a few qubits)",
                },
            },
            "pyzx": {
                "base_url": self.PYZX_COMPILER_URL,
                "name": "PyZX",
                "enabled": True,
                "optimization_levels": {
                    1: "ZX-calculus full_reduce, then circuit extraction",
                    2: "Level 1, then PyZX basic_optimization of the extracted circuit",
                },
            },
            "qmap": {
                "base_url": self.QMAP_COMPILER_URL,
                "name": "MQT QMAP",
                "enabled": True,
                "optimization_levels": {
                    0: "Decompose to u3+cx (Qiskit), then heuristic (A*) mapping onto a linear qubit chain",
                    1: "Decompose to u3+cx (Qiskit), then exact (SAT) mapping onto a linear qubit chain (up to 7 qubits)",
                },
            },
            "cirq-transformers": {
                "base_url": self.CIRQ_COMPILER_URL,
                "name": "Cirq",
                "enabled": True,
                "optimization_levels": {
                    0: "optimize_for_target_gateset to the CZ target gate set (CZ + PhasedXZ, merged)",
                    1: "Level 0, then eject_phased_paulis, eject_z and the drop-negligible/empty cleanups",
                },
            },
            "staq": {
                "base_url": self.STAQ_COMPILER_URL,
                "name": "staq",
                "enabled": True,
                "optimization_levels": {
                    1: "staq -O1: rotation folding and simplification",
                    2: "staq -O2: inline gates other than staq's basic ones (x, h, s, t, rz, cx, swap, ...), simplification, rotation folding",
                    3: "staq -O3: -O2 plus CNOT resynthesis",
                },
            },
            "qsynth": {
                "base_url": self.QSYNTH_COMPILER_URL,
                "name": "Q-Synth",
                "enabled": True,
                "optimization_levels": {
                    0: "Decompose to u3+cx (Qiskit), then SAT peephole synthesis of each CNOT slice for the fewest CNOTs",
                    1: "Decompose to u3+cx (Qiskit), then SAT peephole synthesis of each CNOT slice for the smallest CNOT depth",
                },
            },
            "quartz": {
                "base_url": self.QUARTZ_COMPILER_URL,
                "name": "Quartz",
                "enabled": True,
                "optimization_levels": {
                    0: "Decompose to h+x+rz+cx (Qiskit), then greedy rewriting with a generated ECC set until no rewrite lowers the gate count",
                },
            },
            "synthetiq": {
                "base_url": self.SYNTHETIQ_COMPILER_URL,
                "name": "Synthetiq",
                "enabled": True,
                "optimization_levels": {
                    0: "Clifford+T circuits of up to 3 qubits: Synthetiq synthesises a new Clifford+T circuit for the unitary (simulated annealing, first circuit found within 1000 runs)",
                    1: "As level 0, the lowest-cost of the first 5 circuits found within 2000 runs",
                },
            },
        }

settings = Settings()


def server_git_sha() -> str:
    """The commit the API image was built from (QROSETTA_IMAGE_GIT_SHA, set at build time),
    else QROSETTA_GIT_SHA or GIT_SHA from the environment; 'unknown' if none is set."""
    for name in ("QROSETTA_IMAGE_GIT_SHA", "QROSETTA_GIT_SHA", "GIT_SHA"):
        value = (os.getenv(name) or "").strip()
        if value and value != "unknown":
            return value
    return "unknown"


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
            "honours_seed": svc["honours_seed"],
            "requires_gpu": bool(svc.get("requires_gpu", False)),
        }
        for name, svc in services.items()
    }
