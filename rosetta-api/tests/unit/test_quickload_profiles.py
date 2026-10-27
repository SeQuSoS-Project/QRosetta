"""GET /quickload (Quick Load sets as server data) and the default_selected and profiles
fields of GET /runners and GET /compilers."""
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from config import settings  # noqa: E402
from main import app  # noqa: E402
from schemas import BatchPayload  # noqa: E402
from services import service_listing  # noqa: E402
from services.compilation import COMPILER_SERVICES  # noqa: E402
from services.quickload import set_items  # noqa: E402

_STATIC = Path(__file__).resolve().parents[2] / "static"


def test_quickload_lists_the_three_sets_as_playlist_items():
    sets = TestClient(app).get("/quickload").json()
    assert [s["id"] for s in sets] == ["each", "scaling", "largest"]
    algorithms = TestClient(app).get("/algorithms").json()
    by_id = {s["id"]: s for s in sets}
    assert [i["algorithm"] for i in by_id["each"]["items"]] == [a["id"] for a in algorithms]
    cap = settings.MAX_QUBITS_STATEVECTOR
    assert [i["qubits"] for i in by_id["scaling"]["items"]] == [5, 10, 15, cap]
    assert [i["algorithm"] for i in by_id["largest"]["items"]] == ["random", "bv", "vqe"]
    for s in sets:
        BatchPayload(mode="statevector", tasks=s["items"])
        for item in s["items"]:
            meta = next(a for a in algorithms if a["id"] == item["algorithm"])
            assert meta["min_qubits"] <= item["qubits"] <= min(meta["max_qubits"], cap)


def test_set_items_clamp_and_deduplicate():
    algos = [{"id": "ghz", "name": "", "min_qubits": 2, "max_qubits": 24},
             {"id": "bv", "name": "BV", "min_qubits": 7, "max_qubits": 9}]
    assert [i["qubits"] for i in set_items("scaling", algos, 10)] == [5, 10]
    assert set_items("scaling", algos, 10)[0]["name"] == "ghz"
    assert [i["qubits"] for i in set_items("each", algos, 18)] == [5, 7]
    assert set_items("largest", algos, 18)[1] == {"algorithm": "bv", "qubits": 9, "name": "BV"}
    assert set_items("largest", algos, 18)[0] == {"algorithm": "random", "qubits": 18, "name": "random"}
    assert set_items("unknown", algos, 18) == []


def _available(*_a, **_k):
    async def run():
        return {n: {"available": True, "reason": None, "device": None}
                for n in [*settings.get_runner_services(), *COMPILER_SERVICES]}
    return run()


def test_runner_rows_carry_default_selection_and_profiles(monkeypatch):
    monkeypatch.setattr(service_listing, "runner_availability", _available)
    rows = {r["id"]: r for r in asyncio.run(service_listing.runner_rows())}
    services = settings.get_runner_services()
    for rid, entry in services.items():
        row = rows[rid]
        assert row["default_selected"] is bool(entry["enabled"])
        assert row["backend"] is None and row["version"] is None
        if not entry["enabled"]:
            assert row["profiles"] == []
            continue
        assert ("cpu" in row["profiles"]) is (not entry.get("requires_gpu", False))
        assert "gpu" in row["profiles"] and "full" in row["profiles"]
    minimal = {rid for rid, r in rows.items() if "minimal" in r["profiles"]}
    assert minimal == {"qiskit", "qulacs", "cirq"}
    assert rows["cuquantum"]["profiles"] == ["gpu", "full"]


def test_compiler_rows_are_not_default_selected(monkeypatch):
    monkeypatch.setattr(service_listing, "runner_availability", _available)
    for row in asyncio.run(service_listing.compiler_rows()):
        assert row["default_selected"] is False
        assert row["profiles"] == (["compilers", "full"] if row["enabled"] else [])


def test_the_page_reads_quick_load_from_the_server():
    batch = (_STATIC / "js" / "batch.js").read_text()
    html = (_STATIC / "index.html").read_text()
    assert "presetItems" not in batch and "'scaling'" not in batch
    assert "Sanity Check" not in html and "Sanity Check" not in batch
    assert "/quickload" in (_STATIC / "js" / "app.js").read_text()
    assert "default_selected" in (_STATIC / "js" / "config.js").read_text()
