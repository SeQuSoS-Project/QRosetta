"""Delta-debugging reducer for a validator finding: removes lines, then characters, while the
input still fails the oracle the same way (same exception type and location, or still too
slow) with the same request options.

Usage: python scripts/fuzz/reduce.py FINDING.bin [OUT]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fuzz_targets  # noqa: E402


def signature(data: bytes, flags: dict):
    """Exception type and innermost frame of the oracle failure, or None if the input passes."""
    try:
        fuzz_targets.validator_oracle(data, flags=flags)
    except fuzz_targets.OracleFailure as exc:
        if str(exc).startswith("took"):
            return ("slow",)
        cause = exc.__cause__
        tb = cause.__traceback__ if cause else None
        while tb is not None and tb.tb_next is not None:
            tb = tb.tb_next
        where = (tb.tb_frame.f_code.co_filename, tb.tb_lineno) if tb else None
        return (type(cause).__name__, where)
    return None


def ddmin(units: list, still_fails) -> list:
    """Zeller's ddmin over a list of units."""
    n = 2
    while len(units) >= 2:
        chunk = max(1, len(units) // n)
        reduced = False
        for start in range(0, len(units), chunk):
            candidate = units[:start] + units[start + chunk:]
            if candidate and still_fails(candidate):
                units, n, reduced = candidate, max(n - 1, 2), True
                break
        if not reduced:
            if n >= len(units):
                break
            n = min(len(units), n * 2)
    return units


def reduce(data: bytes) -> bytes:
    flags = fuzz_targets.validator_flags(data)
    target = signature(data, flags)
    if target is None:
        raise SystemExit("the input passes the oracle")
    lines = ddmin(data.splitlines(keepends=True),
                  lambda u: signature(b"".join(u), flags) == target)
    chars = ddmin([bytes([b]) for b in b"".join(lines)],
                  lambda u: signature(b"".join(u), flags) == target)
    return b"".join(chars)


if __name__ == "__main__":
    original = Path(sys.argv[1]).read_bytes()
    result = reduce(original)
    flags = fuzz_targets.validator_flags(original)
    print(f"{len(original)} -> {len(result)} bytes; options {flags}")
    print(result.decode("utf-8", "surrogateescape"))
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_bytes(result)
