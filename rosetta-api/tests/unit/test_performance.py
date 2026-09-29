"""Tests for services/analysis/performance.py rankings."""

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
    assert [r["simulator"] for r in ranking] == ["fast", "slow"]
    assert [r["rank"] for r in ranking] == [1, 2]
    assert ranking[0]["cpu_time_sec"] == 0.4
    assert ranking[0]["gate_count"] == 10
    assert ranking[0]["circuit_depth"] == 5
    assert report["unranked"][0]["simulator"] == "broken"
    assert report["unranked"][0]["status"] == "error"
    assert report["unranked"][0]["rank"] is None
    assert report["ranking_metric"] == "execution_time_sec"


def test_performance_report_keeps_results_without_timing_as_errored():
    report = create_performance_report([
        {"simulator": "ok", "execution_time_sec": 1.0},
        {"simulator": "silent"},
        {"simulator": "none_time", "execution_time_sec": None},
    ])
    assert [r["simulator"] for r in report["ranking"]] == ["ok"]
    unranked = {r["simulator"]: r for r in report["unranked"]}
    assert set(unranked) == {"silent", "none_time"}
    assert all(r["status"] == "error" and r["reason"] == "missing_timing" for r in unranked.values())


def test_performance_report_has_no_winner_when_nothing_succeeded():
    report = create_performance_report([
        {"simulator": "a", "error": "boom", "execution_time_sec": 0.01},
        {"simulator": "b"},
    ])
    assert report["ranking"] == []
    assert len(report["unranked"]) == 2


def test_errored_run_with_fast_time_never_ranks():
    report = create_performance_report([
        {"simulator": "slow_ok", "execution_time_sec": 9.0},
        {"simulator": "fast_err", "error": "boom", "execution_time_sec": 0.001},
    ])
    assert report["ranking"][0]["simulator"] == "slow_ok"
    assert "fast_err" not in [r["simulator"] for r in report["ranking"]]


def test_resource_report_ranks_by_process_peak_rss_not_delta():
    results = [
        {"simulator": "inflated_delta", "memory_usage_mb": 1.0, "process_peak_mb": 50.0,
         "process_peak_rss_mb": 500.0},
        {"simulator": "small_peak", "memory_usage_mb": 20.0, "process_peak_mb": 80.0,
         "process_peak_rss_mb": 100.0},
        {"simulator": "broken", "error": "boom"},
    ]
    report = create_resource_report(results)
    assert [r["simulator"] for r in report["ranking"]] == ["small_peak", "inflated_delta"]
    assert [r["simulator"] for r in report["unranked"]] == ["broken"]
    assert report["ranking_metric"] == "process_peak_rss_mb"
    assert "process peak" in report["summary"].lower()


def test_resource_report_errored_run_with_small_peak_never_ranks():
    report = create_resource_report([
        {"simulator": "crashed", "error": "OOM", "process_peak_rss_mb": 1.0},
        {"simulator": "ok", "process_peak_rss_mb": 512.0},
    ])
    assert [r["simulator"] for r in report["ranking"]] == ["ok"]
    crashed = report["unranked"][0]
    assert crashed["status"] == "error"
    assert crashed["process_peak_rss_mb"] == 1.0


def test_resource_report_has_no_winner_when_nothing_succeeded():
    report = create_resource_report([{"simulator": "crashed", "error": "OOM", "process_peak_rss_mb": 512.0}])
    assert report["ranking"] == []


def test_resource_report_success_without_peak_is_unranked():
    report = create_resource_report([
        {"simulator": "no_peak", "memory_usage_mb": 1.0},
        {"simulator": "ok", "process_peak_rss_mb": 50.0},
    ])
    assert [r["simulator"] for r in report["ranking"]] == ["ok"]
    assert report["unranked"][0]["reason"] == "missing_process_peak_rss"
