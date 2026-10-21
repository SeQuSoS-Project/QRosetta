"""Write the dispatched circuits of every bundled circuit and algorithm template as canonical JSON lines.

Usage: python dump_prepare.py <out.jsonl> [max_source_bytes]
Covers rosetta-api/benchmarks/**/*.qasm, rosetta-api/circuits/*.qasm and every algorithm template
at a few sizes. Each source goes through prepare_statevector_dispatch and prepare_measured_dispatch
with apply_preprocessing True and False; a refusal is recorded as its exception type and message.
A file larger than max_source_bytes (default 130000) is recorded as skipped: the pytket round-trip
of the larger MQT Grover circuits exceeds a 4 GiB container. Seconds per source go to stderr.
"""
import json
import logging
import sys
import time
from pathlib import Path

logging.disable(logging.CRITICAL)

from services import circuit_library  # noqa: E402
from services.circuit_resolver import prepare_measured_dispatch, prepare_statevector_dispatch  # noqa: E402

API = Path(__file__).resolve().parents[2] / "rosetta-api"
TEMPLATE_SIZES = (2, 3, 5, 8, 12)


def outcome(func, *args):
    try:
        return {"ok": func(*args)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def sources(max_bytes):
    files = sorted(API.glob("benchmarks/**/*.qasm")) + sorted(API.glob("circuits/*.qasm"))
    for path in files:
        size = path.stat().st_size
        if size > max_bytes:
            yield str(path.relative_to(API)), {"skipped": f"{size} bytes > {max_bytes}"}
        else:
            yield str(path.relative_to(API)), {"ok": path.read_text()}
    for algorithm in circuit_library.load_algorithms():
        for n in TEMPLATE_SIZES:
            yield f"template:{algorithm}:{n}", outcome(circuit_library.generate_circuit, algorithm, n)


def main():
    max_bytes = int(sys.argv[2]) if len(sys.argv) > 2 else 130000
    counts = {"sources": 0, "calls": 0, "errors": 0, "source_errors": 0, "skipped": 0}
    with Path(sys.argv[1]).open("w") as handle:
        for name, source in sources(max_bytes):
            started = time.perf_counter()
            entry = {"source": name, "text": source}
            counts["sources"] += 1
            if "ok" in source:
                for flag in (True, False):
                    for mode, func in (("statevector", prepare_statevector_dispatch),
                                       ("measured", prepare_measured_dispatch)):
                        result = outcome(func, source["ok"], flag)
                        entry[f"{mode}:preprocessing={flag}"] = result
                        counts["calls"] += 1
                        counts["errors"] += "error" in result
            elif "skipped" in source:
                counts["skipped"] += 1
            else:
                counts["source_errors"] += 1
            handle.write(json.dumps(entry, sort_keys=True, default=repr) + "\n")
            handle.flush()
            print(f"{time.perf_counter() - started:8.2f}s {name}", file=sys.stderr, flush=True)
    print(json.dumps({"python": sys.version.split()[0], **counts}))


if __name__ == "__main__":
    main()
