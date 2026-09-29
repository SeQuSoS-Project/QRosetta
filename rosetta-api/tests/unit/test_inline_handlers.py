"""The inline on*= handlers in index.html, the names js/main.js puts on window, and the
modules that export them must all agree.
"""
import re
from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parents[2] / "static"
_INDEX = _STATIC / "index.html"
_MAIN = _STATIC / "js" / "main.js"

# Names that appear in an on*= attribute but are language keywords, not handlers.
_NOT_HANDLERS = {"if", "return", "this", "function", "for", "while", "typeof", "new"}

pytestmark = pytest.mark.skipif(
    not _INDEX.exists(), reason="frontend not present in this checkout")


def _handlers_in_html() -> set:
    html = _INDEX.read_text()
    found = set(re.findall(r'\son[a-z]+="\s*([A-Za-z_$][\w$]*)\s*\(', html))
    return found - _NOT_HANDLERS


def _names_attached_to_window() -> set:
    """The identifiers listed in main.js's Object.assign(window, {...})."""
    block = re.search(r"Object\.assign\(window,\s*\{(.*?)\n\}\);", _MAIN.read_text(), re.S)
    assert block, "main.js no longer has an Object.assign(window, {...}) block"
    return set(re.findall(r"^\s*([A-Za-z_$][\w$]*),\s*$", block.group(1), re.M))


def _exported_names() -> dict:
    """Exported name -> module filename, across the frontend."""
    exported = {}
    for path in sorted((_STATIC / "js").glob("*.js")):
        for line in path.read_text().split("\n"):
            m = re.match(
                r"^export\s+(?:async\s+)?(?:function\s+([A-Za-z_$][\w$]*)"
                r"|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=|class\s+([A-Za-z_$][\w$]*))",
                line,
            )
            if m:
                exported[next(g for g in m.groups() if g)] = path.name
    return exported


def test_every_inline_handler_is_attached_to_window():
    missing = sorted(_handlers_in_html() - _names_attached_to_window())
    assert not missing, (
        f"index.html calls {missing} from an inline handler, but main.js does not put them "
        "on window. Those controls would do nothing when clicked."
    )


def test_every_attached_name_is_actually_exported():
    exported = _exported_names()
    unresolved = sorted(n for n in _names_attached_to_window() if n not in exported)
    assert not unresolved, f"main.js attaches names no module exports: {unresolved}"


def test_no_stale_names_attached():
    """Every name main.js attaches is used by an on*= attribute in index.html."""
    stale = sorted(_names_attached_to_window() - _handlers_in_html())
    assert not stale, f"main.js attaches unused names: {stale}"


def test_index_loads_exactly_one_module_entry_point():
    html = _INDEX.read_text()
    assert 'type="module"' in html, "index.html should load the frontend as a module"
    assert not re.search(r'<script defer src="js/', html), (
        "index.html still loads individual scripts; the module graph is the entry point now"
    )
