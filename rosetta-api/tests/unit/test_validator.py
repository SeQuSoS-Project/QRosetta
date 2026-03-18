import pytest
from fastapi import HTTPException
from services.validator import validate_request

def test_validate_request_valid_statevector(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_STATEVECTOR", 10)
    
    qasm = "OPENQASM 2.0;\nqreg q[5];\n"
    # Should not raise
    validate_request(qasm, mode="statevector")

def test_validate_request_valid_measured(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_MEASURED", 20)
    
    qasm = "OPENQASM 2.0;\nqreg q[18];\n"
    # Should not raise
    validate_request(qasm, mode="measured")

def test_validate_request_payload_too_large():
    qasm = "A" * 1000001
    with pytest.raises(HTTPException) as exc_info:
        validate_request(qasm)
    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "Payload too large"

def test_validate_request_too_complex():
    qasm = ";" * 10001
    with pytest.raises(HTTPException) as exc_info:
        validate_request(qasm)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Circuit too complex"

def test_validate_request_qubit_limit_regex_match(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_STATEVECTOR", 5)
    
    qasm = "OPENQASM 2.0;\nqreg q[6];\n"
    with pytest.raises(HTTPException) as exc_info:
        validate_request(qasm, mode="statevector")
    assert exc_info.value.status_code == 400
    assert "exceeds the maximum limit" in exc_info.value.detail

def test_validate_request_qubit_limit_fallback_match(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "MAX_QUBITS_STATEVECTOR", 5)
    
    # Missing explicit qreg but uses q[5] which means 6 qubits (0-indexed)
    qasm = "OPENQASM 2.0;\nh q[5];\n"
    with pytest.raises(HTTPException) as exc_info:
        validate_request(qasm, mode="statevector")
    assert exc_info.value.status_code == 400
    assert "uses qubit index 5" in exc_info.value.detail
