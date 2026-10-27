"""Quick Load sets: playlists of preset-circuit references, built from the algorithm list
and the statevector qubit limit."""

SETS = (
    ("each", "Sanity Check (every algorithm, 5 qubits)"),
    ("scaling", "Scaling Test (GHZ, 5 qubits to the statevector limit)"),
    ("largest", "Memory Stress (Random, BV and VQE at the statevector limit)"),
)


def _item(algorithms: list, algorithm_id: str, qubits: int, cap: int) -> dict:
    meta = next((a for a in algorithms if a["id"] == algorithm_id),
                {"id": algorithm_id, "name": algorithm_id})
    lo = meta.get("min_qubits")
    lo = 1 if lo is None else lo
    hi = meta.get("max_qubits")
    hi = min(cap if hi is None else hi, cap)
    return {"algorithm": algorithm_id, "qubits": max(lo, min(qubits, hi)),
            "name": meta.get("name") or algorithm_id}


def set_items(key: str, algorithms: list, cap: int) -> list:
    """The playlist items of Quick Load set ``key``; [] for an unknown key."""
    if key == "each":
        return [_item(algorithms, a["id"], 5, cap) for a in algorithms]
    if key == "scaling":
        sizes = [q for q in dict.fromkeys([5, 10, 15, cap]) if q <= cap]
        return [_item(algorithms, "ghz", q, cap) for q in sizes]
    if key == "largest":
        return [_item(algorithms, a, cap, cap) for a in ("random", "bv", "vqe")]
    return []


def quickload_sets(algorithms: list, cap: int) -> list:
    """Every Quick Load set as ``{id, label, items}``."""
    return [{"id": key, "label": label, "items": set_items(key, algorithms, cap)}
            for key, label in SETS]
