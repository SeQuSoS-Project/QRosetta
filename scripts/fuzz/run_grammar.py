"""Harness 2 long run: generated OpenQASM 2.0 programs through ``grammar_oracle`` for a given
time; each failing program is saved to OUTDIR with its message, and the run goes on.

Usage: python scripts/fuzz/run_grammar.py SECONDS OUTDIR [--no-qiskit]
"""

import collections
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hypothesis import HealthCheck, given, settings  # noqa: E402

import fuzz_targets  # noqa: E402
from qasm_grammar import programs  # noqa: E402


def run(seconds: float, outdir: Path, qiskit: bool = True) -> collections.Counter:
    outdir.mkdir(parents=True, exist_ok=True)
    stats = collections.Counter()
    deadline = time.monotonic() + seconds

    @settings(max_examples=500, deadline=None, database=None, derandomize=False,
              suppress_health_check=list(HealthCheck))
    @given(programs())
    def batch(program):
        try:
            stats[fuzz_targets.grammar_oracle(program, qiskit=qiskit)] += 1
        except fuzz_targets.OracleFailure as exc:
            kind = str(exc).split(":", 1)[0][:60]
            stats["failed: " + kind] += 1
            if stats["failed: " + kind] <= 5:
                text = program.text()
                name = hashlib.sha256(text.encode()).hexdigest()[:16]
                (outdir / f"{name}.qasm").write_text(text)
                (outdir / f"{name}.txt").write_text(f"{exc}\n")
                print(f"FINDING {kind}: {name}", flush=True)
    while time.monotonic() < deadline:
        batch()
    return stats


if __name__ == "__main__":
    result = run(float(sys.argv[1]), Path(sys.argv[2]), qiskit="--no-qiskit" not in sys.argv)
    for key, count in sorted(result.items()):
        print(f"{count:8d} {key}")
