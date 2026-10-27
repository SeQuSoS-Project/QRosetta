"""GET /config ``server`` block: platform version, the API levels this server serves, its
features with their versions, the analysis version and the API image's commit."""

from config import server_git_sha, settings
from services.analysis.divergence import ANALYSIS_VERSION

API_LEVELS = (1, 1)

FEATURES = {
    "request_defaults": 1,
    "quickload": 1,
    "profiles": 1,
}


def server_block() -> dict:
    """The handshake a client reads before it uses any other route."""
    return {
        "platform_version": settings.PLATFORM_VERSION,
        "api_levels": list(API_LEVELS),
        "analysis_version": ANALYSIS_VERSION,
        "git_sha": server_git_sha(),
        "features": dict(FEATURES),
    }
