"""Circuit generation, benchmark-circuit lookup, and Quirk visualisation routes."""

import asyncio

from fastapi import APIRouter, Request, HTTPException
from qrosetta_commons.helpers import get_logger, get_num_qubits_from_qasm
import services.circuit_library as library
import services.benchmark_library as benchmark_library
import services.examples as examples
from schemas import GenerateCircuitPayload, QasmPayload, VisualizerResponse
from services import prep_worker
from services.validator import validate_request
from services.circuit_resolver import RoundTripIntegrityError
from services.quirk_converter import QUIRK_MAX_QUBITS, QuirkUnsupported, quirk_url
from services.quickload import quickload_sets
from config import settings
from services.security import run_rate_limit
from routers.errors import responses
from schemas.listings import (AlgorithmList, ExampleList, ExampleText, MqtIndex, QasmText,
                              QasmbenchIndex)

logger = get_logger("rosetta-api")
router = APIRouter()

@router.get("/algorithms", responses={200: {"model": AlgorithmList, "description": "The preset circuit families."}})
async def get_algorithms():
    """List the preset circuit families available from the circuit generator (e.g. 'ghz',
    'bell', 'qft', 'bv', 'grover'), with each one's supported qubit-count range.
    ``max_qubits`` is the generator's own maximum; ``max_qubits_statevector`` and
    ``max_qubits_measured`` are the largest size a run in that mode accepts."""
    return library.algorithm_list(settings.MAX_QUBITS_MEASURED, settings.MAX_QUBITS_STATEVECTOR)


@router.get("/quickload")
async def get_quickload():
    """The playlist's Quick Load sets: ``id``, ``label`` and ``items``, playlist items
    (``algorithm``, ``qubits``, ``name``) that reference preset circuits, which the server
    generates when the playlist runs. Qubit counts are clamped to each algorithm's range
    and to the statevector limit (``limits.max_qubits_statevector`` in GET /config)."""
    return quickload_sets(
        library.algorithm_list(settings.MAX_QUBITS_MEASURED, settings.MAX_QUBITS_STATEVECTOR),
        settings.MAX_QUBITS_STATEVECTOR)

@router.get("/examples", responses={200: {"model": ExampleList, "description": "The listed bundled examples."}})
async def get_examples():
    """List the bundled example circuits: file name, title, description, the mode each is
    meant for, and its qubit count."""
    return examples.list_examples()


@router.get("/examples/{name}", responses={200: {"model": ExampleText, "description": "The example's text."}, **responses((404, "No bundled example circuit has that name."))})
async def get_example(name: str):
    """One bundled example circuit's OpenQASM 2.0 text. 404 for a name that is not one."""
    qasm = examples.read_example(name)
    if qasm is None:
        raise HTTPException(status_code=404, detail="No bundled example circuit has that name.")
    return {"name": name, "qasm": qasm}


@router.post("/generate_circuit", responses={200: {"model": QasmText, "description": "The generated circuit."}, **responses((400, "Unknown algorithm, or a qubit count outside its range or over max_qubits_measured."))})
@run_rate_limit
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

@router.post("/visualize/quirk", response_model=VisualizerResponse, responses=responses((400, "The circuit is refused at submit, declares more than 16 qubits, or uses reset, classical control or a gate after a measurement on the same qubit, or its drawing exceeds the memory or time limit of circuit preparation.")))
@run_rate_limit
async def visualize_quirk(request: Request, payload: QasmPayload):
    """Convert an OpenQASM 2.0 circuit of at most 16 qubits into a URL that opens it in Quirk
    (https://algassert.com/quirk), an interactive browser-based circuit visualizer. Every gate
    is drawn with the same matrix up to a global phase (gates Quirk has no symbol for are drawn
    as cx and single-qubit rotations, listed in ``notes``); terminal measurements are drawn.
    400 for a circuit the API refuses at submit, more than 16 qubits, reset, classical control
    or a gate after a measurement on the same qubit, or a drawing that exceeds the memory or
    time limit of circuit preparation (it runs in the preparation process)."""
    n_qubits = get_num_qubits_from_qasm(payload.qasm_string)
    if n_qubits > QUIRK_MAX_QUBITS:
        raise HTTPException(
            status_code=400,
            detail=(f"The visualizer opens circuits of at most {QUIRK_MAX_QUBITS} qubits, "
                    f"Quirk's limit; this circuit declares {n_qubits}."))
    await asyncio.to_thread(validate_request, payload.qasm_string, mode="measured")
    try:
        url, notes = await prep_worker.call(quirk_url, payload.qasm_string)
        return {"url": url, "notes": notes}
    except (QuirkUnsupported, RoundTripIntegrityError, prep_worker.PreparationFailed) as exc:
        message = str(exc).rstrip(".")
        raise HTTPException(status_code=400, detail=f"Cannot draw this circuit in Quirk: "
                                                    f"{message[:1].lower() + message[1:]}.")
    except Exception:
        logger.error("Failed to convert QASM for the visualizer", exc_info=True)
        raise HTTPException(status_code=400, detail="Cannot draw this circuit in Quirk: its "
                                                    "text could not be parsed.")

@router.get("/benchmarks/mqt/list", responses={200: {"model": MqtIndex, "description": "Algorithm -> bundled qubit sizes."}})
async def list_mqt_bench():
    """List the bundled MQT Bench algorithm-level circuits, mapped to their available qubit
    sizes (MQT Bench circuits are pre-generated at fixed sizes, baked into the image)."""
    return benchmark_library.list_mqt()

@router.get("/benchmarks/qasmbench/list", responses={200: {"model": QasmbenchIndex, "description": "Circuit names."}})
async def list_qasmbench():
    """List the names of every bundled QASMBench circuit (each is a fixed size; there is no
    qubit-count parameter)."""
    return benchmark_library.list_qasmbench()

@router.get("/benchmarks/mqt", responses={200: {"model": QasmText, "description": "The circuit."}, **responses((400, "Qubit count over max_qubits_measured."), (404, "No bundled MQT Bench circuit for that algorithm and qubit count."))})
@run_rate_limit
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

@router.get("/benchmarks/qasmbench", responses={200: {"model": QasmText, "description": "The circuit."}, **responses((400, "Invalid circuit name."), (404, "No bundled QASMBench circuit has that name."))})
@run_rate_limit
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

