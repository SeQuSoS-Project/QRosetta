"""Shape checks for reports a client submits (export, history, publication rendering)."""

from fastapi import HTTPException

from schemas.benchmark import has_control_characters
from services.exporter import invalid_runner_keys


def report_problems(results) -> list:
    """Reasons a client-supplied report cannot be used; [] when it is usable."""
    if not isinstance(results, dict):
        return ["the report must be a JSON object"]
    problems = []
    reports = [results]
    summary = results.get("benchmark_summary")
    if summary is not None:
        if not isinstance(summary, list) or not all(isinstance(t, dict) for t in summary):
            return ["benchmark_summary must be a list of task reports"]
        reports = summary
    for report in reports:
        raw = report.get("raw_results")
        if raw is not None and (not isinstance(raw, list)
                                or not all(isinstance(r, dict) for r in raw)):
            problems.append("raw_results must be a list of result objects")
            break
    name = results.get("run_name")
    if name is not None and (not isinstance(name, str) or len(name) > 200
                             or has_control_characters(name)):
        problems.append("run_name must be text of at most 200 characters without control "
                        "characters or line separators")
    if not problems:
        bad = invalid_runner_keys(results)
        if bad:
            problems.append("simulator keys must be runner ids or <id>~opt<L>~run<N>; got "
                            + ", ".join(repr(k) for k in bad[:5]))
    return problems


def reject_invalid_report(results) -> None:
    """400 naming what is wrong with a client-supplied report."""
    problems = report_problems(results)
    if problems:
        raise HTTPException(status_code=400, detail="Invalid report: " + "; ".join(problems) + ".")
