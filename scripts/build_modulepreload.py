#!/usr/bin/env python3
"""Writes a <link rel="modulepreload"> for every module in each page's static import graph
into the page's marked block, so the browser fetches the whole graph in one round trip.
--check exits 1 when a page's block differs from the graph."""
import re
import sys
from collections import deque
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "rosetta-api" / "static"
PAGES = ("index.html", "share.html")

IMPORT = re.compile(r"""^\s*(?:import|export)\s(?:[^'"]*?from\s+)?['"]\./([\w.-]+\.js)['"]""", re.M)
ENTRY = re.compile(r'<script type="module" src="js/([\w.-]+\.js)(?:\?v=[\w.]+)?"></script>')
BLOCK = re.compile(r"(?P<indent>[ \t]*)<!-- modulepreload -->\n.*?[ \t]*<!-- /modulepreload -->\n", re.S)


def import_graph(js_dir: Path = STATIC / "js") -> dict:
    return {path.name: IMPORT.findall(path.read_text()) for path in sorted(js_dir.glob("*.js"))}


def preload_order(entry: str, graph: dict) -> list:
    """Modules reachable from entry, excluding it, by first-discovery depth then name."""
    depth = {entry: 0}
    queue = deque([entry])
    while queue:
        name = queue.popleft()
        for dep in graph.get(name, ()):
            if dep not in depth:
                if dep not in graph:
                    raise SystemExit(f"{name} imports {dep}, which does not exist")
                depth[dep] = depth[name] + 1
                queue.append(dep)
    return sorted((name for name in depth if name != entry), key=lambda n: (depth[n], n))


def render_block(modules: list, indent: str = "    ") -> str:
    lines = [f"{indent}<!-- modulepreload -->"]
    lines += [f'{indent}<link rel="modulepreload" href="js/{name}">' for name in modules]
    lines.append(f"{indent}<!-- /modulepreload -->")
    return "\n".join(lines) + "\n"


def page_entry(html: str, page: str) -> str:
    match = ENTRY.search(html)
    if not match:
        raise SystemExit(f"{page}: no <script type=\"module\" src=\"js/...\"> entry")
    return match.group(1)


def updated_html(html: str, page: str, graph: dict) -> str:
    modules = preload_order(page_entry(html, page), graph)
    match = BLOCK.search(html)
    if match:
        return html[:match.start()] + render_block(modules, match.group("indent")) + html[match.end():]
    stylesheet = html.find('<link rel="stylesheet"')
    at = html.index("\n", stylesheet) + 1 if stylesheet >= 0 else html.rfind("\n", 0, html.index("</head>")) + 1
    return html[:at] + render_block(modules) + html[at:]


def main(argv: list) -> int:
    check = "--check" in argv
    graph = import_graph()
    stale = []
    for page in PAGES:
        path = STATIC / page
        html = path.read_text()
        new = updated_html(html, page, graph)
        if new != html:
            stale.append(page)
            if not check:
                path.write_text(new)
    if check and stale:
        print("modulepreload block out of date in: " + ", ".join(stale)
              + "; run scripts/build_modulepreload.py", file=sys.stderr)
        return 1
    for page in stale:
        print(f"updated {page}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
