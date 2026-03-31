import asyncio
import gc
import analysis as comparator
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-aggregator")

async def compile_comparison_reports(aggregated_results: list):
    """
    Takes aggregated statevector execution results, parses them, and fires off
    the heavy comparison logic in a thread pool.
    """
    loop = asyncio.get_event_loop()

    gc.collect() # Clean up before heavy reporting
    logger.info("Generating divergence report...")
    divergence_report_task = loop.run_in_executor(
        None, comparator.create_divergence_report, aggregated_results
    )
    
    logger.info("Generating performance report...")
    performance_report_task = loop.run_in_executor(
        None, comparator.create_performance_report, aggregated_results
    )

    logger.info("Generating resource report...")
    resource_report_task = loop.run_in_executor(
        None, comparator.create_resource_report, aggregated_results
    )

    divergence_report, performance_report, resource_report = await asyncio.gather(
        divergence_report_task, performance_report_task, resource_report_task
    )
    
    return divergence_report, performance_report, resource_report


async def compile_measurement_reports(aggregated_results: list, n_shots: int):
    """
    Takes aggregated measurement execution results, parses them, and fires off
    the heavy counts comparison logic in a thread pool.
    """
    loop = asyncio.get_event_loop()
    
    gc.collect() # Clean up before heavy reporting
    logger.info("Generating counts divergence report...")
    divergence_report_task = loop.run_in_executor(
        None, comparator.create_counts_report, aggregated_results, n_shots
    )
    
    logger.info("Generating performance report...")
    performance_report_task = loop.run_in_executor(
        None, comparator.create_performance_report, aggregated_results
    )
    
    logger.info("Generating resource report...")
    resource_report_task = loop.run_in_executor(
        None, comparator.create_resource_report, aggregated_results
    )

    divergence_report, performance_report, resource_report = await asyncio.gather(
        divergence_report_task, performance_report_task, resource_report_task
    )
    
    return divergence_report, performance_report, resource_report
