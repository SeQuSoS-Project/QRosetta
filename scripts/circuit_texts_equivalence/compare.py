"""The Circuits view's panes as static/js/circuit_panes.js builds them (circuitPanes) against
services.circuit_texts.circuit_panes, which GET /jobs/{id}/circuit-texts serves: the same
panes in the same order with the same id, kind, key, group and text.

    python compare.py <dir or file> [...]

Reads every *.json report (a report, a job envelope with results, or a saved run) and every
results.json inside *.zip crates; a playlist counts once per circuit. Exits non-zero on any
difference. Needs node and the API's Python environment."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(REPO / "rosetta-api"), str(REPO / "shared")]
from services.circuit_texts import circuit_panes  # noqa: E402

HARNESS = REPO / "rosetta-api" / "tests" / "unit" / "circuit_text_harness.mjs"
FIELDS = ("id", "kind", "key", "group", "text")
BATCH = 200


def _load(text):
    return json.loads(text, parse_constant=lambda _: None)


def _reports(path: Path):
    if path.suffix == ".zip":
        try:
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    if name.endswith("results.json"):
                        yield f"{path}!{name}", _load(zf.read(name))
        except (zipfile.BadZipFile, OSError, ValueError):
            return
        return
    try:
        yield str(path), _load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return


def _circuits(doc):
    if not isinstance(doc, dict):
        return []
    if not any(k in doc for k in ("raw_results", "benchmark_summary", "input_qasm", "compiled_circuits")):
        for key in ("results", "report", "full_results"):
            if isinstance(doc.get(key), dict):
                return _circuits(doc[key])
        return []
    tasks = doc.get("benchmark_summary")
    if isinstance(tasks, list):
        return [(f"task {i}", t) for i, t in enumerate(tasks)]
    return [("", doc)]


def _js(reports):
    payload = {"calls": [{"fn": "circuitPanes", "args": [r]} for r in reports]}
    out = subprocess.run(["node", str(HARNESS)], input=json.dumps(payload), capture_output=True, text=True,
                         check=True)
    return json.loads(out.stdout)["results"]


def _project(panes):
    return [{k: p.get(k) for k in FIELDS} for p in panes]


def main(paths):
    cases = []
    for root in map(Path, paths):
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.suffix in (".json", ".zip"))
        for f in files:
            for where, doc in _reports(f):
                cases += [(f"{where} {label}".strip(), report) for label, report in _circuits(doc)]
    differences, panes, texts = 0, 0, 0
    for start in range(0, len(cases), BATCH):
        chunk = cases[start:start + BATCH]
        for (where, report), js in zip(chunk, _js([r for _, r in chunk])):
            py = _project(circuit_panes(report))
            js = _project(js)
            panes += len(py)
            texts += sum(p["text"] is not None for p in py)
            if py != js:
                differences += 1
                print(f"DIFFERS {where}")
    print(f"{len(cases)} circuits, {panes} panes ({texts} with text): {differences} differences")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
