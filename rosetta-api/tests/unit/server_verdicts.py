"""Synthetic reports and pairs with the verdicts the server records, for tests that render
them in Node (the page reads verdicts; it does not compute them)."""
import copy

from services.analysis.divergence.verdicts import annotate_divergence_report, pair_verdict


def with_server_verdicts(report: dict) -> dict:
    """A copy of a single-circuit or playlist report with pair_verdict on every pair and
    backend_verdicts on every divergence report, as the aggregator records them."""
    out = copy.deepcopy(report)
    tasks = out["benchmark_summary"] if isinstance(out.get("benchmark_summary"), list) else [out]
    for task in tasks:
        div = task.get("divergence_report") if isinstance(task, dict) else None
        if isinstance(div, dict):
            annotate_divergence_report(div, task.get("raw_results"), task.get("n_shots"))
    return out


def with_pair_verdict(pair: dict) -> dict:
    """A copy of a pair record with its pair_verdict."""
    return {**copy.deepcopy(pair), "pair_verdict": pair_verdict(pair)}
