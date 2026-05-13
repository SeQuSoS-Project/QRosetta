# Validates QASM and circuit payloads.

from fastapi import HTTPException
from config import settings
import re

def validate_request(qasm: str, mode: str = "statevector"):
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
