# Unit tests for the client-payload statevector strip (_display_result).
# job_manager pulls pytket/kubernetes at import, so skip on a bare host venv.

import pytest

pytest.importorskip("pytket")
pytest.importorskip("kubernetes")

from services.job_manager import (  # noqa: E402
    _display_result,
    _MAX_DISPLAY_STATEVECTOR_B64_CHARS,
    _MAX_DISPLAY_STATEVECTOR_AMPLITUDES,
    _STATEVECTOR_PLACEHOLDER,
)


def test_large_base64_statevector_is_stripped():
    big = {"simulator": "qiskit", "statevector": "A" * (_MAX_DISPLAY_STATEVECTOR_B64_CHARS + 1)}
    out = _display_result(big)
    assert out["statevector"] == _STATEVECTOR_PLACEHOLDER
    assert out["simulator"] == "qiskit"
    # original dict is not mutated
    assert big["statevector"].startswith("A")


def test_small_base64_statevector_is_kept():
    small = {"simulator": "qiskit", "statevector": "AAAA"}
    out = _display_result(small)
    assert out["statevector"] == "AAAA"


def test_large_list_statevector_is_stripped():
    big = {"simulator": "qiskit", "statevector": [0.0] * (_MAX_DISPLAY_STATEVECTOR_AMPLITUDES + 1)}
    assert _display_result(big)["statevector"] == _STATEVECTOR_PLACEHOLDER


def test_small_list_statevector_is_kept():
    small = {"simulator": "qiskit", "statevector": [1.0, 0.0]}
    assert _display_result(small)["statevector"] == [1.0, 0.0]


def test_error_result_untouched():
    err = {"simulator": "qibo", "error": "boom"}
    assert _display_result(err) is err


def test_counts_result_untouched():
    counts = {"simulator": "qibo", "counts": {"00": 512, "11": 512}}
    assert _display_result(counts) is counts
