"""Shrinking a run report before it is stored, exported, or bundled.

Two operations, kept together so the difference between them stays visible:

- ``remove_statevectors`` drops the amplitudes entirely, returning a new structure.
  Used where the statevector is recoverable from elsewhere or simply not wanted.
- ``fingerprint_statevectors`` replaces each one with a sha256 and a length, in place.
  Used where the bundle has to stay verifiable without carrying the full vector.
"""

from typing import Any


def remove_statevectors(data: Any) -> Any:
    """Return a copy of a nested dict/list with every 'statevector' key removed."""
    if isinstance(data, dict):
        return {k: remove_statevectors(v) for k, v in data.items() if k != "statevector"}
    if isinstance(data, list):
        return [remove_statevectors(item) for item in data]
    return data


def fingerprint_statevectors(report: dict, sha256) -> dict:
    """Replace each raw statevector in ``report['raw_results']`` with a digest and a length.

    Metrics, labels and provenance are untouched. Mutates and returns ``report``; the caller
    passes a copy when the original must survive. ``sha256`` is supplied by the caller so
    this module does not fix the digest encoding used by a given bundle.
    """
    for entry in report.get("raw_results", []) or []:
        sv = entry.get("statevector")
        if sv is not None and not isinstance(sv, str):
            entry["statevector"] = None
            entry["statevector_sha256"] = sha256(sv)
            entry["statevector_len"] = len(sv) if hasattr(sv, "__len__") else None
    return report
