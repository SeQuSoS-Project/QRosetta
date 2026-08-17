"""Tests for the shared batch/experiment circuit resolver.

Both callers previously carried their own copy of this logic. The copies applied the
measured-mode qubit cap regardless of the run mode, so a statevector task above the
statevector limit was fully generated before being rejected further downstream.
"""
from unittest.mock import patch

import pytest

from services.circuit_resolver import resolve_circuit_qasm

_QASM = "OPENQASM 2.0;\nqreg q[2];\n"


def test_literal_qasm_is_returned_unchanged():
    assert resolve_circuit_qasm("qasm", None, 2, _QASM) == _QASM


def test_qasm_source_without_body_is_rejected():
    with pytest.raises(ValueError, match="requires qasm_string"):
        resolve_circuit_qasm("qasm", None, 2, None)


def test_literal_qasm_wins_over_a_nominal_preset_source():
    """A batch task carrying QASM uses it whatever its source field says."""
    assert resolve_circuit_qasm("preset", "ghz", 3, _QASM) == _QASM


def test_missing_source_defaults_to_preset():
    with patch("services.circuit_resolver.circuit_library.generate_circuit", return_value=_QASM) as gen:
        assert resolve_circuit_qasm(None, "ghz", 3) == _QASM
    gen.assert_called_once_with("ghz", 3)


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="unknown circuit source"):
        resolve_circuit_qasm("nonsense", "ghz", 3)


def test_mqt_and_qasmbench_delegate_to_the_benchmark_library():
    with patch("services.circuit_resolver.benchmark_library.get_mqt_benchmark", return_value=_QASM) as mqt:
        resolve_circuit_qasm("mqt", "ghz", 5)
    mqt.assert_called_once_with("ghz", 5)

    with patch("services.circuit_resolver.benchmark_library.get_qasmbench_circuit", return_value=_QASM) as qb:
        resolve_circuit_qasm("qasmbench", "adder_n10", 10)
    qb.assert_called_once_with("adder_n10")


def test_preset_uses_the_statevector_cap_in_statevector_mode(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_STATEVECTOR", 18)
    monkeypatch.setattr(config.settings, "MAX_QUBITS_MEASURED", 24)

    with patch("services.circuit_resolver.circuit_library.generate_circuit") as gen:
        with pytest.raises(ValueError, match="exceeds limit of 18"):
            resolve_circuit_qasm("preset", "ghz", 20, mode="statevector")
    gen.assert_not_called()


def test_preset_uses_the_measured_cap_in_measured_mode(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_STATEVECTOR", 18)
    monkeypatch.setattr(config.settings, "MAX_QUBITS_MEASURED", 24)

    with patch("services.circuit_resolver.circuit_library.generate_circuit", return_value=_QASM):
        assert resolve_circuit_qasm("preset", "ghz", 20, mode="measured") == _QASM

    with patch("services.circuit_resolver.circuit_library.generate_circuit") as gen:
        with pytest.raises(ValueError, match="exceeds limit of 24"):
            resolve_circuit_qasm("preset", "ghz", 30, mode="measured")
    gen.assert_not_called()
