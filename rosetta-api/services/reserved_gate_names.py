"""Gate names the circuit parsers in the API and runner images do not let a user redefine.

Read from the images with ``docker run --rm --entrypoint python <image> -c ...``. A user
``gate``/``opaque`` definition under one of these names is replaced, ignored or turned into
a barrier by at least one parser, so ``reserved_gate_reason`` lets the validator reject it.
"""

# pytket 1.33.0 / 1.34.0 pytket/qasm/qasm.py _CircuitTransformer.mixedcall treat_as_barrier
PYTKET_BARRIER_NAMES = frozenset(
    ["sleep"] + [f"order{n}" for n in range(2, 21)] + [f"group{n}" for n in range(2, 21)])

# pytket 1.33.0 / 1.34.0 pytket/qasm/qasm.py NOPARAM_EXTRA_COMMANDS | PARAM_EXTRA_COMMANDS (gdef zip-prefix match)
PYTKET_EXTRA_NAMES = frozenset({
    "v", "vdg", "cv", "cvdg", "csxdg", "bridge", "iswapmax", "zzmax", "ecr", "cs", "csdg",
    "tk2", "iswap", "phasediswap", "yyphase", "xxphase3", "eswap", "fsim",
})

# pytket 1.33.0 / 1.34.0 pytket/qasm/qasm.py NOPARAM_COMMANDS | PARAM_COMMANDS and the qelib1 include gate set
PYTKET_BUILTIN_NAMES = frozenset({
    "CX", "cx", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx", "sxdg", "cz", "cy", "ch",
    "csx", "ccx", "c3x", "c4x", "ZZ", "measure", "reset", "id", "barrier", "swap", "cswap",
    "p", "u", "U", "u3", "u2", "u1", "rx", "rxx", "ry", "rz", "RZZ", "rzz", "Rz", "U1q", "crz",
    "crx", "cry", "cu1", "cu3", "Rxxyyzz", "c3sqrtx", "cp", "cu", "rc3x", "rccx", "u0",
})

# qiskit 0.45.3 / 1.2.4 / 1.4.4 qasm2.LEGACY_CUSTOM_INSTRUCTIONS, qelib1.inc and get_standard_gate_name_mapping()
QISKIT_BUILTIN_NAMES = frozenset({
    "c3sqrtx", "c3sx", "c3x", "c4x", "ccx", "ccz", "ch", "cp", "crx", "cry", "crz", "cs", "csdg",
    "cswap", "csx", "cu", "cu1", "cu3", "cx", "cy", "cz", "dcx", "delay", "ecr", "global_phase",
    "h", "id", "iswap", "measure", "p", "r", "rc3x", "rcccx", "rccx", "reset", "rx", "rxx", "ry",
    "ryy", "rz", "rzx", "rzz", "s", "sdg", "swap", "sx", "sxdg", "t", "tdg", "u", "u0", "u1",
    "u2", "u3", "x", "xx_minus_yy", "xx_plus_yy", "y", "z",
})

# myQLM qat.interop.openqasm OqasmParser.standard_gates (p_gate_decl drops the definition)
MYQLM_BUILTIN_NAMES = frozenset({
    "x", "y", "z", "s", "t", "cx", "ccx", "sdg", "tdg", "pH", "csign", "cz", "rx", "ry", "U",
    "u1", "u2", "u3", "cu1", "cu2", "cu3", "rz", "swap", "crz", "cswap", "h", "ch", "id",
})

# qibo 0.3.1 qibo/models/_openqasm.py _get_gate: _qibo_gate_name(name) in dir(qibo.gates), case-insensitive
QIBO_BUILTIN_UPPER = frozenset({
    "CCZ", "CNOT", "CRX", "CRY", "CRZ", "CSX", "CSXDG", "CU1", "CU2", "CU3", "CY", "CZ",
    "DEUTSCH", "ECR", "FSWAP", "GIVENS", "GPI", "GPI2", "H", "I", "M", "MS", "PRX", "RBS", "RX",
    "RXX", "RXXYY", "RY", "RYY", "RZ", "RZX", "RZZ", "S", "SDG", "SWAP", "SX", "SXDG", "SYC", "T",
    "TDG", "TOFFOLI", "U1", "U2", "U3", "X", "Y", "Z",
})
QIBO_ALIASES = frozenset({"cx", "id", "ccx", "p", "u", "U"})

# quimb 1.13.0 quimb/tensor/circuit.py get_openqasm2_regexes "ignore": ^(creg|measure|barrier)
QUIMB_IGNORED_PREFIXES = ("creg", "measure", "barrier")


def reserved_gate_reason(name: str):
    """Why ``name`` cannot be a user gate name, or None when it can."""
    if name in PYTKET_BARRIER_NAMES:
        return "reserved by the pytket parser (treated as a barrier)"
    if name in PYTKET_EXTRA_NAMES:
        return ("reserved by the pytket parser (a definition matching the start of its "
                "built-in is replaced by the built-in)")
    if name in PYTKET_BUILTIN_NAMES or name in QISKIT_BUILTIN_NAMES:
        return ("reserved by the pytket and Qiskit parsers (built-in gate; Qiskit ignores a "
                "definition under a built-in name)")
    if name in MYQLM_BUILTIN_NAMES:
        return "reserved by the myQLM parser (built-in gate; the definition is ignored)"
    if name in QIBO_ALIASES or name.upper() in QIBO_BUILTIN_UPPER:
        return "reserved by the Qibo parser (built-in gate; the definition is ignored)"
    if name.startswith(QUIMB_IGNORED_PREFIXES):
        return "reserved by the quimb parser (statements starting with this name are ignored)"
    return None
