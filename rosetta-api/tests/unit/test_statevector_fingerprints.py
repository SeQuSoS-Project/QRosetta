"""Stored and exported reports keep statevector_sha256 and statevector_length in place of
the removed vector."""
import hashlib
import json

import numpy as np

from qrosetta_commons.helpers import encode_statevector
from services.report_filters import remove_statevectors, statevector_digest

SV = np.array([1, 0, 0, 1j], dtype=np.complex128) / np.sqrt(2)


def test_base64_and_list_forms_share_one_digest():
    expected = hashlib.sha256(SV.tobytes()).hexdigest()
    assert statevector_digest(encode_statevector(SV))[:2] == (expected, 4)
    assert statevector_digest([[a.real, a.imag] for a in SV])[:2] == (expected, 4)


def test_remove_statevectors_keeps_hash_and_length():
    report = {"benchmark_summary": [{"raw_results": [
        {"simulator": "qiskit", "statevector": encode_statevector(SV)},
        {"simulator": "big", "statevector": "<Statevector too large for display...>"},
        {"simulator": "failed", "error": "x"}]}]}
    out = remove_statevectors(report)["benchmark_summary"][0]["raw_results"]
    assert "statevector" not in out[0]
    assert out[0]["statevector_sha256"] == hashlib.sha256(SV.tobytes()).hexdigest()
    assert out[0]["statevector_length"] == 4
    assert out[0]["statevector_digest_input"] == "base64_decoded_bytes"
    assert out[1] == {"simulator": "big", "statevector_omitted_for_display": True}
    assert out[2] == {"simulator": "failed", "error": "x"}


def test_stored_report_carries_the_fingerprint(tmp_path, monkeypatch):
    import services.storage as storage
    monkeypatch.setattr(storage, "MOCK_S3_DIR", str(tmp_path))
    key = storage.save_run_report(1, "r1", {"raw_results": [
        {"simulator": "qiskit", "statevector": encode_statevector(SV)}]})
    stored = json.loads((tmp_path / key).read_text())
    assert stored["statevector_storage"] == "removed_before_storage"
    assert stored["raw_results"][0]["statevector_length"] == 4
    assert len(stored["raw_results"][0]["statevector_sha256"]) == 64
