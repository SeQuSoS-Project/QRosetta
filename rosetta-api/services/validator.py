"""Request guards: QASM size, gate count, qubit count, statevector compatibility, runner ids
and multi-run fan-out."""

import re

from fastapi import HTTPException
from config import settings
from qrosetta_commons.counts import parse_measurement_layout
from qrosetta_commons.helpers import get_num_qubits_from_qasm, strip_qasm_comments
from services.circuit_resolver import StatevectorIncompatible, strip_terminal_measurements

_VERSION_RE = re.compile(r"^\s*OPENQASM\s+([^;\s]+)\s*;", re.MULTILINE)
_QASM3_DECL_RE = re.compile(r"^\s*(?:qubit|bit)\s*(?:\[|\s+[A-Za-z_])", re.MULTILINE)
_REG_KEYWORD_RE = re.compile(r"\b(qreg|creg)\b")
_REG_DECL_RE = re.compile(r"^(qreg|creg)\s+[A-Za-z_]\w*\s*\[\s*\d+\s*\]$")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_QASM3_MESSAGE = "OpenQASM 3 is not supported; submit OpenQASM 2.0 (header 'OPENQASM 2.0;')."


def validate_runner_config(runner_config: dict):
    """Reject a runner_config that exceeds MAX_RUNS_PER_RUNNER or MAX_TOTAL_RUNS.

    runner_config[name] is an int (one run) or a list of opt levels (one run each).
    """
    if not runner_config:
        return
    total = 0
    for name, val in runner_config.items():
        count = len(val) if isinstance(val, list) else 1
        if count > settings.MAX_RUNS_PER_RUNNER:
            raise HTTPException(
                status_code=422,
                detail=f"Runner '{name}' requested {count} runs, exceeding the per-runner limit of {settings.MAX_RUNS_PER_RUNNER}."
            )
        total += count
    if total > settings.MAX_TOTAL_RUNS:
        raise HTTPException(
            status_code=422,
            detail=f"Requested {total} total runs across all simulators, exceeding the limit of {settings.MAX_TOTAL_RUNS}. Reduce the run counts in multi-run mode."
        )


def validate_runner_ids(target_simulators=None, runner_config=None, runner_phases=None):
    """Raise 400 for runner ids the registry does not know, and for disabled runners named
    in ``target_simulators``. The detail lists every offending id."""
    services = settings.get_runner_services()
    named = list(target_simulators or []) + list(runner_config or {}) + list(runner_phases or {})
    unknown = sorted({name for name in named if name not in services})
    disabled = sorted({name for name in (target_simulators or [])
                       if name in services and not services[name].get("enabled", True)})
    if not unknown and not disabled:
        return
    parts = []
    if unknown:
        parts.append(f"unknown runner id(s): {', '.join(unknown)}")
    if disabled:
        parts.append(f"disabled runner(s): {', '.join(disabled)}")
    enabled = sorted(name for name, svc in services.items() if svc.get("enabled", True))
    raise HTTPException(
        status_code=400,
        detail=f"{'; '.join(parts)}. Enabled runners: {', '.join(enabled)}.",
    )


def _bad_request(detail: str):
    raise HTTPException(status_code=400, detail=detail)


def _comment_free_keeping_lines(qasm: str) -> str:
    """``qasm`` without comments; a block comment is replaced by its newlines."""
    text = _BLOCK_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), qasm)
    return _LINE_COMMENT_RE.sub("", text)


def _top_level_statements(code: str):
    """``(offset, text)`` for each top-level statement; gate bodies are skipped."""
    depth, start = 0, 0
    for i, ch in enumerate(code):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
            if depth == 0:
                start = i + 1
        elif ch == ";" and depth == 0:
            text = code[start:i]
            if text.strip():
                yield start, text
            start = i + 1
    if depth == 0 and code[start:].strip():
        yield start, code[start:]


def check_qasm_syntax(qasm: str) -> None:
    """400 for an OpenQASM 3 program or a malformed qreg/creg declaration (with its line
    number)."""
    code = _comment_free_keeping_lines(qasm)
    version = _VERSION_RE.search(code)
    if version and not version.group(1).startswith("2"):
        if version.group(1).startswith("3"):
            _bad_request(_QASM3_MESSAGE)
        _bad_request(f"Unsupported OpenQASM version '{version.group(1)}'; submit OpenQASM 2.0.")
    if not _REG_KEYWORD_RE.search(code) and _QASM3_DECL_RE.search(code):
        _bad_request(_QASM3_MESSAGE)

    for start, raw in _top_level_statements(code):
        stmt = " ".join(raw.split())
        if _REG_KEYWORD_RE.search(stmt) and not _REG_DECL_RE.match(stmt):
            line = code.count("\n", 0, start + _REG_KEYWORD_RE.search(raw).start()) + 1
            shown = stmt if len(stmt) <= 80 else stmt[:77] + "..."
            _bad_request(
                f"Syntax error on line {line}: malformed register declaration '{shown}'. "
                f"Expected 'qreg name[size];' or 'creg name[size];' (check for a missing "
                f"semicolon).")


def check_measurements(qasm: str) -> None:
    """400 for a ``measure`` whose operands differ in size, or an operand naming an
    undeclared register or bit."""
    try:
        parse_measurement_layout(qasm)
    except ValueError as exc:
        _bad_request(f"Invalid OpenQASM 2.0: {exc}.")
    except KeyError as exc:
        _bad_request(f"Invalid OpenQASM 2.0: measure refers to {exc.args[0][0]}[{exc.args[0][1]}], "
                     f"which is outside the declared register.")


def validate_request(qasm: str, mode: str = "statevector", bypass_limits: bool = False):
    """Raise HTTPException for an oversized, too-complex, malformed, qubit-less or too-wide
    circuit.

    ``bypass_limits`` skips the size and gate-count checks in local mode only. Statements
    are counted after comments are removed.
    """
    code = strip_qasm_comments(qasm)
    if not (bypass_limits and settings.EXECUTION_MODE == "local"):
        if len(qasm) > settings.MAX_QASM_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Payload too large: {len(qasm)} characters exceeds the limit of {settings.MAX_QASM_SIZE}.",
            )
        statements = code.count(";")
        if statements > settings.MAX_QASM_GATES:
            raise HTTPException(
                status_code=400,
                detail=f"Circuit too complex: {statements} statements exceeds the limit of {settings.MAX_QASM_GATES}.",
            )

    check_qasm_syntax(qasm)
    qubit_count = get_num_qubits_from_qasm(qasm)
    if qubit_count < 1:
        raise HTTPException(
            status_code=400,
            detail="Circuit declares no qubits: add a quantum register such as 'qreg q[2];' (size at least 1).",
        )

    max_qubits = settings.max_qubits_for_mode(mode)
    if qubit_count > max_qubits:
        raise HTTPException(
            status_code=400,
            detail=f"Circuit exceeds the maximum limit of {max_qubits} qubits for {mode} mode (requested: {qubit_count}).",
        )
    check_measurements(qasm)


def check_statevector_circuit(qasm: str) -> None:
    """400 for a circuit statevector mode cannot represent (mid-circuit measurement, reset,
    classical control)."""
    try:
        strip_terminal_measurements(qasm)
    except StatevectorIncompatible as exc:
        raise HTTPException(status_code=400, detail=str(exc))
