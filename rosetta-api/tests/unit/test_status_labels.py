"""GET /config status_labels: the words and tooltips of live statuses, which the running
view reads instead of holding its own."""
from pathlib import Path

import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from services.job_manager import JOB_PHASES  # noqa: E402
from services.status_labels import STATUS_LABELS  # noqa: E402
from tests.unit.frontend_harness import call_js, requires_node  # noqa: E402

_JS = Path(__file__).resolve().parents[2] / "static" / "js"
_RUN_STATUSES = {"queued", "spawning", "running", "done", "error", "timeout", "offline"}


def test_config_publishes_every_status():
    labels = TestClient(app).get("/config").json()["status_labels"]
    assert labels == STATUS_LABELS
    assert set(labels["runs"]) == _RUN_STATUSES
    assert set(labels["tasks"]) == {"queued", "running", "analysing", "done", "error"}
    assert set(labels["phases"]) == set(JOB_PHASES)
    for entries in labels.values():
        for entry in entries.values():
            assert set(entry) == {"label", "hint"}
            assert entry["label"] and entry["label"] == entry["label"].upper()


def test_the_running_view_holds_no_status_words():
    src = (_JS / "status_cards.js").read_text()
    for word in ("'QUEUED'", "'SENT'", "'ANALYSING'", "'OFFLINE'", "Not started yet",
                 "could not be reached", "queue_wait_sec"):
        assert word not in src, word
    assert "setStatusLabels(config.status_labels)" in (_JS / "app.js").read_text()


@requires_node
def test_the_running_view_shows_the_server_words():
    looks = call_js(["status_cards.js"], [
        ("_cfg", ["runs", "running"]),
        ("setStatusLabels", [STATUS_LABELS]),
        ("_cfg", ["runs", "running"]),
        ("_cfg", ["runs", "no-such-status"]),
        ("_cfg", ["tasks", "analysing"]),
        ("_cfg", ["runs", "done"]),
    ])
    assert looks[0]["label"] == "RUNNING"
    assert looks[2]["label"] == "SENT" and looks[2]["hint"] == STATUS_LABELS["runs"]["running"]["hint"]
    assert looks[3]["label"] == "QUEUED" and looks[3]["untimed"] is True
    assert looks[4]["label"] == "ANALYSING" and looks[4]["pulse"] is True
    assert looks[5]["terminal"] is True and "hint" not in looks[5]
