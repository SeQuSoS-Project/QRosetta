"""Request guards: QASM size, gate count, qubit count, statevector compatibility, runner ids
and multi-run fan-out."""

from fastapi import HTTPException
from config import settings
from qrosetta_commons.helpers import get_num_qubits_from_qasm, strip_qasm_comments
from services.circuit_resolver import StatevectorIncompatible, strip_terminal_measurements


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


def validate_request(qasm: str, mode: str = "statevector", bypass_limits: bool = False):
    """Raise HTTPException for an oversized, too-complex, qubit-less or too-wide circuit.

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


def check_statevector_circuit(qasm: str) -> None:
    """400 for a circuit statevector mode cannot represent (mid-circuit measurement, reset,
    classical control)."""
    try:
        strip_terminal_measurements(qasm)
    except StatevectorIncompatible as exc:
        raise HTTPException(status_code=400, detail=str(exc))
