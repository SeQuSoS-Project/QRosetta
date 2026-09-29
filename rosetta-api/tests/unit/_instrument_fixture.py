"""Runner-shaped processors for test_instrument_* to run in a spawned child process."""
import time

import numpy as np

from qrosetta_commons.helpers import CompileResult, run_statevector_job

QASM_2Q = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\n'
ALLOC_MIB = 32


def _compile(payload):
    return CompileResult(circuit=None, n_qubits=2)


def _execute_alloc(compiled, payload):
    buf = np.ones(ALLOC_MIB * 1024 * 1024 // 8)
    time.sleep(0.005)
    del buf
    return np.array([1, 0, 0, 0], dtype=np.complex128)


def alloc_32mib(payload):
    return run_statevector_job(
        simulator="fixture", payload=payload, compile_fn=_compile,
        execute_fn=_execute_alloc, qubit_ordering="msb", precision="complex128")
