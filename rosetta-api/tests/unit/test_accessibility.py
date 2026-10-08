"""Static accessibility checks of the app page and the manual: every form control has a name,
every modal dialog goes through modal.js, the page has one h1, a skip link and a live region,
the heatmap's classes carry a symbol, and the manual's tables scroll inside their own box."""
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.unit.frontend_harness import call_js, requires_node

_STATIC = Path(__file__).resolve().parents[2] / "static"
_JS = _STATIC / "js"
_VOID = {"input", "br", "img", "meta", "link", "hr", "source", "area", "col", "wbr"}

# Modal dialog id -> the module that opens and closes it.
MODALS = {
    "auth-modal": "auth.js",
    "history-modal": "history.js",
    "gen-modal": "batch.js",
    "visualizer-panel": "renderers.js",
}


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = ("root", {}, [], None)
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = (tag, dict(attrs), [], self._stack[-1])
        self._stack[-1][2].append(node)
        if tag not in _VOID:
            self._stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                return


def _tree(name="index.html"):
    t = _Tree()
    t.feed((_STATIC / name).read_text())
    return t.root


def _walk(node):
    yield node
    for child in node[2]:
        yield from _walk(child)


def _ancestors(node):
    node = node[3]
    while node is not None:
        yield node
        node = node[3]


def test_every_form_control_has_an_accessible_name():
    root = _tree()
    labelled = {n[1].get("for") for n in _walk(root) if n[0] == "label"}
    missing = []
    for tag, attrs, _children, parent in _walk(root):
        if tag not in ("input", "select", "textarea"):
            continue
        node = (tag, attrs, _children, parent)
        hidden = "hidden" in (attrs.get("class") or "").split() or attrs.get("aria-hidden") == "true" or attrs.get("type") == "hidden"
        if hidden:
            continue
        named = (attrs.get("id") in labelled or attrs.get("aria-label") or attrs.get("aria-labelledby")
                 or any(a[0] == "label" for a in _ancestors(node)))
        if not named:
            missing.append(attrs.get("id") or attrs)
    assert not missing, f"form controls without a label: {missing}"


def test_every_modal_dialog_uses_the_shared_modal_helper():
    root = _tree()
    modals = {n[1]["id"] for n in _walk(root) if n[1].get("role") == "dialog" and n[1].get("aria-modal") == "true"}
    assert modals == set(MODALS), "a modal dialog in index.html has no entry in MODALS"
    for dialog_id, module in MODALS.items():
        text = (_JS / module).read_text()
        assert "from './modal.js'" in text and "openModal(" in text and "closeModal(" in text, module
        assert not re.search(rf"getElementById\('{dialog_id}'\)\.classList\.(remove|add)\('hidden'\)", text), (
            f"{module} shows or hides {dialog_id} itself instead of through openModal/closeModal")
    for path in _JS.glob("*.js"):
        if path.name == "modal.js":
            continue
        assert not re.search(r"key === 'Escape'\) close(AuthModal|HistoryModal|GeneratorModal|Visualizer)", path.read_text()), path.name


def test_modal_dialogs_sit_directly_in_body_so_the_page_behind_can_be_inert():
    root = _tree()
    body = next(n for n in _walk(root) if n[0] == "body")
    top = {n[1].get("id") for n in body[2]}
    assert set(MODALS) <= top


def test_page_has_one_h1_a_skip_link_and_a_polite_live_region():
    root = _tree()
    nodes = list(_walk(root))
    assert sum(1 for n in nodes if n[0] == "h1") == 1
    body = next(n for n in nodes if n[0] == "body")
    first = body[2][0]
    assert first[0] == "a" and first[1].get("href") == "#main-content"
    assert any(n[0] == "main" and n[1].get("id") == "main-content" for n in nodes)
    region = next(n for n in nodes if n[1].get("id") == "sr-announcer")
    assert region[1].get("aria-live") == "polite"


def test_result_panels_are_tabpanels_labelled_by_their_tab():
    text = (_JS / "renderers.js").read_text()
    panels = re.search(r"const TAB_PANELS = \{(.*?)\};", text, re.S).group(1)
    expected = {}
    for tab, keys in re.findall(r"'?([\w-]+)'?: \[([^\]]*)\]", panels):
        for key in re.findall(r"'([\w-]+)'", keys):
            expected[f"{key}-panel"] = f"tab-{tab}"
    root = _tree()
    for node in _walk(root):
        pid = node[1].get("id")
        if pid in expected:
            assert node[1].get("role") == "tabpanel", pid
            assert node[1].get("aria-labelledby") == expected[pid], pid


def test_manual_tables_scroll_inside_their_own_box():
    root = _tree("docs.html")
    tables = [n for n in _walk(root) if n[0] == "table"]
    assert tables
    for table in tables:
        assert "table-scroll" in (table[3][1].get("class") or "").split()


def test_no_low_contrast_gray_text_outside_inactive_controls():
    allowed = {"config.js", "compilers_config.js"}
    offenders = []
    for path in _JS.glob("*.js"):
        if path.name in allowed:
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if "text-gray-400" in line or ("text-gray-300" in line and "qr-placeholder-tab" not in line):
                offenders.append(f"{path.name}:{i}")
    assert not offenders, offenders


def _contrast(a, b):
    def lum(hex_):
        n = int(hex_[1:], 16)
        def lin(c):
            v = c / 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255)
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@requires_node
def test_every_heatmap_class_has_a_symbol_readable_on_its_colour():
    hexes, glyphs = call_js(["tables_renderer.js"], [("AGREEMENT_HEX", []), ("AGREEMENT_GLYPH", [])])
    assert set(hexes) <= set(glyphs)
    colours = sorted(set(hexes.values()) | {"#7a8fa6"})
    texts = call_js(["tables_renderer.js"], [("textColourOn", [c]) for c in colours])
    for colour, text in zip(colours, texts):
        assert _contrast(colour, text) >= 3, (colour, text)


@requires_node
@pytest.mark.parametrize("text,first", [
    ("14 of 14 backends returned a result. Qiskit differs.", "14 of 14 backends returned a result."),
    ("No sentence end", "No sentence end"),
    ("Lowest fidelity 1 - 0.0e+0 here. Next.", "Lowest fidelity 1 - 0.0e+0 here."),
])
def test_first_sentence_of_an_announcement(text, first):
    assert call_js(["announce.js"], [("firstSentence", [text])]) == [first]
