"""Compatibility wrapper for QRosetta analysis reports.

The maintained comparator implementation lives in services.analysis. This module
exists for older scripts or deployments that still import top-level comparator.
Keep this shim thin so local API and Rahti images use one implementation path.
"""

from services.analysis import (
    create_counts_report,
    create_divergence_report,
    create_performance_report,
    create_resource_report,
)

__all__ = [
    "create_divergence_report",
    "create_counts_report",
    "create_performance_report",
    "create_resource_report",
]
