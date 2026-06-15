import os
import re
import glob

from fastapi import HTTPException
from qrosetta_commons.helpers import get_logger

logger = get_logger("benchmark-library")

# Both benchmark suites are served as static, pre-generated QASM files bundled in the
# image — no quantum SDKs in the API. QASMBench is downloaded from pnnl/QASMBench;
# MQTBench is produced once by scripts/generate_mqtbench.py (which needs mqt.bench) and
# committed. Derive the location relative to rosetta-api/ so it resolves in both the
# container (WORKDIR) and local dev checkouts.
_BENCHMARKS_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "benchmarks")
)
_QASMBENCH_DIR = os.path.join(_BENCHMARKS_ROOT, "qasmbench")
_MQTBENCH_DIR = os.path.join(_BENCHMARKS_ROOT, "mqtbench")

# Benchmark identifiers are filesystem path components — restrict them to a safe
# alphabet so a crafted name (e.g. "../../etc/foo") cannot escape the bundled dirs.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _require_safe_name(name: str) -> str:
    if not name or not _SAFE_NAME.match(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid benchmark name. Use letters, digits, '_' and '-' only.",
        )
    return name


def _read_bundled_qasm(base_dir: str, file_name: str, label: str) -> str:
    """Read a bundled .qasm file, guarding against path traversal."""
    file_path = os.path.realpath(os.path.join(base_dir, file_name))
    if os.path.commonpath([file_path, base_dir]) != base_dir:
        raise HTTPException(status_code=400, detail=f"Invalid {label} name.")

    if not os.path.exists(file_path):
        logger.error(f"{label} circuit not found at {file_path}")
        raise HTTPException(status_code=404, detail=f"{label} circuit not found.")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            qasm_str = f.read()
        if "OPENQASM" not in qasm_str:
            raise ValueError("File is not a valid OpenQASM file.")
        return qasm_str
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read {label} {file_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading {label} circuit: {str(e)}")


def get_qasmbench_circuit(circuit_name: str) -> str:
    """Read a bundled QASMBench circuit, e.g. 'adder_n4', 'qpe_n9'."""
    _require_safe_name(circuit_name)
    logger.info(f"Reading QASMBench circuit: {circuit_name}")
    return _read_bundled_qasm(_QASMBENCH_DIR, f"{circuit_name}.qasm", "QASMBench")


def list_qasmbench() -> list[str]:
    """Return the sorted names of all bundled QASMBench circuits (no extension)."""
    return sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(_QASMBENCH_DIR, "*.qasm"))
    )


def get_mqt_benchmark(algorithm: str, qubits: int) -> str:
    """Read a bundled MQTBench (algorithm-level) circuit for the given size."""
    _require_safe_name(algorithm)
    logger.info(f"Reading MQTBench circuit: {algorithm} ({qubits}q)")
    return _read_bundled_qasm(_MQTBENCH_DIR, f"{algorithm}_n{qubits}.qasm", "MQTBench")


def list_mqt() -> dict[str, list[int]]:
    """Return available MQTBench algorithms mapped to their bundled qubit sizes."""
    available: dict[str, list[int]] = {}
    for p in glob.glob(os.path.join(_MQTBENCH_DIR, "*.qasm")):
        stem = os.path.splitext(os.path.basename(p))[0]
        m = re.match(r"^(.*)_n(\d+)$", stem)
        if not m:
            continue
        available.setdefault(m.group(1), []).append(int(m.group(2)))
    return {algo: sorted(sizes) for algo, sizes in sorted(available.items())}
