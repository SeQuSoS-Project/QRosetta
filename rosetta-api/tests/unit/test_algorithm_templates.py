"""The random preset produces a non-trivial, reproducible state; the bit-order probe is
asymmetric under bit reversal."""
import numpy as np
import pytest

import services.circuit_library as library

qiskit = pytest.importorskip("qiskit")
pytest.importorskip("pytket")
from qiskit import qasm2  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402


@pytest.mark.parametrize("n", [2, 3, 5, 8])
def test_random_preset_leaves_the_zero_state(n):
    qasm = library.generate_circuit("random", n)
    assert qasm == library.generate_circuit("random", n)
    assert qasm != library.generate_circuit("random", n, seed=12345)
    probs = Statevector(qasm2.loads(qasm)).probabilities()
    assert probs[0] < 0.99
    assert {"h", "rx", "ry"} & {inst.operation.name for inst in qasm2.loads(qasm).data}


@pytest.mark.parametrize("n", [2, 3, 6])
def test_bit_order_probe_detects_reversal(n):
    circ = qasm2.loads(library.generate_circuit("bitorder", n))
    probs = Statevector(circ).probabilities()
    reversed_probs = Statevector(circ.reverse_bits()).probabilities()
    assert np.abs(probs - reversed_probs).sum() > 0.1
