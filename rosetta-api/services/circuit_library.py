# Generates QASM by executing the algorithm_templates/*.json code strings.

import json
import os
import random
from typing import Dict, Any
from pytket.circuit import Circuit, OpType
from pytket.qasm import circuit_to_qasm_str
from pytket.transform import Transform
from qrosetta_commons.helpers import get_logger
from services.pytket_lock import PYTKET_LOCK

logger = get_logger("rosetta-circuit-library")

_ALGORITHMS_CACHE: Dict[str, Any] = {}

PRESET_ORDER = ["ghz", "bell", "qft", "bv", "grover", "vqe", "random", "bitorder"]

_EXEC_GLOBALS: Dict[str, Any] = {"__builtins__": __builtins__}

def load_algorithms() -> Dict[str, Any]:
    """Loads algorithm JSON files from algorithm_templates/ directory."""
    global _ALGORITHMS_CACHE
    if _ALGORITHMS_CACHE:
        return _ALGORITHMS_CACHE

    algorithms_dir = os.path.join(os.path.dirname(__file__), "..", "algorithm_templates")
    loaded = {}

    if not os.path.exists(algorithms_dir):
        logger.warning(f"Algorithms directory not found at {algorithms_dir}")
        return loaded

    for filename in sorted(os.listdir(algorithms_dir)):
        if filename.endswith(".json"):
            filepath = os.path.join(algorithms_dir, filename)
            try:
                with open(filepath) as f:
                    data = json.load(f)
                    if "id" in data and "code" in data:
                        loaded[data["id"]] = data
            except Exception as e:
                logger.error(f"Failed to load algorithm data from {filename}: {e}")

    rank = {aid: i for i, aid in enumerate(PRESET_ORDER)}
    _ALGORITHMS_CACHE = dict(sorted(loaded.items(), key=lambda kv: (rank.get(kv[0], len(rank)), kv[0])))
    return _ALGORITHMS_CACHE


def algorithm_list(max_measured: int, max_statevector: int) -> list:
    """The preset circuit families as GET /algorithms lists them, in menu order."""
    return [
        {
            "id": algo["id"],
            "name": algo.get("name", ""),
            "min_qubits": algo.get("min_qubits", 2),
            "max_qubits": algo.get("max_qubits", max_measured),
            "max_qubits_statevector": min(algo.get("max_qubits", max_measured), max_statevector),
            "max_qubits_measured": min(algo.get("max_qubits", max_measured), max_measured),
            "default_qubits": algo.get("default_qubits", 3),
            "description": algo.get("description", ""),
        }
        for algo in load_algorithms().values()
    ]

def generate_circuit(algorithm_id: str, n_qubits: int, seed: int = None) -> str:
    """Generates a circuit by dynamically executing the algorithm's code template.

    ``seed`` is passed to templates with random content; None lets them derive it from
    ``n_qubits``.
    """
    algorithms = load_algorithms()
    if algorithm_id not in algorithms:
        raise ValueError(f"Unknown algorithm: {algorithm_id}")

    algo_data = algorithms[algorithm_id]

    local_context = {
        "n_qubits": n_qubits,
        "Circuit": Circuit,
        "OpType": OpType,
        "circuit_to_qasm_str": circuit_to_qasm_str,
        "Transform": Transform,
        "random": random,
        "seed": seed,
        "qasm": ""
    }

    try:
        with PYTKET_LOCK:
            exec(algo_data["code"], _EXEC_GLOBALS, local_context)
        return local_context.get("qasm", "")
    except Exception as e:
        logger.error(f"Error executing python generator for {algorithm_id}: {e}")
        raise
