import pytest
import asyncio
from unittest.mock import patch, MagicMock
from services.aggregator import compile_comparison_reports, compile_measurement_reports

@pytest.fixture
def mock_results():
    return [{"runner": "qiskit", "statevector": [1, 0, 0, 0]},
            {"runner": "cirq", "statevector": [1, 0, 0, 0]}]

@pytest.mark.asyncio
@patch("services.aggregator.comparator")
async def test_compile_comparison_reports(mock_comparator, mock_results):
    # Setup mock returns
    mock_comparator.create_divergence_report.return_value = {"divergence": 0.0}
    mock_comparator.create_performance_report.return_value = {"performance": 1.0}
    mock_comparator.create_resource_report.return_value = {"resources": 100}

    div, perf, res = await compile_comparison_reports(mock_results)

    # Asserts
    assert div == {"divergence": 0.0}
    assert perf == {"performance": 1.0}
    assert res == {"resources": 100}
    
    # Check that the underlying logic was called
    mock_comparator.create_divergence_report.assert_called_once_with(mock_results)
    mock_comparator.create_performance_report.assert_called_once_with(mock_results)
    mock_comparator.create_resource_report.assert_called_once_with(mock_results)

@pytest.mark.asyncio
@patch("services.aggregator.comparator")
async def test_compile_measurement_reports(mock_comparator, mock_results):
    # Setup mock returns
    mock_comparator.create_counts_report.return_value = {"counts_div": 0.0}
    mock_comparator.create_performance_report.return_value = {"performance": 2.0}
    mock_comparator.create_resource_report.return_value = {"resources": 200}

    div, perf, res = await compile_measurement_reports(mock_results, n_shots=1000)

    # Asserts
    assert div == {"counts_div": 0.0}
    assert perf == {"performance": 2.0}
    assert res == {"resources": 200}
    
    # Check that counts_report was called with n_shots
    mock_comparator.create_counts_report.assert_called_once_with(mock_results, 1000)
    mock_comparator.create_performance_report.assert_called_once_with(mock_results)
    mock_comparator.create_resource_report.assert_called_once_with(mock_results)
