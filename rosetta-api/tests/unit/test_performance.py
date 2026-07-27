"""Unit tests for services/analysis/performance.py (T3.8 / FIX-033 resource ranking)."""

from services.analysis.performance import create_performance_report, create_resource_report


def test_performance_report_ranks_fastest_first_and_reports_cpu_gate_metrics():
    results = [
        {"simulator": "slow", "execution_time_sec": 2.0, "compilation_time_sec": 1.0,
         "simulation_time_sec": 1.0, "cpu_time_sec": 1.9, "gate_count": 10, "circuit_depth": 5},
        {"simulator": "fast", "execution_time_sec": 0.5, "compilation_time_sec": 0.2,
         "simulation_time_sec": 0.3, "cpu_time_sec": 0.4, "gate_count": 10, "circuit_depth": 5},
        {"simulator": "broken", "error": "boom"},
    ]
    report = create_performance_report(results)
    ranking = report["ranking"]
    assert [r["simulator"] for r in ranking] == ["fast", "slow", "broken"]
    assert ranking[0]["cpu_time_sec"] == 0.4
    assert ranking[0]["gate_count"] == 10
    assert ranking[0]["circuit_depth"] == 5
    assert ranking[2]["status"] == "error" and ranking[2]["execution_time_sec"] is None


def test_resource_report_ranks_by_process_peak_rss_not_delta():
    # 'inflated_delta' has the SMALLER memory_usage_mb delta (the old, biased metric)
    # but the LARGER true process_peak_rss_mb (the new, kernel-authoritative metric).
    # Ranking must follow process_peak_rss_mb, not memory_usage_mb.
    results = [
        {"simulator": "inflated_delta", "memory_usage_mb": 1.0, "process_peak_mb": 50.0,
         "process_peak_rss_mb": 500.0},
        {"simulator": "honest", "memory_usage_mb": 20.0, "process_peak_mb": 80.0,
         "process_peak_rss_mb": 100.0},
        {"simulator": "broken", "error": "boom"},
    ]
    report = create_resource_report(results)
    ranking = report["ranking"]
    assert [r["simulator"] for r in ranking] == ["honest", "inflated_delta", "broken"]
    assert "process peak" in report["summary"].lower()


def test_resource_report_error_entries_carry_process_peak_rss_if_present():
    results = [{"simulator": "crashed", "error": "OOM", "process_peak_rss_mb": 512.0}]
    ranking = create_resource_report(results)["ranking"]
    assert ranking[0]["status"] == "error"
    assert ranking[0]["process_peak_rss_mb"] == 512.0
