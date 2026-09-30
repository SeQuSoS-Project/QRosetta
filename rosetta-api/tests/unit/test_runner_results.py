"""Unit tests for the shared runner result-assembly helpers."""

import numpy as np

from qrosetta_commons.helpers import (
    statevector_result,
    counts_result,
    runner_error,
    decode_statevector,
    theoretical_statevector_mb,
)


class _FakeMonitor:
    def get_peak_usage_mb(self):
        return 12.5

    def get_process_peak_mb(self):
        return 210.0


def test_statevector_result_shape_and_encoding():
    sv = np.array([1 / np.sqrt(2), 1 / np.sqrt(2)], dtype=complex)
    r = statevector_result(
        simulator="qiskit", statevector=sv, compilation_time=0.2, simulation_time=0.8,
        monitor=_FakeMonitor(), qubit_ordering="lsb", n_qubits=1,
        preprocessing_applied=["pass"], transpiled_qasm="OPENQASM 2.0;")
    assert r["simulator"] == "qiskit"
    assert r["execution_time_sec"] == 1.0
    assert r["compilation_time_sec"] == 0.2 and r["simulation_time_sec"] == 0.8
    assert r["memory_usage_mb"] == 12.5 and r["process_peak_mb"] == 210.0
    assert r["qubit_ordering"] == "lsb"
    assert r["theoretical_statevector_mb"] == theoretical_statevector_mb(1)
    assert r["preprocessing_applied"] == ["pass"]
    assert r["transpiled_qasm"] == "OPENQASM 2.0;"
    assert np.allclose(decode_statevector(r["statevector"]), sv)
    assert "counts" not in r and "error" not in r


def test_statevector_result_accepts_list_input():
    r = statevector_result(
        simulator="qibo", statevector=[1.0, 0.0], compilation_time=0.0, simulation_time=0.0,
        monitor=_FakeMonitor(), qubit_ordering="msb", n_qubits=1,
        preprocessing_applied=[], transpiled_qasm="q")
    assert np.allclose(decode_statevector(r["statevector"]), np.array([1.0, 0.0]))


def test_counts_result_shape():
    r = counts_result(
        simulator="qibo", counts={"00": 5, "11": 5}, sampling_method="native",
        compilation_time=0.1, simulation_time=0.4, monitor=_FakeMonitor(),
        qubit_ordering="msb", n_qubits=2, preprocessing_applied=[], transpiled_qasm="q")
    assert r["counts"] == {"00": 5, "11": 5}
    assert r["sampling_method"] == "native"
    assert r["execution_time_sec"] == 0.5
    assert r["qubit_ordering"] == "msb"
    assert "statevector" not in r


def test_runner_error_shape():
    r = runner_error("pennylane-default", ValueError("boom"))
    assert r == {
        "simulator": "pennylane-default",
        "error": "boom",
        "execution_time_sec": None,
        "compilation_time_sec": None,
        "simulation_time_sec": None,
        "simulation_cpu_time_sec": None,
        "memory_usage_mb": None,
        "process_peak_mb": None,
        "process_peak_rss_mb": None,
        "cpu_time_sec": None,
        "compilation_throttled_sec": None,
        "simulation_throttled_sec": None,
        "simulation_cgroup_cpu_time_sec": None,
    }
