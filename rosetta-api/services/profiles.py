"""Built-in service profiles and default selection, as GET /runners and GET /compilers
publish them.

minimal: qiskit, qulacs and cirq. cpu: enabled runners that need no GPU. gpu: cpu plus the
GPU runners. compilers: enabled compile-only services. full: every enabled runner and
compile-only service. A disabled service is in no profile."""

MINIMAL_RUNNERS = ("qiskit", "qulacs", "cirq")
PROFILE_NAMES = ("minimal", "cpu", "gpu", "compilers", "full")


def runner_profiles(runner_id: str, entry: dict) -> list:
    """The built-in profiles a runner belongs to, in PROFILE_NAMES order."""
    if not entry.get("enabled", True):
        return []
    names = {"gpu", "full"}
    if runner_id in MINIMAL_RUNNERS:
        names.add("minimal")
    if not entry.get("requires_gpu", False):
        names.add("cpu")
    return [p for p in PROFILE_NAMES if p in names]


def compiler_profiles(entry: dict) -> list:
    """The built-in profiles a compile-only service belongs to."""
    return ["compilers", "full"] if entry.get("enabled", True) else []


def runner_default_selected(entry: dict) -> bool:
    """Whether a run that names no backends uses this runner when it is available: every
    enabled runner."""
    return bool(entry.get("enabled", True))


def compiler_default_selected(_entry: dict) -> bool:
    """A run uses a compile-only service only when the request names it."""
    return False
