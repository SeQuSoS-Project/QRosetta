"""Runs exported functions of pure frontend modules in Node through frontend_harness.mjs."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("frontend_harness.mjs")

requires_node = pytest.mark.skipif(NODE is None, reason="node not available")


def call_js(modules, calls):
    """Return the result of each ``(fn, args)`` call against the named modules."""
    payload = {"modules": list(modules), "calls": [{"fn": fn, "args": list(args)} for fn, args in calls]}
    out = subprocess.run([NODE, str(HARNESS)], input=json.dumps(payload), capture_output=True,
                         text=True, check=True, timeout=60)
    return json.loads(out.stdout)["results"]
