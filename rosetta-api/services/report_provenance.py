"""Report fields about the run rather than the circuit: the images that ran (``specimens``),
timing caveats, and ``run_completeness`` (whether every planned circuit has a report).
None of them is part of the agreement analysis or its ANALYSIS_VERSION."""

from services import specimens, timing_caveats

COMPLETENESS = {
    "complete": "Every planned circuit of the job has a report.",
    "partial": ("The job stopped before every planned circuit had a report; only the circuits "
                "listed in this crate ran."),
    "failed": "The job finished as failed: {reason}",
    "not_recorded": ("The report predates the run_completeness field; whether every planned "
                     "circuit ran is not recorded."),
    "not_checked": ("This crate was built from a report supplied to the server (for example the "
                    "copy held in the browser, exported after the server's copy of the job had "
                    "expired). The server cannot tell whether the run it describes finished or "
                    "covers every planned circuit."),
}


def annotate(report: dict) -> None:
    """Add ``specimen``/``timing_caveats`` per result and ``specimens``, ``timing_caveats`` and
    ``timing_caveats_version`` to a single-circuit report."""
    specimens.annotate(report)
    timing_caveats.annotate(report)


def run_completeness(job_status: str, planned_tasks: int, recorded_tasks: int,
                     tasks_with_results: int, reason: str = None) -> dict:
    """The ``run_completeness`` record of a finished job."""
    record = {"job_status": job_status, "planned_tasks": planned_tasks,
              "recorded_tasks": recorded_tasks, "tasks_with_results": tasks_with_results,
              "stopped_early": recorded_tasks < planned_tasks}
    if reason:
        record["reason"] = reason
    return record


def completeness_statement(report: dict, trusted: bool) -> tuple:
    """``(value, description)`` for a crate: complete, partial, failed, not_recorded, or
    not_checked when the report is not the server's own."""
    record = report.get("run_completeness") if isinstance(report, dict) else None
    if not trusted:
        text = COMPLETENESS["not_checked"]
        if isinstance(record, dict):
            text += (f" The report states job_status {record.get('job_status')!r} with "
                     f"{record.get('recorded_tasks')} of {record.get('planned_tasks')} planned "
                     "circuits recorded, as supplied.")
        return "not_checked", text
    if not isinstance(record, dict):
        return "not_recorded", COMPLETENESS["not_recorded"]
    counts = (f" {record.get('recorded_tasks')} of {record.get('planned_tasks')} planned "
              f"circuit(s) have a report; {record.get('tasks_with_results')} of them have "
              "at least one backend result.")
    if record.get("stopped_early"):
        return "partial", COMPLETENESS["partial"] + counts
    if record.get("job_status") == "failed":
        reason = record.get("reason") or "no backend returned a result."
        return "failed", COMPLETENESS["failed"].format(reason=reason) + counts
    return "complete", COMPLETENESS["complete"] + counts


def specimens_of(reports: list) -> dict:
    """The ``specimens`` record over task reports, from each report's own record when it has
    one, else derived from its results."""
    return specimens.combine(
        r["specimens"] if isinstance(r.get("specimens"), dict)
        else specimens.summarize(specimens.report_entries(r)) for r in reports)


def timing_caveats_of(reports: list) -> tuple:
    """``(caveats, version, derived_at_export)`` over task reports: each report's stored list
    when it has one, else derived now from its recorded fields."""
    lists, versions, derived = [], set(), False
    for r in reports:
        if isinstance(r.get("timing_caveats"), list):
            lists.append(r["timing_caveats"])
            versions.add(str(r.get("timing_caveats_version") or "not recorded"))
        else:
            results = [x for x in r.get("raw_results") or [] if isinstance(x, dict)]
            lists.append(timing_caveats.summarize((str(x.get("simulator")), x) for x in results))
            versions.add(timing_caveats.TIMING_CAVEATS_VERSION)
            derived = True
    return timing_caveats.combine(lists), ", ".join(sorted(versions)), derived
