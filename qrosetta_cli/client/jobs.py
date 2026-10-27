"""`qrosetta jobs` and `qrosetta jobs status` (spec §6.19): the jobs this machine submitted, from
the job index, with the server's status of each unless --offline; one job's envelope without
its report."""

import os

from qrosetta_cli import output
from qrosetta_cli.client import jobindex, results, servers
from qrosetta_cli.client.conn import Conn
from qrosetta_cli.client.waiting import status_line
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit


def _server_status(conn, job_id):
    try:
        env = conn.get(f"/jobs/{job_id}")
    except CliError as exc:
        if exc.code == Exit.NOT_FOUND:
            return "expired"
        raise
    return env.get("phase") or env.get("status")


def cmd_jobs(ctx):
    offline = ctx.opt("offline")
    conns: dict = {}
    rows = []
    for entry in jobindex.entries(ctx.env):
        d = entry.get("dir")
        row = {
            "job_id": entry["job_id"],
            "server": entry.get("server"),
            "endpoint": entry.get("endpoint"),
            "kind": entry.get("kind"),
            "mode": entry.get("mode"),
            "title": entry.get("title"),
            "submitted_at": entry.get("submitted_at"),
            "dir": d,
            "save_status": results.read_status(d) if d and os.path.isdir(d) else None,
            "server_status": None,
        }
        if not offline and row["server"]:
            if row["server"] not in conns:
                try:
                    conns[row["server"]] = Conn(ctx, server=servers.resolve(row["server"], "job index", ctx.cfg))
                except CliError as exc:
                    conns[row["server"]] = exc
            conn = conns[row["server"]]
            row["server_status"] = _server_status(conn, row["job_id"]) if isinstance(conn, Conn) else "unreachable"
        rows.append(row)
    if not rows:
        output.result("No jobs in the job index yet.")
    else:
        output.result(f"{'JOB':<10} {'SUBMITTED':<21} {'MODE':<12} {'SERVER':<12} {'SAVED':<18} DIR")
        for r in rows:
            mode = r["mode"] or ("compile" if r["kind"] else "-")
            output.result(
                f"{r['job_id'][:8]:<10} {r['submitted_at'] or '-':<21} {mode:<12} "
                f"{(r['server_status'] or ('-' if offline else '?')):<12} {(r['save_status'] or 'not saved'):<18} "
                f"{r['dir'] or '-'}"
            )
    return Result(0, {"index": jobindex.path(ctx.env), "offline": bool(offline), "jobs": rows})


def cmd_jobs_status(ctx):
    conn = Conn(ctx)
    ref = ctx.args.job
    job_id = ref[4:] if ref.startswith("job:") else ref
    entry = jobindex.find(ctx.env, job_id, conn.url)
    if entry is not None:
        job_id = entry["job_id"]
    env = conn.get(f"/jobs/{job_id}", what=f"job {job_id[:8]}")
    env = {k: v for k, v in env.items() if k != "results"}
    labels = conn.config.get("status_labels") or {}
    output.result(status_line(env, labels, f"Job {job_id}"))
    if env.get("error"):
        output.result(f"Error: {env['error']}")
    if entry and entry.get("dir"):
        output.result(f"Results: {entry['dir']} ({results.read_status(entry['dir']) or 'not saved'})")
    return Result(
        0,
        {
            "job": env,
            "dir": (entry or {}).get("dir"),
            "save_status": results.read_status(entry["dir"]) if entry and entry.get("dir") else None,
        },
    )
