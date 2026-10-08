"""Summary headline (overview_renderer.js headlineSentences over backend_verdicts.js headlineModel)
on synthetic reports: named outliers, groups that differ from each other, isolated pairs, spread
disagreement, inconclusive pairs that are neither agreement nor difference, BY-only pairs, multi-run
keys, and a random sweep checking that every sentence is complete and every red backend differs."""
import random
import re
from itertools import combinations

import pytest

from tests.unit.frontend_harness import call_js, requires_node

pytestmark = requires_node

S = ["qiskit", "cirq", "qulacs", "quest", "pennylane-lightning", "pennylane-default", "qsim-cirq", "qibo",
     "qrisp", "myqlm", "pyquil", "torchquantum", "quimb", "cuquantum"]

_MEASURED = {"agree": "consistent_within_shot_noise", "differ": "distinguishable", "by": "distinguishable",
             "inc": "inconclusive_low_shots", "marg": "consistent_within_shot_noise",
             "marginc": "inconclusive_low_shots"}


def _report(names, verdict, measured=False, magnitude=None, n_shots=8200, timeout=None):
    pairs = []
    for a, b in combinations(names, 2):
        v = verdict(a, b)
        size = magnitude(a, b) if magnitude else None
        if not measured:
            metrics = {} if size is None else {"label_aligned_fidelity": size}
            pairs.append({"simulators": [a, b], "mode": "statevector",
                          "agreement": "residual_disagreement" if v == "differ" else "agree_directly",
                          "metrics": metrics})
            continue
        st = {"significant_fwer": v != "by", "verdict": _MEASURED[v]}
        if size is not None:
            st["effect_size"] = {"total_variation": size}
        pairs.append({"simulators": [a, b], "mode": "measured", "agreement": "distance_within_threshold",
                      "measured_assessment": _MEASURED[v],
                      "marginal_assessment": "marginal_distinguishable" if v in ("marg", "marginc")
                      else "no_marginal_difference_detected",
                      "metrics": {"marginal_test": {}, "statistical_test": st}})
    report = {"raw_results": [{"simulator": s, "dispatch_status": "ok"} for s in names],
              "divergence_report": {"pairwise_agreement": pairs, "simulators": names, "ordering_map": {}}}
    if measured:
        report["n_shots"] = n_shots
    if timeout is not None:
        report["timeout_seconds"] = timeout
    return report


def _groups(*sets):
    return lambda a, b: "agree" if any(a in s and b in s for s in sets) else "differ"


def _headline(report):
    return call_js(["overview_renderer.js"], [("headlineSentences", [report])])[0]


def _many(reports):
    return call_js(["overview_renderer.js"], [("headlineSentences", [r]) for r in reports])


def _assert_well_formed(out):
    for line in out["lines"]:
        assert re.search(r"\w", line), out["lines"]
        assert line.endswith("."), line
        assert ".." not in line and " ." not in line and "()" not in line, line
        assert not line.startswith((".", ",", ";")), line


def test_all_agree_is_an_all_clear():
    out = _headline(_report(S, lambda a, b: "agree"))
    assert out["tone"] == "success" and out["model"]["kind"] == "none"
    assert out["lines"][1] == "Every comparable pair of backends agrees."


def test_one_outlier_with_inconclusive_correct_pairs_names_only_the_outlier():
    rng = random.Random(7)
    inconclusive = {frozenset(p) for p in combinations([s for s in S if s != "qrisp"], 2) if rng.random() < 0.4}
    def verdict(a, b):
        if "qrisp" in (a, b):
            return "differ"
        return "inc" if frozenset((a, b)) in inconclusive else "agree"
    out = _headline(_report(S, verdict, measured=True, magnitude=lambda a, b: 0.087 if "qrisp" in (a, b) else 0.001))
    _assert_well_formed(out)
    assert out["model"]["flagged"] == ["qrisp"]
    assert out["lines"][1] == ("Qrisp differs from all 13 other backends (13 distinguishable; "
                               "total variation 0.087 against the other 13 backends).")
    assert out["lines"][2].startswith("Among the other 13 backends, no pair is distinguishable")


def test_backend_in_every_differing_pair_is_named_with_its_count():
    differing = {"qiskit", "cirq", "qulacs", "quest", "pennylane-lightning", "pennylane-default", "qsim-cirq"}
    def verdict(a, b):
        if "qrisp" in (a, b):
            return "differ" if ({a, b} - {"qrisp"}) <= differing else "inc"
        return "agree"
    out = _headline(_report(S, verdict, measured=True))
    _assert_well_formed(out)
    assert out["model"]["kind"] == "named" and out["model"]["flagged"] == ["qrisp"]
    assert out["lines"][1] == "Qrisp differs from 7 of 13 other backends (7 distinguishable)."


def test_two_outliers_that_differ_from_each_other():
    out = _headline(_report(S, lambda a, b: "differ" if {a, b} & {"qibo", "qrisp"} else "agree"))
    _assert_well_formed(out)
    assert sorted(out["model"]["flagged"]) == ["qibo", "qrisp"]
    assert out["lines"][1] == "Qibo differs from all 13 other backends. Qrisp differs from all 13 other backends."
    assert out["lines"][2] == "The other 12 backends agree with each other."


def test_two_outliers_that_agree_form_a_group():
    out = _headline(_report(S, _groups({"qibo", "qrisp"}, set(S) - {"qibo", "qrisp"}),
                            magnitude=lambda a, b: 0.146))
    assert out["lines"][1] == ("Qibo and Qrisp agree with each other and differ from every other backend "
                               "(12; lowest fidelity 0.146 against the other 12 backends).")


def test_tied_groups_are_described_as_groups():
    for sets in ([set(S[:7]), set(S[7:])], [set(S[:5]), set(S[5:10]), set(S[10:])]):
        out = _headline(_report(S, _groups(*sets)))
        _assert_well_formed(out)
        assert out["model"]["kind"] == "camps"
        assert out["lines"][1].startswith(f"The backends split into {len(sets)} groups that differ from each other")
        assert out["lines"][2] == "Within each group no pair differs."


def test_bridge_backend_is_set_aside():
    a, b = set(S[:6]), set(S[6:]) - {"qrisp"}
    out = _headline(_report(S, lambda x, y: "agree" if "qrisp" in (x, y) else _groups(a, b)(x, y)))
    _assert_well_formed(out)
    assert out["model"]["kind"] == "camps" and out["model"]["neutral"] == ["qrisp"]
    assert "qrisp" not in out["model"]["flagged"]
    assert "Qrisp differs from no backend." in out["lines"]


def test_single_and_non_transitive_pairs():
    out = _headline(_report(S, lambda a, b: "differ" if {a, b} == {"qiskit", "cuquantum"} else "agree"))
    assert out["model"]["kind"] == "pairs" and out["lines"][1] == "One pair differs: cuQuantum (NVIDIA) × Qiskit (IBM)."
    chain = [{"qiskit", "cirq"}, {"qulacs", "quest"}]
    out = _headline(_report(S, lambda a, b: "differ" if {a, b} in chain else "agree"))
    _assert_well_formed(out)
    assert out["model"]["kind"] == "pairs" and len(out["model"]["pairs"]) == 2
    out = _headline(_report(S, lambda a, b: "differ" if {a, b} in ({"qiskit", "cirq"}, {"cirq", "qulacs"}) else "agree"))
    assert out["model"]["flagged"] == ["cirq"]


def test_isolated_measured_pair_suggests_more_shots():
    out = _headline(_report(S, lambda a, b: "differ" if {a, b} == {"pyquil", "quest"} else "agree", measured=True,
                            n_shots=100))
    _assert_well_formed(out)
    assert any("rerun with another seed to confirm" in line for line in out["lines"])
    assert out["lines"][-1].startswith("If a rerun confirms a difference")


def test_by_only_hub_is_named_without_an_all_clear():
    out = _headline(_report(S, lambda a, b: "by" if "qrisp" in (a, b) else "agree", measured=True))
    _assert_well_formed(out)
    assert out["tone"] == "inconclusive" and out["model"]["flagged"] == []
    assert out["lines"][1].startswith("Qrisp is distinguishable from all 13 other backends under Benjamini–Yekutieli")


def test_all_inconclusive_is_neither_clear_nor_anomalous():
    out = _headline(_report(S, lambda a, b: "inc", measured=True))
    _assert_well_formed(out)
    assert out["tone"] == "inconclusive" and out["model"]["flagged"] == []


def test_multi_run_groups_of_runs():
    names = [f"qiskit~opt{lvl}~run1" for lvl in range(3)] + [f"cirq~opt{lvl}~run1" for lvl in range(3)]
    out = _headline(_report(names, lambda a, b: "agree" if a[:4] == b[:4] else "differ"))
    _assert_well_formed(out)
    assert out["model"]["kind"] == "camps"
    assert out["lines"][1] == ("The runs split into 2 groups that differ from each other: all 3 Cirq (Google) runs (3); "
                               "all 3 Qiskit (IBM) runs (3).")


def test_brand_names_keep_their_case_at_sentence_start():
    out = _headline(_report(S, lambda a, b: "differ" if "cuquantum" in (a, b) else "agree"))
    assert out["lines"][1].startswith("cuQuantum (NVIDIA) differs from all 13")
    out = _headline(_report(S, _groups({"cuquantum", "myqlm"}, set(S) - {"cuquantum", "myqlm"})))
    assert out["lines"][1].startswith("cuQuantum (NVIDIA) and myQLM (Eviden) agree")


def test_timeout_advice_depends_on_the_server_maximum():
    raws = [{"simulator": "a", "dispatch_status": "ok"}, {"simulator": "b", "dispatch_status": "ok"},
            {"simulator": "c", "dispatch_status": "timeout", "error": "TIMEOUT"}]
    base = {"raw_results": raws, "divergence_report": {"simulators": ["a", "b"], "pairwise_agreement": [
        {"simulators": ["a", "b"], "mode": "statevector", "agreement": "agree_directly", "metrics": {}}]}}
    steps = call_js(["overview_renderer.js"], [("nextSteps", [{**base, "timeout_seconds": 300}]),
                                               ("nextSteps", [{**base, "timeout_seconds": 60}])])
    assert any("already at the server maximum (300 s)" in s for s in steps[0])
    assert any("raise the timeout" in s for s in steps[1])


def test_lower_bound_recommendation_is_worded_as_at_least():
    pairs = [{"simulators": ["a", "b"], "mode": "measured", "agreement": "distance_within_threshold",
              "measured_assessment": "inconclusive_low_shots", "marginal_assessment": "no_marginal_difference_detected",
              "metrics": {"statistical_test": {"verdict": "inconclusive_low_shots", "recommendation_is_lower_bound": lb,
                                               "n_shots": {"a": 8200, "b": 8200},
                                               "power": {"recommended_shots_per_backend": 82000,
                                                         "recommended_exceeds_actual": True}}}}
             for lb in (True,)]
    report = {"n_shots": 8200, "raw_results": [{"simulator": s, "dispatch_status": "ok"} for s in "ab"],
              "divergence_report": {"simulators": ["a", "b"], "pairwise_agreement": pairs}}
    steps = call_js(["overview_renderer.js"], [("nextSteps", [report])])[0]
    assert any("at least 82,000 shots per backend" in s or "at least 82000 shots per backend" in s for s in steps), steps


@pytest.mark.parametrize("seed", range(6))
def test_random_reports_give_complete_sentences_and_red_only_for_differing_backends(seed):
    rng = random.Random(seed)
    reports = []
    for _ in range(40):
        names = rng.sample(S, rng.randint(2, 14))
        measured = rng.random() < 0.5
        p_differ, p_inc = rng.random() * 0.5, rng.random() * 0.5
        wrong = set(rng.sample(names, rng.randint(0, min(3, len(names)))))
        table = {}
        for a, b in combinations(names, 2):
            r = rng.random()
            if {a, b} & wrong and r < 0.8:
                v = "differ"
            elif r < p_differ * 0.3:
                v = "differ"
            elif measured and r < p_differ * 0.3 + p_inc:
                v = rng.choice(["inc", "by", "marg"])
            else:
                v = "agree"
            table[frozenset((a, b))] = v
        reports.append(_report(names, lambda a, b, t=table: t[frozenset((a, b))], measured=measured,
                               magnitude=lambda a, b: rng.random()))
    for report, out in zip(reports, _many(reports)):
        _assert_well_formed(out)
        pairs = report["divergence_report"]["pairwise_agreement"]
        robust = {s for p in pairs for s in p["simulators"]
                  if p.get("measured_assessment") == "distinguishable" and p["metrics"]["statistical_test"]["significant_fwer"]
                  or p.get("marginal_assessment") == "marginal_distinguishable" or p["agreement"] == "residual_disagreement"}
        assert set(out["model"]["flagged"]) <= robust
        assert (out["tone"] == "anomaly") == bool(robust)
        if out["model"]["kind"] == "named":
            n_rest = len(report["raw_results"]) - len(out["model"]["flagged"])
            if n_rest >= 2:
                assert any(f"other {n_rest} backends" in line for line in out["lines"]), out["lines"]


def test_outlier_plus_an_unrelated_pair_lists_that_pair():
    def verdict(a, b):
        return "differ" if "qrisp" in (a, b) or {a, b} == {"qiskit", "cirq"} else "agree"
    out = _headline(_report(S, verdict))
    _assert_well_formed(out)
    assert out["model"]["flagged"] == ["qrisp"]
    assert out["lines"][1] == "Qrisp differs from all 13 other backends."
    assert out["lines"][2] == "Among the other 13 backends, 1 pair differs: Cirq (Google) × Qiskit (IBM)."


def test_backend_rows_order_run_numbers_numerically():
    names = [f"qiskit~opt0~run{n}" for n in (1, 2, 10, 11)] + ["cirq"]
    report = _report(names, lambda a, b: "agree")
    v = call_js(["backend_verdicts.js"], [("backendVerdicts", [report])])[0]
    rows = call_js(["overview_renderer.js"], [("backendRows", [v])])[0]
    assert [r["key"] for r in rows] == ["cirq", "qiskit~opt0~run1", "qiskit~opt0~run2", "qiskit~opt0~run10",
                                        "qiskit~opt0~run11"]
