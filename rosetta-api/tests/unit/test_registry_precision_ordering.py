"""The registry's precision and qubit_ordering per runner and endpoint equal what each
runner's source passes to the shared instrument, and GET /runners publishes them."""
import asyncio
from pathlib import Path

import pytest

from config import settings
from services import service_listing
from tests.unit.runner_declarations import declared

_REPO = Path(__file__).resolve().parents[3]
_ENDPOINTS = ("statevector", "measured")
_PRECISIONS = {"complex64", "complex128", None}

pytestmark = pytest.mark.skipif(not (_REPO / "runners").is_dir(),
                                reason="runner sources not available in this checkout")


def _infra(base_url: str) -> str:
    return base_url.split("//")[1].split(":")[0]


@pytest.mark.parametrize("runner_id", list(settings.get_runner_services()))
def test_registry_values_are_the_runner_declarations(runner_id):
    entry = settings.get_runner_services()[runner_id]
    found = declared(_infra(entry["base_url"]))
    assert set(found) == set(_ENDPOINTS), f"{runner_id}: job calls found for {sorted(found)}"
    for endpoint in _ENDPOINTS:
        assert entry["precision"][endpoint] == found[endpoint]["precision"], (runner_id, endpoint)
        assert entry["qubit_ordering"][endpoint] == found[endpoint]["qubit_ordering"], (runner_id, endpoint)
        assert entry["precision"][endpoint] in _PRECISIONS
        assert entry["qubit_ordering"][endpoint] in {"lsb", "msb"}


def test_a_precision_set_at_run_time_is_null():
    assert settings.get_runner_services()["cuquantum"]["precision"] == {"statevector": None, "measured": None}


def test_runners_route_publishes_the_fields(monkeypatch):
    async def available(*_a, **_k):
        return {n: {"available": True, "reason": None, "device": None}
                for n in settings.get_runner_services()}
    monkeypatch.setattr(service_listing, "runner_availability", available)
    rows = {r["id"]: r for r in asyncio.run(service_listing.runner_rows())}
    for runner_id, entry in settings.get_runner_services().items():
        assert rows[runner_id]["precision"] == entry["precision"]
        assert rows[runner_id]["qubit_ordering"] == entry["qubit_ordering"]
