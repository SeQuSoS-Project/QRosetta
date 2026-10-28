"""Shape checks for reports a client submits (export, history, publication rendering)."""

import math
import sys

from fastapi import HTTPException

from config import settings
from schemas.benchmark import has_control_characters
from services.export_compiled import compiler_keys
from services.exporter import RUNNER_KEY_RE, invalid_runner_keys


MAX_REPORT_DEPTH = 64

REPORT_SHAPE_ERRORS = (TypeError, ValueError, AttributeError, IndexError, KeyError)
"""What reading a report raises when a field holds a value of the wrong type or shape."""


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


_LARGEST_FLOAT_INT = int(sys.float_info.max)


def _non_finite_path(value):
    """``(location, problem)`` of the first NaN or infinite number in ``value``, or of an
    integer beyond the double-precision range, which no conversion to float survives
    (``"a.b[2]"``), else None. JSON has no NaN or Infinity, but Python's parser reads them, and
    it reads integers of any length."""
    stack = [(value, "")]
    while stack:
        node, path = stack.pop()
        if isinstance(node, float) and not math.isfinite(node):
            return path or "(top level)", "is NaN or infinite"
        if isinstance(node, int) and not isinstance(node, bool) and abs(node) > _LARGEST_FLOAT_INT:
            return path or "(top level)", "is an integer beyond the double-precision range"
        if isinstance(node, dict):
            stack.extend((child, f"{path}.{key}" if path else str(key)) for key, child in node.items())
        elif isinstance(node, list):
            stack.extend((child, f"{path}[{index}]") for index, child in enumerate(node))
    return None


_PAIR_LISTS = ("pairwise_agreement", "divergences_found")
_BACKEND_MAPS = ("simulators", "ordering_map")


def report_caps() -> dict:
    """Size caps on a client-supplied report, published in GET /config ``limits``: playlist
    circuits, runner results (and compiled circuits, and backends in a divergence report)
    per circuit, and pairwise comparisons per circuit. No server job produces more."""
    keys = settings.MAX_TOTAL_RUNS
    return {"max_report_tasks": settings.MAX_REPORT_TASKS, "max_report_runner_keys": keys,
            "max_report_pairs": keys * (keys - 1) // 2}


def _size_problems(reports: list) -> list:
    caps = report_caps()
    if len(reports) > caps["max_report_tasks"]:
        return [f"benchmark_summary holds {len(reports)} circuits; at most "
                f"{caps['max_report_tasks']} are accepted"]
    keys, pairs = caps["max_report_runner_keys"], caps["max_report_pairs"]
    for report in reports:
        for field in ("raw_results", "compiled_circuits"):
            value = report.get(field)
            if isinstance(value, list) and len(value) > keys:
                return [f"{field} holds {len(value)} entries; at most {keys} per circuit are accepted"]
        for section in ("performance_report", "resource_report"):
            rows = report.get(section).get("ranking") if isinstance(report.get(section), dict) else None
            if isinstance(rows, (list, dict)) and len(rows) > keys:
                return [f"{section}.ranking holds {len(rows)} entries; at most {keys} per circuit "
                        f"are accepted"]
        divergence = report.get("divergence_report")
        if not isinstance(divergence, dict):
            continue
        for field, value in divergence.items():
            if isinstance(value, dict) and field in _BACKEND_MAPS and len(value) > keys:
                return [f"divergence_report.{field} holds more than {keys} entries; at most "
                        f"{keys} backends and {pairs} pairs per circuit are accepted"]
            if not isinstance(value, list):
                continue
            matrix = bool(value) and all(isinstance(row, list) for row in value)
            if field in _PAIR_LISTS:
                limit = pairs
            elif field == "simulators" or matrix:
                limit = keys
            else:
                continue
            if len(value) > limit or (matrix and any(len(row) > keys for row in value)):
                return [f"divergence_report.{field} holds more than {limit} entries; at most "
                        f"{keys} backends and {pairs} pairs per circuit are accepted"]
    return []


MAX_RUNNER_KEY_LENGTH = 64


def _backend_keys(report: dict):
    """(field, value) for every place a report names a backend: raw_results, the divergence
    report's simulators, pairs and ordering map, and the performance and resource rankings."""
    raw = report.get("raw_results")
    for r in raw if isinstance(raw, list) else []:
        if isinstance(r, dict) and "simulator" in r:
            yield "raw_results[].simulator", r["simulator"]
    divergence = report.get("divergence_report")
    if isinstance(divergence, dict):
        sims = divergence.get("simulators")
        if sims is not None and not isinstance(sims, list):
            yield "divergence_report.simulators", sims
        for sim in sims if isinstance(sims, list) else []:
            yield "divergence_report.simulators", sim
        if isinstance(divergence.get("ordering_map"), dict):
            for sim in divergence["ordering_map"]:
                yield "divergence_report.ordering_map", sim
        pairs = divergence.get("pairwise_agreement")
        for pair in pairs if isinstance(pairs, list) else []:
            if isinstance(pair, dict) and isinstance(pair.get("simulators"), list):
                for sim in pair["simulators"]:
                    yield "divergence_report.pairwise_agreement[].simulators", sim
    for section in ("performance_report", "resource_report"):
        rows = report.get(section).get("ranking") if isinstance(report.get(section), dict) else None
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and "simulator" in row:
                yield f"{section}.ranking[].simulator", row["simulator"]


def _backend_key_problems(reports: list) -> list:
    """A backend named by anything but a runner key of at most MAX_RUNNER_KEY_LENGTH
    characters; figures draw these as axis labels."""
    for report in reports:
        for field, value in _backend_keys(report):
            if (not isinstance(value, str) or len(value) > MAX_RUNNER_KEY_LENGTH
                    or not RUNNER_KEY_RE.match(value)):
                shown = repr(value)[:40]
                return [f"{field} holds {shown}; backends are named by runner ids or "
                        f"<id>~opt<L>~run<N> of at most {MAX_RUNNER_KEY_LENGTH} characters"]
    return []


MAX_CODE_LENGTH = 64
_PAIR_CODES = ("agreement", "measured_assessment", "marginal_assessment", "registered_transform",
               "pair_verdict", "mode")


def _code_problems(reports: list) -> list:
    """A pair's agreement label or verdict code, or a verdict-count key, longer than
    MAX_CODE_LENGTH characters; figures draw these as axis labels."""
    for report in reports:
        divergence = report.get("divergence_report")
        if not isinstance(divergence, dict):
            continue
        pairs = divergence.get("pairwise_agreement")
        values = [(f"divergence_report.pairwise_agreement[].{field}", pair.get(field))
                  for pair in (pairs if isinstance(pairs, list) else []) if isinstance(pair, dict)
                  for field in _PAIR_CODES]
        summary = divergence.get("statistical_test_summary")
        counts = summary.get("verdict_counts") if isinstance(summary, dict) else None
        values += [("divergence_report.statistical_test_summary.verdict_counts", key)
                   for key in (counts if isinstance(counts, dict) else {})]
        for field, value in values:
            if isinstance(value, str) and len(value) > MAX_CODE_LENGTH:
                return [f"{field} holds a label of {len(value)} characters; labels and codes "
                        f"have at most {MAX_CODE_LENGTH}"]
    return []


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
    size = _size_problems(reports) or _backend_key_problems(reports) or _code_problems(reports)
    if size:
        return size
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
    else:
        found = _non_finite_path(results)
        if found is not None:
            problems.append(f"{found[0]} {found[1]}; a report holds finite numbers or null")
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


def unreadable_report(exc: Exception) -> HTTPException:
    """400 for a client-supplied report that a table, figure or crate builder could not read
    (one of ``REPORT_SHAPE_ERRORS``); the server's own reports keep their 500."""
    return HTTPException(status_code=400, detail=(
        "Invalid report: a field holds a value of the wrong type or shape, so it cannot be read."))
