"""Single-bit marginal tests: they find a backend whose marginal differs in a distribution too
wide for the full-table test, leave measured_assessment unchanged, and rarely flag
backends that sample the same distribution."""
import json

import numpy as np

from services.analysis.divergence import create_counts_report
from services.analysis.divergence.marginals import marginal_block


def _counts(rng, p_one, shots, ordering="msb"):
    """Counts of independent bits with P(bit k = 1) = p_one[k]; key position k is clbit k (msb)."""
    bits = (rng.random((shots, len(p_one))) < np.asarray(p_one)).astype(int)
    keys = ["".join(map(str, row)) for row in bits]
    if ordering == "lsb":
        keys = [k[::-1] for k in keys]
    out = {}
    for key in keys:
        out[key] = out.get(key, 0) + 1
    return out


def _report(results):
    return create_counts_report(results, n_shots=8200)


def test_a_dense_wide_distribution_with_one_wrong_bit_is_found_by_its_marginal():
    rng = np.random.default_rng(1)
    good = [0.4] * 21
    bad = [0.4] * 20 + [0.0]
    results = [{"simulator": f"s{k}", "qubit_ordering": "msb", "counts": _counts(rng, good, 8200)} for k in range(3)]
    results.append({"simulator": "wrong", "qubit_ordering": "msb", "counts": _counts(rng, bad, 8200)})
    report = _report(results)
    for record in report["pairwise_agreement"]:
        assert record["measured_assessment"] != "distinguishable"
        expected = "marginal_distinguishable" if "wrong" in record["simulators"] else "no_marginal_difference_detected"
        assert record["marginal_assessment"] == expected, record["simulators"]
        if "wrong" in record["simulators"]:
            assert record["metrics"]["marginal_test"]["differing_clbits"] == [20]
    summary = report["statistical_test_summary"]["marginal_test_summary"]
    assert summary["family_size"] <= 6 * 21 and summary["correction"] == "Holm"
    json.dumps(report, allow_nan=False)


def test_lsb_and_msb_keys_are_compared_bit_for_bit_in_the_aligned_basis():
    rng = np.random.default_rng(2)
    p = [0.1, 0.5, 0.9, 0.3]
    results = [{"simulator": "m", "qubit_ordering": "msb", "counts": _counts(rng, p, 8200)},
               {"simulator": "l", "qubit_ordering": "lsb", "counts": _counts(rng, p, 8200, "lsb")}]
    record = _report(results)["pairwise_agreement"][0]
    block = record["metrics"]["marginal_test"]
    assert record["marginal_assessment"] == "no_marginal_difference_detected"
    assert [round(b["p_one"][0], 1) for b in block["bits"]] == p
    assert [b["clbit"] for b in block["bits"]] == [0, 1, 2, 3]


def test_one_bit_keys_have_no_marginal_test():
    results = [{"simulator": "a", "qubit_ordering": "msb", "counts": {"0": 50, "1": 50}},
               {"simulator": "b", "qubit_ordering": "msb", "counts": {"0": 49, "1": 51}}]
    assert _report(results)["pairwise_agreement"][0]["marginal_assessment"] == "not_applicable"
    assert marginal_block({"0": 1}, {"1": 1}, "msb") is None


def test_backends_sampling_one_distribution_are_rarely_flagged():
    rng = np.random.default_rng(3)
    flagged = 0
    for _ in range(40):
        p = rng.uniform(0.05, 0.95, size=12)
        results = [{"simulator": f"s{k}", "qubit_ordering": "msb", "counts": _counts(rng, p, 2000)} for k in range(5)]
        report = _report(results)
        flagged += any(r["marginal_assessment"] == "marginal_distinguishable" for r in report["pairwise_agreement"])
    assert flagged <= 4


def test_constant_bits_are_not_tested_and_correct_pairs_are_not_flagged_beside_a_wrong_backend():
    rng = np.random.default_rng(4)
    good = [0.0, 0.3, 0.5, 0.7, 0.2, 0.6]
    bad = [0.0, 0.42, 0.62, 0.82, 0.32, 0.72]
    results = [{"simulator": f"s{k}", "qubit_ordering": "msb", "counts": _counts(rng, good, 8200)} for k in range(6)]
    results.append({"simulator": "wrong", "qubit_ordering": "msb", "counts": _counts(rng, bad, 8200)})
    report = _report(results)
    for record in report["pairwise_agreement"]:
        bit0 = record["metrics"]["marginal_test"]["bits"][0]
        assert not bit0["tested"] and bit0["not_tested_reason"] == "constant_in_both"
        expected = "marginal_distinguishable" if "wrong" in record["simulators"] else "no_marginal_difference_detected"
        assert record["marginal_assessment"] == expected, record["simulators"]
    assert report["statistical_test_summary"]["marginal_test_summary"]["family_size"] == 21 * 5
