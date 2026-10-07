"""Bundled example circuits (rosetta-api/circuits/*.qasm) with a title, a description and the
mode they are meant for. Files that repeat a generated algorithm (GHZ, Bell) are served but
not listed."""

import os
import re
from typing import Dict, List, Optional

from qrosetta_commons.helpers import get_num_qubits_from_qasm

_DIR = os.path.join(os.path.dirname(__file__), "..", "circuits")
_NAME = re.compile(r"^[A-Za-z0-9_-]+\.qasm$")

_NOT_LISTED = {"bell_state_2q.qasm", "ghz_state_3q.qasm"}

_META = {
    "rotation_1q.qasm": ("Single rotation", "One qubit, ry(0.5): the smallest circuit with a non-trivial amplitude.", "statevector"),
    "qrisp_measured_bias_16q.qasm": (
        "Sampler bias, 16 qubits",
        "With 16 qubits the full-distribution test needs far more shots than the default, and the "
        "single-bit marginal test shows a backend whose sampler is biased "
        "(see Known backend issues in the manual).", "measured"),
}


def _files() -> List[str]:
    if not os.path.isdir(_DIR):
        return []
    return sorted(f for f in os.listdir(_DIR) if _NAME.match(f))


def list_examples() -> List[Dict]:
    out = []
    for name in _files():
        if name in _NOT_LISTED:
            continue
        title, description, mode = _META.get(name, (name[:-5].replace("_", " "), "", "statevector"))
        with open(os.path.join(_DIR, name)) as fh:
            qubits = get_num_qubits_from_qasm(fh.read())
        out.append({"name": name, "title": title, "description": description, "mode": mode, "qubits": qubits})
    return out


def read_example(name: str) -> Optional[str]:
    """The QASM text of a bundled example, or None for a name that is not one."""
    if name not in _files():
        return None
    with open(os.path.join(_DIR, name)) as fh:
        return fh.read()
