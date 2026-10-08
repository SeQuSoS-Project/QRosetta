"""Tests for services/circuit_resolver.py, including the per-mode qubit cap."""
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


def test_pytket_cnx_calls_are_renamed_by_operand_count():
    from services.circuit_resolver import _name_cnx_by_size
    text = ("c4x q[0],q[1],q[2],q[3];\nc4x q[0],q[1],q[2],q[3],q[4];\nc4x q[0],q[1],q[2];\n"
            "if(c==1) c4x q[0],q[1];\n")
    renamed, names = _name_cnx_by_size(text)
    assert renamed == ("c3x q[0],q[1],q[2],q[3];\nc4x q[0],q[1],q[2],q[3],q[4];\nccx q[0],q[1],q[2];\n"
                       "if(c==1) cx q[0],q[1];\n")
    assert names == ["c3x", "ccx", "cx"]


def test_pytket_cnx_wider_than_qelib1_is_refused():
    from services.circuit_resolver import RoundTripIntegrityError, _name_cnx_by_size
    with pytest.raises(RoundTripIntegrityError, match="6 qubits"):
        _name_cnx_by_size("c4x q[0],q[1],q[2],q[3],q[4],q[5];\n")


def test_c3x_survives_the_preprocessing_round_trip():
    pytest.importorskip("pytket")
    from services.circuit_resolver import prepare_statevector_dispatch
    qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[4];\nh q[0];\nc3x q[0],q[1],q[2],q[3];\n'
    out = prepare_statevector_dispatch(qasm, apply_preprocessing=True)
    assert "c3x q[0],q[1],q[2],q[3];" in out["qasm"]
    assert "c4x" not in out["qasm"]


def test_flatten_qregs_refuses_a_broadcast_over_registers_of_different_sizes():
    from services.circuit_resolver import BroadcastSizeError, flatten_qregs
    qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg a[2];\nqreg b[3];\ncx a,b;\n'
    with pytest.raises(BroadcastSizeError, match="different sizes"):
        flatten_qregs(qasm)


def test_round_trip_refuses_a_call_of_an_opaque_gate():
    from services.circuit_resolver import RoundTripIntegrityError, prepare_statevector_dispatch
    qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nopaque myop a;\nqreg q[1];\nh q[0];\nmyop q[0];\n'
    with pytest.raises(RoundTripIntegrityError, match="myop is declared opaque"):
        prepare_statevector_dispatch(qasm, True)


def test_round_trip_still_removes_calls_of_an_empty_gate_definition():
    from services.circuit_resolver import prepare_statevector_dispatch
    qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\ngate e a { }\nqreg q[1];\nh q[0];\ne q[0];\n'
    notes = prepare_statevector_dispatch(qasm, True)["api_preprocessing_applied"]
    assert any("removed the calls to e, whose gate definition is empty" in n for n in notes)
