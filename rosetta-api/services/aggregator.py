"""Builds the divergence, performance and resource reports from aggregated runner results.

Agreement analysis is pairwise; no fleet-wide consensus is computed. Every divergence report
records each pair's verdict and the per-backend counts (``analysis.divergence.verdicts``)."""

import asyncio
import services.analysis as comparator
from services.analysis.divergence.verdicts import annotate_divergence_report
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-aggregator")


def _with_verdicts(build, aggregated_results: list, n_shots, *args) -> dict:
    """``build(aggregated_results, *args)`` with the pair verdicts and per-backend counts
    recorded on it."""
    report = build(aggregated_results, *args)
    annotate_divergence_report(report, aggregated_results, n_shots)
    return report


async def _compile_reports(divergence_task_factory, aggregated_results: list):
    """Run the divergence, performance and resource builders concurrently in the thread pool.

    ``divergence_task_factory(loop)`` schedules the mode-specific divergence builder.
    """
    loop = asyncio.get_event_loop()

    divergence_report_task = divergence_task_factory(loop)
    performance_report_task = loop.run_in_executor(
        None, comparator.create_performance_report, aggregated_results
    )
    resource_report_task = loop.run_in_executor(
        None, comparator.create_resource_report, aggregated_results
    )

    return await asyncio.gather(
        divergence_report_task, performance_report_task, resource_report_task
    )


async def compile_comparison_reports(aggregated_results: list, thresholds: dict = None):
    """Compile the statevector divergence, performance and resource reports.

    ``thresholds`` overrides the agreement tolerances; None keeps the defaults.
    """
    logger.info("Generating divergence report...")
    return await _compile_reports(
        lambda loop: loop.run_in_executor(
            None, _with_verdicts, comparator.create_divergence_report, aggregated_results, None,
            thresholds
        ),
        aggregated_results,
    )


async def compile_measurement_reports(aggregated_results: list, n_shots: int, thresholds: dict = None):
    """Compile the counts divergence, performance and resource reports.

    ``thresholds`` overrides the descriptive JS/Hellinger cut-offs; None keeps the defaults.
    """
    logger.info("Generating counts divergence report...")
    return await _compile_reports(
        lambda loop: loop.run_in_executor(
            None, _with_verdicts, comparator.create_counts_report, aggregated_results, n_shots,
            n_shots, thresholds
        ),
        aggregated_results,
    )
