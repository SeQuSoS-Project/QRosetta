"""The runner lists in docker-compose.yml, safe_boot.sh, rahti_push.sh, runners/ and the
contract test must match config.py's registry (see CONTRIBUTING.md); the compile-only
services in compilers/ must match its compiler registry in the same files.
"""
import ast
import re
from pathlib import Path

import pytest
import yaml

from config import settings

_REPO = Path(__file__).resolve().parents[3]
_COMPOSE = _REPO / "docker-compose.yml"
_SAFE_BOOT = _REPO / "scripts" / "safe_boot.sh"
_RAHTI_PUSH = _REPO / "scripts" / "rahti_push.sh"
_CONTRACT_TEST = _REPO / "tests" / "integration" / "test_runner_contract_asymmetric.py"

pytestmark = pytest.mark.skipif(
    not _COMPOSE.exists(), reason="repository layout not available in this checkout")


def _infra_name(base_url: str) -> str:
    """The runner's infrastructure name, derived from its base_url."""
    return base_url.split("//")[1].split(":")[0]


def _registry() -> dict:
    """Canonical id -> service entry from config.py."""
    return settings.get_runner_services()


def _compilers() -> dict:
    """Compiler id -> service entry from config.py."""
    return settings.get_compiler_services()


def _compose_services() -> set:
    return set(yaml.safe_load(_COMPOSE.read_text()).get("services", {}))


def _bash_array(path: Path, name: str) -> set:
    body = re.search(rf"{name}=\((.*?)\n\)", path.read_text(), re.DOTALL)
    assert body, f"{name} not found in {path.name}"
    return set(re.findall(r'"([^"]+)"', body.group(1)))


def _service_map_keys() -> set:
    body = re.search(r"SERVICE_MAP=\((.*?)\n\)", _RAHTI_PUSH.read_text(), re.DOTALL)
    assert body, "SERVICE_MAP not found in rahti_push.sh"
    return set(re.findall(r'\["([^"]+)"\]', body.group(1)))


def _contract_test_runners() -> set:
    body = re.search(r"ACTIVE_STATEVECTOR_RUNNERS = \[(.*?)\]",
                     _CONTRACT_TEST.read_text(), re.DOTALL)
    assert body, "ACTIVE_STATEVECTOR_RUNNERS not found"
    return set(re.findall(r'"([^"]+)"', body.group(1)))


def test_every_registered_runner_has_a_source_directory():
    for canonical_id, entry in _registry().items():
        directory = _REPO / "runners" / _infra_name(entry["base_url"])
        assert directory.is_dir(), f"{canonical_id}: {directory} is missing"
        assert (directory / "main.py").is_file(), f"{canonical_id}: no main.py"
        assert (directory / "Dockerfile").is_file(), f"{canonical_id}: no Dockerfile"


def test_every_runner_directory_is_registered():
    """Every directory under runners/ is registered in config.py."""
    registered = {_infra_name(e["base_url"]) for e in _registry().values()}
    on_disk = {d.name for d in (_REPO / "runners").iterdir() if d.is_dir()}
    assert on_disk == registered, f"unregistered runner directories: {on_disk - registered}"


def test_docker_compose_defines_every_registered_runner():
    compose = _compose_services()
    for canonical_id, entry in _registry().items():
        service = _infra_name(entry["base_url"]).replace("-", "_")
        assert service in compose, f"{canonical_id}: no '{service}' service in docker-compose.yml"


def test_safe_boot_builds_every_registered_runner():
    """safe_boot.sh RUNNERS matches the registry."""
    expected = {_infra_name(e["base_url"]).replace("-", "_") for e in _registry().values()}
    assert _bash_array(_SAFE_BOOT, "RUNNERS") == expected


def test_rahti_push_maps_every_registered_runner_and_compiler():
    """rahti_push.sh SERVICE_MAP matches the runner and compiler registries plus rosetta-api."""
    expected = ({_infra_name(e["base_url"]) for e in _registry().values()}
                | {_infra_name(e["base_url"]) for e in _compilers().values()} | {"rosetta-api"})
    assert _service_map_keys() == expected


def test_contract_test_covers_exactly_the_enabled_runners():
    enabled = {cid for cid, e in _registry().items() if e.get("enabled", True)}
    assert _contract_test_runners() == enabled


def test_disabled_runners_are_excluded_from_contract_coverage():
    disabled = {cid for cid, e in _registry().items() if not e.get("enabled", True)}
    assert not (disabled & _contract_test_runners()), \
        "a disabled runner is listed for contract testing"


def test_every_runner_declares_whether_it_honours_the_seed():
    """honours_seed has no default: a runner that ignores its seed must say so."""
    missing = [cid for cid, e in _registry().items() if not isinstance(e.get("honours_seed"), bool)]
    assert not missing, f"no explicit boolean honours_seed for: {missing}"


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_names(path: Path) -> set:
    names = set()
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        names.add(_normalise(re.split(r"[\[<>=!~;\s]", line, 1)[0]))
    return names


def _declared_sdk_packages(main_py: Path) -> list:
    tree = ast.parse(main_py.read_text())
    declared = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "declare_sdk_packages"):
            for arg in node.args:
                assert isinstance(arg, ast.Constant) and isinstance(arg.value, str), (
                    f"{main_py.parent.name}: declare_sdk_packages takes string literals")
                declared.append(arg.value)
    return declared


@pytest.mark.parametrize("canonical_id", sorted(settings.get_runner_services()))
def test_runner_declares_its_sdk_packages_from_its_requirements(canonical_id):
    """sdk_versions lists exactly what the runner declares. Each name must be pinned in its
    requirements.txt, or in requirements.lock for a dependency the SDK pulls in (cirq-core
    under cirq)."""
    directory = _REPO / "runners" / _infra_name(_registry()[canonical_id]["base_url"])
    declared = _declared_sdk_packages(directory / "main.py")
    assert declared, f"{directory.name}/main.py never calls declare_sdk_packages"
    pinned = set()
    for name in ("requirements.txt", "requirements.lock"):
        if (directory / name).is_file():
            pinned |= _requirement_names(directory / name)
    unpinned = [name for name in declared if _normalise(name) not in pinned]
    assert not unpinned, (
        f"{directory.name}: declared but in neither requirements.txt nor requirements.lock: "
        f"{unpinned}")


_RUNNER_ENV = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
               "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS", "RUNNER_MAX_CONCURRENT")


def test_compose_runner_blocks_pin_threads_and_concurrency():
    """Every runner service sets the five thread variables and RUNNER_MAX_CONCURRENT."""
    from qrosetta_commons.helpers import THREAD_ENV_VARS
    assert set(THREAD_ENV_VARS) <= set(_RUNNER_ENV)
    services = yaml.safe_load(_COMPOSE.read_text()).get("services", {})
    problems = []
    for canonical_id, entry in _registry().items():
        service = services.get(_infra_name(entry["base_url"]).replace("-", "_"), {})
        env = service.get("environment") or []
        names = set(env) if isinstance(env, dict) else {str(v).split("=", 1)[0] for v in env}
        missing = [name for name in _RUNNER_ENV if name not in names]
        if missing:
            problems.append(f"{canonical_id}: {missing}")
    assert not problems, "compose environment missing: " + "; ".join(problems)


def test_every_registered_compiler_has_a_source_directory():
    for compiler_id, entry in _compilers().items():
        directory = _REPO / "compilers" / _infra_name(entry["base_url"])
        for name in ("main.py", "Dockerfile", "requirements.txt", "requirements.lock"):
            assert (directory / name).is_file(), f"{compiler_id}: no {name} in {directory}"


def test_every_compiler_directory_is_registered():
    registered = {_infra_name(e["base_url"]) for e in _compilers().values()}
    on_disk = {d.name for d in (_REPO / "compilers").iterdir() if d.is_dir()}
    assert on_disk == registered, f"unregistered compiler directories: {on_disk - registered}"


def test_compilers_are_built_and_defined_like_runners():
    services = yaml.safe_load(_COMPOSE.read_text()).get("services", {})
    expected = {_infra_name(e["base_url"]).replace("-", "_") for e in _compilers().values()}
    assert _bash_array(_SAFE_BOOT, "COMPILERS") == expected
    for name in expected:
        service = services.get(name)
        assert service, f"no '{name}' service in docker-compose.yml"
        assert "ports" not in service and service.get("networks") == ["isolated_net"], name
        env = {str(v).split("=", 1)[0] for v in service.get("environment") or []}
        assert set(_RUNNER_ENV) <= env, f"{name}: compose environment missing thread pins"


def test_compiler_ids_are_distinct_from_runner_ids_and_valid_keys():
    from services.exporter import RUNNER_KEY_RE
    assert not set(_compilers()) & set(_registry())
    assert all(RUNNER_KEY_RE.match(cid) for cid in _compilers())


@pytest.mark.parametrize("compiler_id", sorted(settings.get_compiler_services()))
def test_compiler_declares_its_sdk_packages_from_its_requirements(compiler_id):
    directory = _REPO / "compilers" / _infra_name(_compilers()[compiler_id]["base_url"])
    declared = _declared_sdk_packages(directory / "main.py")
    assert declared, f"{directory.name}/main.py never calls declare_sdk_packages"
    pinned = _requirement_names(directory / "requirements.txt") | _requirement_names(directory / "requirements.lock")
    unpinned = [name for name in declared if _normalise(name) not in pinned]
    assert not unpinned, f"{directory.name}: declared but not pinned: {unpinned}"
