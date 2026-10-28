"""Harness 4: client-supplied reports with odd values, sent in process to every route that
reads one (POST /export, /summary, /publication/artifacts, /publication/render,
/timing-caveats). The oracle: no 5xx, every answer within ``REQUEST_LIMIT_SEC`` and without
raising the process's peak RSS by more than ``MEMORY_LIMIT_MIB``, crate ZIP
member names free of control, bidi and '..' parts. Crate CSV cells that a spreadsheet would
read as a formula (first character = + - @, tab or CR) are counted, not failed: crate tables
hold values as recorded (DESIGN_DECISIONS.md, "CSV cells in crates").

Usage: python scripts/fuzz/report_fuzz.py SECONDS OUTDIR
"""

import copy
import csv
import hashlib
import io
import json
import logging
import os
import resource
import random
import sys
import tempfile
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fuzz_targets  # noqa: E402,F401  (sets sys.path for the API)

REQUEST_LIMIT_SEC = 10.0
MEMORY_LIMIT_MIB = 256
csv.field_size_limit(sys.maxsize)
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
BIDI = "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200e\u200f\u061c"
ODD_STRINGS = [
    "=HYPERLINK(\"http://example.invalid\",\"x\")", "+1+1", "-2+3", "@SUM(1,1)", "\t=1",
    "\r=1", "=cmd|' /C calc'!A0", "abc\u202edcba", "\u2066x\u2069", "\u200f", "../../etc",
    "a/../b", "/abs", "C:\\x", "\x00", "a\nb", "<img src=x onerror=alert(1)>", "]]>",
    "</text><script>1</script>", "\ud83d\ude00", "x" * 300,
]


def odd_values(rng: random.Random):
    """One odd JSON value."""
    kind = rng.randrange(12)
    if kind == 0:
        return rng.choice(ODD_STRINGS)
    if kind == 1:
        return rng.choice(BIDI) * rng.randrange(1, 50) + rng.choice(ODD_STRINGS)
    if kind == 2:
        return "y" * rng.choice([10_000, 200_000, 900_000])
    if kind == 3:
        depth = rng.choice([50, 1_000, 20_000])
        value = []
        for _ in range(depth):
            value = [value]
        return value
    if kind == 4:
        return {f"k{i}": i for i in range(rng.choice([1_000, 50_000]))}
    if kind == 5:
        return rng.choice([10 ** 400, -10 ** 30, 2 ** 63, -0.0, 1e308, 5e-324])
    if kind == 6:
        return rng.choice([None, True, [], {}, "", 0])
    if kind == 7:
        return [rng.choice(ODD_STRINGS) for _ in range(rng.randrange(1, 20))]
    if kind == 8:
        return {rng.choice(ODD_STRINGS): rng.choice(ODD_STRINGS)}
    if kind == 9:
        return rng.choice(["qiskit", "cirq~opt1~run2", "QISKIT", "qiskit~opt99999999999~run1"])
    if kind == 10:
        return str(rng.uniform(-1e6, 1e6))
    return rng.choice(ODD_STRINGS) + "," + rng.choice(ODD_STRINGS)


def _paths(value, prefix=()):
    yield prefix
    if len(prefix) > 12:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _paths(item, prefix + (key,))
    elif isinstance(value, list):
        for i, item in enumerate(value[:20]):
            yield from _paths(item, prefix + (i,))


def mutate(report: dict, rng: random.Random, edits: int) -> dict:
    """``report`` with ``edits`` values replaced by odd ones, keys renamed or dropped."""
    out = copy.deepcopy(report)
    for _ in range(edits):
        paths = [p for p in _paths(out) if p]
        if not paths:
            break
        path = rng.choice(paths)
        parent = out
        for key in path[:-1]:
            parent = parent[key]
        action = rng.randrange(6)
        if action == 0 and isinstance(parent, dict):
            del parent[path[-1]]
        elif action == 1 and isinstance(parent, dict):
            parent[rng.choice(ODD_STRINGS)] = parent.pop(path[-1])
        else:
            parent[path[-1]] = odd_values(rng)
    return out


def base_reports() -> list:
    from tests.unit.test_publication import MEASURED, STATEVECTOR
    reports = [MEASURED, STATEVECTOR]
    example = fuzz_targets.REPO / "examples" / "ro-crate-export" / "results.json"
    if example.exists():
        reports.append(json.loads(example.read_text()))
    return reports


def make_client(workdir: Path):
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{workdir / 'fuzz.db'}")
    os.environ.setdefault("QROSETTA_JOB_SPILL_DIR", str(workdir / "spill"))
    from fastapi.testclient import TestClient
    import services.storage as storage
    from main import app
    from services.security import limiter
    storage.MOCK_S3_DIR = str(workdir / "s3")
    limiter.enabled = False
    logging.disable(logging.WARNING)
    return TestClient(app, raise_server_exceptions=False)


TABLE_VIEWS = ["agreement", "statistical_test", "counts", "marginals", "hamming", "rank",
               "fidelity_heatmap", "js_divergence_heatmap", "execution_time", "resource_usage",
               "metadata"]
FIGURE_ARTIFACTS = {"agreement_distribution", "counts_overview", "fidelity_heatmap",
                    "hamming_weight", "rank_probability", "performance_time"}
RENDER_ARTIFACTS = sorted(FIGURE_ARTIFACTS) + [
    "agreement", "counts_table", "matrix_fidelity", "matrix_js", "metadata", "performance",
    "qubit_marginals_table", "resources", "statistical_test", "glossary"]


def requests_for(report: dict, rng: random.Random) -> list:
    """(path, json body) for each route that reads a supplied report."""
    artifact = rng.choice(RENDER_ARTIFACTS)
    fmt = "svg" if artifact in FIGURE_ARTIFACTS else rng.choice(["csv", "latex", "html"])
    items = [{"view": view, "formats": ["csv"]} for view in TABLE_VIEWS]
    return [
        ("/export", {"results": report, "include_statevectors": rng.random() < 0.2,
                     "author_name": rng.choice(ODD_STRINGS[:12]),
                     "publication_artifacts": {"items": items}}),
        ("/summary", {"results": report}),
        ("/publication/artifacts", {"results": report}),
        ("/publication/render", {"results": report, "artifact_id": artifact, "format": fmt}),
        ("/timing-caveats", {"raw_results": report.get("raw_results")
                             if isinstance(report.get("raw_results"), list) else []}),
    ]


def check_crate(body: bytes, stats: dict) -> list:
    """Problems with a crate's member names; counts formula-like CSV cells into ``stats``."""
    problems = []
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        for name in zf.namelist():
            parts = name.split("/")
            if ".." in parts or name.startswith("/") or any(
                    ord(ch) < 32 or ch in BIDI or ch == "\\" for ch in name):
                problems.append(f"member name {name!r}")
            if name.endswith(".csv"):
                text = zf.read(name).decode("utf-8")
                for row in csv.reader(io.StringIO(text)):
                    for cell in row:
                        if cell.startswith(FORMULA_START):
                            stats["formula_like_cells"] = stats.get("formula_like_cells", 0) + 1
                            try:
                                float(cell)
                            except ValueError:
                                stats["formula_like_text_cells"] = stats.get(
                                    "formula_like_text_cells", 0) + 1
                                if cell in ODD_STRINGS:
                                    stats.setdefault("formula_examples", set()).add(
                                        f"{name}: {cell[:40]!r}")
    return problems


def run(seconds: float, outdir: Path, seed: int = 0) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="report-fuzz-", dir=os.environ.get("TMPDIR")))
    client = make_client(workdir)
    rng = random.Random(seed)  # noqa: S311
    reports = base_reports()
    stats: dict = {"requests": 0, "by_status": {}}
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        report = mutate(rng.choice(reports), rng, rng.randrange(1, 6))
        for path, body in requests_for(report, rng):
            try:
                data = json.dumps(body, allow_nan=False).encode()
            except (ValueError, RecursionError):
                continue
            peak_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            start = time.perf_counter()
            response = client.post(path, content=data, headers={"Content-Type": "application/json"})
            elapsed = time.perf_counter() - start
            grew = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 - peak_before
            stats["requests"] += 1
            key = f"{path} {response.status_code}"
            stats["by_status"][key] = stats["by_status"].get(key, 0) + 1
            problems = []
            if response.status_code >= 500:
                problems.append(f"status {response.status_code}: {response.text[:200]}")
            if elapsed > REQUEST_LIMIT_SEC:
                problems.append(f"took {elapsed:.1f} s")
            if grew > MEMORY_LIMIT_MIB:
                problems.append(f"raised the process's peak RSS by {grew:.0f} MiB")
            if path == "/export" and response.status_code == 200:
                problems += check_crate(response.content, stats)
            if problems:
                name = hashlib.sha256(data).hexdigest()[:16]
                (outdir / f"{name}.json").write_bytes(data)
                (outdir / f"{name}.txt").write_text(f"{path}\n" + "\n".join(problems) + "\n")
                print(f"FINDING {path}: {problems[0][:120]} ({name})", flush=True)
    stats["formula_examples"] = sorted(stats.get("formula_examples", set()))
    return stats


if __name__ == "__main__":
    result = run(float(sys.argv[1]), Path(sys.argv[2]),
                 seed=int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    print(json.dumps(result, indent=2, default=str))
