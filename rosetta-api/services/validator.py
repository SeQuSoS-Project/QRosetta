from fastapi import HTTPException
from config import settings
import re

MAX_QASM_SIZE = 1000000

def validate_request(qasm: str):
    if len(qasm) > MAX_QASM_SIZE:
        raise HTTPException(status_code=413, detail="Payload too large")
    if qasm.count(";") > 10000:
        raise HTTPException(status_code=400, detail="Circuit too complex")

    # Dynamic Qubit Validation
    # Build regex to find 'qreg name[size];'
    # Common pattern: qreg q[5];
    match = re.search(r"qreg\s+\w+\[(\d+)\];", qasm)
    if match:
        qubit_count = int(match.group(1))
        if qubit_count > settings.MAX_QUBITS:
            raise HTTPException(
                status_code=400,
                detail=f"Circuit exceeds the maximum limit of {settings.MAX_QUBITS} qubits (requested: {qubit_count})."
            )
    else:
        # Fallback: scan for highest index used like q[4]
        indices = re.findall(r"\w+\[(\d+)\]", qasm)
        if indices:
            max_index = max(map(int, indices))
            # index is 0-based, so count is max_index + 1
            if (max_index + 1) > settings.MAX_QUBITS:
                 raise HTTPException(
                    status_code=400,
                    detail=f"Circuit uses qubit index {max_index}, exceeding limit of {settings.MAX_QUBITS} qubits."
                )
