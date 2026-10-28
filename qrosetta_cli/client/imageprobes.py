"""The self-test's image probes (spec §6.17 step 2), read through the server: one fresh probe
round of GET /runners and one of GET /compilers (S8), each image's row checked for an answer,
the registry fields the self-test compares results with, and the commit the image reports
against the API's. The server probes no service with a dispatch in flight and serves cached
rows during an exclusive run; those images are SKIP."""

from qrosetta_cli import localstack, output
from qrosetta_cli.errors import CliError, Exit

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
PRECISIONS = ("complex64", "complex128")
ORDERINGS = ("lsb", "msb")
PARTS = ("statevector", "measured")
UNIDENTIFIED = ("", "unknown", "not recorded")
ERROR_KINDS = {
    "dns": "the API cannot resolve it on the internal network",
    "connect": "it does not accept connections yet (its SDK may still be loading)",
    "timeout": "it did not answer within 5 s",
    "http": "it answered with an error status",
}


def probe_headers(conn, env):
    """The lifecycle token's header for a local server when the connection sends no sign-in."""
    if not conn.local or getattr(conn.transport, "token", None):
        return None
    return localstack.token_headers(env) or None


def fresh_rows(conn, path, headers):
    """(rows, None) from a fresh probe round, else (cached rows, why they are not fresh)."""
    try:
        rows = conn.get(path, query={"fresh": "true"}, headers=headers, what=f"GET {path}?fresh=true")
    except CliError as exc:
        if exc.code not in (Exit.AUTH, Exit.BUSY):
            raise
        why = (
            "fresh probes are rate-limited (6 a minute)"
            if exc.code == Exit.BUSY
            else "fresh probes need the lifecycle token of a stack `qrosetta start` started, or a sign-in"
        )
        return conn.get(path), why
    if not isinstance(rows, list):
        raise CliError(
            f"GET {path} answered with {type(rows).__name__}, not a list.",
            Exit.INCOMPATIBLE,
            "unexpected_response",
            hint="qrosetta info",
        )
    if rows and not any(isinstance(r, dict) and "fresh" in r for r in rows):
        return rows, "this server has no on-demand probes"
    return rows, None


def _answers(row):
    if row is None:
        return FAIL, "the server does not list it"
    if row.get("reason") == "busy":
        return SKIP, "a run is using it, so it was not probed"
    if row.get("reason") == "exclusive_run":
        return SKIP, "an exclusive run holds the server, so it was not probed"
    if not row.get("available"):
        kind = row.get("error_kind")
        return FAIL, ERROR_KINDS.get(kind) or f"not available ({row.get('unavailable_reason') or 'no reason given'})"
    if row.get("error_kind"):
        return FAIL, ERROR_KINDS.get(row["error_kind"], row["error_kind"])
    return PASS, f"answered at {row.get('probed_at') or 'the probe round'}"


def _registry(row):
    bad, parts = [], []
    for part in PARTS:
        precision = (row.get("precision") or {}).get(part, "missing")
        ordering = (row.get("qubit_ordering") or {}).get(part, "missing")
        if precision is not None and precision not in PRECISIONS:
            bad.append(f"{part} precision {precision}")
        if ordering is not None and ordering not in ORDERINGS:
            bad.append(f"{part} qubit ordering {ordering}")
        parts.append(f"{part} {precision or 'set at run time'}, {ordering or 'set at run time'}")
    if bad:
        return FAIL, "the registry declares " + "; ".join(bad)
    return PASS, "; ".join(parts)


def _commit(row, api_sha):
    versions = row.get("versions") or {}
    identity = versions.get("image_identity") or {}
    reported = [v for v in (identity.get("git_sha"), versions.get("image_git_sha")) if isinstance(v, str)]
    if not reported:
        return (
            SKIP,
            (
                "its probe row does not carry the image's commit (the API and the images report it from "
                "this version on; `qrosetta build` rebuilds them)"
            ),
            None,
        )
    sha = next((v for v in reported if v not in UNIDENTIFIED), reported[0])
    if sha in UNIDENTIFIED:
        return FAIL, "the image does not record the commit it was built from", sha
    if sha.endswith("-dirty"):
        return FAIL, f"built from uncommitted changes ({sha}): source not identifiable", sha
    source = identity.get("source") if identity.get("source") not in UNIDENTIFIED else None
    built = f"{source.replace('_', ' ')} from {sha}" if source else f"built from {sha}"
    if api_sha and api_sha != sha:
        return WARN, f"{built}; the API image is from {api_sha} (a mixed stack)", sha
    return PASS, f"{built}{', as the API' if api_sha else ''}", sha


def check_image(row, kind, api_sha, key=None):
    """One image's probe result: its checks and the worst status among them (SKIP aside)."""
    checks = []
    status, reason = _answers(row)
    checks.append({"check": "answers", "status": status, "reason": reason})
    if row is not None and status != FAIL:
        if kind == "runner":
            status, reason = _registry(row)
            checks.append({"check": "registry", "status": status, "reason": reason})
        status, reason, sha = _commit(row, api_sha)
        checks.append({"check": "commit", "status": status, "reason": reason})
    else:
        sha = None
    statuses = {c["status"] for c in checks}
    worst = FAIL if FAIL in statuses else WARN if WARN in statuses else PASS
    versions = (row or {}).get("versions") or {}
    return {
        "id": key or (row or {}).get("id"),
        "kind": kind,
        "status": worst,
        "fresh": (row or {}).get("fresh"),
        "probed_at": (row or {}).get("probed_at"),
        "image_git_sha": sha,
        "image_source": (versions.get("image_identity") or {}).get("source"),
        "checks": checks,
    }


def probe_images(conn, env, runner_rows, runner_why, keys):
    """The image-probe block of selftest.json: the runners under test from `runner_rows` (one
    fresh round already read) and the available compilers from one more round."""
    api_sha = (conn.block or {}).get("git_sha")
    if runner_why:
        return {"status": "not_probed", "reason": runner_why, "server_git_sha": api_sha, "images": []}
    by_id = {r.get("id"): r for r in runner_rows if isinstance(r, dict)}
    images = [check_image(by_id.get(k), "runner", api_sha, k) for k in keys]
    compiler_rows, why = fresh_rows(conn, "/compilers", probe_headers(conn, env))
    if why:
        output.progress(f"Compiler images not probed: {why}.")
    else:
        images += [
            check_image(r, "compiler", api_sha)
            for r in compiler_rows
            if isinstance(r, dict) and r.get("enabled") and (r.get("available") or r.get("reason") == "busy")
        ]
    return {
        "status": "probed",
        "reason": None if not why else f"compilers: {why}",
        "server_git_sha": api_sha,
        "images": images,
    }


def lines_and_findings(block):
    """(output lines, failures, warnings) for the selftest's Images line."""
    if block["status"] == "skipped":
        return ["Images      skipped (--no-images)"], [], []
    if block["status"] == "not_probed":
        return [f"Images      not probed: {block['reason']}"], [], []
    images = block["images"]
    counts = {s: sum(i["status"] == s for i in images) for s in (PASS, WARN, FAIL)}
    runners = [i["id"] for i in images if i["kind"] == "runner"]
    compilers = [i["id"] for i in images if i["kind"] == "compiler"]
    probed = f"{len(runners)} runner{'s' * (len(runners) != 1)}"
    if compilers:
        probed += f" and {len(compilers)} compiler{'s' * (len(compilers) != 1)}"
    lines = [f"Images      {probed} probed now: {counts[PASS]} passed, {counts[WARN]} warned, {counts[FAIL]} failed"]
    skipped: dict = {}
    for image in images:
        for c in image["checks"]:
            if c["status"] == SKIP:
                skipped.setdefault((c["check"], c["reason"]), []).append(image["id"])
    for (check, reason), ids in skipped.items():
        lines.append(f"            {check} not checked for {', '.join(ids)}: {reason}")
    fails, warns = [], []
    for image in images:
        for c in image["checks"]:
            text = f"image {c['check']} ({image['id']}): {c['reason']}"
            if c["status"] == FAIL:
                fails.append(text)
            elif c["status"] == WARN:
                warns.append(text)
    return lines, fails, warns
