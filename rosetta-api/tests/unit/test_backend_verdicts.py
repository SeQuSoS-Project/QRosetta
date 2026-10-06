"""backendVerdicts/headlineModel (static/js/backend_verdicts.js): per-backend counts follow
isDisagreement exactly, keep marginal and full-distribution counts apart, and name failed
backends."""
from itertools import combinations

from tests.unit.frontend_harness import call_js, requires_node

pytestmark = requires_node

MODULES = ["backend_verdicts.js", "run_status.js"]


def _sv_pair(a, b, label):
    return {"simulators": [a, b], "mode": "statevector", "agreement": label, "metrics": {}}


def _m_pair(a, b, assessment, marginal="no_marginal_difference_detected", agreement="distance_within_threshold"):
    return {"simulators": [a, b], "mode": "measured", "agreement": agreement,
            "measured_assessment": assessment, "marginal_assessment": marginal, "metrics": {}}


def _report(pairs, sims, n_shots=None, raws=None):
    raws = raws if raws is not None else [{"simulator": s, "dispatch_status": "ok"} for s in sims]
    return {"n_shots": n_shots, "raw_results": raws,
            "divergence_report": {"simulators": sims, "pairwise_agreement": pairs,
                                  "ordering_map": {s: "msb" for s in sims}}}


def _verdicts(report):
    v, h = call_js(MODULES, [("backendVerdicts", [report]),
                             ("headlineModel", [call_js(MODULES, [("backendVerdicts", [report])])[0]])])
    return {b["key"]: b for b in v["backends"]}, v, h


def _disagreement_counts(report):
    pairs = report["divergence_report"]["pairwise_agreement"]
    flags = call_js(MODULES, [("isDisagreement", [p]) for p in pairs])
    counts = {}
    for p, flag in zip(pairs, flags):
        for s in p["simulators"]:
            counts[s] = counts.get(s, 0) + bool(flag)
    return counts


def test_one_wrong_statevector_backend_is_the_outlier():
    sims = ["a", "b", "c", "d"]
    pairs = [_sv_pair(x, y, "residual_disagreement" if "d" in (x, y) else "agree_directly")
             for x, y in combinations(sims, 2)]
    report = _report(pairs, sims)
    by_key, v, h = _verdicts(report)
    assert by_key["d"]["differs"] == 3 and by_key["d"]["compared"] == 3
    assert all(by_key[s]["differs"] == 1 for s in "abc")
    assert {k: b["differs"] for k, b in by_key.items()} == _disagreement_counts(report)
    assert [b["key"] for b in h["outliers"]] == ["d"]
    assert h["explainedByOutliers"] is True
    assert sorted(b["key"] for b in h["rest"]) == ["a", "b", "c"]
    assert v["disagreeing"] == 3


def test_bit_reversal_pairs_are_not_disagreements():
    sims = ["lsb1", "msb1", "msb2"]
    pairs = [_sv_pair("lsb1", "msb1", "agree_after_bit_reversal"),
             _sv_pair("lsb1", "msb2", "agree_after_bit_reversal"),
             _sv_pair("msb1", "msb2", "agree_directly")]
    by_key, v, h = _verdicts(_report(pairs, sims))
    assert all(b["differs"] == 0 for b in by_key.values())
    assert h["differing"] == [] and h["outliers"] == []


def test_measured_marginal_and_full_counts_stay_separate():
    sims = ["q", "r", "s"]
    pairs = [_m_pair("q", "r", "consistent_within_shot_noise", marginal="marginal_distinguishable"),
             _m_pair("q", "s", "distinguishable", agreement="distance_exceeds_threshold"),
             _m_pair("r", "s", "inconclusive_low_shots")]
    report = _report(pairs, sims, n_shots=100)
    by_key, v, _ = _verdicts(report)
    assert v["mode"] == "measured"
    assert by_key["q"]["differs"] == 2
    assert by_key["q"]["differsMarginal"] == 1 and by_key["q"]["differsFull"] == 1
    assert by_key["r"]["inconclusive"] == 1 and by_key["s"]["inconclusive"] == 1
    assert v["inconclusive"] == 1
    assert {k: b["differs"] for k, b in by_key.items()} == _disagreement_counts(report)


def test_distinguishable_pair_within_distance_threshold_counts_as_differing():
    pairs = [_m_pair("x", "y", "distinguishable", agreement="distance_within_threshold")]
    by_key, _, _ = _verdicts(_report(pairs, ["x", "y"], n_shots=8200))
    assert by_key["x"]["differs"] == 1


def test_failed_backends_are_named_and_not_comparable_counted():
    sims = ["a", "b"]
    raws = [{"simulator": "a", "dispatch_status": "ok"}, {"simulator": "b", "dispatch_status": "ok"},
            {"simulator": "c", "dispatch_status": "offline", "error": "UNAVAILABLE"},
            {"simulator": "d", "dispatch_status": "timeout", "error": "TIMEOUT"}]
    pairs = [{"simulators": ["a", "b"], "mode": "statevector", "agreement": "not_comparable",
              "metrics": {"reason": "shape_mismatch"}}]
    by_key, v, h = _verdicts(_report(pairs, sims, raws=raws))
    assert h["failed"] == {"offline": ["c"], "error": [], "timeout": ["d"]}
    assert by_key["a"]["notComparable"] == 1 and by_key["a"]["compared"] == 0
    assert h["ok"] == 2


def test_multi_run_keys_are_separate_backends():
    sims = ["qiskit~opt0~run1", "qiskit~opt0~run2", "cirq"]
    pairs = [_sv_pair(x, y, "agree_directly") for x, y in combinations(sims, 2)]
    by_key, _, _ = _verdicts(_report(pairs, sims))
    assert set(by_key) == set(sims)
    assert by_key["qiskit~opt0~run1"]["compared"] == 2


def test_outlier_plus_one_more_pair_lists_the_residual_pair():
    sims = ["a", "b", "c", "d", "e"]
    def label(x, y):
        return "residual_disagreement" if "e" in (x, y) or {x, y} == {"a", "b"} else "agree_directly"
    pairs = [_sv_pair(x, y, label(x, y)) for x, y in combinations(sims, 2)]
    _, _, h = _verdicts(_report(pairs, sims))
    assert [b["key"] for b in h["outliers"]] == ["e"]
    assert h["residualPairs"] == [["a", "b"]]


def test_inconclusive_count_includes_pairs_that_differ_in_a_marginal():
    pairs = [_m_pair("x", "y", "inconclusive_low_shots", marginal="marginal_distinguishable"),
             _m_pair("x", "z", "inconclusive_low_shots"),
             _m_pair("y", "z", "consistent_within_shot_noise")]
    by_key, v, _ = _verdicts(_report(pairs, ["x", "y", "z"], n_shots=8200))
    assert v["inconclusive"] == 2
    assert by_key["x"]["inconclusive"] == 2 and by_key["x"]["differs"] == 1
