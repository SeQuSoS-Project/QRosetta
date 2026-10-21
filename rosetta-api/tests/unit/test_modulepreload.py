"""index.html and share.html preload exactly the modules their entry point's static import
graph reaches (scripts/build_modulepreload.py writes the block)."""
import importlib.util
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_STATIC = _ROOT / "rosetta-api" / "static"
_SPEC = importlib.util.spec_from_file_location("build_modulepreload", _ROOT / "scripts" / "build_modulepreload.py")
_builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_builder)

_PRELOAD = re.compile(r'<link rel="modulepreload" href="([^"]+)">')


def _reachable(entry: str) -> set:
    graph = _builder.import_graph()
    seen, stack = set(), [entry]
    while stack:
        for dep in graph[stack.pop()]:
            if dep not in seen:
                seen.add(dep)
                stack.append(dep)
    return seen - {entry}


def test_blocks_match_the_import_graph():
    graph = _builder.import_graph()
    stale = [page for page in _builder.PAGES
             if _builder.updated_html((_STATIC / page).read_text(), page, graph) != (_STATIC / page).read_text()]
    assert not stale, f"modulepreload block out of date in {stale}; run scripts/build_modulepreload.py"


def test_each_page_preloads_its_whole_graph_once():
    for page in _builder.PAGES:
        html = (_STATIC / page).read_text()
        hrefs = _PRELOAD.findall(html)
        assert len(hrefs) == len(set(hrefs)), f"{page}: duplicate modulepreload links"
        assert all(href.startswith("js/") and "?" not in href for href in hrefs), (
            f"{page}: a preload URL must equal the import's URL (js/<name>.js, no query) or the module is fetched twice")
        entry = _builder.page_entry(html, page)
        assert {href[3:] for href in hrefs} == _reachable(entry), page


def test_bare_imports_are_part_of_the_graph():
    graph = _builder.import_graph()
    assert "autosave.js" in graph["main.js"]


def test_pages_share_one_asset_version():
    versions = {page: set(re.findall(r'\?v=([\w.]+)"', (_STATIC / page).read_text())) for page in _builder.PAGES}
    assert all(len(v) == 1 for v in versions.values()), versions
    assert len(set().union(*versions.values())) == 1, versions
