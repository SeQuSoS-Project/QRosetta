"""Circuit generation, benchmark-circuit lookup, and Quirk visualisation routes."""

import asyncio

from fastapi import APIRouter, Request, HTTPException
from qrosetta_commons.helpers import get_logger
import services.circuit_library as library
import services.benchmark_library as benchmark_library
import services.examples as examples
from schemas import GenerateCircuitPayload, QasmPayload, VisualizerResponse
from services.validator import validate_request
from services.quirk_converter import QuirkCompiler
from config import settings
from services.security import limiter

logger = get_logger("rosetta-api")
router = APIRouter()

@router.get("/algorithms")
async def get_algorithms():
    """List the preset circuit families available from the circuit generator (e.g. 'ghz',
    'bell', 'qft', 'bv', 'grover'), with each one's supported qubit-count range."""
    algorithms = library.load_algorithms()
    return [
        {
            "id": algo["id"],
            "name": algo.get("name", ""),
            "min_qubits": algo.get("min_qubits", 2),
            "max_qubits": algo.get("max_qubits", settings.MAX_QUBITS_MEASURED),
            "default_qubits": algo.get("default_qubits", 3),
            "description": algo.get("description", "")
        }
        for algo in algorithms.values()
    ]

@router.get("/examples")
async def get_examples():
    """List the bundled example circuits: file name, title, description, the mode each is
    meant for, and its qubit count."""
    return examples.list_examples()


@router.get("/examples/{name}")
async def get_example(name: str):
    """One bundled example circuit's OpenQASM 2.0 text. 404 for a name that is not one."""
    qasm = examples.read_example(name)
    if qasm is None:
        raise HTTPException(status_code=404, detail="No bundled example circuit has that name.")
    return {"name": name, "qasm": qasm}


@router.post("/generate_circuit")
@limiter.limit(settings.RUN_RATE_LIMIT)
async def generate_circuit_endpoint(request: Request, payload: GenerateCircuitPayload):
    """Build one preset circuit's OpenQASM 2.0 text server-side, without running it."""
    if payload.qubits > settings.MAX_QUBITS_MEASURED:
        raise HTTPException(status_code=400, detail=f"Qubit count {payload.qubits} exceeds limit of {settings.MAX_QUBITS_MEASURED}")
    try:
        qasm = await asyncio.to_thread(library.generate_circuit, payload.algorithm, payload.qubits, payload.seed)
        return {"qasm": qasm}
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.error("Circuit generation failed for algorithm=%s qubits=%s", payload.algorithm, payload.qubits, exc_info=True)
        raise HTTPException(status_code=500, detail="Circuit generation failed")

@router.post("/visualize/quirk", response_model=VisualizerResponse)
async def visualize_quirk(payload: QasmPayload):
    """Convert an OpenQASM 2.0 circuit into a URL that opens it in Quirk
    (https://algassert.com/quirk), an interactive browser-based circuit visualizer. 400 if the
    circuit uses gates Quirk's URL format cannot represent."""
    validate_request(payload.qasm_string, mode="statevector")
    try:
        compiler = QuirkCompiler(payload.qasm_string)
        url = compiler.generate_url()
        return {"url": url}
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Failed to generate Quirk URL: {ve}")
    except Exception:
        logger.error("Failed to compile QASM for Visualizer", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to generate Quirk URL")

@router.get("/benchmarks/mqt/list")
async def list_mqt_bench():
    """List the bundled MQT Bench algorithm-level circuits, mapped to their available qubit
    sizes (MQT Bench circuits are pre-generated at fixed sizes, baked into the image)."""
    return benchmark_library.list_mqt()

@router.get("/benchmarks/qasmbench/list")
async def list_qasmbench():
    """List the names of every bundled QASMBench circuit (each is a fixed size; there is no
    qubit-count parameter)."""
    return benchmark_library.list_qasmbench()

@router.get("/benchmarks/mqt")
@limiter.limit(settings.RUN_RATE_LIMIT)
async def get_mqt_bench(request: Request, algorithm: str, qubits: int = 3):
    """Fetch one bundled MQT Bench circuit's OpenQASM 2.0 text, by algorithm name and qubit
    count (see GET /benchmarks/mqt/list for the available combinations)."""
    if qubits > settings.MAX_QUBITS_MEASURED:
        raise HTTPException(status_code=400, detail=f"Qubit count {qubits} exceeds limit of {settings.MAX_QUBITS_MEASURED}")
    try:
        qasm = benchmark_library.get_mqt_benchmark(algorithm, qubits)
        return {"qasm": qasm}
    except HTTPException:
        raise
    except Exception:
        logger.error("MQT Bench lookup failed for algorithm=%s qubits=%s", algorithm, qubits, exc_info=True)
        raise HTTPException(status_code=500, detail="Benchmark circuit could not be loaded")

@router.get("/benchmarks/qasmbench")
@limiter.limit(settings.RUN_RATE_LIMIT)
async def get_qasmbench(request: Request, circuit: str):
    """Fetch one bundled QASMBench circuit's OpenQASM 2.0 text, by name (see GET
    /benchmarks/qasmbench/list for the available names)."""
    try:
        qasm = benchmark_library.get_qasmbench_circuit(circuit)
        return {"qasm": qasm}
    except HTTPException:
        raise
    except Exception:
        logger.error("QASMBench lookup failed for circuit=%s", circuit, exc_info=True)
        raise HTTPException(status_code=500, detail="Benchmark circuit could not be loaded")

