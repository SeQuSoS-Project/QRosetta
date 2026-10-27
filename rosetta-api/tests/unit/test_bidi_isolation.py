"""Bidirectional isolation of displayed text (V2-05): the page and the share page isolate every
text node holding a bidi formatting character or a right-to-left letter, in the DOM only; the
publication preview modules, which must match the Python builders, are not involved."""
import re
from pathlib import Path

import pytest

from tests.unit.frontend_harness import call_js, requires_node

_JS = Path(__file__).resolve().parents[2] / "static" / "js"


@requires_node
@pytest.mark.parametrize("text,expected", [
    ("‮gnp.exe‬", True),
    ("note ⁧x⁩", True),
    ("a‏b", True),
    ("שלום", True),
    ("مرحبا", True),
    ("\U00010900", True),
    ("Qiskit 1.4.4 (complex128)", False),
    ("", False),
    ("ä ö ü — × ≤ ↺", False),
])
def test_v2_05_needs_isolation(text, expected):
    assert call_js(["bidi_isolation.js"], [("needsIsolation", [text])]) == [expected]


def test_v2_05_both_pages_watch_their_body():
    for entry in ("main.js", "share_main.js"):
        text = (_JS / entry).read_text()
        assert "from './bidi_isolation.js'" in text, entry
        assert "watchBidi(document.body);" in text, entry


def test_v2_05_isolation_is_a_leaf_used_only_by_the_entry_points():
    text = (_JS / "bidi_isolation.js").read_text()
    assert not re.search(r"^\s*import\s", text, re.M)
    users = sorted(p.name for p in _JS.glob("*.js") if "bidi_isolation.js" in p.read_text() and p.name != "bidi_isolation.js")
    assert users == ["main.js", "share_main.js"]
    for path in _JS.glob("artifact_*.js"):
        assert "bdi" not in path.read_text().lower(), path.name
