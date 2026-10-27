"""`qrosetta show artifacts`, `show views`, `export views` and `export figure` (spec §6.20,
§6.21, experimental): the figures and tables a job's report offers, the export views with their
parameters (GET /publication/views), and one figure or table written through the publication
render routes, from the job's server copy or, once it has expired, from the saved report.json
(recorded as client-supplied)."""

import json
import os
import re

from qrosetta_cli import output
from qrosetta_cli.client import results
from qrosetta_cli.client.circuits import Server, keep, one_job
from qrosetta_cli.client.commands import parse_value
from qrosetta_cli.client.conn import http_error
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage

VIEWS_FEATURE = "publication_views"
VIEWS_FILE = "publication-views.json"
EXTENSIONS = {"latex": "tex", "markdown": "md", "text": "txt"}
FORMATS_BY_EXTENSION = {v: k for k, v in EXTENSIONS.items()}


def _views(conn):
    if not conn.has(VIEWS_FEATURE):
        raise CliError(
            "This server offers no GET /publication/views.",
            Exit.INCOMPATIBLE,
            "feature_missing",
            hint="qrosetta show artifacts lists what a result offers",
        )
    return conn.request("GET", "/publication/views", what="GET /publication/views")


def _param_line(p):
    if p.get("type") == "choice":
        kind = " | ".join(p.get("choices") or [])
    elif p.get("type") in ("int", "float"):
        kind = f"{p['type']} {p.get('min')}-{p.get('max')}"
    elif p.get("type") == "bits":
        kind = f"list of up to {p.get('max_items')} classical bits"
    else:
        kind = p.get("type", "")
    default = p.get("default_when_null") if p.get("default") is None else json.dumps(p.get("default"))
    return f"    {p.get('name')}: {kind} (default {default})"


def cmd_show_views(ctx):
    listing = _views(Server(ctx).conn).json()
    for view in listing.get("views") or []:
        arts = "; ".join(
            f"{a['kind']} {a['artifact_id']} ({', '.join(a['formats'])})" for a in view.get("artifacts", [])
        )
        output.result(f"{view['id']}  {arts}")
        for p in view.get("params") or []:
            output.result(_param_line(p))
    scale = listing.get("scale") or {}
    output.progress(
        f"Raster scale {scale.get('min')}-{scale.get('max')}. Which of these a result offers: qrosetta show artifacts"
    )
    return Result(0, listing)


def cmd_export_views(ctx):
    resp = _views(Server(ctx).conn)
    dest = ctx.opt("output") or os.path.join(results.parent_dir(ctx), VIEWS_FILE)
    if dest == "-":
        output.raw(resp.body)
        return Result(0, {"path": None})
    dest = os.path.abspath(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    results.write_bytes(dest, resp.body)
    output.progress(f"Wrote {len(resp.body)} bytes to {dest}")
    output.result(dest)
    return Result(0, {"path": dest})


def _saved_report(job):
    path = os.path.join(job.dir, "report.json") if job.dir else None
    return path if path and os.path.isfile(path) else None


def _supplied_body(path, task, extra, limit):
    """The body of a POST with the saved report (one playlist circuit when `task` is set),
    sent as saved; refused when over the server's request limit."""
    with open(path, "rb") as fh:
        text = fh.read()
    if task is not None:
        tasks = json.loads(text).get("benchmark_summary")
        if not isinstance(tasks, list) or not 0 <= task < len(tasks):
            raise usage(
                f"--task {task}: the saved report has no such circuit.",
                hint="qrosetta show circuits",
                reason="bad_task",
            )
        text = json.dumps(tasks[task], ensure_ascii=False).encode("utf-8")
    options = json.dumps(extra, ensure_ascii=False).encode("utf-8")[1:-1]
    body = b'{"results":' + text + (b"," + options if options else b"") + b"}"
    if limit and len(body) > limit:
        raise CliError(
            f"{path} is too large to send ({len(body)} bytes; the server accepts {limit}).",
            Exit.REFUSED,
            "request_too_large",
            hint="render it while the job lives",
        ) from None
    return body


def _expired(exc):
    detail = json.dumps(exc.detail, default=str) if exc.detail is not None else exc.message
    return exc.code == Exit.NOT_FOUND and "Unknown artifact" not in detail and "no circuit" not in detail


def cmd_show_artifacts(ctx):
    server = Server(ctx)
    job = one_job(ctx, server)
    conn = server.conn
    task = ctx.opt("task")
    source = "server job"
    try:
        catalog = conn.get(
            f"/jobs/{job.job_id}/publication/artifacts",
            query={"task": str(task)} if task is not None else None,
            what=f"artifacts of job {job.job_id[:8]}",
        )
    except CliError as exc:
        report = _saved_report(job)
        if not _expired(exc) or not report:
            raise
        body = _supplied_body(report, task, {}, conn.limit("max_request_bytes"))
        resp = conn.transport.request(
            "POST", "/publication/artifacts", body=body, headers={"Content-Type": "application/json"}
        )
        if resp.status != 200:
            raise http_error("POST", "/publication/artifacts", resp) from None
        catalog, source = resp.json(), "client-supplied report (the saved report.json)"
    output.result(
        f"{job.request().get('title') or 'Job'} (job {job.job_id[:8]}): "
        f"saved {results.read_status(job.dir) if job.dir else 'not saved'}; {source}"
    )
    width = max([len("ARTIFACT")] + [len(a.get("id", "")) for a in catalog])
    output.result(f"{'ARTIFACT':<{width}}  {'VIEW':<22}  FORMATS")
    for a in catalog:
        output.result(
            f"{a.get('id', ''):<{width}}  {(a.get('view_id') or '-'):<22}  {', '.join(a.get('formats') or [])}"
        )
    output.progress("One of them as a file: qrosetta export figure ARTIFACT [--format F] [--param K=V]")
    return Result(0, {"job_id": job.job_id, "source": source, "artifacts": catalog})


def _params(values):
    params = {}
    for value in values or []:
        if value.startswith("@"):
            try:
                with open(value[1:], encoding="utf-8") as fh:
                    loaded = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                raise usage(f"--param {value}: {exc}", hint="qrosetta export figure --help", reason="param") from None
            if not isinstance(loaded, dict):
                raise usage(
                    f"--param {value}: the file holds no JSON object.",
                    hint="qrosetta export figure --help",
                    reason="param",
                )
            params.update(loaded)
            continue
        key, sep, raw = value.partition("=")
        if not sep or not key:
            raise usage(f"--param takes KEY=VALUE or @FILE, not {value!r}.", hint="qrosetta show views", reason="param")
        params[key] = parse_value(raw)
    return params


def _format(ctx, conn, artifact):
    if ctx.opt("format"):
        return ctx.opt("format")
    out = ctx.opt("output")
    if out and out != "-" and "." in os.path.basename(out):
        ext = out.rsplit(".", 1)[1].lower()
        return FORMATS_BY_EXTENSION.get(ext, ext)
    if out == "-":
        raise usage(
            "Writing to stdout needs --format.",
            hint=f"qrosetta export figure {artifact} --format svg -o -",
            reason="format_missing",
        )
    if conn.has(VIEWS_FEATURE):
        for view in _views(conn).json().get("views") or []:
            for a in view.get("artifacts") or []:
                if a.get("artifact_id") == artifact and a.get("formats"):
                    return a["formats"][0]
    return "svg"


def file_name(artifact, params, fmt):
    """<artifact>[_<key>-<value>...].<extension>"""

    def text(value):
        if isinstance(value, list):
            return "-".join(text(v) for v in value)
        return value if isinstance(value, str) else json.dumps(value)

    parts = [artifact] + [f"{k}-{text(v)}" for k, v in sorted(params.items())]
    stem = re.sub(r"-{2,}", "-", re.sub(r"[^A-Za-z0-9._-]+", "-", "_".join(parts))).strip("-")[:120]
    return f"{stem}.{EXTENSIONS.get(fmt, fmt)}"


def cmd_export_figure(ctx):
    server = Server(ctx)
    job = one_job(ctx, server)
    conn = server.conn
    artifact = ctx.opt("artifact")
    params = _params(ctx.opt("param"))
    fmt = _format(ctx, conn, artifact)
    task = ctx.opt("task")
    body = {"artifact_id": artifact, "format": fmt, "scale": ctx.opt("scale") or 1, "params": params}
    if task is not None:
        body["task"] = task
    out = ctx.opt("output")
    if out == "-":
        dest = "-"
    elif out:
        dest = os.path.abspath(out)
    else:
        dest = os.path.join(job.dir or os.getcwd(), file_name(artifact, params, fmt))
    source = "server_job"
    try:
        resp = conn.request(
            "POST", f"/jobs/{job.job_id}/publication/render", payload=body, what=f"render of {artifact}"
        )
    except CliError as exc:
        report = _saved_report(job)
        if not _expired(exc) or not report:
            raise
        extra = {k: v for k, v in body.items() if k != "task"}
        raw = _supplied_body(report, task, extra, conn.limit("max_request_bytes"))
        resp = conn.transport.request(
            "POST", "/publication/render", body=raw, headers={"Content-Type": "application/json"}
        )
        if resp.status != 200:
            raise http_error("POST", "/publication/render", resp) from None
        source = "client_supplied"
    data = {
        "path": None,
        "job_id": job.job_id,
        "artifact_id": artifact,
        "format": fmt,
        "params": params,
        "report_source": source,
    }
    if dest == "-":
        output.raw(resp.body)
        return Result(0, data)
    if job.dir and os.path.dirname(dest) == job.dir:
        keep(job.dir, os.path.basename(dest), resp.body)
    else:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        results.write_bytes(dest, resp.body)
    if source == "client_supplied":
        output.progress("The job has expired on the server; drawn from the saved report.json (client-supplied).")
    output.progress(f"Wrote {len(resp.body)} bytes to {dest}")
    output.result(dest)
    return Result(0, {**data, "path": dest})
