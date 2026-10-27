"""The self-test circuits (``circuits/selftest/``) and their expected answers, computed by
``reference`` from each committed file and pinned in ``circuits/selftest/expected.json``.

Regenerate the pinned file with ``python -m services.selftest.circuits`` from rosetta-api/;
``EXPECTED_SHA256`` in ``plan`` must then be updated by hand.
"""

import hashlib
import json
import os
import sys

import numpy as np

from services.selftest import reference

CIRCUITS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "circuits", "selftest"))
EXPECTED_FILE = os.path.join(CIRCUITS_DIR, "expected.json")

STATEVECTOR = "statevector"
MEASURED = "measured"

# name, part, kind of check, what it tests
CIRCUITS = (
    ("sv_one_hot_idle", STATEVECTOR, "statevector",
     "x q[0] with q[1] and q[2] idle: bit order and idle qubits (one populated index per order)"),
    ("sv_distinct_amplitudes", STATEVECTOR, "statevector",
     "distinct ry angles, a cx chain and one rz, eight distinct amplitude magnitudes: qubit "
     "permutation, bit reversal, cx direction and rz sign"),
    ("sv_ghz_3q", STATEVECTOR, "statevector",
     "GHZ-3: support and amplitudes; invariant under every qubit permutation, so it does not "
     "test bit order"),
    ("m_probe_one_hot", MEASURED, "counts_key",
     "contract probe ONE_HOT_MEASURED_QASM: measured bit order through the API path"),
    ("m_probe_clbit_order", MEASURED, "counts_key",
     "contract probe clbit_order: classical bit 0 rightmost under lsb, leftmost under msb"),
    ("m_probe_creg_declaration_order", MEASURED, "counts_key",
     "contract probe creg_declaration_order: cregs flattened in declaration order, not by name"),
    ("m_probe_unmeasured_clbit_mid_creg", MEASURED, "counts_key",
     "contract probe unmeasured_clbit_mid_creg: an unmeasured classical bit inside a creg reads 0"),
    ("m_probe_unmeasured_clbit_first_creg", MEASURED, "counts_key",
     "contract probe unmeasured_clbit_first_creg: keys hold classical bits, not qubits"),
    ("m_ghz_3q", MEASURED, "ghz_sampling",
     "GHZ-3 sampled: only all-0 and all-1 outcomes, and p(all-0) within 6 sigma of 0.5"),
)
CIRCUIT_PARTS = {name: part for name, part, _kind, _what in CIRCUITS}
CIRCUIT_KINDS = {name: kind for name, _part, kind, _what in CIRCUITS}


def circuit_text(name: str) -> str:
    with open(os.path.join(CIRCUITS_DIR, f"{name}.qasm"), encoding="utf-8") as fh:
        return fh.read()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pairs(state) -> list:
    return [[float(v.real), float(v.imag)] for v in np.asarray(state, dtype=complex)]


def compute_expected() -> dict:
    """The expected answers of every circuit, computed now by ``reference``."""
    out = {}
    for name, part, kind, _what in CIRCUITS:
        text = circuit_text(name)
        circuit = reference.parse_circuit(text)
        entry = {"file": f"{name}.qasm", "qasm_sha256": _sha256(text), "part": part,
                 "check": kind, "n_qubits": circuit["n_qubits"]}
        if kind == "statevector":
            entry["statevector_lsb"] = _pairs(reference.statevector(text))
        elif kind == "counts_key":
            entry["counts_key"] = reference.deterministic_counts_key(text)
        else:
            state = reference.statevector(text)
            n = circuit["n_qubits"]
            support = [i for i, p in enumerate(np.abs(state) ** 2) if p > 1e-12]
            keys = [format(i, f"0{n}b") for i in support]
            entry["support"] = {"lsb": keys, "msb": [k[::-1] for k in keys]}
            entry["p_all_zero"] = float(abs(state[0]) ** 2)
        out[name] = entry
    return {"generator": "services/selftest/reference.py", "circuits": out}


def expected_file_text(expected: dict) -> str:
    return json.dumps(expected, indent=2, sort_keys=True) + "\n"


def load_expected() -> dict:
    with open(EXPECTED_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def expected_file_sha256() -> str:
    with open(EXPECTED_FILE, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def expected_statevector(entry: dict, ordering: str) -> np.ndarray:
    """The pinned expected statevector of a circuit entry in ``ordering`` (lsb or msb)."""
    state = np.array([complex(re, im) for re, im in entry["statevector_lsb"]])
    return reference.to_msb(state) if ordering == "msb" else state


if __name__ == "__main__":
    with open(EXPECTED_FILE, "w", encoding="utf-8") as fh:
        fh.write(expected_file_text(compute_expected()))
    sys.stderr.write(expected_file_sha256() + "\n")
