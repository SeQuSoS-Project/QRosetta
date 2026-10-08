"""Shot advice margin, the degenerate test method, and the statistical-test table columns."""
from services.analysis.divergence import create_counts_report
from services.analysis.divergence.statistics import RECOMMENDATION_MARGIN, _with_margin
from services.publication.tables import _tbl_statistical


def _pair(report, a, b):
    return next(p for p in report["pairwise_agreement"] if set(p["simulators"]) == {a, b})


def test_margin_rounds_up_to_two_significant_figures():
    assert RECOMMENDATION_MARGIN == 1.1
    assert _with_margin(4444) == 4900
    assert _with_margin(9732) == 11000
    assert _with_margin(8199) == 9100
    assert _with_margin(30) == 33
    assert _with_margin(None) is None
    assert _with_margin(999_000) == 1_000_000


def test_recommendation_keeps_the_minimum_beside_the_advice():
    report = create_counts_report([{"simulator": s, "counts": {"0": 50, "1": 50}} for s in "ab"], n_shots=100)
    power = _pair(report, "a", "b")["metrics"]["statistical_test"]["power"]
    assert power["shots_per_backend_for_target_power"] == 1570
    assert power["recommended_shots_per_backend"] == 1800
    assert power["recommendation_margin"] == 1.1


def test_single_shared_outcome_is_degenerate_not_asymptotic():
    report = create_counts_report([{"simulator": s, "counts": {"00": 8200}} for s in "ab"], n_shots=8200)
    st = _pair(report, "a", "b")["metrics"]["statistical_test"]
    assert st["test_method"] == "degenerate"
    assert st["chi2"]["method"] == st["g_test"]["method"] == "degenerate"
    assert st["chi2"]["p_value"] == 1.0 and st["verdict"] == "consistent"


def test_statistical_table_has_method_untested_and_lower_bound_columns():
    report = create_counts_report([
        {"simulator": "a", "counts": {"00": 8200}},
        {"simulator": "b", "counts": {"00": 8200}},
        {"simulator": "c", "counts": {"00": 8199, "11": 1}},
    ], n_shots=8200)
    headers, rows, _title, caption = _tbl_statistical(report)
    for h in ("Lower bound", "Untested outcomes", "Method"):
        assert h in headers
    methods = {row[headers.index("Pair")]: row[headers.index("Method")] for row in rows}
    assert sorted(methods.values()) == ["degenerate", "exact_conditional", "exact_conditional"]
    assert "pooled into one bin. A non-significant" not in caption
    assert "degenerate" in caption and "Untested outcomes" in caption and "times 1.1" in caption
