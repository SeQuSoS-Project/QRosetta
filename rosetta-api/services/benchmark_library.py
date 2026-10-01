"""Reads the bundled QASMBench and MQTBench .qasm files under rosetta-api/benchmarks/."""

import os
import re
import glob
from functools import lru_cache

from fastapi import HTTPException
from qrosetta_commons.counts import parse_measurement_layout
from qrosetta_commons.helpers import get_logger, strip_qasm_comments

logger = get_logger("benchmark-library")

_BENCHMARKS_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "benchmarks")
)
_QASMBENCH_DIR = os.path.join(_BENCHMARKS_ROOT, "qasmbench")
_MQTBENCH_DIR = os.path.join(_BENCHMARKS_ROOT, "mqtbench")

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _require_safe_name(name: str) -> str:
    if not name or not _SAFE_NAME.match(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid benchmark name. Use letters, digits, '_' and '-' only.",
        )
    return name


def invalid_qasm_reason(qasm: str):
    """Why a bundled file is not valid OpenQASM 2.0 (no header, or a measure into an
    undeclared register), or None."""
    if not re.search(r"^\s*OPENQASM\s+2\.0\s*;", strip_qasm_comments(qasm), re.MULTILINE):
        return "it has no 'OPENQASM 2.0;' header"
    try:
        parse_measurement_layout(qasm)
    except (KeyError, ValueError) as exc:
        return f"its measurements do not match its registers ({exc})"
    return None


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
        reason = invalid_qasm_reason(qasm_str)
        if reason:
            raise HTTPException(status_code=422, detail=(
                f"The bundled {label} file {file_name} is not valid OpenQASM 2.0 as distributed "
                f"upstream: {reason}."))
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


def _valid_file(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return invalid_qasm_reason(fh.read()) is None
    except OSError:
        return False


@lru_cache(maxsize=1)
def _qasmbench_names() -> tuple:
    return tuple(sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(_QASMBENCH_DIR, "*.qasm")) if _valid_file(p)
    ))


def list_qasmbench() -> list[str]:
    """Return the sorted names of the bundled QASMBench circuits that are valid OpenQASM 2.0
    (no extension); see ``invalid_qasm_reason``."""
    return list(_qasmbench_names())


def get_mqt_benchmark(algorithm: str, qubits: int) -> str:
    """Read a bundled MQTBench (algorithm-level) circuit for the given size."""
    _require_safe_name(algorithm)
    logger.info(f"Reading MQTBench circuit: {algorithm} ({qubits}q)")
    return _read_bundled_qasm(_MQTBENCH_DIR, f"{algorithm}_n{qubits}.qasm", "MQTBench")


@lru_cache(maxsize=1)
def _mqt_index() -> tuple:
    available: dict[str, list[int]] = {}
    for p in glob.glob(os.path.join(_MQTBENCH_DIR, "*.qasm")):
        stem = os.path.splitext(os.path.basename(p))[0]
        m = re.match(r"^(.*)_n(\d+)$", stem)
        if not m:
            continue
        available.setdefault(m.group(1), []).append(int(m.group(2)))
    return tuple((algo, tuple(sorted(sizes))) for algo, sizes in sorted(available.items()))


def list_mqt() -> dict[str, list[int]]:
    """Return available MQTBench algorithms mapped to their bundled qubit sizes."""
    return {algo: list(sizes) for algo, sizes in _mqt_index()}
