"""Tests that client-supplied runner keys cannot place files outside an RO-Crate export."""
import pytest
from fastapi import HTTPException

from services import exporter
from services.report_validation import reject_invalid_report


def test_traversal_keys_are_rejected():
    for key in ("../../../../tmp/zipslip", "a/b", "qiskit/../x", "QISKIT"):
        with pytest.raises(HTTPException) as exc:
            reject_invalid_report({"raw_results": [{"simulator": key}]})
        assert exc.value.status_code == 400


def test_runner_and_self_comparison_keys_are_accepted():
    reject_invalid_report({"raw_results": [{"simulator": "qiskit"},
                                           {"simulator": "qsim-cirq~opt1~run2"}]})


def test_malformed_reports_are_rejected():
    for report in ({"raw_results": [1, 2]}, {"raw_results": "x"}, {"benchmark_summary": [3]}):
        with pytest.raises(HTTPException):
            reject_invalid_report(report)


def test_file_stems_and_members_cannot_escape():
    assert "/" not in exporter._file_stem("../../etc/passwd") and ".." not in exporter._file_stem("..")
    for bad in ("../x", "/abs", "a/../b", "a//b"):
        with pytest.raises(ValueError):
            exporter._member("root", bad)
    assert exporter._member("root", "dispatched_circuits/qiskit.qasm") == "root/dispatched_circuits/qiskit.qasm"
