"""Request guards: QASM size, gate count, qubit count, statevector compatibility, runner ids
and multi-run fan-out."""

import re

from fastapi import HTTPException
from config import settings
from qrosetta_commons.counts import parse_measurement_layout
from qrosetta_commons.helpers import get_num_qubits_from_qasm
from services.circuit_resolver import (
    ParameterExpressionError, StatevectorIncompatible, check_parameter_value,
    evaluate_caret_parameters, gate_body_statements, gate_parameter_names, split_statements,
    statement_parameters,
    strip_terminal_measurements,
)
from services.reserved_gate_names import reserved_gate_reason

_VERSION_RE = re.compile(r"^\s*OPENQASM\s+([^;\s]+)\s*;", re.MULTILINE)
_QASM3_DECL_RE = re.compile(r"^\s*(?:qubit|bit)\s*(?:\[|\s+[A-Za-z_])", re.MULTILINE)
_REG_KEYWORD_RE = re.compile(r"\b(qreg|creg)\b")
_REG_DECL_RE = re.compile(r"^(qreg|creg)\s+[A-Za-z_]\w*\s*\[\s*\d+\s*\]$")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_QASM3_MESSAGE = "OpenQASM 3 is not supported; submit OpenQASM 2.0 (header 'OPENQASM 2.0;')."
_DEFINITION_RE = re.compile(r"^\s*(?:gate|opaque)\s+([A-Za-z_]\w*)")
_NAME_RE = re.compile(r"[A-Za-z_]\w*")
_NON_OPERATION_RE = re.compile(r"^\s*(?:OPENQASM|include|qreg|creg|gate|opaque)\b")


def _unprocessable(loc: list, msg: str):
    raise HTTPException(status_code=422, detail=[{"loc": loc, "msg": msg, "type": "value_error"}])


def validate_runner_config(runner_config: dict):
    """Reject a runner_config that exceeds MAX_RUNS_PER_RUNNER or MAX_TOTAL_RUNS (422), or
    names a level above a runner's highest supported level (400, naming the max).

    runner_config[name] is an int (one run) or a list of opt levels (one run each).
    """
    if not runner_config:
        return
    services = settings.get_runner_services()
    total = 0
    for name, val in runner_config.items():
        levels = val if isinstance(val, list) else [val]
        if len(levels) > settings.MAX_RUNS_PER_RUNNER:
            _unprocessable(["body", "runner_config", name],
                           f"Runner '{name}' requested {len(levels)} runs, exceeding the "
                           f"per-runner limit of {settings.MAX_RUNS_PER_RUNNER}.")
        total += len(levels)
        supported = services.get(name, {}).get("optimization_levels") or {}
        if supported and levels and max(levels) > max(supported):
            raise HTTPException(
                status_code=400,
                detail=f"runner_config requests optimization level {max(levels)} for '{name}', "
                       f"whose highest supported level is {max(supported)}.")
    if total > settings.MAX_TOTAL_RUNS:
        _unprocessable(["body", "runner_config"],
                       f"Requested {total} total runs across all simulators, exceeding the "
                       f"limit of {settings.MAX_TOTAL_RUNS}. Reduce the run counts in "
                       f"multi-run mode.")


def validate_runner_ids(target_simulators=None, runner_config=None, runner_phases=None):
    """Raise 400 for runner ids the registry does not know, and for disabled runners named
    in ``target_simulators``. The detail lists every offending id."""
    services = settings.get_runner_services()
    named = list(target_simulators or []) + list(runner_config or {}) + list(runner_phases or {})
    unknown = sorted({name for name in named if name not in services})
    disabled = sorted({name for name in (target_simulators or [])
                       if name in services and not services[name].get("enabled", True)})
    outside = sorted({name for name in list(runner_config or {}) + list(runner_phases or {})
                      if target_simulators and name in services and name not in target_simulators})
    if outside and not unknown and not disabled:
        raise HTTPException(
            status_code=400,
            detail=(f"runner_config or runner_phases names runner(s) not in target_simulators: "
                    f"{', '.join(outside)}. Add them to target_simulators or remove them."))
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
    """``(offset, text, terminated)`` for each top-level statement; gate bodies are skipped.
    ``terminated`` is False only for trailing text with no closing semicolon."""
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
                yield start, text, True
            start = i + 1
    if depth == 0 and code[start:].strip():
        yield start, code[start:], False


def check_qasm_syntax(qasm: str) -> None:
    """400 for an OpenQASM 3 program, a malformed qreg/creg declaration, or a final
    statement with no semicolon (each with its line number)."""
    code = _comment_free_keeping_lines(qasm)
    version = _VERSION_RE.search(code)
    if version and not version.group(1).startswith("2"):
        if version.group(1).startswith("3"):
            _bad_request(_QASM3_MESSAGE)
        _bad_request(f"Unsupported OpenQASM version '{version.group(1)}'; submit OpenQASM 2.0.")
    if not _REG_KEYWORD_RE.search(code) and _QASM3_DECL_RE.search(code):
        _bad_request(_QASM3_MESSAGE)

    for start, raw, terminated in _top_level_statements(code):
        stmt = " ".join(raw.split())
        if not terminated:
            line = code.count("\n", 0, start + len(raw) - len(raw.lstrip())) + 1
            shown = stmt if len(stmt) <= 80 else stmt[:77] + "..."
            _bad_request(
                f"Syntax error on line {line}: statement '{shown}' is missing its "
                f"terminating semicolon.")
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


def count_gate_statements(qasm: str, statements: list = None) -> int:
    """Top-level operation statements (gates, measure, reset, barrier, if); the header,
    includes, register declarations and gate definitions are not counted."""
    statements = split_statements(qasm) if statements is None else statements
    return sum(1 for stmt in statements if not _NON_OPERATION_RE.match(stmt))


def check_gate_names(qasm: str, statements: list = None) -> None:
    """400 for a ``gate``/``opaque`` definition whose name a runner's parser reserves
    (``services.reserved_gate_names``)."""
    statements = split_statements(qasm) if statements is None else statements
    for stmt in statements:
        m = _DEFINITION_RE.match(stmt)
        if not m:
            continue
        reason = reserved_gate_reason(m.group(1))
        if reason:
            _bad_request(f"gate name '{m.group(1)}' is {reason}; rename the gate")


def check_parameter_expressions(qasm: str) -> None:
    """400 for a '^' the API cannot evaluate before the pytket round-trip."""
    if "^" not in qasm:
        return
    try:
        evaluate_caret_parameters(qasm)
    except ParameterExpressionError as exc:
        _bad_request(f"Invalid gate parameter: {exc}.")


def _clip(text: str, limit: int = 80) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "…"


def check_parameter_values(qasm: str, statements: list = None) -> None:
    """400 for a top-level gate parameter that is not a finite constant expression or whose
    magnitude exceeds MAX_PARAMETER_MAGNITUDE (``check_parameter_value``)."""
    statements = split_statements(qasm) if statements is None else statements
    for stmt in statements:
        checks = [(param, stmt) for param in statement_parameters(stmt)]
        names = gate_parameter_names(stmt)
        for inner in gate_body_statements(stmt):
            checks += [(param, inner) for param in statement_parameters(inner)
                       if not _NAME_RE.findall(param) or not set(_NAME_RE.findall(param)) & names]
        for param, where in checks:
            try:
                check_parameter_value(param)
            except ParameterExpressionError as exc:
                _bad_request(f"Invalid gate parameter: '{_clip(param)}' in '{_clip(where)}': {exc}.")


def validate_request(qasm: str, mode: str = "statevector", bypass_limits: bool = False,
                     apply_preprocessing: bool = True, check_reserved_names: bool = True):
    """Raise HTTPException for an oversized, too-complex, malformed, qubit-less or too-wide
    circuit, a gate definition under a reserved name (``check_reserved_names``; off for the
    bundled benchmark circuits, whose definitions carry the built-in semantics), or (with
    ``apply_preprocessing``) a '^' parameter expression the API cannot evaluate.

    ``bypass_limits`` skips the size and gate-count checks in local mode only. Gate
    statements are counted by ``count_gate_statements``.
    """
    statements = None
    if not (bypass_limits and settings.EXECUTION_MODE == "local"):
        if len(qasm) > settings.MAX_QASM_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Payload too large: {len(qasm)} characters exceeds the limit of {settings.MAX_QASM_SIZE}.",
            )
        statements = split_statements(qasm)
        n_gates = count_gate_statements(qasm, statements)
        if n_gates > settings.MAX_QASM_GATES:
            raise HTTPException(
                status_code=400,
                detail=(f"Circuit too complex: {n_gates} gate statements exceeds the limit of "
                        f"{settings.MAX_QASM_GATES} (the header, includes, register declarations "
                        f"and gate definitions are not counted)."),
            )

    check_qasm_syntax(qasm)
    if check_reserved_names:
        check_gate_names(qasm, statements)
    check_parameter_values(qasm, statements)
    if apply_preprocessing:
        check_parameter_expressions(qasm)
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
