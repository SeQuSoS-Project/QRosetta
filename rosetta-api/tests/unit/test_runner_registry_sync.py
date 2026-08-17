"""A runner has to be listed in five places, and nothing checked they agree.

config.py is the only one the application reads at runtime. The rest are build and
deployment lists, so a runner missing from one of them is not an error — it is silently
absent from that path: never built locally, never pushed to the registry, never
contract-tested. That failure mode is quiet by construction, which is what makes it worth
a test.

CONTRIBUTING.md documents the same five places; this keeps the code honest about them.
"""
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
    """The runner's infrastructure name, derived from its base_url as config.py intends."""
    return base_url.split("//")[1].split(":")[0]


def _registry() -> dict:
    """Canonical id -> service entry, straight from the single runtime source."""
    return settings.get_runner_services()


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
    """An orphan directory is a runner nobody can reach."""
    registered = {_infra_name(e["base_url"]) for e in _registry().values()}
    on_disk = {d.name for d in (_REPO / "runners").iterdir() if d.is_dir()}
    assert on_disk == registered, f"unregistered runner directories: {on_disk - registered}"


def test_docker_compose_defines_every_registered_runner():
    compose = _compose_services()
    for canonical_id, entry in _registry().items():
        service = _infra_name(entry["base_url"]).replace("-", "_")
        assert service in compose, f"{canonical_id}: no '{service}' service in docker-compose.yml"


def test_safe_boot_builds_every_registered_runner():
    """A runner missing here is silently excluded from every local boot."""
    expected = {_infra_name(e["base_url"]).replace("-", "_") for e in _registry().values()}
    assert _bash_array(_SAFE_BOOT, "RUNNERS") == expected


def test_rahti_push_maps_every_registered_runner():
    """A runner missing here is never pushed, so its Kubernetes Jobs cannot pull an image."""
    expected = {_infra_name(e["base_url"]) for e in _registry().values()} | {"rosetta-api"}
    assert _service_map_keys() == expected


def test_contract_test_covers_exactly_the_enabled_runners():
    enabled = {cid for cid, e in _registry().items() if e.get("enabled", True)}
    assert _contract_test_runners() == enabled


def test_disabled_runners_are_excluded_from_contract_coverage():
    disabled = {cid for cid, e in _registry().items() if not e.get("enabled", True)}
    assert not (disabled & _contract_test_runners()), \
        "a disabled runner is listed for contract testing"
