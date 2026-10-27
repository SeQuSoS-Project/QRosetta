"""Verdict summary of a report: each pair's verdict, the per-backend counts and the outcome
counts with each outcome's role, computed with the rule the aggregator records in every new
report (``analysis.divergence.verdicts``), for a job's report, a saved run or a
client-supplied report."""

from services.analysis.divergence.common import ANALYSIS_VERSION
from services.analysis.divergence.verdicts import backend_verdicts, pair_verdict
from services.exporter import RUNNER_KEY_RE

OUTCOME_ROLES = {
    "differs": "difference",
    "differs_by_only": "difference",
    "inconclusive": "not_established",
    "not_comparable": "not_established",
    "unassessed": "not_established",
    "no_comparison": "not_established",
    "runs_without_output": "runs_without_output",
    "agrees": "agreement",
    "bit_order": "agreement",
}

_KEYS_PROBLEM = ("divergence_report.simulators and the simulators of each pair must be runner ids "
                 "or <id>~opt<L>~run<N>")


def _task_reports(results: dict) -> list:
    summary = results.get("benchmark_summary")
    return summary if isinstance(summary, list) else [results]


def _runner_keys(div: dict):
    """The runner keys the per-backend counts are keyed by, or None when one is not a list."""
    sims = div.get("simulators")
    if sims is not None and not isinstance(sims, list):
        return None
    keys = list(sims or [])
    for p in div.get("pairwise_agreement") or []:
        pair_sims = p.get("simulators")
        if isinstance(pair_sims, list) and len(pair_sims) == 2:
            keys += pair_sims
    return keys


def summary_problems(results) -> list:
    """Reasons the pair records of a report cannot be summarised; [] when they can. Every
    pair must be an object, and the backends the counts are keyed by must be runner keys."""
    if not isinstance(results, dict):
        return ["the report must be a JSON object"]
    for report in _task_reports(results):
        div = report.get("divergence_report") if isinstance(report, dict) else None
        if not isinstance(div, dict):
            continue
        pairs = div.get("pairwise_agreement")
        if pairs is not None and not (isinstance(pairs, list) and all(isinstance(p, dict) for p in pairs)):
            return ["divergence_report.pairwise_agreement must be a list of pair objects"]
        keys = _runner_keys(div)
        if keys is None or not all(isinstance(k, str) and RUNNER_KEY_RE.match(k) for k in keys):
            return [_KEYS_PROBLEM]
    return []


def outcome_catalog() -> dict:
    """The outcome names a summary counts, with each one's role, and the rule's version:
    GET /config summary_outcomes."""
    return {"analysis_version": ANALYSIS_VERSION, "roles": dict(OUTCOME_ROLES)}


def _outcomes(report: dict, verdicts: list, backends: dict) -> tuple:
    """(outcome counts, runs) of one circuit's report. Each pair counts under its verdict;
    no_comparison is 1 when no pair was compared; runs_without_output counts the runs whose
    status is not ok, plus 1 for a circuit that failed before any runner ran."""
    counts = dict.fromkeys(OUTCOME_ROLES, 0)
    for v in verdicts:
        if v["verdict"] in counts:
            counts[v["verdict"]] += 1
    compared = sum(1 for v in verdicts if v["verdict"] != "not_comparable")
    counts["no_comparison"] = 0 if compared else 1
    statuses = [b["status"] for b in backends.get("backends") or []]
    failed_task = bool(report.get("error")) and not report.get("raw_results")
    returned = sum(1 for s in statuses if s == "ok")
    counts["runs_without_output"] = len(statuses) - returned + (1 if failed_task else 0)
    return counts, {"total": len(statuses), "returned": returned,
                    "without_output": len(statuses) - returned, "circuit_failed": failed_task}


def task_summary(report) -> dict:
    """Verdicts of one circuit's report: the analysis version it records, each pair's verdict
    (in pairwise_agreement order, with its simulators), the per-backend counts, the outcome
    counts and the runs."""
    report = report if isinstance(report, dict) else {}
    div = report.get("divergence_report")
    div = div if isinstance(div, dict) else {}
    pairs = div.get("pairwise_agreement")
    recorded = div.get("analysis_version")
    verdicts = [{"simulators": p.get("simulators"), **pair_verdict(p)}
                for p in (pairs if isinstance(pairs, list) else [])]
    backends = backend_verdicts(report)
    outcomes, runs = _outcomes(report, verdicts, backends)
    return {
        "report_analysis_version": recorded if recorded is not None else report.get("analysis_version"),
        "pair_verdicts": verdicts,
        "backend_verdicts": backends,
        "outcomes": outcomes,
        "runs": runs,
    }


def _envelope(source: str, saved_from=None) -> dict:
    out = {"analysis_version": ANALYSIS_VERSION, "report_source": source,
           "outcome_roles": dict(OUTCOME_ROLES)}
    if source == "saved_run":
        out["saved_from"] = saved_from
    return out


def batch_summary(task_summaries: list, source: str, saved_from=None) -> dict:
    """The summary of a playlist report from its tasks' ``task_summary``; ``outcomes`` and
    ``runs`` are the sums over its tasks."""
    outcomes = dict.fromkeys(OUTCOME_ROLES, 0)
    runs = {"total": 0, "returned": 0, "without_output": 0, "circuits_failed": 0}
    for task in task_summaries:
        for name, n in (task.get("outcomes") or {}).items():
            outcomes[name] = outcomes.get(name, 0) + n
        task_runs = task.get("runs") or {}
        for key in ("total", "returned", "without_output"):
            runs[key] += task_runs.get(key, 0)
        runs["circuits_failed"] += 1 if task_runs.get("circuit_failed") else 0
    return {**_envelope(source, saved_from), "outcomes": outcomes, "runs": runs,
            "benchmark_summary": task_summaries}


def report_summary(results: dict, source: str, saved_from=None) -> dict:
    """The summary of a single-circuit or playlist report. ``analysis_version`` names the
    rule applied (this server's); ``report_analysis_version`` the analysis that produced the
    pair records. ``source`` is server_job, saved_run (with the run's ``saved_from``) or
    client_supplied."""
    if isinstance(results.get("benchmark_summary"), list):
        return batch_summary([task_summary(t) for t in results["benchmark_summary"]], source, saved_from)
    return {**_envelope(source, saved_from), **task_summary(results), "benchmark_summary": None}
