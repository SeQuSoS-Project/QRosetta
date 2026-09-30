"""Runner sources: register order and classical-bit readout go through the shared helpers."""
import re
from pathlib import Path

import pytest

_RUNNERS = Path(__file__).resolve().parents[3] / "runners"
_SOURCES = {p.parent.name: p.read_text() for p in sorted(_RUNNERS.glob("*/main.py"))}

pytestmark = pytest.mark.skipif(not _SOURCES, reason="runner sources not present")


def test_pytket_parsed_statevectors_follow_declaration_order():
    """A runner that parses with pytket reorders its statevector or refuses several qregs."""
    offenders = [
        name for name, src in _SOURCES.items()
        if "pytket.qasm.circuit_from_qasm_str" in src
        and "statevector_in_declaration_order" not in src
        and "Enable apply_preprocessing" not in src
    ]
    assert not offenders, f"pytket runners returning alphabetical register order: {offenders}"


def test_multi_register_pytket_runners_expand_register_broadcasts():
    """pytket runs a call mixing indexed and register operands on the register's first qubit."""
    offenders = [
        name for name, src in _SOURCES.items()
        if "pytket.qasm.circuit_from_qasm_str" in src
        and "Enable apply_preprocessing" not in src
        and "expand_register_broadcasts(" not in src
    ]
    assert not offenders, f"pytket runners parsing register broadcasts unexpanded: {offenders}"


def test_pytket_result_counts_are_not_zipped_by_position():
    """BackendResult keys cover only read-out bits, so zipping them with every bit shifts keys."""
    pattern = re.compile(r"zip\(\s*bits\s*,\s*key\s*\)")
    offenders = [name for name, src in _SOURCES.items() if pattern.search(src)]
    assert not offenders, f"runners zipping counts keys with declared bits: {offenders}"
    users = [name for name, src in _SOURCES.items() if "result.get_counts()" in src
             and "BackendResult" in src]
    assert not users, f"runners reading pytket counts without counts_from_pytket_result: {users}"
