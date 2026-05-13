import json
import os
import random
from typing import Dict, Any
from pytket.circuit import Circuit, OpType
from pytket.qasm import circuit_to_qasm_str
from pytket.transform import Transform
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-circuit-library")

# Cache for loaded algorithms mapping id to metadata/code
_ALGORITHMS_CACHE: Dict[str, Any] = {}

# Isolated globals for exec() — uses real __builtins__ so injected pytket
# functions (Circuit, circuit_to_qasm_str, etc.) can call __import__ internally,
# but template code cannot access any module-level name from this file
# (os, json, _ALGORITHMS_CACHE, logger, etc.) because they are not in this dict.
_EXEC_GLOBALS: Dict[str, Any] = {"__builtins__": __builtins__}

def load_algorithms() -> Dict[str, Any]:
    """Loads algorithm JSON files from algorithm_templates/ directory."""
    global _ALGORITHMS_CACHE
    if _ALGORITHMS_CACHE:
        return _ALGORITHMS_CACHE

    # services/ is one level below rosetta-api/, so step up to find algorithm_templates/
    algorithms_dir = os.path.join(os.path.dirname(__file__), "..", "algorithm_templates")
    loaded = {}

    if not os.path.exists(algorithms_dir):
        logger.warning(f"Algorithms directory not found at {algorithms_dir}")
        return loaded

    for filename in os.listdir(algorithms_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(algorithms_dir, filename)
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    if "id" in data and "code" in data:
                        loaded[data["id"]] = data
            except Exception as e:
                logger.error(f"Failed to load algorithm data from {filename}: {e}")

    _ALGORITHMS_CACHE = loaded
    return _ALGORITHMS_CACHE

def generate_circuit(algorithm_id: str, n_qubits: int) -> str:
    """Generates a circuit by dynamically executing the algorithm's code template."""
    algorithms = load_algorithms()
    if algorithm_id not in algorithms:
        raise ValueError(f"Unknown algorithm: {algorithm_id}")

    algo_data = algorithms[algorithm_id]

    # We provide the necessary local variables for the exec context
    # to mimic the old static functions.
    local_context = {
        "n_qubits": n_qubits,
        "Circuit": Circuit,
        "OpType": OpType,
        "circuit_to_qasm_str": circuit_to_qasm_str,
        "Transform": Transform,
        "random": random,
        "qasm": ""
    }

    try:
        exec(algo_data["code"], _EXEC_GLOBALS, local_context)
        return local_context.get("qasm", "")
    except Exception as e:
        logger.error(f"Error executing python generator for {algorithm_id}: {e}")
        raise
