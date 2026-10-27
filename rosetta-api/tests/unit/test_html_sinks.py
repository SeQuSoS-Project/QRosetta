"""Text from a report, a server response or the user reaches the page's HTML parser only
escaped: every interpolation in a template literal that builds markup goes through an escape
function or is on the reviewed list below, and every innerHTML-style assignment takes a
literal, such a template or a reviewed name."""
import re
from pathlib import Path

import pytest

_JS = Path(__file__).resolve().parents[2] / "static" / "js"

pytestmark = pytest.mark.skipif(not _JS.exists(), reason="frontend not present in this checkout")

_ESCAPES = ("_escapeHtml", "_artHtmlEscape")

# Interpolations in markup templates that are not escaped, by module: each is a number, a
# constant of the module (export_view_ui.js: icon path data), a ternary between literals,
# markup built from escaped parts, or text that never reaches markup (render_helpers.js: an
# Error message naming a template id).
_REVIEWED = {
    "app.js": {"BASE_URL"},
    "config.js": {
        "_multiRunEnabled ? 'checked' : ''", "_orderingEnabled ? 'checked' : ''",
        "_orderingEnabled ? '' : 'hidden'", "i", "i === defaultGlobal ? ' selected' : ''",
        "GLOBAL_LABELS[i] ?? i", "globalOpts", "ROW_CLASS", "LEVEL_COLUMN", "levelHeads",
        "desc ? ` — ${_escapeHtml(desc.split(':')[0])}` : ''",
        "getState().maxRunsPerRunner || 16", "isDisabled ? 'disabled' : ''",
        "isDisabled ? 'cursor-not-allowed text-gray-400' : ''",
        "isDefaultChecked && !isDisabled ? 'checked' : ''",
        "isDisabled ? 'disabled data-locked=\"1\"' : ''", "isDisabled ? 'line-through' : ''",
        "max === 0 || isDisabled ? 'disabled' : ''", "optionsHtml", "countsHtml",
    },
    "artifact_formats.js": {"head", "body"},
    "export_view_ui.js": {"d"},
    "render_helpers.js": {"id"},
}

# innerHTML-style assignments whose value is a name: markup saved from the same element
# before it was replaced, or a constant icon.
_REVIEWED_NAMES = {
    ("artifacts_renderer.js", "old"), ("utils.js", "old"), ("utils.js", "label"),
    ("utils.js", "COPY_ICON_SVG"), ("renderers.js", "originalText"), ("render_helpers.js", "icon"),
}

_SINK = re.compile(r"\.(?:innerHTML|outerHTML)\s*\+?=(?!=)\s*|\.insertAdjacentHTML\(\s*['\"][a-z]+['\"]\s*,\s*"
                   r"|document\.write(?:ln)?\(|\.srcdoc\s*=|createContextualFragment\(|\.parseFromString\(")


def _skip_string(text, i):
    quote = text[i]
    i += 1
    while text[i] != quote:
        i += 2 if text[i] == "\\" else 1
    return i + 1


def _regex_start(text, i):
    """True when the '/' at text[i] opens a regular-expression literal."""
    if text.startswith("//", i) or text.startswith("/*", i):
        return False
    k = i - 1
    while k >= 0 and text[k] in " \t\n":
        k -= 1
    return k < 0 or text[k] in "(,=:[!&|?{};+-*%<>~^" or text[max(0, k - 5):k + 1] == "return"


def _skip_regex(text, i):
    i += 1
    in_class = False
    while in_class or text[i] != "/":
        if text[i] == "\\":
            i += 1
        elif text[i] == "[":
            in_class = True
        elif text[i] == "]":
            in_class = False
        i += 1
    return i + 1


def _skip_comment(text, i):
    if text.startswith("//", i):
        return text.index("\n", i)
    return text.index("*/", i) + 2


def _template(text, i, found, html_parent=False):
    """Parse the template literal starting at text[i] == '`'; append (line, html, exprs) for
    it and any nested one to ``found``; return the index after it."""
    start = i
    i += 1
    static, exprs, nested = [], [], []
    seg = ""
    while text[i] != "`":
        if text[i] == "\\":
            seg += text[i:i + 2]
            i += 2
        elif text.startswith("${", i):
            static.append(seg)
            seg = ""
            j, depth = i + 2, 1
            while depth:
                c = text[j]
                if c in "'\"":
                    j = _skip_string(text, j)
                    continue
                if c == "`":
                    nested.append(j)
                    j = _template(text, j, [], False)
                    continue
                if text.startswith("//", j) or text.startswith("/*", j):
                    j = _skip_comment(text, j)
                    continue
                if c == "/" and _regex_start(text, j):
                    j = _skip_regex(text, j)
                    continue
                depth += {"{": 1, "}": -1}.get(c, 0)
                j += 1
            exprs.append((i + 2, text[i + 2:j - 1].strip()))
            i = j
        else:
            seg += text[i]
            i += 1
    static.append(seg)
    html = html_parent or bool(re.search(r"<[a-zA-Z/!]", "".join(static)))
    found.append((text.count("\n", 0, start) + 1, html, [e for _, e in exprs]))
    for pos in nested:
        _template(text, pos, found, html)
    return i + 1


def _templates(text):
    found, i = [], 0
    while i < len(text):
        c = text[i]
        if c in "'\"":
            i = _skip_string(text, i)
        elif text.startswith("//", i) or text.startswith("/*", i):
            i = _skip_comment(text, i)
        elif c == "/" and _regex_start(text, i):
            i = _skip_regex(text, i)
        elif c == "`":
            i = _template(text, i, found)
        else:
            i += 1
    return found


def _escaped(expr):
    for name in _ESCAPES:
        if expr.startswith(name + "(") and expr.endswith(")"):
            depth = 0
            for k, c in enumerate(expr[len(name):]):
                depth += {"(": 1, ")": -1}.get(c, 0)
                if depth == 0:
                    return k == len(expr) - len(name) - 1
    return False


def test_markup_templates_escape_every_interpolation():
    offenders = []
    for path in sorted(_JS.glob("*.js")):
        allowed = _REVIEWED.get(path.name, set())
        for line, html, exprs in _templates(path.read_text()):
            if not html:
                continue
            offenders += [f"{path.name}:{line}: ${{{e}}}" for e in exprs if not _escaped(e) and e not in allowed]
    assert not offenders, (
        "Markup templates interpolate text without _escapeHtml (escape it, or build the element "
        "with createElement/textContent):\n" + "\n".join(offenders))


def test_reviewed_interpolations_still_exist():
    for name, allowed in _REVIEWED.items():
        used = {e for _, html, exprs in _templates((_JS / name).read_text()) if html for e in exprs}
        assert allowed <= used, f"{name}: reviewed entries no longer used: {sorted(allowed - used)}"


def _value_after(text, end):
    """The assigned value from ``end`` to the end of the statement, roughly."""
    depth, j = 0, end
    while j < len(text):
        c = text[j]
        if c in "'\"":
            j = _skip_string(text, j)
            continue
        if c == "`":
            j = _template(text, j, [])
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif c == ";" and depth == 0:
            break
        j += 1
    return text[end:j].strip()


def test_every_html_sink_takes_a_literal_an_escaped_template_or_a_reviewed_name():
    offenders = []
    for path in sorted(_JS.glob("*.js")):
        text = path.read_text()
        for m in _SINK.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            value = _value_after(text, m.end())
            if re.fullmatch(r"'[^'\\]*'|\"[^\"\\]*\"", value):
                continue
            if value.startswith("`") and value.endswith("`"):
                continue
            if re.fullmatch(r"'[^']*'\s*\+\s*`[^`]*`|`[^`]*`(\s*\+\s*`[^`]*`)*", value, re.S):
                continue
            if (path.name, value) in _REVIEWED_NAMES:
                continue
            offenders.append(f"{path.name}:{line}: {m.group(0).strip()} {value[:80]}")
    assert not offenders, "HTML sinks with an unreviewed value:\n" + "\n".join(offenders)


def test_scanner_finds_an_unescaped_interpolation():
    found = _templates("const a = `<b>${name}</b>` + `${x}`; const s = '`'; el.innerHTML = `<i>${_escapeHtml(t)}</i>`;")
    assert [(html, exprs) for _, html, exprs in found] == [(True, ["name"]), (False, ["x"]), (True, ["_escapeHtml(t)"])]
    assert not _escaped("_escapeHtml(a) + b") and _escaped("_escapeHtml(a + b)")
