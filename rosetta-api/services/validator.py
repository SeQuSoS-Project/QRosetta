# Validates QASM and circuit payloads.

from fastapi import HTTPException
from config import settings
import re

def validate_runner_config(runner_config: dict):
    """Bound multi-run fan-out. runner_config[name] may be an int (one run) or a
    list of opt levels (one run each). Without a cap, a crafted request could spawn
    unbounded runner jobs (httpx tasks locally, K8s pods on Rahti) and explode the
    O(n^2) divergence analysis. Enforced server-side regardless of the UI."""
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

def validate_request(qasm: str, mode: str = "statevector", bypass_limits: bool = False):
    if bypass_limits and settings.EXECUTION_MODE == "local":
        pass  # Skip gate limits for massive local runs
    else:
        if len(qasm) > settings.MAX_QASM_SIZE:
            raise HTTPException(status_code=413, detail="Payload too large")
        if qasm.count(";") > settings.MAX_QASM_GATES:
            raise HTTPException(status_code=400, detail="Circuit too complex")

    max_qubits = settings.MAX_QUBITS_STATEVECTOR if mode == "statevector" else settings.MAX_QUBITS_MEASURED

    match = re.search(r"qreg\s+\w+\[(\d+)\];", qasm)
    if match:
        qubit_count = int(match.group(1))
        if qubit_count > max_qubits:
            raise HTTPException(
                status_code=400,
                detail=f"Circuit exceeds the maximum limit of {max_qubits} qubits (requested: {qubit_count})."
            )
    else:

        indices = re.findall(r"\w+\[(\d+)\]", qasm)
        if indices:
            max_index = max(map(int, indices))

            if (max_index + 1) > max_qubits:
                 raise HTTPException(
                    status_code=400,
                    detail=f"Circuit uses qubit index {max_index}, exceeding limit of {max_qubits} qubits."
                )
