"""Environment checks of the self-test: what each runner result records about its vessel
(CPU quota, thread pinning, memory method and limit, precision and bit order against the
registry, host virtualisation and emulation, image provenance), each PASS, WARN, FAIL or
SKIP by the rules ``plan.ENVIRONMENT_CHECKS`` publishes."""

from config import settings
from qrosetta_commons.helpers import THREAD_ENV_VARS
from services.selftest.plan import (
    RUNNER_CPU_QUOTA_CORES, RUNNER_MEMORY_LIMIT_MIB, THREAD_ENV_VALUE,
)

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"

VM_CAVEAT = ("virtual machine (hypervisor flag): timings are not comparable with bare-metal "
             "runs; known-answer checks are unaffected")
_RELEASE_SOURCES = ("release", "pulled", "loaded")
_WARN_SOURCES = ("built_locally", "pulled-other")
_ROSETTA_CPU_MODEL = "VirtualApple"


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def registry_value(key: str, field: str, part: str):
    """The runner registry's ``field`` for the backend of result key ``key`` (a string, or a
    per-mode dict read at ``part``); None when the registry does not record it."""
    service = settings.get_runner_services().get(str(key).split("~")[0]) or {}
    value = service.get(field)
    if isinstance(value, dict):
        value = value.get(part)
    return value if isinstance(value, str) else None


def _cpu_quota(result, _key, _part):
    value = _dict(result.get("cpu_environment")).get("cpu_quota_cores")
    if isinstance(value, (int, float)) and abs(value - RUNNER_CPU_QUOTA_CORES) < 1e-9:
        return PASS, f"{value:g} core", value
    if value is None:
        return FAIL, "no CPU quota recorded (null): the runner ran without the 1-core quota", None
    return FAIL, f"CPU quota {value} cores, expected {RUNNER_CPU_QUOTA_CORES:g}", value


def _thread_env(result, _key, _part):
    env = result.get("thread_env")
    if not isinstance(env, dict):
        return FAIL, "thread_env not recorded", None
    wrong = sorted(name for name in THREAD_ENV_VARS if env.get(name) != THREAD_ENV_VALUE)
    if wrong:
        return FAIL, "not pinned to 1: " + ", ".join(f"{n}={env.get(n)!r}" for n in wrong), env
    return PASS, "every thread variable is 1", env


def _memory_method(result, _key, _part):
    method = result.get("memory_method")
    if method == "vmhwm":
        return PASS, "kernel high-water mark (VmHWM)", method
    if method is None:
        return WARN, "memory method not recorded", None
    return WARN, f"sampling fallback {method}: short allocations can be missed", method


def _memory_limit(result, _key, _part):
    value = _dict(result.get("cpu_environment")).get("memory_limit_mib")
    if isinstance(value, (int, float)) and abs(value - RUNNER_MEMORY_LIMIT_MIB) < 0.5:
        return PASS, f"{value:g} MiB", value
    if value is None:
        return WARN, "no memory limit recorded (null)", None
    return WARN, f"memory limit {value:g} MiB, registered {RUNNER_MEMORY_LIMIT_MIB} MiB", value


def _registered(field):
    def check(result, key, part):
        registered = registry_value(key, field, part)
        value = result.get(field)
        if registered is None:
            return SKIP, f"the runner registry records no {field} for this backend in {part} mode", value
        if value == registered:
            return PASS, f"{value}, as registered", value
        return FAIL, f"result reports {value!r}, the registry records {registered!r}", value
    return check


def _hypervisor(result, _key, _part):
    cpu = _dict(result.get("cpu_environment"))
    flag = cpu["hypervisor"] if "hypervisor" in cpu else \
        _dict(result.get("image_identity")).get("host_hypervisor_cpu_flag")
    if flag is True:
        return WARN, VM_CAVEAT, True
    if flag is False:
        return PASS, "no hypervisor flag (bare metal)", False
    return SKIP, "hypervisor flag not recorded by this runner", None


def _emulation(result, _key, _part):
    cpu = _dict(result.get("cpu_environment"))
    model = str(cpu.get("cpu_model") or "")
    if _ROSETTA_CPU_MODEL in model:
        return FAIL, f"CPU model {model!r} is Rosetta translation: the image runs emulated", model
    emulation = cpu["emulation"] if "emulation" in cpu else \
        _dict(result.get("image_identity")).get("emulation")
    record = _dict(emulation)
    if isinstance(emulation, dict):
        emulation = emulation.get("emulated")
    archs = (f" (image {record['image_arch']}, host {record['host_arch']})"
             if record.get("image_arch") and record.get("host_arch") else "")
    if emulation is True:
        return FAIL, f"emulation recorded: the image architecture differs from the host's{archs}", True
    if emulation is False:
        return PASS, f"no emulation recorded{archs}", False
    return SKIP, "emulation signature not recorded by this runner", None


def _provenance(result, _key, _part):
    identity = result.get("image_identity")
    if "image_source" not in result and not isinstance(identity, dict):
        return SKIP, "image provenance not recorded by this server's runners", None
    identity = _dict(identity)
    source = result.get("image_source") or identity.get("source")
    git_sha = str(identity.get("git_sha") or result.get("image_git_sha") or "")
    value = {"source": source, "git_sha": git_sha or None}
    if git_sha.endswith("-dirty"):
        return FAIL, f"image built from uncommitted changes ({git_sha}): source not identifiable", value
    if source in _RELEASE_SOURCES:
        return PASS, f"image source {source}", value
    if source in _WARN_SOURCES:
        return WARN, f"image source {source} (commit {git_sha or 'not recorded'})", value
    return FAIL, f"image source {source!r}: the image cannot be identified", value


CHECKS = (
    ("cpu_quota_cores", _cpu_quota),
    ("thread_env", _thread_env),
    ("memory_method", _memory_method),
    ("memory_limit_mib", _memory_limit),
    ("precision", _registered("precision")),
    ("qubit_ordering", _registered("qubit_ordering")),
    ("host_virtualisation", _hypervisor),
    ("host_emulation", _emulation),
    ("provenance", _provenance),
)


def result_environment(result: dict, key: str, part: str) -> list:
    """``[(check, status, reason, value)]`` for one result that ran."""
    return [(name, *check(result, key, part)) for name, check in CHECKS]
