from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from qrosetta_commons.helpers import get_logger
import library
from schemas import GenerateCircuitPayload
from services.validator import validate_request
from config import settings
from security import limiter

logger = get_logger("rosetta-api")
router = APIRouter()

ALGORITHM_HANDLERS = {
    "ghz": library.generate_ghz,
    "bell": library.generate_bell_state,
    "qft": library.generate_qft,
    "grover": library.generate_grover_search,
    "bv": library.generate_bernstein_vazirani,
    "vqe": library.generate_vqe_ansatz,
    "random": library.generate_random_circuit
}

@router.get("/algorithms")
async def get_algorithms():
    return [
        {"id": "bell", "name": "Bell State (Simple)", "min_qubits": 2, "max_qubits": 2, "default_qubits": 2, "description": "Maximally entangled state on 2 qubits."},
        {"id": "ghz", "name": "GHZ State (Entanglement)", "min_qubits": 2, "max_qubits": 20, "default_qubits": 3, "description": "Greenberger-Horne-Zeilinger state on N qubits."},
        {"id": "qft", "name": "Quantum Fourier Transform", "min_qubits": 1, "max_qubits": 20, "default_qubits": 3, "description": "Standard QFT circuit (without inverse)."},
        {"id": "grover", "name": "Grover Search (Oracle)", "min_qubits": 2, "max_qubits": 14, "default_qubits": 3, "description": "Grover's algorithm with a dummy oracle (limited to 14 qubits for browser safety due to depth)."},
        {"id": "bv", "name": "Bernstein-Vazirani", "min_qubits": 2, "max_qubits": 20, "default_qubits": 4, "description": "BV algorithm with 'all-ones' secret string."},
        {"id": "vqe", "name": "VQE Ansatz", "min_qubits": 2, "max_qubits": 20, "default_qubits": 4, "description": "Hardware Efficient Ansatz with rotation layers."},
        {"id": "random", "name": "Random Circuit", "min_qubits": 2, "max_qubits": 20, "default_qubits": 5, "description": "Random gates to defeat compiler optimizations."}
    ]

@router.post("/generate_circuit")
@limiter.limit("10/minute")
async def generate_circuit_endpoint(request: Request, payload: GenerateCircuitPayload):
    if payload.qubits > settings.MAX_QUBITS:
        return JSONResponse(status_code=400, content={"error": f"Qubit count {payload.qubits} exceeds limit of {settings.MAX_QUBITS}"})
    try:
        handler = ALGORITHM_HANDLERS.get(payload.algorithm)
        if not handler:
            return JSONResponse(content={"error": f"Unknown algorithm: {payload.algorithm}"}, status_code=400)
        
        qasm = handler(payload.qubits)
        return {"qasm": qasm}
    except Exception as e:
        logger.error(f"CRITICAL ERROR in generate_circuit: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)
