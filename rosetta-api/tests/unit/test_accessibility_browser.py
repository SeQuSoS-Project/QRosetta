"""axe-core in headless Chrome over the page states reachable without a run (load, the settings
popovers, Bench, Auto-Gen, sign-in, register, the manual, the share page), and bidi isolation in
a real DOM. Skipped unless QROSETTA_AXE_NODE_MODULES names a node_modules directory holding
axe-core and playwright-core and a Chrome or Chromium binary is found (QROSETTA_CHROME, else
the PATH); CI installs neither."""
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

_MODULES = os.environ.get("QROSETTA_AXE_NODE_MODULES", "")
_CHROME = os.environ.get("QROSETTA_CHROME") or next(
    (p for p in map(shutil.which, ("google-chrome", "chromium", "chromium-browser")) if p), None)
_NODE = shutil.which("node")
_READY = bool(_MODULES and _CHROME and _NODE and (Path(_MODULES) / "axe-core" / "axe.min.js").is_file()
              and (Path(_MODULES) / "playwright-core").is_dir())

pytestmark = pytest.mark.skipif(not _READY, reason="axe-core, playwright-core or Chrome not available")

# Text of an inactive component has no contrast requirement (WCAG 1.4.3): the greyed tab
# strip shown before a result exists.
_EXEMPT = {("color-contrast", "qr-placeholder-tab")}


@pytest.fixture(scope="module")
def axe_result(monkeypatch_module):
    import uvicorn

    import services.availability as availability
    from main import app

    async def probe(client, svc):
        return {"available": True, "reason": None, "device": "CPU"}, None
    monkeypatch_module.setattr(availability, "probe_with_kind", probe)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    try:
        out = subprocess.run([_NODE, str(Path(__file__).with_name("axe_page.mjs")), f"http://127.0.0.1:{port}", _MODULES, _CHROME],
                             capture_output=True, text=True, check=True, timeout=240)
        return json.loads(out.stdout)
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_axe_finds_no_wcag_2_2_aa_violation(axe_result):
    found = []
    for state in axe_result["states"]:
        for v in state["violations"]:
            for node in v["targets"]:
                if not any(v["id"] == rule and marker in node["html"] for rule, marker in _EXEMPT):
                    found.append((state["name"], v["id"], v["impact"], node["target"]))
    assert len(axe_result["states"]) == 13
    assert not found, found


def test_v2_05_bidi_text_is_isolated_in_the_browser(axe_result):
    bidi = axe_result["bidi"]
    assert bidi["isolated"] == ["#text", "BDI", "#text"]
    assert bidi["text"] == "Error: ‮gnp.exe (qulacs)"
    assert bidi["plainUntouched"]
