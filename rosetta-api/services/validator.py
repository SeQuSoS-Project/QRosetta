from fastapi import HTTPException

MAX_QUBITS = 24
MAX_QASM_SIZE = 15000

def validate_request(qasm: str):
    if len(qasm) > MAX_QASM_SIZE:
        raise HTTPException(status_code=413, detail="Payload too large")
    if qasm.count(";") > 5000:
        raise HTTPException(status_code=400, detail="Circuit too complex")
