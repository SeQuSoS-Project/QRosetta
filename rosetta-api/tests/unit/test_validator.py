# Tests for services/validator.py.

import pytest
from fastapi import HTTPException
from services.validator import validate_request
from config import settings

def test_validate_request_valid_statevector(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_STATEVECTOR", 10)

    qasm = "OPENQASM 2.0;\nqreg q[5];\n"

    validate_request(qasm, mode="statevector")

def test_validate_request_valid_measured(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_MEASURED", 20)

    qasm = "OPENQASM 2.0;\nqreg q[18];\n"

    validate_request(qasm, mode="measured")

def test_validate_request_payload_too_large():
    qasm = "A" * (settings.MAX_QASM_SIZE + 1)
    with pytest.raises(HTTPException) as exc_info:
        validate_request(qasm)
    assert exc_info.value.status_code == 413
    assert exc_info.value.detail.startswith("Payload too large")
    assert str(settings.MAX_QASM_SIZE) in exc_info.value.detail

def test_validate_request_too_complex():
    qasm = ";" * (settings.MAX_QASM_GATES + 1)
    with pytest.raises(HTTPException) as exc_info:
        validate_request(qasm)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail.startswith("Circuit too complex")
    assert f"limit of {settings.MAX_QASM_GATES}" in exc_info.value.detail

def test_validate_request_qubit_limit_regex_match(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_STATEVECTOR", 5)

    qasm = "OPENQASM 2.0;\nqreg q[6];\n"
    with pytest.raises(HTTPException) as exc_info:
        validate_request(qasm, mode="statevector")
    assert exc_info.value.status_code == 400
    assert "exceeds the maximum limit" in exc_info.value.detail

@pytest.mark.parametrize("qasm", [
    "",
    "   \n\t ",
    'OPENQASM 2.0;\ninclude "qelib1.inc";\n',
    "OPENQASM 2.0;\nqreg q[0];\n",
    "OPENQASM 2.0;\nh q[5];\n",
    "OPENQASM 2.0;\n// qreg q[3];\n",
])
def test_validate_request_rejects_circuits_without_qubits(qasm):
    with pytest.raises(HTTPException) as exc_info:
        validate_request(qasm, mode="statevector")
    assert exc_info.value.status_code == 400
    assert "declares no qubits" in exc_info.value.detail


def test_gate_count_ignores_semicolons_in_comments(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QASM_GATES", 5)
    qasm = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\n// ;;;;;;;;;;\n// /* ;;;;;; */\nh q[0];\n"
    validate_request(qasm, mode="statevector")


def test_qubit_limit_message_states_the_limit(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_STATEVECTOR", 5)
    with pytest.raises(HTTPException) as exc_info:
        validate_request("OPENQASM 2.0;\nqreg q[6];\n", mode="statevector")
    assert "limit of 5 qubits" in exc_info.value.detail


def test_validate_request_sums_multiple_qregs(monkeypatch):
    """A circuit split across registers is sized by their total, not the first one."""
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_MEASURED", 24)

    qasm = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg a[2];\nqreg b[28];\nh a[0];\n"
    with pytest.raises(HTTPException) as exc_info:
        validate_request(qasm, mode="measured")
    assert exc_info.value.status_code == 400
    assert "requested: 30" in exc_info.value.detail


def test_validate_request_multi_qreg_within_limit(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_STATEVECTOR", 10)

    validate_request("OPENQASM 2.0;\nqreg q[6];\nqreg anc[4];\n", mode="statevector")


def test_validate_runner_ids_lists_unknown_and_disabled():
    from services.validator import validate_runner_ids
    with pytest.raises(HTTPException) as exc_info:
        validate_runner_ids(["qiskit", "projectq", "mars"], {"nope": 1}, {})
    detail = exc_info.value.detail
    assert exc_info.value.status_code == 400
    assert "unknown runner id(s): mars, nope" in detail
    assert "disabled runner(s): projectq" in detail


def test_validate_runner_ids_accepts_enabled_ids():
    from services.validator import validate_runner_ids
    validate_runner_ids(["qiskit", "cirq"], {"qiskit": [0, 1]}, {"cirq": 2})
    validate_runner_ids([], {}, {})


_HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'


def test_indexed_operand_of_a_prefix_named_register_counts_once():
    from services.validator import expanded_counts
    qasm = _HEAD + "qreg q[22];\nqreg qa[2];\ncreg c[2];\n" + "x qa[0];\n" * 9998
    assert expanded_counts(qasm) == (9998, 0)
    validate_request(qasm, mode="measured")


def test_broadcasts_over_prefix_named_registers_use_their_own_size():
    from services.validator import expanded_counts
    qasm = _HEAD + "qreg q[5];\nqreg qa[3];\nx qa;\ncx q, qa[0];\nx q[1];\n"
    assert expanded_counts(qasm) == (3 + 5 + 1, 0)


def test_gate_calls_on_prefix_named_registers_count_through_definitions():
    from services.validator import expanded_counts
    body = "gate g a { x a; }\ngate f a { g a; g a; }\n"
    qasm = _HEAD + body + "qreg q[20];\nqreg qb[2];\n" + "f qb[1];\n" * 3
    assert expanded_counts(qasm) == (6, 6)
    assert expanded_counts(qasm.replace("f qb[1];", "f qb;")) == (12, 12)


def test_commented_out_register_does_not_change_broadcast_width():
    from services.validator import expanded_counts
    for comment in ("// qreg q[24];\n", "/* qreg q[24]; */\n"):
        assert expanded_counts(_HEAD + comment + "qreg q[2];\nx q;\n") == (2, 0)
