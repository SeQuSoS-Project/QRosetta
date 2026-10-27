"""GET /config server block: the handshake a client reads first."""
from pathlib import Path

import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from config import server_git_sha, settings  # noqa: E402
from main import app  # noqa: E402
from services import server_info  # noqa: E402
from services.analysis.divergence import ANALYSIS_VERSION  # noqa: E402

_DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def test_config_carries_the_server_block():
    server = TestClient(app).get("/config").json()["server"]
    assert server["platform_version"] == settings.PLATFORM_VERSION
    assert server["analysis_version"] == ANALYSIS_VERSION
    assert server["git_sha"] == server_git_sha()
    lo, hi = server["api_levels"]
    assert isinstance(lo, int) and isinstance(hi, int) and 1 <= lo <= hi
    assert all(isinstance(k, str) and isinstance(v, int) and v >= 1
               for k, v in server["features"].items())
    assert server["features"]["request_defaults"] == 1


def test_features_are_a_copy():
    block = server_info.server_block()
    block["features"]["x"] = 1
    assert "x" not in server_info.FEATURES


def test_platform_version_is_baked_into_the_api_image():
    text = _DOCKERFILE.read_text()
    assert "ARG QROSETTA_VERSION=" in text
    assert "ENV QROSETTA_VERSION=${QROSETTA_VERSION}" in text
