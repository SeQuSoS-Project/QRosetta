"""Summary headline sizes and caveats: a named backend's difference is sized against the backends
the headline does not name, not over pairs with other differing backends; spread headlines name
groups and list the rest; a backend that differs from a minority of the others gets a chance
caveat; the p-value method note."""
from tests.unit.frontend_harness import call_js, requires_node
from tests.unit.test_headline_cases import S, _assert_well_formed, _groups, _headline, _report

pytestmark = requires_node

PL = {"pennylane-default", "pennylane-lightning"}


def test_measured_size_is_against_the_unnamed_backends():
    def verdict(a, b):
        return "differ" if {a, b} & ({"qibo"} | PL) and not {a, b} <= PL else "agree"

    def size(a, b):
        pair = {a, b}
        if "qibo" in pair and pair & PL:
            return 0.069
        if "qibo" in pair:
            return 0.0085 if "qiskit" in pair else 0.012 if "cirq" in pair else 0.016 if "quest" in pair else 0.011
        if pair & PL and not pair <= PL:
            return 0.06
        return 0.002
    out = _headline(_report(S, verdict, measured=True, magnitude=size))
    _assert_well_formed(out)
    assert out["model"]["kind"] == "named" and sorted(out["model"]["flagged"]) == sorted({"qibo"} | PL)
    line = out["lines"][1]
    assert "0.069" not in line
    assert ("Qibo differs from all 13 other backends (13 distinguishable; median total variation 0.011 "
            "against the other 11 backends, range 0.0085–0.016)") in line
    assert "(12; total variation 0.060 against the other 11 backends)" in line


def test_statevector_fidelity_is_against_the_unnamed_backends():
    wrong = {"qsim-cirq", "qrisp", "torchquantum"}

    def size(a, b):
        if "qrisp" in (a, b):
            return 0.953
        if {a, b} & wrong:
            return 1 - 1.5e-13
        return 1.0
    out = _headline(_report(S, lambda a, b: "differ" if {a, b} & wrong else "agree", magnitude=size))
    _assert_well_formed(out)
    assert "qsim (Google) differs from all 13 other backends (lowest fidelity 1 − 1.5e-13 against the other 11 backends)" \
        in out["lines"][1]
    assert "Qrisp differs from all 13 other backends (lowest fidelity 0.953 against the other 11 backends)" in out["lines"][1]


def test_camps_are_sized_between_groups():
    a, b = set(S[:7]), set(S[7:])
    out = _headline(_report(S, _groups(a, b), magnitude=lambda x, y: 0.5 if (x in a) != (y in a) else 1.0))
    assert "(lowest fidelity 0.500 between the groups)" in out["lines"][1]


def test_spread_names_the_worst_groups_and_lists_the_others():
    small = {"qibo", "qrisp", "qsim-cirq", "torchquantum"}

    def verdict(x, y):
        pair = {x, y}
        if pair <= PL:
            return "agree"
        return "differ" if pair & (small | PL) else "agree"

    def size(x, y):
        pair = {x, y}
        if pair & PL and not pair <= PL:
            return 0.94
        if "qibo" in pair:
            return 0.99
        return 1 - 1e-13 if pair & small else 1.0
    out = _headline(_report(S, verdict, magnitude=size))
    _assert_well_formed(out)
    model = out["model"]
    assert model["kind"] == "spread"
    assert sorted(model["named"][0]["members"]) == sorted(PL)
    assert set(model["flagged"]) == small | PL
    assert len(model["unnamed"]) >= 1
    assert out["lines"][1].startswith("PL Default and PL Lightning agree with each other")
    assert any("also differ from more than half of the backends they were compared with" in line
               for line in out["lines"])


def test_minority_differences_get_a_chance_caveat():
    out = _headline(_report(S, lambda a, b: "differ" if {a, b} in ({"quest", "qiskit"}, {"quest", "cirq"}) else "agree",
                            measured=True))
    _assert_well_formed(out)
    assert out["model"]["chance"] == ["quest"]
    assert any(line.startswith("QuEST is consistent with the other 11 backends it was compared with. With 91 pairs")
               and "rerun with another seed" in line for line in out["lines"])
    assert out["lines"][-1].startswith("If a rerun confirms a difference")


def test_majority_differences_and_statevector_get_no_chance_caveat():
    out = _headline(_report(S, lambda a, b: "differ" if "quest" in (a, b) else "agree", measured=True))
    assert out["model"]["chance"] == [] and out["lines"][-1].startswith("A pair that differs shows")
    out = _headline(_report(S, lambda a, b: "differ" if {a, b} in ({"quest", "qiskit"}, {"quest", "cirq"}) else "agree"))
    assert out["model"]["chance"] == []
    partly_inconclusive = _report(S, lambda a, b: "differ" if {a, b} in ({"quest", "qiskit"}, {"quest", "cirq"})
                                  else "inc" if "quest" in (a, b) else "agree", measured=True)
    assert _headline(partly_inconclusive)["model"]["chance"] == []


def test_test_method_note_counts_exact_and_degenerate_pairs():
    report = _report(["a", "b", "c"], lambda x, y: "agree", measured=True)
    methods = ["exact_conditional", "degenerate", "asymptotic"]
    for p, m in zip(report["divergence_report"]["pairwise_agreement"], methods):
        p["metrics"]["statistical_test"]["test_method"] = m
    note = call_js(["overview_renderer.js"], [("testMethodNote", [report])])[0]
    assert note == ("1 of 3 pairs have exact conditional p-values (2 × 2 tables with expected counts below 5); "
                    "in 1 of 3 pairs both backends returned the same single outcome, so there was nothing to test (p = 1).")
    for p in report["divergence_report"]["pairwise_agreement"]:
        p["metrics"]["statistical_test"]["test_method"] = "asymptotic"
    assert call_js(["overview_renderer.js"], [("testMethodNote", [report])])[0] is None
