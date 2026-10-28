"""`qrosetta images` (list) and `images verify` (spec §6.6). Verify reads only engine inspect
data: the qrosetta labels, the baked commit, the identity the build wrote (from the image's
build history), and in installed mode the repo digest or image id the release manifest records,
plus the cosign signature when cosign is installed. It runs no container."""

import json

from qrosetta_cli import manifest as mf
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import archive, serve, signatures
from qrosetta_cli.stack import ownership as own
from qrosetta_cli.stack import project as st
from qrosetta_cli.stack.actions import human_bytes
from qrosetta_cli.stack.status import classify, image_text


def selected(stack, names, profile, cfg):
    return serve.requested_services(stack, names, profile, cfg) or list(stack.services)


def rows(engine, stack, services):
    """One record per service: its image's classification, size and whether qrosetta owns it."""
    refs = {s: stack.image_for(s) for s in services}
    found = st.find_images(engine, list(refs.values()))
    out = []
    for service in services:
        ref, img = refs[service], found.get(refs[service])
        record = (
            classify(stack, ref, img, service)
            if img
            else {"state": "missing", "ref": ref, "digest": None, "image_id": None, "git_sha": None, "release": None}
        )
        refusal = own.image_refusal(stack, service, ref, img) if img else None
        out.append(
            dict(
                record,
                id=stack.services[service].id,
                kind=stack.kind_of(service),
                compose_service=service,
                size_bytes=img.size if img else None,
                owned=bool(img) and refusal is None,
                refusal=refusal,
            )
        )
    return out, found


def cmd_images_list(ctx):
    from qrosetta_cli.stack.commands import open_stack

    mode, engine, stack = open_stack(ctx)
    table, _ = rows(engine, stack, selected(stack, [], ctx.opt("profile"), ctx.cfg))
    lines = [("SERVICE", "KIND", "STATE", "SIZE", "IMAGE")]
    for r in table:
        note = "" if r["owned"] or r["state"] == "missing" else f" (not this stack's: {r['refusal']})"
        lines.append(
            (
                r["id"],
                r["kind"],
                r["state"],
                human_bytes(r["size_bytes"]) if r["size_bytes"] else "",
                image_text(r) + note,
            )
        )
    widths = [max(len(row[i]) for row in lines) for i in range(len(lines[0]))]
    for row in lines:
        result("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    withheld = mf.not_distributable(stack.release)
    if withheld:
        result(f"\nNot published by the release (licence): {', '.join(sorted(withheld))}; a checkout builds them.")
    missing = [r["id"] for r in table if r["state"] == "missing"]
    if missing:
        how = "qrosetta pull" if stack.release else "qrosetta build"
        progress(
            f"{len(missing)} missing: `{how} {' '.join(missing)}`"
            + (" or `qrosetta images load DIR`." if stack.release else ".")
        )
    return Result(
        0,
        {
            "project": stack.name,
            "mode": mode.name,
            "release": (stack.release or {}).get("platform_version"),
            "images": [
                {
                    k: r[k]
                    for k in (
                        "id",
                        "kind",
                        "compose_service",
                        "state",
                        "ref",
                        "digest",
                        "image_id",
                        "git_sha",
                        "release",
                        "size_bytes",
                        "owned",
                    )
                }
                for r in table
            ],
            "not_published": sorted(withheld),
        },
    )


def history(engine, image_id):
    """The created-by text of each build step, newest first, or None when the engine cannot say."""
    out = engine.cli("image", "history", "--no-trunc", "--format", "{{json .CreatedBy}}", image_id)
    if out.returncode != 0:
        return None
    steps = []
    for line in out.stdout.splitlines():
        try:
            steps.append(json.loads(line))
        except json.JSONDecodeError:
            steps.append(line)
    return [s if isinstance(s, str) else "" for s in steps]


def _check(checks, name, status, detail):
    checks.append({"check": name, "status": status, "detail": detail})


def image_checks(engine, stack, row, img, require_signature, env):
    """[{check, status PASS|WARN|FAIL|SKIP, detail}] for one present image."""
    checks: list = []
    release = stack.release
    service, sid = row["compose_service"], row["id"]
    _check(
        checks,
        "labels",
        "PASS" if row["owned"] else "FAIL",
        f"org.qrosetta.image.project={stack.name}, org.qrosetta.service={service}"
        if row["owned"]
        else f"{row['ref']} {row['refusal']}; `start` would run it",
    )
    sha = img.git_sha
    dirty = sha.endswith("-dirty")
    _check(
        checks,
        "commit",
        "FAIL" if sha == "unknown" or (dirty and release) else "WARN" if dirty else "PASS",
        "no baked commit (QROSETTA_IMAGE_GIT_SHA)"
        if sha == "unknown"
        else f"{sha}: source not identifiable"
        if dirty
        else sha,
    )
    if row["kind"] in ("runner", "compiler"):
        steps = history(engine, img.id)
        ident = archive.identity_from_history(steps) if steps is not None else None
        if steps is None:
            _check(checks, "identity", "FAIL", "the engine reported no build history for the image")
        elif ident is None:
            _check(
                checks,
                "identity",
                "FAIL",
                f"no build step wrote {archive.IDENTITY_PATH} (an image built before images recorded their source)",
            )
        else:
            problems = []
            if ident["git_sha"] != sha:
                problems.append(f"identity commit {ident['git_sha']} differs from the baked {sha}")
            if release:
                if ident["source"] != "release":
                    problems.append(f"source {ident['source']}, not release")
                if ident["release"] != release.get("platform_version"):
                    problems.append(f"release {ident['release']}, not {release.get('platform_version')}")
            elif ident["source"] not in ("built_locally", "release"):
                problems.append(f"source {ident['source']!r} is neither built_locally nor release")
            _check(
                checks,
                "identity",
                "FAIL" if problems else "PASS",
                "; ".join(problems)
                or f"source={ident['source']} release={ident['release'] or '-'} git_sha={ident['git_sha']}",
            )
    if release:
        sid_known = sid in release.get("services", {})
        if row["state"] in ("pulled", "loaded"):
            _check(
                checks,
                "release",
                "PASS",
                f"{row['state']} {release.get('platform_version')}: "
                + (f"repo digest {row['digest']}" if row["state"] == "pulled" else f"image id {img.id}"),
            )
        else:
            _check(
                checks,
                "release",
                "FAIL",
                f"neither the repo digest nor the image id the release manifest records for {sid}"
                if sid_known
                else f"{sid} is not in the release manifest",
            )
        if release.get("git_sha") and sha not in ("unknown", release["git_sha"]):
            _check(checks, "release commit", "FAIL", f"baked {sha}, release built from {release['git_sha']}")
        if sid == "api" and img.env.get("QROSETTA_VERSION") != release.get("platform_version"):
            _check(
                checks,
                "platform version",
                "FAIL",
                f"QROSETTA_VERSION={img.env.get('QROSETTA_VERSION')}, release {release.get('platform_version')}",
            )
        ref = mf.published_refs(release).get(sid)
        status, detail = signatures.verify(engine, release, ref, env) if ref else ("unavailable", "no digest")
        mapping = {"verified": "PASS", "rejected": "FAIL", "unchecked": "WARN", "unavailable": "SKIP"}
        state = mapping[status]
        if require_signature and status != "verified":
            state = "FAIL"
        _check(checks, "signature", state, detail)
    return checks


def cmd_images_verify(ctx):
    from qrosetta_cli.stack.commands import open_stack

    args = ctx.args
    mode, engine, stack = open_stack(ctx)
    if args.require_signature and not stack.release:
        raise usage(
            "--require-signature applies to release images; a checkout runs the images it builds, "
            "which carry no signature.",
            hint="qrosetta images verify",
            reason="no_release",
        )
    services = selected(stack, args.services, args.profile, ctx.cfg)
    table, found = rows(engine, stack, services)
    named = bool(args.services or args.profile)
    report, failed = [], []
    for r in table:
        img = found.get(r["ref"])
        if img is None:
            entry = {
                "id": r["id"],
                "state": "missing",
                "checks": [{"check": "present", "status": "FAIL" if named else "SKIP", "detail": "no image"}],
            }
        else:
            entry = {
                "id": r["id"],
                "state": r["state"],
                "image_id": img.id,
                "checks": image_checks(engine, stack, r, img, args.require_signature, ctx.env),
            }
        report.append(entry)
        bad = [c for c in entry["checks"] if c["status"] == "FAIL"]
        if bad:
            failed.append(r["id"])
        result(f"{r['id']}: {entry['state']}")
        for c in entry["checks"]:
            result(f"  {c['status']:<4}  {c['check']}: {c['detail']}")
    data = {
        "project": stack.name,
        "mode": mode.name,
        "release": (stack.release or {}).get("platform_version"),
        "images": report,
        "failed": failed,
    }
    present = sum(1 for e in report if e["state"] != "missing")
    if failed:
        raise CliError(
            f"{len(failed)} of {len(report)} images failed a check: {', '.join(failed)}.",
            Exit.ENGINE,
            "images_unverified",
            data=data,
            hint=("qrosetta pull " if stack.release else "qrosetta build ") + " ".join(failed),
        )
    result(f"\n{present} of {len(report)} images present; every check of those passed.")
    return Result(0, data)
