"""Bundled circuits whose preparation with preprocessing on reaches the server's preparation
memory limit (settings.PREP_MAX_MIB), from the peaks in benchmarks/preparation_peaks.json."""

import json
import os
from functools import lru_cache

from config import settings

_PEAKS_PATH = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "preparation_peaks.json")


@lru_cache(maxsize=1)
def _recorded() -> dict:
    """(source, algorithm, qubits) -> (peak MiB, whether it is a lower bound)."""
    with open(_PEAKS_PATH, encoding="utf-8") as fh:
        circuits = json.load(fh)["circuits"]
    out = {}
    for c in circuits:
        at_least = "peak_mib_at_least" in c
        out[(c["source"], c["algorithm"], int(c.get("qubits") or 0))] = (
            c["peak_mib_at_least"] if at_least else c["peak_mib"], at_least)
    return out


def _over_limit(peak_mib: float) -> bool:
    return peak_mib >= settings.PREP_MAX_MIB


def bundled_over_prep_limit() -> list:
    """``[{source, algorithm, qubits}]`` of the bundled circuits whose recorded preparation
    peak reaches PREP_MAX_MIB. A lower bound under the limit leaves its circuit out."""
    return [{"source": s, "algorithm": a, "qubits": q}
            for (s, a, q), (peak, _) in sorted(_recorded().items()) if _over_limit(peak)]


def bundled_prep_problem(source, algorithm, qubits) -> str | None:
    """Why the bundled circuit cannot be prepared with preprocessing on, or None. A QASMBench
    circuit is named by its file alone, so its ``qubits`` is not part of the key."""
    key = (source or "preset", algorithm, 0 if source == "qasmbench" else int(qubits or 0))
    recorded = _recorded().get(key)
    if recorded is None or not _over_limit(recorded[0]):
        return None
    peak, at_least = recorded
    size = f"at least {peak:,} MiB" if at_least else f"about {peak:,} MiB"
    width = f" ({key[2]} qubits)" if key[2] else ""
    return (f"Preparing the bundled circuit {algorithm}{width} with SDK preprocessing on takes "
            f"{size}, over the server's {settings.PREP_MAX_MIB:,} MiB limit for circuit "
            f"preparation (limits.prep_max_mib in GET /config). Run it with preprocessing off, "
            f"or remove it from the run.")
