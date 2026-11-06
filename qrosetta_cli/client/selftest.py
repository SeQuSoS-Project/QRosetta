"""`qrosetta selftest` (spec §6.17), the client half: the server's pinned self-test plan
(GET /selftest) submitted as published with the backends under test added, each job saved with
its report, summary and crate, the server's evaluation of each job, and selftest.json with the
combined result. Before the jobs, each image's fresh probe row is checked (`imageprobes`). The
CLI compares no result itself; its one rule turns a cpu_quota_cores FAIL into a WARN on a local
stack started without the CPU quota. Exit 9 when any check FAILs."""

import os
import time

from qrosetta_cli import __version__, layout, localstack, manifest as mf, output
from qrosetta_cli.client import imageprobes, jobindex, results, save, waiting
from qrosetta_cli.client.conn import Conn, body_bytes
from qrosetta_cli.client.run import Follower, confirm_large, plan_document
from qrosetta_cli.client.transport import origin
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage

FEATURE = "selftest"
QUOTA_CHECK = "cpu_quota_cores"
UNREACHABLE = "unreachable"


def _split(values):
    out = []
    for v in values or []:
        out += [x.strip() for x in v.split(",") if x.strip()]
    return out


def _runner_rows(ctx, conn):
    """(rows, None) from a fresh probe round, with the lifecycle token on a local stack, else
    (the cached rows, why)."""
    rows, why = imageprobes.fresh_rows(conn, "/runners", imageprobes.probe_headers(conn, ctx.env))
    if why:
        output.progress(f"Readiness from the cached runner list ({why}).")
    return rows, why


def backends_under_test(ctx, conn, runner_rows=None):
    """(keys under test, [(key, reason)] enabled but not tested); `runner_rows` from
    `_runner_rows`, else read here."""
    rows = runner_rows if runner_rows is not None else _runner_rows(ctx, conn)[0]
    wanted = _split(ctx.opt("backends"))
    known = {r.get("id"): r for r in rows}
    for key in wanted:
        if key not in known:
            raise usage(
                f"--backends {key}: no such backend on this server.",
                hint="qrosetta api GET /runners",
                reason="unknown_key",
            )
    if wanted:
        keys = wanted
    elif conn.local:
        keys = [r["id"] for r in rows if r.get("available")]
    else:
        keys = [r["id"] for r in rows if r.get("available") and r.get("default_selected")]
    left = [
        (r["id"], r.get("unavailable_reason") or ("not selected" if r.get("available") else "unavailable"))
        for r in rows
        if r.get("enabled") and r["id"] not in keys
    ]
    left = [(key, mf.not_included_text([key]) if why == mf.NOT_INCLUDED else why) for key, why in left]
    if conn.local and any(why == UNREACHABLE for _, why in left):
        left = _not_started(ctx, left)
    return keys, left


def _not_started(ctx, left):
    """On a local stack, a backend the server cannot reach that the installed release publishes
    no image of is "not included in this release"; one whose service this stack has no
    container for is "not started in this stack (profile NAME)"; "unreachable" stays for a
    started service that does not answer."""
    try:
        stack = ctx.local_stack(ctx) if ctx.local_stack else None
    except CliError:
        stack = None
    if not stack:
        return left
    where = f" (profile {stack['profile']})" if stack.get("profile") else ""
    withheld = stack.get("not_included") or set()

    def reason(key, why):
        if why != UNREACHABLE:
            return why
        if key in withheld:
            return mf.not_included_text([key])
        return f"not started in this stack{where}" if key not in stack["created"] else why

    return [(key, reason(key, why)) for key, why in left]


def not_tested_lines(left):
    """One "Not tested" line per reason, naming its backends and their number, in the order the
    reasons first occur; the backends the release does not include share one line."""
    groups: dict = {}
    for key, why in left:
        groups.setdefault(mf.NOT_INCLUDED if why.startswith(mf.NOT_INCLUDED) else why, []).append(key)
    return [
        f"Not tested  {mf.not_included_text(keys) if why == mf.NOT_INCLUDED else why}: {', '.join(keys)} ({len(keys)})"
        for why, keys in groups.items()
    ]


def _route(spec, job_id):
    method, _, path = (spec or "GET /jobs/{job_id}/selftest-result").partition(" ")
    return method.upper(), path.replace("{job_id}", job_id)


def _apply_cli_rule(evaluation, quota_off, applied):
    if not quota_off:
        return evaluation
    for row in evaluation.get("environment_checks") or []:
        if row.get("check") == QUOTA_CHECK and row.get("status") == "FAIL":
            row["status"] = "WARN"
            row["reason"] = f"{row.get('reason', '')} (stack started without the CPU quota)".strip()
            applied.append({"rule": "cpu_quota_off", "backend": row.get("backend")})
    rows = [r for k in ("plan", "known_answer", "environment_checks") for r in evaluation.get(k) or []]
    statuses = {r.get("status") for r in rows}
    evaluation["status"] = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
    return evaluation


def screen_lines(lines, fails, warns, invocation):
    """The terminal form of the result `lines` (selftest.json keeps those): the part and image
    lines, each failure and warning as a check row, what happened, and the command that shows
    the jobs' summaries, last."""
    head = [line for line in lines[:-1] if not line.startswith(("FAIL        ", "WARN        "))]
    out = list(head)
    if fails or warns:
        out += [""] + layout.rows([("FAIL", "", t) for t in fails] + [("WARN", "", t) for t in warns])
    tail = f", {layout.plural(len(warns), 'warning')}" if warns else ""
    where = f"Results: {invocation}{os.sep}"
    if fails:
        out += ["", f"Self-test failed: {layout.plural(len(fails), 'check')} failed{tail}. {where}"]
        out += ["", "Read the jobs' summaries:", "  qrosetta show summary"]
    else:
        out += ["", f"Self-test passed{f' with {tail[2:]}' if warns else ''}. {where}"]
        out += ["Summaries:  qrosetta show summary"]
    return out


def cmd_selftest(ctx):
    conn = Conn(ctx, features=("plan",))
    if not conn.has(FEATURE):
        raise CliError(
            "This server offers no self-test (GET /selftest); nothing was run.",
            Exit.INCOMPATIBLE,
            "feature_missing",
            hint="upgrade the server to one whose GET /config lists the selftest feature",
        )
    plan = conn.get("/selftest", what="GET /selftest")
    runner_rows, runner_why = _runner_rows(ctx, conn)
    keys, left = backends_under_test(ctx, conn, runner_rows)
    if not keys:
        raise CliError(
            "No backend is available to test.",
            Exit.UNREACHABLE,
            "no_backends",
            hint="qrosetta status",
            evidence=[f"{k}: {why}" for k, why in left],
            step="List the services and their state:",
        )
    quota_off = conn.local and localstack.cpu_quota(ctx.env, ctx.cfg)[0] is False
    output.progress(f"Backends under test: {', '.join(keys)}")
    images: dict
    if ctx.opt("no_images"):
        images = {"status": "skipped", "reason": "--no-images", "server_git_sha": None, "images": []}
    else:
        images = imageprobes.probe_images(conn, ctx.env, runner_rows, runner_why, keys)
    image_lines, image_fails, image_warns = imageprobes.lines_and_findings(images)
    runs = []
    for job in plan.get("jobs") or []:
        payload = dict(job.get("request") or {}, target_simulators=keys)
        limit = conn.limit("max_request_bytes")
        if limit and len(body_bytes(payload)) > limit:
            raise CliError(
                f"The self-test's {job.get('part')} request is over the server's {limit} bytes.",
                Exit.REFUSED,
                "request_too_large",
                hint="qrosetta selftest --backends KEYS",
                step="Test fewer backends:",
            )
        runs.append(
            {
                "endpoint": job.get("endpoint", "/run_batch_suite"),
                "kind": "batch",
                "mode": job.get("part"),
                "title": f"Self-test ({job.get('part')})",
                "payload": payload,
                "sources": {k: "selftest_plan" for k in payload}
                | {"target_simulators": "flag" if ctx.opt("backends") else "server_default"},
                "evaluate": job.get("evaluate"),
            }
        )
    parent = results.parent_dir(ctx)
    invocation = results.new_invocation(parent, "selftest", ctx.opt("output"))
    doc = plan_document(ctx, conn, {"selftest": True, "backends": keys}, {"runs": runs, "problems": []}, invocation)
    doc["selftest_plan"] = {
        k: plan.get(k) for k in ("selftest_version", "expected_sha256", "expected_source", "tolerances", "pass_rule")
    }
    plan_path = os.path.join(invocation, results.PLAN_FILE)
    results.write_json(plan_path, doc)
    output.progress(f"Results: {invocation}")

    saver = save.Saver(conn, {"report", "summary", "crate"}, False, {}, confirm_large(ctx, interactive=False))
    follower = Follower(ctx, conn, saver, [])
    jobs: list = []
    applied: list = []
    lines = list(image_lines)
    for i, run in enumerate(runs):
        with waiting.submitting() as state:
            env = conn.post(run["endpoint"], run["payload"], what=f"POST {run['endpoint']}")
        job_id = results.server_job_id(env, f"POST {run['endpoint']}")
        job_dir = os.path.join(invocation, results.job_dir_name("batch", run["mode"], job_id))
        os.mkdir(job_dir)
        results.write_json(
            os.path.join(job_dir, "request.json"),
            {
                "job_id": job_id,
                "endpoint": run["endpoint"],
                "kind": "batch",
                "mode": run["mode"],
                "title": run["title"],
                "payload": run["payload"],
                "sources": run["sources"],
                "server_defaults": {},
            },
        )
        results.write_json(os.path.join(job_dir, "job.json"), env)
        doc["job_dirs"].append(os.path.basename(job_dir))
        results.write_json(plan_path, doc)
        jobindex.append(
            ctx.env,
            {
                "job_id": job_id,
                "server": origin(conn.url),
                "endpoint": run["endpoint"],
                "kind": "batch",
                "mode": run["mode"],
                "title": run["title"],
                "dir": job_dir,
                "invocation": invocation,
                "submitted_at": output.utc_now(),
                "save": {"items": ["crate", "report", "summary"], "minimal": False, "crate": {}},
                "fail_on": [],
                "detached": False,
            },
        )
        if state["interrupted"]:
            raise follower.stop_message(job_id, Exit.SIGINT, len(runs) - i - 1)
        found: dict = {}

        def evaluate(env, job_id=job_id, job_dir=job_dir, run=run, found=found):
            evaluation = {
                "status": "FAIL",
                "plan": [
                    {"check": "job", "status": "FAIL", "reason": f"job {env.get('status')}: {env.get('error') or ''}"}
                ],
            }
            if env.get("status") == "completed":
                method, path = _route(run["evaluate"], job_id)
                try:
                    evaluation = conn.request(method, path, what="self-test evaluation").json()
                except CliError as exc:
                    evaluation = {
                        "status": "FAIL",
                        "plan": [{"check": "evaluation", "status": "FAIL", "reason": exc.message}],
                    }
            found["evaluation"] = _apply_cli_rule(evaluation, quota_off, applied)
            results.write_json(os.path.join(job_dir, "selftest-result.json"), found["evaluation"])

        entry = follower.follow(
            job_id, job_dir, run["title"], "batch", time.time(), remaining=len(runs) - i - 1, before_save=evaluate
        )
        evaluation = found.get("evaluation") or {
            "status": "FAIL",
            "plan": [{"check": "job", "status": "FAIL", "reason": "the job did not finish"}],
        }
        jobs.append(
            {
                "part": run["mode"],
                "job_id": job_id,
                "dir": job_dir,
                "status": entry.get("status"),
                "save_status": entry.get("save_status"),
                "evaluation": evaluation,
            }
        )
    fails, warns = list(image_fails), list(image_warns)
    for job in jobs:
        ev = job["evaluation"]
        counts = ev.get("counts") or {}
        lines.append(
            f"{job['part'].capitalize():<11} {ev.get('status')}"
            + (f" ({', '.join(f'{v} {k}' for k, v in counts.items())})" if counts else "")
        )
        for key in ("plan", "known_answer", "environment_checks"):
            for row in ev.get(key) or []:
                where = ", ".join(x for x in (row.get("backend"), row.get("circuit")) if x)
                text = f"{row.get('check')}{f' ({where})' if where else ''}: {row.get('reason', '')}"
                if row.get("status") == "FAIL":
                    fails.append(text)
                elif row.get("status") == "WARN":
                    warns.append(text)
        for caveat in ev.get("caveats") or []:
            warns.append(str(caveat))
    lines += [f"FAIL        {t}" for t in fails] + [f"WARN        {t}" for t in dict.fromkeys(warns)]
    if plan.get("tested"):
        lines.append(f"Tested      {plan['tested']}")
    if plan.get("not_tested"):
        lines.append(f"Not tested  {plan['not_tested']}")
    lines += not_tested_lines(left)
    status = "FAIL" if fails else "PASS"
    lines.append(
        f"{status}{f' ({len(fails)} failed)' if fails else ''}"
        f"{f' ({len(dict.fromkeys(warns))} warnings)' if warns and not fails else ''}. Results: "
        f"{invocation}{os.sep}"
    )
    for line in screen_lines(lines, fails, list(dict.fromkeys(warns)), invocation):
        output.result(line)
    combined = {
        "schema": "qrosetta.cli/selftest@1",
        "cli_version": __version__,
        "created_at": output.utc_now(),
        "server": conn.url,
        "status": status,
        "selftest_version": plan.get("selftest_version"),
        "expected_sha256": plan.get("expected_sha256"),
        "backends_under_test": keys,
        "not_tested": [{"backend": k, "reason": why} for k, why in left],
        "image_probes": images,
        "jobs": jobs,
        "failures": fails,
        "warnings": list(dict.fromkeys(warns)),
        "cli_rules_applied": applied,
        "lines": lines,
    }
    results.write_json(os.path.join(invocation, results.SELFTEST_FILE), combined)
    if results.invocation_complete(invocation):
        results.update_latest(parent, invocation)
    data = {k: v for k, v in combined.items() if k not in ("schema", "cli_version")}
    data["results_dir"] = invocation
    return Result(Exit.SELFTEST_FAILED if fails else Exit.OK, data)
