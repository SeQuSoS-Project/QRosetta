"""Turning one batch or experiment task into OpenQASM text.

The batch runner and the experiment sweep both accept the same four circuit sources
(literal QASM, MQT Bench, QASMBench, generated preset) and previously each resolved them
with their own copy of this logic, which had drifted apart in error handling and in which
qubit cap they applied.
"""

from config import settings
import services.benchmark_library as benchmark_library
import services.circuit_library as circuit_library


def resolve_circuit_qasm(
    source: str | None,
    algorithm: str | None,
    qubits: int | None,
    qasm_string: str | None = None,
    mode: str = "measured",
) -> str:
    """Return the OpenQASM 2.0 text for one task.

    ``mode`` selects which qubit cap a generated preset is checked against, so a
    statevector task is rejected before an oversized circuit is built rather than after.
    Raises ValueError for an unknown source or a task the source cannot satisfy.
    """
    normalized = (source or "preset").lower()

    if normalized == "qasm":
        if not qasm_string:
            raise ValueError("source 'qasm' requires qasm_string")
        return qasm_string

    # A task carrying literal QASM uses it whatever its nominal source says.
    if qasm_string:
        return qasm_string

    if normalized == "mqt":
        return benchmark_library.get_mqt_benchmark(algorithm, int(qubits or 0))

    if normalized == "qasmbench":
        return benchmark_library.get_qasmbench_circuit(algorithm)

    if normalized == "preset":
        n_qubits = int(qubits or 0)
        max_qubits = settings.max_qubits_for_mode(mode)
        if n_qubits > max_qubits:
            raise ValueError(f"Qubit count {n_qubits} exceeds limit of {max_qubits}")
        return circuit_library.generate_circuit(algorithm, n_qubits)

    raise ValueError(f"unknown circuit source '{source}'")
