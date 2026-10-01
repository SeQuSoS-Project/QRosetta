"""Compile-only services on the live stack: every compiler is available, its image's
self-test passes, and through the API every level compiles the self-test probes into text
that declares the input's qubits, carries text-counted metrics and, where Qiskit is
installed, has the compile input's unitary (QMAP read through its layout lines)."""
import os
import shutil
import subprocess
import time

import httpx
import pytest

from qrosetta_commons.compile_service import SELF_TEST_PROBES, _PROBE_HEADER
from qrosetta_commons.helpers import count_qasm_gates_and_depth, get_num_qubits_from_qasm

BASE_URL = os.environ.get("QROSETTA_BASE_URL", "http://localhost")
CONTAINER_RUNTIME = shutil.which("podman") or shutil.which("docker")


def _compilers():
    response = httpx.get(f"{BASE_URL}/compilers", timeout=30)
    response.raise_for_status()
    return [c for c in response.json() if c["enabled"]]


def _run(qasm, compilers, timeout=300):
    job = httpx.post(f"{BASE_URL}/compare", json={
        "qasm_string": qasm, "target_simulators": ["qiskit"], "compilers": compilers,
        "timeout_seconds": 120, "execution_target": "local"}, timeout=30)
    assert job.status_code == 200, job.text
    job_id = job.json()["job_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = httpx.get(f"{BASE_URL}/jobs/{job_id}", timeout=30).json()["status"]
        if status in ("completed", "failed"):
            return httpx.get(f"{BASE_URL}/jobs/{job_id}/report", timeout=60).json()
        time.sleep(2)
    raise AssertionError(f"job {job_id} did not finish in {timeout} s")


def _layout(text, tag):
    return [int(x) for x in next(l for l in text.splitlines() if l.startswith(f"// {tag} ")).split()[2:]]


def _equivalent(compile_input, record):
    qiskit = pytest.importorskip("qiskit")
    from qiskit.quantum_info import Operator
    source = qiskit.QuantumCircuit.from_qasm_str(compile_input)
    output = qiskit.QuantumCircuit.from_qasm_str(record["transpiled_qasm"])
    if record["compiler_id"] != "qmap":
        return Operator(output).equiv(Operator(source), atol=1e-6)
    start, end = _layout(record["transpiled_qasm"], "i"), _layout(record["transpiled_qasm"], "o")
    wire = {physical: k for k, physical in enumerate(start)}
    logical = qiskit.QuantumCircuit(source.num_qubits)
    logical.compose(output, qubits=[wire[p] for p in range(source.num_qubits)], inplace=True)
    holds = [None] * source.num_qubits
    for k, physical in enumerate(end):
        holds[wire[physical]] = k
    for w in range(source.num_qubits):
        while holds[w] != w:
            other = holds[w]
            logical.swap(w, other)
            holds[w], holds[other] = holds[other], holds[w]
    return Operator(logical).equiv(Operator(source), atol=1e-8)


def test_every_enabled_compiler_is_available():
    unavailable = [(c["id"], c["unavailable_reason"]) for c in _compilers() if not c["available"]]
    assert not unavailable, f"unavailable compilers: {unavailable}"


@pytest.mark.skipif(CONTAINER_RUNTIME is None, reason="no container runtime to reach the images")
@pytest.mark.parametrize("compiler", ["bqskit", "pyzx", "qmap", "cirq", "staq", "qsynth", "quartz"])
def test_image_self_test_passes(compiler):
    result = subprocess.run([CONTAINER_RUNTIME, "exec", f"{compiler}-compiler", "python", "main.py", "--self-test"],
                            capture_output=True, text=True, timeout=900)
    failures = [line for line in result.stdout.splitlines() if line.startswith("FAIL")]
    assert result.returncode == 0 and not failures, failures or result.stderr[-500:]


@pytest.mark.parametrize("probe", sorted(SELF_TEST_PROBES))
def test_every_level_compiles_each_probe_through_the_api(probe):
    compilers = {c["id"]: [int(level) for level in c["optimization_levels"]] for c in _compilers()}
    report = _run(_PROBE_HEADER + SELF_TEST_PROBES[probe], compilers)
    compile_input = report["compile_input"]["qasm"]
    records = report["compiled_circuits"]
    assert len(records) == sum(len(levels) for levels in compilers.values())
    for record in records:
        assert record["dispatch_status"] == "ok", (record["compiler"], record.get("error"))
        text = record["transpiled_qasm"]
        assert get_num_qubits_from_qasm(text) == get_num_qubits_from_qasm(compile_input), record["compiler"]
        assert (record["gate_count"], record["circuit_depth"]) == count_qasm_gates_and_depth(text)
        assert _equivalent(compile_input, record), record["compiler"]
    assert [r["simulator"] for r in report["raw_results"]] == ["qiskit"]


def test_cirq_refuses_a_cu3_it_would_import_wrongly():
    qasm = _PROBE_HEADER + "h q[0];\ncu3(-0.4,0.4,-1.1) q[0],q[1];\nh q[2];\n"
    (record,) = _run(qasm, {"cirq-transformers": [0]})["compiled_circuits"]
    assert record["dispatch_status"] == "error" and "cirq-core 1.7.0 imports cu3" in record["error"]


def test_staq_keeps_registers_and_custom_gates():
    qasm = ('OPENQASM 2.0;\ninclude "qelib1.inc";\ngate g(t) a,b { cu1(t) a,b; h b; }\n'
            'qreg a[2];\nqreg b[1];\nh a[0];\ng(pi/4) a[0],b[0];\ncx a[1],b[0];\n')
    report = httpx.post(f"{BASE_URL}/compare", json={"qasm_string": qasm, "apply_preprocessing": False,
                                                     "target_simulators": ["qiskit"], "compilers": {"staq": [1]},
                                                     "execution_target": "local"}, timeout=30)
    assert report.status_code == 200, report.text
    job_id = report.json()["job_id"]
    for _ in range(150):
        if httpx.get(f"{BASE_URL}/jobs/{job_id}", timeout=30).json()["status"] in ("completed", "failed"):
            break
        time.sleep(2)
    (record,) = httpx.get(f"{BASE_URL}/jobs/{job_id}/report", timeout=60).json()["compiled_circuits"]
    assert record["dispatch_status"] == "ok", record.get("error")
    assert "qreg a[2];" in record["transpiled_qasm"] and "qreg b[1];" in record["transpiled_qasm"]
