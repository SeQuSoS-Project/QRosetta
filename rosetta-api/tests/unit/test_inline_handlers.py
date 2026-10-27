"""The pages carry no inline script, event handler or style (their Content-Security-Policy
allows scripts and styles from this origin only), and every control main.js wires exists in
index.html."""
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parents[2] / "static"
_INDEX = _STATIC / "index.html"
_MAIN = _STATIC / "js" / "main.js"
_PAGES = sorted(_STATIC.glob("*.html"))

pytestmark = pytest.mark.skipif(
    not _INDEX.exists(), reason="frontend not present in this checkout")


class _Page(HTMLParser):
    """Elements of one page: ids, input names, inline handlers, styles and scripts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.input_names = set()
        self.handlers = []
        self.style_attrs = []
        self.style_elements = 0
        self.inline_scripts = 0
        self.script_urls = []
        self._in_script = False
        self._script_text = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "input" and a.get("name"):
            self.input_names.add(a["name"])
        for name, value in attrs:
            if name.startswith("on"):
                self.handlers.append(f"line {line}: <{tag} {name}=\"{value}\">")
            if name == "style":
                self.style_attrs.append(f"line {line}: <{tag} style=\"{value}\">")
            if name in ("href", "src", "action", "formaction") and (value or "").strip().lower().startswith("javascript:"):
                self.handlers.append(f"line {line}: <{tag} {name}=\"{value}\">")
        if tag == "style":
            self.style_elements += 1
        if tag == "script":
            self._in_script = "src" not in a
            self._script_text = ""
            if "src" in a:
                self.script_urls.append(a["src"])

    def handle_data(self, data):
        if self._in_script:
            self._script_text += data

    def handle_endtag(self, tag):
        if tag == "script":
            if self._in_script and self._script_text.strip():
                self.inline_scripts += 1
            self._in_script = False


def _parse(path: Path) -> _Page:
    page = _Page()
    page.feed(path.read_text())
    return page


def _controls() -> list:
    """(selector, event type) of every entry in main.js's CONTROLS table."""
    block = re.search(r"const CONTROLS = \[(.*?)\n\];", _MAIN.read_text(), re.S)
    assert block, "main.js no longer has a CONTROLS table"
    return re.findall(r"^\s*\['([^']+)', '([a-z]+)', ", block.group(1), re.M)


@pytest.mark.parametrize("page", _PAGES, ids=lambda p: p.name)
def test_page_has_no_inline_handlers_scripts_or_styles(page):
    parsed = _parse(page)
    assert not parsed.handlers, f"{page.name}: inline event handlers or javascript: URLs:\n" + "\n".join(parsed.handlers)
    assert parsed.inline_scripts == 0, f"{page.name}: inline <script> blocks; move them to a file under js/"
    assert parsed.style_elements == 0, f"{page.name}: <style> elements; move them to a file under css/"
    assert not parsed.style_attrs, f"{page.name}: style attributes; use classes:\n" + "\n".join(parsed.style_attrs)
    assert all(not re.match(r"[a-z]+:|//", url) for url in parsed.script_urls), (
        f"{page.name}: scripts from another origin: {parsed.script_urls}")


def test_index_ids_are_unique():
    ids = _parse(_INDEX).ids
    assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})


def test_every_wired_control_exists_in_index():
    page = _parse(_INDEX)
    ids = set(page.ids)
    missing = []
    for selector, _ in _controls():
        if selector.startswith("#"):
            if selector[1:] not in ids:
                missing.append(selector)
        else:
            m = re.fullmatch(r'input\[name="([\w-]+)"\]', selector)
            assert m, f"main.js CONTROLS uses a selector this test cannot check: {selector}"
            if m.group(1) not in page.input_names:
                missing.append(selector)
    assert not missing, f"main.js wires controls index.html does not have: {missing}"


def test_controls_table_has_no_duplicates():
    controls = _controls()
    assert len(controls) == len(set(controls)), [c for c in controls if controls.count(c) > 1]


def test_nothing_is_published_on_window_but_the_state_store():
    for path in sorted((_STATIC / "js").glob("*.js")):
        text = path.read_text()
        assert "Object.assign(window" not in text, f"{path.name} publishes names on window"
        for name in re.findall(r"^\s*window\.([A-Za-z_$][\w$]*)\s*=", text, re.M):
            if name.startswith("on"):
                continue
            assert (path.name, name) in {("state.js", "dispatch"), ("state.js", "getState")}, f"{path.name}: window.{name}"


def test_generated_markup_has_no_inline_handlers_or_styles():
    """Markup built in JS wires its controls with addEventListener and styles them with
    classes or the CSSOM; an on*= or style= attribute in markup is blocked by the policy."""
    offenders = []
    for path in sorted((_STATIC / "js").glob("*.js")):
        for lineno, line in enumerate(path.read_text().split("\n"), 1):
            if re.search(r"""\son(?:click|dbl\w+|change|input|submit|key\w+|mouse\w+|pointer\w+|focus\w*|blur|load|error|drag\w*|drop|scroll|toggle)\s*=\s*\\?["'`]""", line) or re.search(
                    r"""setAttribute\(\s*['"](?:on[a-z]+|style)['"]""", line) or re.search(
                    r"""<[a-zA-Z][^>]*\sstyle\s*=\s*\\?["'`]""", line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "Inline event handlers or style attributes in JS-generated markup:\n" + "\n".join(offenders)
    )


def test_index_loads_exactly_one_module_entry_point():
    html = _INDEX.read_text()
    assert len(re.findall(r"<script\b", html)) == 1
    assert re.search(r'<script type="module" src="js/main\.js[^"]*"></script>', html)
