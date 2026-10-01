"""Shape checks for reports a client submits (export, history, publication rendering)."""

from fastapi import HTTPException

from schemas.benchmark import has_control_characters
from services.export_compiled import compiler_keys
from services.exporter import invalid_runner_keys


MAX_REPORT_DEPTH = 64


def _depth(value, limit=MAX_REPORT_DEPTH + 1) -> int:
    """Nesting depth of lists and dicts in ``value``, counted iteratively up to ``limit``."""
    deepest, stack = 0, [(value, 1)]
    while stack:
        node, level = stack.pop()
        if isinstance(node, (dict, list)):
            deepest = max(deepest, level)
            if deepest >= limit:
                return deepest
            children = node.values() if isinstance(node, dict) else node
            stack.extend((child, level + 1) for child in children)
    return deepest


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
                        "characters, invisible formatting characters or line separators")
    for report in reports:
        task_name = report.get("task_name")
        if task_name is not None and (not isinstance(task_name, str) or len(task_name) > 200
                                      or has_control_characters(task_name)):
            problems.append("task_name must be text of at most 200 characters without control "
                            "characters, invisible formatting characters or line separators")
            break
    depth = _depth(results)
    if depth > MAX_REPORT_DEPTH:
        problems.append(f"the report nests {depth} levels deep; at most {MAX_REPORT_DEPTH} are accepted")
    for report in reports:
        keys = compiler_keys(report) if isinstance(report, dict) else []
        if "" in keys:
            problems.append("every compiled_circuits record needs a compiler key")
            break
        repeated = sorted({k for k in keys if keys.count(k) > 1})
        if repeated:
            problems.append("compiled_circuits repeats compiler key(s) " + ", ".join(repr(k) for k in repeated[:5]))
            break
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
