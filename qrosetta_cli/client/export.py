"""`qrosetta export crate` and `qrosetta export report` (spec §6.21): files only. A crate comes
from the job's server copy (POST /jobs/{id}/export), else from the saved report.json sent
unchanged (POST /export, which records report_source client_supplied and needs
--allow-supplied); a report from GET /jobs/{id}/report, else the saved copy."""

import json
import os
import shutil
import sys

from qrosetta_cli import output
from qrosetta_cli.client import results, save
from qrosetta_cli.client.conn import Conn, http_error
from qrosetta_cli.client.run import confirm_large
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage


def _one_job(ctx, conn):
    target = results.resolve(ctx, ctx.args.result, conn.url if (ctx.args.result or "").startswith("job:") else None)
    jobs = target.jobs
    if ctx.opt("job"):
        jobs = [j for j in jobs if (j.mode() or "compile") == ctx.args.job]
    if len(jobs) != 1:
        modes = ", ".join(j.mode() or "compile" for j in target.jobs) or "none"
        raise usage(f"This result holds {len(target.jobs)} jobs ({modes}); choose one with --job MODE.",
                    hint="qrosetta export crate --job statevector", reason="several_jobs")
    return jobs[0]


def _destination(ctx, job, default_name):
    out = ctx.args.output
    if out == "-":
        return "-"
    if out:
        return os.path.abspath(out)
    if not job.dir:
        return os.path.abspath(default_name)
    return os.path.join(job.dir, default_name)


def _to_stdout(path):
    out = getattr(sys.stdout, "buffer", None)
    with open(path, "rb") as fh:
        if out is None:
            sys.stdout.write(fh.read().decode("utf-8", "replace"))
        else:
            shutil.copyfileobj(fh, out)
    sys.stdout.flush()


def _deliver(ctx, tmp, dest):
    if dest == "-":
        try:
            _to_stdout(tmp)
        finally:
            os.unlink(tmp)
        return None
    os.replace(tmp, dest)
    output.progress(f"Wrote {os.path.getsize(dest)} bytes to {dest}")
    output.result(dest)
    return dest


def _tmp_for(dest, job):
    base = job.dir if dest == "-" and job.dir else (os.path.dirname(dest) if dest != "-" else os.getcwd())
    return os.path.join(base, f".qrosetta-export-{os.getpid()}")


def _note_concurrency(conn, job, kind):
    if not job.dir or conn.dispatches_in_flight(conn.refresh_config()) == 0:
        return
    record = results.read_json(os.path.join(job.dir, "job.json")) or {}
    record["concurrent_with_other_jobs"] = True
    record.setdefault("exports", []).append({"kind": kind, "at": output.utc_now(), "concurrent_with_other_jobs": True})
    results.write_json(os.path.join(job.dir, "job.json"), record)


def cmd_export_crate(ctx):
    args = ctx.args
    conn = Conn(ctx)
    job = _one_job(ctx, conn)
    body = save.crate_options(args)
    dest = _destination(ctx, job, "ro-crate.zip")
    tmp = _tmp_for(dest, job)
    source = "server_job"
    try:
        _note_concurrency(conn, job, "crate")
        conn.download("POST", f"/jobs/{job.job_id}/export", tmp, body, confirm_large=confirm_large(ctx))
    except CliError as exc:
        if exc.code != Exit.NOT_FOUND:
            raise
        report = os.path.join(job.dir, "report.json") if job.dir else None
        if not report or not os.path.isfile(report):
            raise CliError(f"Job {job.job_id[:8]} has expired on the server and no report.json is saved.",
                           Exit.NOT_FOUND, "result_missing", hint="qrosetta jobs") from None
        if not args.allow_supplied:
            if not ctx.tty:
                raise usage("The job has expired on the server; a crate from the saved report.json records "
                            "report_source client_supplied.", hint="qrosetta export crate --allow-supplied",
                            reason="supplied_needs_consent") from None
            answer = output.prompt("The job has expired; build a crate from the saved report.json (recorded as "
                                   "client_supplied)? [y/N] ", stdin=ctx.stdin)
            if not answer or answer.strip().lower() not in ("y", "yes"):
                raise usage("No crate built.", hint="qrosetta export crate --allow-supplied",
                            reason="supplied_declined") from None
        with open(report, "rb") as fh:
            text = fh.read()
        options = json.dumps(body, ensure_ascii=False).encode("utf-8")[1:-1]
        payload = b'{"results":' + text + (b"," + options if options else b"") + b"}"
        limit = conn.limit("max_request_bytes")
        if limit and len(payload) > limit:
            raise CliError(f"{report} is too large to send ({len(payload)} bytes; the server accepts {limit}).",
                           Exit.REFUSED, "request_too_large",
                           hint="make the crate while the job lives (`run --crate`) or save the run to history") from None
        if not args.output and job.dir:
            dest = os.path.join(job.dir, "ro-crate.client-supplied.zip")
            tmp = _tmp_for(dest, job)
        source = "client_supplied"
        with open(tmp, "wb") as out:
            resp = conn.transport.download("POST", "/export", out, body=payload,
                                           headers={"Content-Type": "application/json"})
        if not 200 <= resp.status < 300:
            os.unlink(tmp)
            raise http_error("POST", "/export", resp) from None
    path = _deliver(ctx, tmp, dest)
    return Result(0, {"path": path, "job_id": job.job_id, "report_source": source})


def cmd_export_report(ctx):
    conn = Conn(ctx)
    job = _one_job(ctx, conn)
    dest = _destination(ctx, job, "report.json")
    saved = os.path.join(job.dir, "report.json") if job.dir else None
    if saved and os.path.isfile(saved) and dest != saved:
        if dest == "-":
            _to_stdout(saved)
            return Result(0, {"path": None, "job_id": job.job_id, "source": "saved report.json"})
        shutil.copyfile(saved, dest)
        output.progress(f"Copied the saved report to {dest}")
        output.result(dest)
        return Result(0, {"path": dest, "job_id": job.job_id, "source": "saved report.json"})
    if saved and dest == saved and os.path.isfile(saved):
        output.result(dest)
        return Result(0, {"path": dest, "job_id": job.job_id, "source": "saved report.json"})
    tmp = _tmp_for(dest, job)
    _note_concurrency(conn, job, "report")
    conn.download("GET", f"/jobs/{job.job_id}/report", tmp, confirm_large=confirm_large(ctx))
    path = _deliver(ctx, tmp, dest)
    return Result(0, {"path": path, "job_id": job.job_id, "source": "server job"})
