"""`qrosetta run` and `qrosetta wait` (spec §6.18, §6.19): plan through POST /plan, submit the
planned requests unchanged one after another, follow each job, save it completely before the
next is submitted, and print what the server's summary says. Exit codes for outcomes come from
the summary's outcome names and roles (--fail-on, default none)."""

import hashlib
import os
import time

from qrosetta_cli import __version__, localstack, mode as modes, output
from qrosetta_cli.client import handshake, jobindex, outcomes, replay, results, runplan, save, waiting
from qrosetta_cli.client.conn import Conn, body_bytes
from qrosetta_cli.client.transport import origin
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage, worst

STATUS_EXIT = {"failed": Exit.JOB_FAILED, "cancelled": Exit.JOB_CANCELLED}
REPLAY_CONFLICTS = (
    ("circuits", "circuits"),
    ("playlist", "--playlist"),
    ("mode", "--mode"),
    ("compile_only", "--compile-only"),
    ("shots", "--shots"),
    ("backends", "--backends"),
    ("skip", "--skip"),
    ("opt_level", "--opt-level"),
    ("timeout", "--timeout"),
    ("repeats", "--repeats"),
    ("exclusive", "--exclusive"),
    ("preprocessing", "--preprocessing"),
    ("compiler", "--compiler"),
    ("threshold", "--threshold"),
    ("seed", "--seed"),
    ("name", "--name"),
    ("order", "--order"),
    ("execution_target", "--execution-target"),
    ("bypass_limits", "--bypass-limits"),
    ("keep_statevectors", "--keep-statevectors"),
    ("set", "--set"),
)


def duration_text(seconds):
    seconds = int(seconds or 0)
    if seconds % 3600 == 0 and seconds >= 3600:
        return f"{seconds // 3600} h"
    if seconds >= 3600:
        return f"{seconds // 3600} h {seconds % 3600 // 60} min"
    if seconds >= 60:
        return f"{seconds // 60} min"
    return f"{seconds} s"


def retention_text(ttl, now=None):
    """'for 24 h, until 10:15 tomorrow'."""
    if not ttl:
        return "for as long as the server keeps finished jobs"
    now = time.time() if now is None else now
    until = time.localtime(now + ttl)
    day = (
        ""
        if time.localtime(now).tm_yday == until.tm_yday
        else (" tomorrow" if ttl < 172800 else time.strftime(" on %Y-%m-%d", until))
    )
    return f"for {duration_text(ttl)}, until {time.strftime('%H:%M', until)}{day}"


def confirm_large(ctx, interactive=True):
    """Whether to download a body over 1 GiB: --yes, else a question on a terminal; after a
    wait (`interactive` False) never a question (spec P5)."""

    def ask(size):
        if ctx.opt("yes"):
            return True
        if not interactive or not ctx.tty:
            return False
        answer = output.prompt(f"The report is {size / (1 << 30):.1f} GiB. Download it? [y/N] ", stdin=ctx.stdin)
        return bool(answer) and answer.strip().lower() in ("y", "yes")

    return ask


def stack_record(ctx):
    """The local stack's CPU quota setting as `qrosetta start` recorded it (spec §6.1)."""
    enabled, since, source = localstack.cpu_quota(ctx.env, ctx.cfg)
    entry = localstack.stack_settings(ctx.env)
    return {
        "cpu_quota": enabled,
        "cpu_quota_source": source,
        "cpu_quota_since": since,
        "cpu_quota_override_sha256": entry.get("override_sha256") if not enabled else None,
    }


def _compose_record(ctx, conn):
    if not conn.local:
        return None
    try:
        mode = modes.detect(ctx.opt("project_dir"), ctx.env, ctx.checkout)
    except CliError:
        return None
    path = modes.compose_file(mode.project_dir) if mode.project_dir else None
    if not path:
        return None
    with open(path, "rb") as fh:
        return {"path": path, "sha256": hashlib.sha256(fh.read()).hexdigest()}


def plan_document(ctx, conn, req, plan, invocation, replay_of=None, replay_force=False, fail_on=(), planner=None):
    levels = handshake.levels(conn.block)
    return {
        "schema": "qrosetta.cli/plan@1",
        "cli_version": __version__,
        "created_at": output.utc_now(),
        "server": {
            "url": conn.url,
            **{
                k: conn.block.get(k)
                for k in ("platform_version", "api_levels", "analysis_version", "git_sha", "features")
            },
        },
        "api_level": min(levels[1], handshake.CLI_API_LEVELS[1]) if levels else None,
        "results_dir": invocation,
        "plan_request": req,
        "planner_sources": planner or {},
        "plan": plan,
        "planned_jobs": len(plan.get("runs") or []),
        "job_dirs": [],
        "replay_of": replay_of,
        "replay_force": bool(replay_force),
        "fail_on": list(fail_on),
        "stack": stack_record(ctx) if conn.local else None,
        "compose": _compose_record(ctx, conn),
    }


def _problems(plan, req):
    problems = plan.get("problems") or []
    if not problems:
        return
    circuits = req.get("circuits") or []
    lines = [runplan.problem_text(p, circuits) for p in problems]
    for line in lines[1:]:
        output.progress(f"qrosetta: {line}")
    first = problems[0]
    raise CliError(
        lines[0],
        Exit.REFUSED,
        first.get("code") or "refused",
        hint="qrosetta run --dry-run shows the plan",
        detail={"problems": problems},
    )


def _check_sizes(conn, plan):
    limit = conn.limit("max_request_bytes")
    for i, run in enumerate(plan.get("runs") or []):
        size = len(body_bytes(run["payload"]))
        if limit and size > limit:
            raise CliError(
                f"this run's request is {size} bytes; the server accepts {limit}. Split the playlist.",
                Exit.REFUSED,
                "request_too_large",
                hint="qrosetta run --dry-run shows the plan",
                detail={"run_index": i, "bytes": size, "max": limit},
            )


def job_files(info):
    return {"request": "request.json", "job": "job.json", **(info.get("files") or {})}


def job_line(title, env, summary, elapsed):
    status = env.get("status")
    runs = (summary or {}).get("runs") or {}
    text = f"{title}: {status}" + (f" in {round(elapsed)} s." if elapsed is not None else ".")
    if runs.get("total"):
        text += f" {runs.get('returned', 0)} of {runs['total']} runs returned."
    if env.get("error"):
        text += f" {env['error']}"
    return text


NOT_PAIR_OUTCOMES = ("no_comparison", "runs_without_output")


def pairs_line(summary):
    """The pair counts of a summary, grouped by the role the server gives each outcome."""
    counts = (summary or {}).get("outcomes")
    roles = (summary or {}).get("outcome_roles") or {}
    if not counts:
        return None

    def by_role(role):
        return sum(n for name, n in counts.items() if roles.get(name) == role and name not in NOT_PAIR_OUTCOMES)

    nc = counts.get("not_comparable", 0)
    total = sum(n for name, n in counts.items() if name not in NOT_PAIR_OUTCOMES)
    agree, differ = by_role("agreement"), by_role("difference")
    text = (
        f"Pairs: {total - nc} compared, {agree} agree, {differ} differ"
        + (f" ({counts['differs_by_only']} under Benjamini-Yekutieli only)" if counts.get("differs_by_only") else "")
        + f", {counts.get('inconclusive', 0)} inconclusive, {nc} not comparable."
    )
    if counts.get("no_comparison"):
        text += " No pair was compared."
    return text


def caveats_line(summary):
    caveats = (summary or {}).get("timing_caveats")
    if not caveats:
        return None
    texts = [c.get("message") or c.get("text") or c.get("kind") if isinstance(c, dict) else str(c) for c in caveats]
    return "Timing caveats: " + "; ".join(t for t in texts if t) + "."


def crate_line(conn, job_id, info):
    if info["crate"] == "saved" or info["status"] == results.JOB_FAILED:
        return None
    ttl = conn.limit("job_ttl_sec")
    if info["crate"] == "deferred":
        record = info.get("record") or {}
        since = save._epoch(record.get("crate_deferred_since")) or time.time()
        until = time.strftime("%H:%M", time.localtime(since + (ttl or 1800) - save.DEFER_MARGIN_SEC))
        return f"Crate: deferred until the server is idle (up to {until}); `qrosetta wait job:{job_id[:8]}` finishes it"
    return f"Crate: `qrosetta export crate --result job:{job_id[:8]}` (the server keeps the job {retention_text(ttl)})"


JOB_LINK_FEATURE = "job_link"


def page_link(conn, job_id):
    """The page's link to the job, `<server>/#job=<id>`, when the server's page opens one."""
    if not conn.has(JOB_LINK_FEATURE):
        return None
    return f"{conn.url.rstrip('/')}/#job={job_id}"


class Follower:
    """Follows and saves jobs of one server for run and wait."""

    def __init__(self, ctx, conn, saver, fail_on, wait_timeout=None):
        self.ctx, self.conn, self.saver = ctx, conn, saver
        self.fail_on = fail_on
        self.wait_timeout = wait_timeout
        self.codes = []
        self.matched = []
        self.version = outcomes.rule_version(conn.config)
        self.jobs = []
        self.results_dir = None

    def stop_message(self, job_id, reason_code, remaining=0):
        ttl = self.conn.limit("job_ttl_sec")
        text = (
            f"Stopped waiting. Job {job_id[:8]} keeps running on the server; it is kept for "
            f"{duration_text(ttl) if ttl else 'a while'} after it finishes (this server's retention)."
        )
        if remaining:
            text += f" {remaining} planned job{'s' if remaining > 1 else ''} not submitted."
        return CliError(
            text, reason_code, "detached", hint=f"qrosetta wait job:{job_id[:8]}", data=self.data(self.results_dir)
        )

    def follow(self, job_id, job_dir, title, kind, started=None, remaining=0, previous=None, before_save=None):
        """Wait for one job and save it; returns its data entry. `before_save(envelope)` runs
        between the two, for files that must be in place before STATUS."""
        try:
            with waiting.stop_signals():
                try:
                    env = waiting.wait_job(self.conn, job_id, title, self.wait_timeout)
                except KeyboardInterrupt:
                    raise waiting.Stopped(Exit.SIGINT) from None
        except waiting.Stopped as stop:
            jobindex.append(self.ctx.env, {"job_id": job_id, "detached": True})
            raise self.stop_message(job_id, stop.code, remaining) from None
        except waiting.WaitTimeout:
            output.progress(f"--wait-timeout reached; job {job_id[:8]} keeps running on the server.")
            self.codes.append(Exit.WAIT_TIMEOUT)
            entry = {"job_id": job_id, "status": "running", "save_status": None, "dir": job_dir, "title": title}
            self.jobs.append(entry)
            return entry
        elapsed = time.time() - started if started else None
        if before_save is not None:
            before_save(env)
        info = self.saver.save(job_dir, job_id, kind, env, previous=previous)
        jobindex.append(
            self.ctx.env,
            {"job_id": job_id, "status": env.get("status"), "save_status": info["status"], "detached": False},
        )
        summary = info.get("summary")
        if summary is None and self.fail_on and env.get("status") == "completed":
            summary = self._summary(job_id, kind)
        code, matched = outcomes.evaluate(self.fail_on, summary, self.conn.config)
        if summary:
            self.version = outcomes.rule_version(self.conn.config, summary)
        self.codes.append(worst([code, STATUS_EXIT.get(env.get("status"), Exit.OK)]))
        self.matched += [m for m in matched if m not in self.matched]
        for line in (job_line(title, env, summary, elapsed), pairs_line(summary), caveats_line(summary)):
            if line:
                output.result(line)
        saved = ", ".join(
            info["files"][k] for k in ("report", "summary", "circuits", "crate", "bundle") if k in info["files"]
        )
        output.result(
            f"Saved {job_dir}{os.sep}"
            + (f" ({saved})" if saved else "")
            + ("" if info["status"] == results.COMPLETE else f" [{info['status']}]")
        )
        line = crate_line(self.conn, job_id, info)
        if line:
            output.result(line)
        link = page_link(self.conn, job_id)
        if link:
            output.result(f"Open in the browser: {link}")
        request = results.read_json(os.path.join(job_dir, "request.json")) or {}
        backends = [
            b.get("key") for b in ((summary or {}).get("backend_verdicts") or {}).get("backends") or []
        ] or list((request.get("payload") or {}).get("target_simulators") or [])
        entry = {
            "job_id": job_id,
            "endpoint": request.get("endpoint"),
            "kind": kind,
            "mode": request.get("mode"),
            "title": title,
            "status": env.get("status"),
            "save_status": info["status"],
            "dir": job_dir,
            "files": job_files(info),
            "backends": backends,
            "concurrent_with_other_jobs": info["concurrent"],
            "page_url": link,
            "summary": summary,
        }
        self.jobs.append(entry)
        return entry

    def _summary(self, job_id, kind):
        """The server's summary for --fail-on when the save set leaves it out."""
        if kind == "experiment":
            output.warn("An experiment has no summary, so --fail-on is not applied to it.", "fail_on_experiment")
            return None
        try:
            return self.conn.get(f"/jobs/{job_id}/summary", what=f"summary of job {job_id[:8]}")
        except CliError as exc:
            output.warn(f"--fail-on not applied: {exc.message}", "fail_on_unavailable")
            return None

    def data(self, results_dir=None):
        return {"results_dir": results_dir, "jobs": list(self.jobs)}

    def outcome(self):
        return outcomes.block(self.fail_on, self.matched, self.version)

    def closing_hint(self, invocation):
        """The command a non-zero outcome ends with (spec P11)."""
        if self.code() == Exit.OK:
            return
        running = [j["job_id"] for j in self.jobs if j.get("status") == "running"]
        if self.code() == Exit.WAIT_TIMEOUT and running:
            output.progress(f"qrosetta wait job:{running[0][:8]}")
            return
        if self.matched:
            output.progress(f"--fail-on matched {', '.join(self.matched)}.")
        target = f" --result {invocation}" if invocation else ""
        output.progress(f"qrosetta show summary{target}")

    def code(self):
        return worst(self.codes) if self.codes else Exit.OK


def _connect(ctx):
    return Conn(ctx, features=("plan",))


def _fail_on(ctx, conn):
    return outcomes.resolve(outcomes.parse(ctx.opt("fail_on")), conn.config)


def _wait_timeout(ctx):
    value = ctx.opt("wait_timeout")
    return runplan.parse_duration(value, "--wait-timeout") if value else None


def cmd_run(ctx):
    args = ctx.args
    conn = _connect(ctx)
    fail_on = _fail_on(ctx, conn)
    wait_timeout = _wait_timeout(ctx)
    items, minimal, note = save.save_set(conn, args)
    crate_body = save.crate_options(args)
    replay_of, force = None, bool(args.force)
    if args.request:
        given = [flag for attr, flag in REPLAY_CONFLICTS if getattr(args, attr, None) not in (None, False, [])]
        if given:
            raise usage(
                f"--request replays a saved run as it was; {', '.join(given)} cannot change it.",
                hint="qrosetta run --request FILE, without circuits or run settings",
                reason="replay_with_settings",
            )
        req, original, api_level, reports = replay.load(args.request)
        replay.check_versions(conn, original, api_level, force)
        settings = replay.settings_of(req)
        replay.fill(req, reports, settings)
        planner = {"modes": "replay", "preprocessing": "replay", "compilers": "replay", "name": "replay"}
        slug_name = req.get("name") or replay.original_slug(args.request)
        replay_of = os.path.abspath(args.request)
    else:
        req, settings, planner, slug_name = runplan.build(args, conn, ctx.stdin)
    runplan.check_server_fields(conn, settings)
    plan = conn.post("/plan", req, what="POST /plan")
    _problems(plan, req)
    _check_sizes(conn, plan)
    runs = plan.get("runs") or []
    if args.detach and len(runs) > 1:
        raise usage(
            f"--detach runs one job, and this plan has {len(runs)}.",
            hint="drop --detach (the jobs run one after another), or run one mode at a time",
            reason="detach_multi_job",
        )
    if args.dry_run:
        doc = plan_document(ctx, conn, req, plan, None, replay_of, force, fail_on, planner)
        for i, run in enumerate(runs):
            output.result(f"{i + 1}. {run['endpoint']} {run.get('title')}: {len(body_bytes(run['payload']))} bytes")
        output.progress("Dry run: nothing was sent to the run routes.")
        return Result(0, doc, schema="plan@1")

    parent = results.parent_dir(ctx)
    slug = results.slugify(slug_name)
    invocation = results.new_invocation(parent, slug, args.output)
    doc = plan_document(ctx, conn, req, plan, invocation, replay_of, force, fail_on, planner)
    doc["slug"] = slug
    plan_path = os.path.join(invocation, results.PLAN_FILE)
    results.write_json(plan_path, doc)
    output.progress(f"Results: {invocation}")
    differ = runplan.differing_settings(conn, req.get("settings") or {}, runs[0]["endpoint"]) if runs else []
    if differ:
        output.progress("Settings that differ from the server defaults: " + ", ".join(differ))
    if note:
        output.progress(note)
    if args.detach:
        in_flight = conn.dispatches_in_flight()
        if in_flight:
            output.progress(
                f"{in_flight} runs in flight on this server; this job will overlap them, and the overlap is recorded."
            )

    saver = save.Saver(conn, items, minimal, crate_body, confirm_large(ctx, interactive=False))
    follower = Follower(ctx, conn, saver, fail_on, wait_timeout)
    follower.results_dir = invocation
    for i, run in enumerate(runs):
        title = run.get("title") or run["endpoint"]
        started = time.time()
        with waiting.submitting() as state:
            env = conn.post(
                run["endpoint"],
                run["payload"],
                what=f"POST {run['endpoint']}",
                hint="qrosetta run --dry-run shows the planned request",
            )
        job_id = results.server_job_id(env, f"POST {run['endpoint']}")
        job_dir = os.path.join(invocation, results.job_dir_name(run.get("kind"), run.get("mode"), job_id))
        os.mkdir(job_dir)
        results.write_json(os.path.join(job_dir, "request.json"), runplan.request_record(conn, run, planner, job_id))
        results.write_json(os.path.join(job_dir, "job.json"), env)
        doc["job_dirs"].append(os.path.basename(job_dir))
        results.write_json(plan_path, doc)
        jobindex.append(
            ctx.env,
            {
                "job_id": job_id,
                "server": origin(conn.url),
                "endpoint": run["endpoint"],
                "kind": run.get("kind"),
                "mode": run.get("mode"),
                "title": title,
                "dir": job_dir,
                "invocation": invocation,
                "submitted_at": output.utc_now(),
                "save": {"items": sorted(items), "minimal": minimal, "crate": crate_body},
                "fail_on": fail_on,
                "detached": bool(args.detach),
            },
        )
        output.progress(f"Submitted {title}: job {job_id}")
        if state["interrupted"]:
            raise follower.stop_message(job_id, Exit.SIGINT, len(runs) - i - 1)
        if args.detach:
            output.result(f"Job {job_id} submitted; results go to {job_dir}{os.sep}")
            output.result(f"qrosetta wait job:{job_id[:8]}")
            if page_link(conn, job_id):
                output.result(f"Open in the browser: {page_link(conn, job_id)}")
            follower.jobs.append(
                {
                    "job_id": job_id,
                    "endpoint": run["endpoint"],
                    "kind": run.get("kind"),
                    "mode": run.get("mode"),
                    "title": title,
                    "status": env.get("status"),
                    "save_status": None,
                    "dir": job_dir,
                    "files": {"request": "request.json", "job": "job.json"},
                    "backends": [],
                    "summary": None,
                }
            )
            return Result(0, follower.data(invocation), follower.outcome())
        follower.follow(job_id, job_dir, title, run.get("kind"), started, remaining=len(runs) - i - 1)
        if follower.codes and follower.codes[-1] == Exit.WAIT_TIMEOUT:
            if len(runs) - i - 1:
                output.progress(f"{len(runs) - i - 1} planned jobs not submitted.")
            break
    if results.invocation_complete(invocation):
        results.update_latest(parent, invocation)
    follower.closing_hint(invocation)
    return Result(follower.code(), follower.data(invocation), follower.outcome())


def _unfinished(entry):
    d = entry.get("dir")
    status = results.read_status(d) if d and os.path.isdir(d) else None
    return status is None or status == results.CRATE_DEFERRED


def cmd_wait(ctx):
    args = ctx.args
    conn = Conn(ctx)
    wait_timeout = _wait_timeout(ctx)
    here = origin(conn.url)
    known = [e for e in jobindex.entries(ctx.env) if e.get("server") == here]
    if args.all:
        targets = [e for e in known if _unfinished(e)]
    elif args.jobs:
        targets = []
        for ref in args.jobs:
            job_id = ref[4:] if ref.startswith("job:") else ref
            entry = jobindex.find(ctx.env, job_id, conn.url)
            if entry is None:
                raise CliError(
                    f"No job {job_id!r} for {conn.url} in the job index.",
                    Exit.NOT_FOUND,
                    "job_unknown",
                    hint="qrosetta jobs",
                )
            targets.append(entry)
    else:
        pending = [e for e in known if _unfinished(e)]
        if not pending:
            raise CliError(
                f"No unfinished job for {conn.url} in the job index.",
                Exit.NOT_FOUND,
                "job_unknown",
                hint="qrosetta jobs",
            )
        targets = pending[-1:]
    fail_on = _fail_on(ctx, conn) if ctx.opt("fail_on") else []
    follower = None
    for entry in targets:
        job_dir = entry.get("dir")
        if not job_dir or not os.path.isdir(job_dir):
            raise CliError(
                f"Job {entry['job_id'][:8]} has no results directory on this machine.",
                Exit.NOT_FOUND,
                "result_missing",
                hint=f"qrosetta jobs status {entry['job_id'][:8]}",
            )
        if args.no_save:
            items, minimal = set(), True
        elif args.save:
            items, minimal = save.parse_items(args.save)
        else:
            stored = entry.get("save") or {}
            items, minimal = set(stored.get("items") or ["report", "summary"]), bool(stored.get("minimal"))
        crate_body = (entry.get("save") or {}).get("crate") or {}
        previous = results.read_json(os.path.join(job_dir, "job.json")) or {}
        saver = save.Saver(conn, items, minimal, crate_body, confirm_large(ctx, interactive=False), patient=True)
        if follower is None:
            follower = Follower(ctx, conn, saver, fail_on or entry.get("fail_on") or [], wait_timeout)
        follower.saver = saver
        follower.follow(
            entry["job_id"], job_dir, entry.get("title") or entry["job_id"][:8], entry.get("kind"), previous=previous
        )
        inv = entry.get("invocation")
        if inv and results.invocation_complete(inv):
            results.update_latest(os.path.dirname(inv), inv)
    follower.closing_hint(None)
    return Result(follower.code(), follower.data(), follower.outcome())
