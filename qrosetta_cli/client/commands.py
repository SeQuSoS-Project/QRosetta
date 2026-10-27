"""`qrosetta api`: one request through the selected server, with its token, the envelope and the
exit codes (spec §6.23)."""

import json
import os
import sys

from qrosetta_cli import output
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")
QUERY_METHODS = ("GET", "DELETE", "HEAD")
ROUTES_HINT = "qrosetta api GET /openapi.json"


def status_error(status, retry_after=None):
    """(exit code, reason, hint) for an HTTP status that is not success."""
    if status in (400, 413, 422):
        return Exit.REFUSED, {413: "request_too_large", 422: "request_invalid"}.get(status, "refused"), ROUTES_HINT
    if status in (401, 403):
        return (Exit.AUTH, "unauthorised" if status == 401 else "forbidden",
                "set QROSETTA_TOKEN to a token from POST /auth/token (`qrosetta login` arrives with the run commands)")
    if status == 404:
        return Exit.NOT_FOUND, "not_found", ROUTES_HINT
    if status in (429, 503):
        wait = f" after {retry_after} s" if retry_after else " later"
        return Exit.BUSY, "rate_limited" if status == 429 else "unavailable", f"run the same command again{wait}"
    if status >= 500:
        return Exit.UNREACHABLE, "server_error", "qrosetta logs api --tail 50 (local stack), or ask the server's operator"
    return Exit.REFUSED, "refused", ROUTES_HINT


def parse_value(text):
    """A JSON literal (number, true/false/null, array, object) as itself; anything else a string."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def parse_fields(pairs):
    fields = {}
    for pair in pairs or []:
        key, sep, value = pair.rpartition("=")
        if not sep or not key:
            raise usage(f"-f takes KEY=VALUE, not {pair!r}.", hint="qrosetta api --help")
        fields[key] = value
    return fields


def read_input(source, stdin):
    if source == "-":
        data = getattr(stdin, "buffer", stdin).read()
        return data.encode() if isinstance(data, str) else data
    try:
        with open(source, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise CliError(f"Cannot read {source}: {exc.strerror}.", Exit.NOT_FOUND, "input_missing",
                       hint="qrosetta api METHOD PATH --input FILE, with FILE readable") from None


def cmd_api(ctx):
    args = ctx.args
    method = args.method.upper()
    if method not in METHODS:
        raise usage(f"Method {args.method!r} is not one of {', '.join(METHODS)}.", hint="qrosetta api --help")
    if not args.path.startswith("/"):
        raise usage(f"PATH must start with '/', not {args.path!r}.", hint=f"qrosetta api {method} /{args.path}")
    fields = parse_fields(args.field)
    body, query, headers = None, None, {}
    if args.input is not None:
        if fields and method not in QUERY_METHODS:
            raise usage("Give the body with --input or with -f, not both.", hint="qrosetta api --help")
        body = read_input(args.input, ctx.stdin)
        headers["Content-Type"] = "application/json"
    if fields:
        if method in QUERY_METHODS:
            query = fields
        else:
            body = json.dumps({k: parse_value(v) for k, v in fields.items()}, ensure_ascii=False).encode()
            headers["Content-Type"] = "application/json"
    transport = ctx.transport(with_token=not args.anonymous)
    resp = transport.request(method, args.path, query=query, body=body, headers=headers)
    parsed = resp.json()
    if resp.status >= 400:
        code, reason, hint = status_error(resp.status, resp.headers.get("retry-after"))
        detail = parsed if parsed is not None else resp.body.decode("utf-8", "replace")
        summary = detail.get("detail", detail) if isinstance(detail, dict) else detail
        raise CliError(f"{method} {args.path} answered HTTP {resp.status}: {summary}", code, reason, hint,
                       http_status=resp.status, detail=detail)
    if args.output and args.output != "-":
        path = os.path.abspath(args.output)
        with open(path, "wb") as fh:
            fh.write(resp.body)
        output.progress(f"Wrote {len(resp.body)} bytes to {path}")
        return Result(0, {"path": path, "http_status": resp.status, "content_type": resp.content_type})
    if output.json_mode():
        data = parsed if parsed is not None else {"text": resp.body.decode("utf-8", "replace")}
        return Result(0, data)
    output.raw(resp.body)
    if resp.body and not resp.body.endswith(b"\n") and sys.stdout.isatty():
        output.raw(b"\n")
    return Result(0, None)
