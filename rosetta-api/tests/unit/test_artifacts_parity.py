"""Parity guard: the browser text-artifact builders (static/js/artifact_formats.js) must
render byte-identically to services/publication.py, since the interactive Artifacts tab and the
RO-Crate export are meant to agree. Catches silent drift between the two hand-kept copies.

Runs the JS builders in Node; skips if Node is unavailable.
"""
import json
import os
import shutil
import subprocess

import pytest

from services.publication import list_artifacts, render_artifact
from tests.unit.test_publication import MEASURED, STATEVECTOR

_NODE = shutil.which("node")
_HARNESS = os.path.join(os.path.dirname(__file__), "artifacts_parity_harness.mjs")

pytestmark = pytest.mark.skipif(_NODE is None, reason="node not available")


def _js_render(results, requests):
    proc = subprocess.run(
        [_NODE, _HARNESS], input=json.dumps({"results": results, "requests": requests}),
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"harness failed: {proc.stderr}"
    return json.loads(proc.stdout)


# xlsx is a server-only binary format (openpyxl); the browser tab does not offer it, so it is
# not part of the JS/Python text-builder parity surface.
_SERVER_ONLY_FORMATS = {"xlsx"}


def _text_requests(results, mode):
    """Every text artifact × every browser-renderable format it supports."""
    reqs = []
    for a in list_artifacts(results, mode):
        if a["view"] == "text":
            for fmt in a["formats"]:
                if fmt not in _SERVER_ONLY_FORMATS:
                    reqs.append({"id": a["id"], "fmt": fmt})
    return reqs


@pytest.mark.parametrize("mode,results", [("measured", MEASURED), ("statevector", STATEVECTOR)])
def test_text_artifacts_match_publication_py(mode, results):
    reqs = _text_requests(results, mode)
    assert reqs, "fixture produced no text artifacts"
    js = _js_render(results, reqs)

    mismatches = []
    for req in reqs:
        key = f"{req['id']}|{req['fmt']}"
        py = render_artifact(results, mode, req["id"], req["fmt"])[0].decode("utf-8")
        if js.get(key) != py:
            mismatches.append(key)
    assert not mismatches, (
        "JS/publication.py drift on: " + ", ".join(mismatches)
        + " — update static/js/artifact_formats.js to match services/publication.py.")


def test_harness_covers_expected_artifacts():
    ids = {a["id"] for a in list_artifacts(MEASURED, "measured") if a["view"] == "text"}
    # the core tables + glossary must be present so the parity test is meaningful
    assert {"agreement", "performance", "resources", "metadata", "glossary"} <= ids
