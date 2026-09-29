"""Shrinking a run report before it is stored, exported, or bundled.

- ``remove_statevectors`` drops every statevector, returning a new structure.
- ``fingerprint_statevectors`` replaces each statevector with a sha256 and a length, in place.
- ``statevector_inventory`` counts which results carry a real statevector.
"""

import base64
import binascii
import hashlib
from typing import Any

DISPLAY_PLACEHOLDER_PREFIX = "<Statevector too large"
OMITTED_FOR_DISPLAY = "statevector_omitted_for_display"


def remove_statevectors(data: Any) -> Any:
    """Return a copy of a nested dict/list with every 'statevector' key removed."""
    if isinstance(data, dict):
        return {k: remove_statevectors(v) for k, v in data.items() if k != "statevector"}
    if isinstance(data, list):
        return [remove_statevectors(item) for item in data]
    return data


def is_display_placeholder(entry: dict) -> bool:
    """True if ``entry`` holds the browser-copy placeholder instead of a statevector."""
    sv = entry.get("statevector")
    return bool(entry.get(OMITTED_FOR_DISPLAY)) or (
        isinstance(sv, str) and sv.startswith(DISPLAY_PLACEHOLDER_PREFIX))


def fingerprint_statevectors(report: dict, sha256) -> dict:
    """Replace each statevector in ``report['raw_results']`` with a digest and a length.

    - Base64 string (the runner wire format): ``statevector_sha256`` is the sha256 of the
      decoded bytes (complex128 amplitudes), ``statevector_len`` the amplitude count, and
      ``statevector_digest_input = "base64_decoded_bytes"``.
    - List: ``sha256(list)`` from the caller-supplied function,
      ``statevector_digest_input = "json_list"``.
    - Display placeholder: no digest; ``statevector_omitted_for_display = True``.

    Mutates and returns ``report``.
    """
    for entry in report.get("raw_results", []) or []:
        if not isinstance(entry, dict):
            continue
        sv = entry.get("statevector")
        if sv is None:
            continue
        if is_display_placeholder(entry):
            entry["statevector"] = None
            entry[OMITTED_FOR_DISPLAY] = True
            continue
        if isinstance(sv, str):
            try:
                raw = base64.b64decode(sv, validate=True)
            except (binascii.Error, ValueError):
                raw = sv.encode("utf-8")
                entry["statevector_digest_input"] = "utf8_string"
                entry["statevector_len"] = None
            else:
                entry["statevector_digest_input"] = "base64_decoded_bytes"
                entry["statevector_len"] = len(raw) // 16
            entry["statevector_sha256"] = hashlib.sha256(raw).hexdigest()
        else:
            entry["statevector_sha256"] = sha256(sv)
            entry["statevector_digest_input"] = "json_list"
            entry["statevector_len"] = len(sv) if hasattr(sv, "__len__") else None
        entry["statevector"] = None
    return report


def _iter_raw_results(report: dict):
    if not isinstance(report, dict):
        return
    for entry in report.get("raw_results", []) or []:
        if isinstance(entry, dict):
            yield entry
    for task in report.get("benchmark_summary", []) or []:
        yield from _iter_raw_results(task)


def statevector_inventory(report: dict) -> dict:
    """Count results with a real statevector, a display placeholder, or none.

    Returns ``{"present", "omitted_for_display", "absent", "storage"}``; ``storage`` is the
    report's ``statevector_storage`` marker or None.
    """
    present = omitted = absent = 0
    for entry in _iter_raw_results(report):
        if entry.get("error"):
            continue
        if is_display_placeholder(entry):
            omitted += 1
        elif entry.get("statevector") is not None:
            present += 1
        elif "counts" not in entry:
            absent += 1
    return {"present": present, "omitted_for_display": omitted, "absent": absent,
            "storage": report.get("statevector_storage") if isinstance(report, dict) else None}
