"""Statevector labels are assigned in the basis the declared qubit orderings imply."""

import numpy as np

from services.analysis.divergence import create_divergence_report


def _u3(theta, phi, lam):
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([[c, -np.exp(1j * lam) * s],
                     [np.exp(1j * phi) * s, np.exp(1j * (phi + lam)) * c]])


def _h_h_cu3_lsb():
    """h q[0]; h q[1]; cu3(0.7,0.3,1.1) q[0],q[1]; indexed q1*2 + q0 (lsb)."""
    v = np.full(4, 0.5, dtype=complex)
    u = _u3(0.7, 0.3, 1.1)
    for q0 in (0, 1):
        if q0 == 1:
            a, b = v[0 * 2 + q0], v[1 * 2 + q0]
            v[0 * 2 + q0], v[1 * 2 + q0] = u[0, 0] * a + u[0, 1] * b, u[1, 0] * a + u[1, 1] * b
    return v


def _reverse(v):
    n = int(np.log2(len(v)))
    return v.reshape([2] * n).transpose(list(reversed(range(n)))).reshape(-1)


def _res(sim, order, sv):
    return {"simulator": sim, "qubit_ordering": order, "statevector": [complex(x) for x in sv]}


def _pair(report, a, b):
    return next(p for p in report["pairwise_agreement"] if p["simulators"] == [a, b])


def test_lsb_msb_pair_equal_as_reported_on_an_asymmetric_state_is_a_disagreement():
    lsb = _h_h_cu3_lsb()
    report = create_divergence_report([
        _res("qiskit", "lsb", lsb),
        _res("pennylane-lightning", "msb", lsb),
        _res("cirq", "msb", _reverse(lsb)),
    ])
    swapped = _pair(report, "qiskit", "pennylane-lightning")
    assert swapped["metrics"]["direct_fidelity"] > 1 - 1e-9
    assert swapped["agreement"] == "residual_disagreement"
    assert swapped["metrics"]["label_aligned_basis"] == "bit_reversal"
    assert swapped["metrics"]["unaligned_basis_match"] == "direct"
    assert _pair(report, "qiskit", "cirq")["agreement"] == "agree_after_bit_reversal"
    assert _pair(report, "pennylane-lightning", "cirq")["metrics"]["unaligned_basis_match"] == (
        "bit_reversal")
    flagged = {tuple(d["simulators"]) for d in report["divergences_found"] if d["type"] == "Fidelity"}
    assert flagged == {("qiskit", "pennylane-lightning"), ("pennylane-lightning", "cirq")}


def test_same_ordering_pair_is_labelled_directly_and_symmetric_cross_pair_after_reversal():
    ghz = np.zeros(8, dtype=complex)
    ghz[0] = ghz[7] = 2 ** -0.5
    report = create_divergence_report([
        _res("a", "lsb", ghz), _res("b", "lsb", ghz), _res("c", "msb", -ghz)])
    assert _pair(report, "a", "b")["agreement"] == "agree_directly"
    cross = _pair(report, "a", "c")
    assert cross["agreement"] == "agree_after_bit_reversal"
    assert cross["transform_effect"]["global_phase_aligned"] is True
    assert [d["type"] for d in report["divergences_found"]] == ["Phase", "Phase"]


def test_one_qubit_lsb_msb_pair_agrees_directly():
    v = np.array([0.6, 0.8j])
    report = create_divergence_report([_res("a", "lsb", v), _res("b", "msb", v)])
    rec = _pair(report, "a", "b")
    assert rec["agreement"] == "agree_directly"
    assert rec["metrics"]["basis_source"] == "single_qubit"


def test_undeclared_permutation_is_a_disagreement_group():
    rng = np.random.default_rng(3)
    v = rng.normal(size=8) + 1j * rng.normal(size=8)
    v /= np.linalg.norm(v)
    permuted = v.reshape(2, 2, 2).transpose(1, 0, 2).reshape(-1)
    report = create_divergence_report([_res("a", "lsb", v), _res("b", "lsb", permuted)])
    assert _pair(report, "a", "b")["agreement"] == "agree_after_qubit_permutation"
    (entry,) = report["divergences_found"]
    assert entry["type"] == "Fidelity"
    assert entry["group"] == "disagreement: agrees only after an undeclared qubit permutation"


def test_unnormalized_permutation_match_is_not_relabelled_as_agreement():
    rng = np.random.default_rng(4)
    v = rng.normal(size=8) + 0j
    v /= np.linalg.norm(v)
    permuted = 2 * v.reshape(2, 2, 2).transpose(1, 0, 2).reshape(-1)
    rec = _pair(create_divergence_report([_res("a", "lsb", v), _res("b", "lsb", permuted)]),
                "a", "b")
    assert rec["agreement"] == "agree_after_qubit_permutation"
