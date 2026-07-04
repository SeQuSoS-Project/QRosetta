# Regression tests for the comparator compatibility wrapper.

import comparator
import services.analysis as analysis


def test_top_level_comparator_reexports_active_analysis_functions():
    assert comparator.create_divergence_report is analysis.create_divergence_report
    assert comparator.create_counts_report is analysis.create_counts_report
    assert comparator.create_performance_report is analysis.create_performance_report
    assert comparator.create_resource_report is analysis.create_resource_report


def test_top_level_counts_report_uses_maintained_implementation():
    results = [
        {
            "simulator": "a",
            "counts": {"0": 10},
            "qubit_ordering": "lsb",
        },
        {
            "simulator": "b",
            "counts": {"0": 10},
            "qubit_ordering": "lsb",
        },
    ]

    report = comparator.create_counts_report(results, n_shots=10)

    assert "hellinger_distance_matrix" in report
    assert report["ordering_map"] == {"a": "lsb", "b": "lsb"}
