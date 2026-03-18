from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from qrosetta_commons.helpers import get_logger
import library
from schemas import GenerateCircuitPayload, QasmPayload, VisualizerResponse
from services.validator import validate_request
from services.quirk_converter import QuirkCompiler
from config import settings
from security import limiter

logger = get_logger("rosetta-api")
router = APIRouter()

@router.get("/algorithms")
async def get_algorithms():
    algorithms = library.load_algorithms()
    return [
        {
            "id": algo["id"],
            "name": algo.get("name", ""),
            "min_qubits": algo.get("min_qubits", 2),
            "max_qubits": algo.get("max_qubits", 20),
            "default_qubits": algo.get("default_qubits", 3),
            "description": algo.get("description", "")
        }
        for algo in algorithms.values()
    ]

@router.post("/generate_circuit")
@limiter.limit("10/minute")
async def generate_circuit_endpoint(request: Request, payload: GenerateCircuitPayload):
    if payload.qubits > settings.MAX_QUBITS_MEASURED:
        return JSONResponse(status_code=400, content={"error": f"Qubit count {payload.qubits} exceeds limit of {settings.MAX_QUBITS_MEASURED}"})
    try:
        qasm = library.generate_circuit(payload.algorithm, payload.qubits)
        return {"qasm": qasm}
    except ValueError as ve:
        return JSONResponse(content={"error": str(ve)}, status_code=400)
    except Exception as e:
        logger.error(f"CRITICAL ERROR in generate_circuit: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

@router.post("/visualize/quirk", response_model=VisualizerResponse)
async def visualize_quirk(payload: QasmPayload):
    try:
        compiler = QuirkCompiler(payload.qasm_string)
        url = compiler.generate_url()
        return {"url": url}
    except Exception as e:
        logger.error(f"Failed to compile QASM for Visualizer: {str(e)}", exc_info=True)
        return JSONResponse(status_code=400, content={"error": f"Failed to generate Quirk URL: {str(e)}"})
