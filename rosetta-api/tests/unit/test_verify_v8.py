"""The V8 statistical validation helpers (scripts/verify/): distributions and their total variation,
sampled keys in each declared ordering, Monte Carlo estimates and intervals, per-run tallies from
the server's analysis, the calibration branches and the mutation operators, on small run counts."""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "verify"))

import false_flags  # noqa: E402
import v8_calibration  # noqa: E402
import v8_common as c  # noqa: E402
import v8_mutation  # noqa: E402

sys.path.remove(str(REPO / "scripts" / "verify"))


def test_keys_follow_the_declared_ordering():
    assert c.lsb_keys(2) == ["00", "01", "10", "11"]
    assert c.key_for(1, 3, "lsb") == "001"
    assert c.key_for(1, 3, "msb") == "100"


@pytest.mark.parametrize("k", [2, 4, 8, 16])
def test_least_favourable_alternative_has_the_stated_size(k):
    p = c.uniform(k)
    q = c.least_favourable(p, 0.05)
    d = q - p
    assert c.total_variation(p, q) == pytest.approx(0.05)
    assert (d ** 2 / p).sum() == pytest.approx(4 * 0.05 ** 2)
    assert q.sum() == pytest.approx(1.0)


def test_least_favourable_refuses_an_unequal_split():
    with pytest.raises(ValueError):
        c.least_favourable(np.array([0.7, 0.2, 0.1]), 0.05)


def test_shift_moves_exactly_tv():
    q = c.shift(c.uniform(4), 0.05, 0, 1)
    assert q.tolist() == pytest.approx([0.2, 0.3, 0.25, 0.25])
    with pytest.raises(ValueError):
        c.shift(c.uniform(4), 0.3, 0, 1)


def test_independent_bits_has_the_requested_marginals():
    p = c.independent_bits([0.1, 0.7, 0.5])
    idx = np.arange(8)
    for bit, want in enumerate([0.1, 0.7, 0.5]):
        assert p[(idx >> bit) & 1 == 1].sum() == pytest.approx(want)


def test_common_and_rare_masses():
    p, common = c.common_and_rare(8, 4, 0.03)
    assert p.sum() == pytest.approx(1.0)
    assert p[common].sum() == pytest.approx(0.97)
    assert len(common) == 4


def test_msb_sample_is_the_lsb_sample_with_reversed_keys():
    p = c.peaked(8)
    a = c.sample_counts(np.random.default_rng(5), p, 1000, "lsb")
    b = c.sample_counts(np.random.default_rng(5), p, 1000, "msb")
    assert {k[::-1]: v for k, v in a.items()} == b
    assert sum(a.values()) == 1000


def test_clopper_pearson_known_values():
    lo, hi = c.clopper_pearson(0, 40)
    assert lo == 0.0 and hi == pytest.approx(1 - 0.025 ** (1 / 40))
    lo, hi = c.clopper_pearson(1, 40)
    assert lo == pytest.approx(0.000633, abs=2e-6) and hi == pytest.approx(0.1316, abs=2e-4)
    est = c.proportion(20, 2000)
    assert est["estimate"] == 0.01 and est["mcse"] == pytest.approx(math.sqrt(0.01 * 0.99 / 2000))


def test_clustered_rate_with_equal_totals_is_the_mean_of_run_rates():
    events = [0, 1, 2, 0, 3]
    out = c.clustered_rate(events, [10] * 5)
    rates = np.array(events) / 10
    assert out["estimate"] == pytest.approx(rates.mean())
    assert out["mcse"] == pytest.approx(rates.std(ddof=1) / math.sqrt(5))


def test_run_record_counts_false_and_true_flags():
    rng = np.random.default_rng(1)
    good, bad = c.uniform(4), c.least_favourable(c.uniform(4), 0.4)
    results = [c.runner_result(f"b{i}", c.sample_counts(rng, good, 8200), "lsb", seed=i)
               for i in range(3)]
    results.append(c.runner_result("w", c.sample_counts(rng, bad, 8200), "lsb", seed=9))
    rec = c.run_record(c.analyse(results, 8200), {"w"})
    assert rec["correct_pairs"] == 3 and rec["wrong_pairs"] == 3
    assert rec["tp_differs"] == 3 and rec["tp_full_by"] == 3
    assert rec["wrong_distinguishable"] == 3


def test_one_monte_carlo_run_detects_a_gross_backend():
    rec = false_flags.one_run("B-gross40-2", 0)
    assert rec["wrong_pairs"] == 13 and rec["correct_pairs"] == 78
    assert rec["tp_full_by"] == 13


def test_summary_of_runs_has_intervals():
    recs = [false_flags.one_run("D-defect-bitflip", r) for r in range(2)]
    out = false_flags.summarise("D-defect-bitflip", recs)
    assert out["runs"] == 2
    assert out["pair_power_differs"]["estimate"] == 1.0
    assert 0 <= out["any_false_flag_differs"]["lo"] <= out["any_false_flag_differs"]["hi"] <= 1


def test_unequal_pair_rejections_are_counted():
    rejected = false_flags.unequal_pair_runs((8200, 400, range(20)))
    assert 0 <= rejected <= 20


def test_stated_minimum_shots_are_the_platform_minimum():
    rows = false_flags.recommended_shots()
    assert {k: v["minimum"] for k, v in rows.items()} == false_flags.STATED_SHOTS


@pytest.mark.parametrize("name,branch", [
    ("exact-small-table", "exact_conditional|direct/single_bit"),
    ("basis-lsb-msb-16", "bit_reversal/declared_qubit_ordering"),
    ("single-bit-lsb-msb", "direct/single_bit"),
])
def test_calibration_generators_reach_their_branch(name, branch):
    seen = [s for r in range(5) for s in v8_calibration.one_sample(name, r)]
    assert any(branch in s["branch"] for s in seen)
    assert all(0.0 <= s["chi2"] <= 1.0 and 0.0 <= s["g"] <= 1.0 for s in seen)


def test_calibration_rows_judge_against_a_plus_two_mcse():
    samples = [{"chi2": x, "g": x, "branch": "b"} for x in np.linspace(0.0005, 1, 1000)]
    rows = v8_calibration.calibration_rows("u", samples, ("chi2",))
    assert rows[0]["ok_at_0.05"] and rows[0]["P(p<=0.05)"] == pytest.approx(0.05, abs=0.002)
    bad = [{"chi2": 0.0001, "g": 0.0001, "branch": "b"}] * 100
    assert not v8_calibration.calibration_rows("x", bad, ("chi2",))[0]["ok_at_0.05"]


def test_calibration_rows_split_by_branch():
    samples = ([{"chi2": 0.5, "g": 0.5, "branch": "a"}] * 3
               + [{"chi2": 0.001, "g": 0.001, "branch": "b"}] * 3)
    rows = v8_calibration.calibration_rows("x", samples, ("chi2",), min_branch=2)
    assert [(r["branch"], r["n"]) for r in rows] == [("all", 6), ("a", 3), ("b", 3)]
    assert rows[2]["P(p<=0.01)"] == 1.0


def test_swap_qubits_exchanges_two_qubits():
    state = np.zeros(8, dtype=complex)
    state[0b001] = 1
    assert np.flatnonzero(v8_mutation.swap_qubits(state, 0, 1)).tolist() == [0b010]
    assert np.flatnonzero(v8_mutation.swap_qubits(state, 0, 2)).tolist() == [0b100]


def test_key_mutations():
    assert v8_mutation.reverse_keys({"001": 3, "100": 1}) == {"100": 3, "001": 1}
    assert v8_mutation.swap_key_clbits({"001": 5}, "lsb") == {"010": 5}
    assert v8_mutation.swap_key_clbits({"100": 5}, "msb") == {"010": 5}


def test_statevector_mutants_flagged_and_controls_not():
    rows = v8_mutation.statevector_case(3)
    for r in rows:
        if r["kind"] == "control":
            assert not r["flagged"], r
        elif not r["equivalent"]:
            assert r["flagged"], r
    score = v8_mutation.score(rows)["statevector-synthetic"]
    assert score["controls_flagged"]["k"] == 0
