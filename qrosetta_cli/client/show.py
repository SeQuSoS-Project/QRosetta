"""`qrosetta show summary` (spec §6.20): the server's summary of a result, from the saved
summary.json, else GET /jobs/{id}/summary, else POST /summary with the saved report.json sent
unchanged. Every job starts with its save status and the summary's source; a self-test
directory starts with selftest.json."""

import os

from qrosetta_cli import output
from qrosetta_cli.client import results, run
from qrosetta_cli.client.conn import Conn, http_error
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage

SOURCE_TEXT = {"server_job": "server job", "saved_run": "saved run", "client_supplied": "client-supplied report"}


def _conn(ctx, cache):
    if "conn" not in cache:
        cache["conn"] = Conn(ctx)
    return cache["conn"]


def summary_for(ctx, job, cache):
    """(summary, where it came from) for one JobRef."""
    if job.dir:
        saved = results.read_json(os.path.join(job.dir, "summary.json"))
        if isinstance(saved, dict):
            return saved, "saved summary.json"
    try:
        conn = _conn(ctx, cache)
        return conn.get(f"/jobs/{job.job_id}/summary", what=f"summary of job {job.job_id[:8]}"), "the server's job"
    except CliError as exc:
        if exc.code != Exit.NOT_FOUND or not job.dir:
            raise
    report = os.path.join(job.dir, "report.json")
    if not os.path.isfile(report):
        raise CliError(
            f"Job {job.job_id[:8]} has expired on the server and no report.json or summary.json is saved.",
            Exit.NOT_FOUND,
            "result_missing",
            hint="qrosetta jobs",
        )
    conn = _conn(ctx, cache)
    limit = conn.limit("max_request_bytes")
    size = os.path.getsize(report) + len('{"results":}')
    if limit and size > limit:
        raise CliError(
            f"{report} is {size} bytes; POST /summary accepts {limit}.",
            Exit.REFUSED,
            "request_too_large",
            hint="save the summary while the job lives (`qrosetta run` saves it by default)",
        )
    with open(report, "rb") as fh:
        body = b'{"results":' + fh.read() + b"}"
    resp = conn.transport.request("POST", "/summary", body=body, headers={"Content-Type": "application/json"})
    if resp.status != 200:
        raise http_error("POST", "/summary", resp)
    return resp.json(), "POST /summary of the saved report.json"


def _job_lines(summary, task=None):
    lines = []
    tasks = summary.get("benchmark_summary")
    if isinstance(tasks, list) and task is not None:
        if not 0 <= task < len(tasks):
            raise usage(
                f"--task {task}: this playlist has {len(tasks)} circuits (0-{len(tasks) - 1}).",
                hint="qrosetta show summary",
                reason="bad_task",
            )
        return _job_lines(
            {
                **tasks[task],
                "analysis_version": summary.get("analysis_version"),
                "outcome_roles": summary.get("outcome_roles"),
            }
        )
    line = run.pairs_line(summary)
    if line:
        lines.append(line)
    runs = summary.get("runs") or {}
    if runs.get("total"):
        lines.append(
            f"Runs: {runs.get('returned', 0)} of {runs['total']} returned"
            + (f"; {runs['circuits_failed']} circuits failed" if runs.get("circuits_failed") else "")
            + "."
        )
    if isinstance(tasks, list):
        for i, t in enumerate(tasks):
            pl = run.pairs_line({**t, "outcome_roles": summary.get("outcome_roles")}) or "no pairs"
            lines.append(f"  circuit {i}: {pl}")
        return lines
    backends = (summary.get("backend_verdicts") or {}).get("backends") or []
    model = (summary.get("backend_verdicts") or {}).get("headline_model") or {}
    flagged = model.get("flagged") or []
    if model.get("kind") and model.get("kind") != "none":
        lines.append(f"Headline ({model['kind']}): differs: {', '.join(flagged) if flagged else 'see the pairs'}.")
    elif model.get("kind") == "none":
        lines.append("Headline: no pair differs.")
    if backends:
        width = max(len("BACKEND"), *(len(b.get("key", "")) for b in backends))
        lines.append(f"{'BACKEND':<{width}}  STATUS   COMPARED  DIFFERS  INCONCLUSIVE  NOT COMPARABLE")
        for b in backends:
            lines.append(
                f"{b.get('key', ''):<{width}}  {b.get('status', ''):<7}  {b.get('compared', 0):>8}  "
                f"{b.get('differs', 0):>7}  {b.get('inconclusive', 0):>12}  {b.get('not_comparable', 0):>14}"
            )
    caveats = run.caveats_line(summary)
    if caveats:
        lines.append(caveats)
    for block in ("known_answer", "environment_checks"):
        rows = summary.get(block)
        if rows:
            lines.append(f"{block.replace('_', ' ').capitalize()}:")
            for r in rows if isinstance(rows, list) else [rows]:
                if isinstance(r, dict):
                    where = ", ".join(str(r[k]) for k in ("backend", "circuit") if r.get(k))
                    r = f"{r.get('status', '')} {r.get('check', '')}{f' ({where})' if where else ''}: {r.get('reason', '')}"
                lines.append(f"  {r}")
    return lines


def _selftest_lines(doc):
    lines = [f"Self-test: {doc.get('status', '?')}"]
    for row in doc.get("lines") or []:
        lines.append(f"  {row}")
    return lines


def cmd_show_summary(ctx):
    args = ctx.args
    cache: dict = {}
    server_url = None
    if (args.result or "").startswith("job:"):
        server_url = _conn(ctx, cache).url
    target = results.resolve(ctx, args.result, server_url)
    jobs = target.jobs
    if args.job:
        jobs = [
            j
            for j in jobs
            if (j.mode() or "compile") == args.job
            or (j.kind() == "experiment" and args.job == f"experiment-{j.mode()}")
        ]
        if not jobs:
            raise CliError(
                f"No {args.job} job in this result.", Exit.NOT_FOUND, "result_missing", hint="qrosetta show summary"
            )
    data = {"result": target.invocation, "jobs": []}
    if target.invocation:
        selftest = results.read_json(os.path.join(target.invocation, results.SELFTEST_FILE))
        if isinstance(selftest, dict):
            for line in _selftest_lines(selftest):
                output.result(line)
            data["selftest"] = selftest
    for job in jobs:
        status = results.read_status(job.dir) if job.dir else None
        req = job.request()
        if job.kind() == "experiment":
            output.result(
                f"{req.get('title') or job.job_id}: experiment; its results are in bundle.zip "
                "(`show experiment` arrives with the experimental views)."
            )
            data["jobs"].append({"job_id": job.job_id, "dir": job.dir, "save_status": status, "summary": None})
            continue
        summary, where = summary_for(ctx, job, cache)
        source = SOURCE_TEXT.get(summary.get("report_source"), summary.get("report_source") or "unknown source")
        output.result(
            f"{req.get('title') or 'Job'} (job {job.job_id[:8]}): saved {status or 'not saved'}; "
            f"{source}, read from {where}; rule {summary.get('analysis_version')}"
        )
        for line in _job_lines(summary, args.task):
            output.result(line)
        data["jobs"].append(
            {"job_id": job.job_id, "dir": job.dir, "save_status": status, "source": where, "summary": summary}
        )
    return Result(0, data)
