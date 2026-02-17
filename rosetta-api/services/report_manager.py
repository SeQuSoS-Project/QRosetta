import os
import json
import cachetools
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-api")

REPORTS_DIR = "export/reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

RESULT_CACHE = cachetools.TTLCache(maxsize=10, ttl=3600)  # Kept for backward compatibility if needed

from config import settings

def save_report_to_disk(data: list):
    # Always update cache (in-memory persistence for this instance)
    RESULT_CACHE["latest_full_report"] = data

    if settings.STORAGE_MODE == "memory":
        logger.info("STORAGE_MODE=memory: Skipping saving report to disk.")
        return

    try:
        with open(os.path.join(REPORTS_DIR, "latest_full_report.json"), "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write report to disk: {e}")

def get_latest_report_path():
    return os.path.join(REPORTS_DIR, "latest_full_report.json")
