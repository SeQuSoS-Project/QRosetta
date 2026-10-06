"""Every popover in index.html follows the .qr-popover anatomy (a header holding the title the
dialog is labelled by, one scrolling body, an optional footer), and every settings chip names an existing
popover and has a summary in settings_bar.js."""
import re
from html.parser import HTMLParser
from pathlib import Path

_STATIC = Path(__file__).resolve().parents[2] / "static"
_VOID = {"input", "br", "img", "meta", "link", "hr", "source", "area", "col", "wbr"}


class _Tree(HTMLParser):
    """Element tree: (tag, attrs, children) nodes."""

    def __init__(self):
        super().__init__()
        self.root = ("root", {}, [])
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = (tag, dict(attrs), [])
        self._stack[-1][2].append(node)
        if tag not in _VOID:
            self._stack.append(node)

    def handle_endtag(self, tag):
        if len(self._stack) > 1 and self._stack[-1][0] == tag:
            self._stack.pop()


def _walk(node):
    yield node
    for child in node[2]:
        yield from _walk(child)


def _classes(node):
    return set((node[1].get("class") or "").split())


def _tree():
    parser = _Tree()
    parser.feed((_STATIC / "index.html").read_text())
    return parser.root


def _popovers(root):
    return [n for n in _walk(root) if n[1].get("role") == "dialog" and "qr-popover" in _classes(n)]


_PARTS = {"qr-popover-header", "qr-popover-body", "qr-popover-footer"}


def test_every_popover_has_header_title_and_one_body():
    root = _tree()
    popovers = _popovers(root)
    assert len(popovers) >= 7
    for tag, attrs, children in popovers:
        pid = attrs.get("id")
        kinds = [c for c in children if not isinstance(c, str)]
        parts = [_classes(c) & _PARTS for c in kinds]
        assert parts in ([{"qr-popover-header"}, {"qr-popover-body"}],
                         [{"qr-popover-header"}, {"qr-popover-body"}, {"qr-popover-footer"}]), \
            f"{pid}: children must be header, body and an optional footer"
        titles = [n for n in _walk(kinds[0]) if "qr-popover-title" in _classes(n)]
        assert len(titles) == 1 and titles[0][1].get("id") == attrs.get("aria-labelledby"), f"{pid}: title id"
        assert "hidden" in _classes((tag, attrs, children)), f"{pid}: starts hidden"


def test_every_chip_names_a_popover_and_has_a_summary():
    root = _tree()
    popover_ids = {n[1]["id"] for n in _popovers(root)}
    chips = [n for n in _walk(root) if "settings-chip" in _classes(n)]
    assert chips
    summaries = set(re.findall(r"'(chip-[a-z-]+)':\s*\[", (_STATIC / "js" / "settings_bar.js").read_text()))
    for _, attrs, _ in chips:
        assert attrs.get("data-popover") in popover_ids, f"{attrs.get('id')}: no such popover"
        assert attrs.get("id") in summaries, f"{attrs.get('id')}: no summary in settings_bar.js"
