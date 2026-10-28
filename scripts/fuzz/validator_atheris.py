"""Harness 1, coverage-guided: Atheris (libFuzzer) feeds bytes to the request validator.

Usage: see scripts/fuzz/README.md. libFuzzer flags pass through, for example
``-max_total_time=1800 -timeout=30 -rss_limit_mb=1024 -dict=scripts/fuzz/qasm.dict CORPUS SEEDS``.
With FUZZ_FINDINGS_DIR set, an input that breaks the oracle is saved there (at most three
per kind of failure) and fuzzing goes on; otherwise the first one stops the run.
"""

import hashlib
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import atheris  # noqa: E402

import fuzz_targets  # noqa: E402

with atheris.instrument_imports(include=["services", "qrosetta_commons"]):
    import services.validator  # noqa: E402,F401


FINDINGS = os.environ.get("FUZZ_FINDINGS_DIR")
_seen: dict = {}


def _kind(exc: BaseException) -> str:
    kind = re.sub(r"[\d.]+", "N", str(exc).split(":", 1)[0].split(" with ", 1)[0])
    tb = exc.__cause__.__traceback__ if exc.__cause__ else None
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is not None:
        kind += f" at {Path(tb.tb_frame.f_code.co_filename).name}:{tb.tb_lineno}"
    return kind


def test_one_input(data: bytes) -> None:
    try:
        fuzz_targets.validator_oracle(data)
    except fuzz_targets.OracleFailure as exc:
        if not FINDINGS:
            raise
        kind = _kind(exc)
        _seen[kind] = _seen.get(kind, 0) + 1
        if _seen[kind] <= 3:
            name = hashlib.sha256(data).hexdigest()[:16]
            Path(FINDINGS).mkdir(parents=True, exist_ok=True)
            Path(FINDINGS, f"{name}.bin").write_bytes(data)
            Path(FINDINGS, f"{name}.txt").write_text(f"{exc}\n")
            print(f"FINDING {kind}: {name}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
