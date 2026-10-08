"""Shrinking a run report before it is stored, exported, or bundled.

- ``remove_statevectors`` replaces every statevector with its sha256 and length, returning
  a new structure.
- ``fingerprint_statevectors`` replaces each statevector with a sha256 and a length, in place.
- ``statevector_inventory`` counts which results carry a real statevector.
"""

import base64
import binascii
import hashlib
from typing import Any

import numpy as np

DISPLAY_PLACEHOLDER_PREFIX = "<Statevector too large"
OMITTED_FOR_DISPLAY = "statevector_omitted_for_display"


def statevector_digest(sv):
    """``(sha256 hex, amplitude count, digest input)`` of a statevector, or None.

    A Base64 string (the runner wire format) is hashed as its decoded bytes, which are
    little-endian complex128 amplitudes (complex64 results are widened before encoding). A list of numbers or of ``[re, im]`` pairs is converted to
    complex128 and hashed the same way, so both forms of one vector give the same digest.
    """
    if isinstance(sv, str):
        try:
            raw = base64.b64decode(sv, validate=True)
        except (binascii.Error, ValueError):
            return None
        return hashlib.sha256(raw).hexdigest(), len(raw) // 16, "base64_decoded_bytes"
    if isinstance(sv, list):
        try:
            arr = np.asarray(sv, dtype=float)
            if arr.ndim == 2 and arr.shape[1] == 2:
                arr = arr[:, 0] + 1j * arr[:, 1]
            elif arr.ndim != 1:
                return None
        except (TypeError, ValueError):
            try:
                arr = np.asarray(sv, dtype=np.complex128)
            except (TypeError, ValueError):
                return None
            if arr.ndim != 1:
                return None
        arr = np.ascontiguousarray(arr, dtype=np.complex128)
        return hashlib.sha256(arr.tobytes()).hexdigest(), int(arr.shape[0]), "complex128_bytes"
    return None


def _without_statevector(entry: dict) -> dict:
    out = {k: remove_statevectors(v) for k, v in entry.items() if k != "statevector"}
    sv = entry.get("statevector")
    if sv is None:
        return out
    if is_display_placeholder(entry):
        out[OMITTED_FOR_DISPLAY] = True
        return out
    digest = statevector_digest(sv)
    if digest is not None:
        out["statevector_sha256"], out["statevector_length"], out["statevector_digest_input"] = digest
    return out


def remove_statevectors(data: Any) -> Any:
    """Return a copy of a nested dict/list with every 'statevector' key removed.

    A removed vector leaves ``statevector_sha256``, ``statevector_length`` (amplitudes) and
    ``statevector_digest_input`` (see ``statevector_digest``); a display placeholder leaves
    ``statevector_omitted_for_display``.
    """
    if isinstance(data, dict):
        if "statevector" in data:
            return _without_statevector(data)
        return {k: remove_statevectors(v) for k, v in data.items()}
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
      decoded bytes (little-endian complex128 amplitudes; backends that compute in complex64
      are widened to complex128 before encoding), ``statevector_length`` the amplitude
      count, and ``statevector_digest_input = "base64_decoded_bytes"``.
    - List: ``sha256(list)`` from the caller-supplied function,
      ``statevector_digest_input = "json_list"``.
    - Display placeholder: no digest; ``statevector_omitted_for_display = True``.

    A ``statevector_len`` field of an older report is renamed ``statevector_length``.
    Mutates and returns ``report``.
    """
    for entry in report.get("raw_results", []) or []:
        if not isinstance(entry, dict):
            continue
        if "statevector_len" in entry:
            legacy = entry.pop("statevector_len")
            entry.setdefault("statevector_length", legacy)
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
                entry["statevector_length"] = None
            else:
                entry["statevector_digest_input"] = "base64_decoded_bytes"
                entry["statevector_length"] = len(raw) // 16
            entry["statevector_sha256"] = hashlib.sha256(raw).hexdigest()
        else:
            entry["statevector_sha256"] = sha256(sv)
            entry["statevector_digest_input"] = "json_list"
            entry["statevector_length"] = len(sv) if hasattr(sv, "__len__") else None
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
