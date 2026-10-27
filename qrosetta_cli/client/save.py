"""Saving a finished job into its directory (spec Q6): job.json, then the save set (report,
summary, circuit texts, crate; an experiment's bundle instead), SHA256SUMS, and STATUS last.

On a local stack whose server offers gated saves, the report and the crate are requested with
?gated=true, admitted only while no dispatch is in flight; a busy gate defers the crate, which
`wait` finishes, saving ungated once the deferral reaches 10 minutes before the job's retention
ends. Every ungated save records whether /config showed other dispatches in flight."""

import calendar
import json
import os
import time

from qrosetta_cli import __version__, output
from qrosetta_cli.client import results, waiting
from qrosetta_cli.errors import CliError, Exit, usage

ITEMS = ("report", "summary", "circuits", "crate")
FILES = {
    "report": "report.json",
    "summary": "summary.json",
    "circuits": "circuit-texts.json",
    "crate": "ro-crate.zip",
    "bundle": "bundle.zip",
}
GATED_FEATURE = "gated_saves"
CIRCUIT_TEXTS_FEATURE = "circuit_texts"
REPORT_GATE_WAIT_SEC = 60
CRATE_GATE_WAIT_SEC = 30
DEFER_MARGIN_SEC = 600
BACKOFF_SEC = (2, 4, 8, 15, 30, 60)


def parse_items(values):
    """(items, minimal) from --save values; (None, False) when none were given."""
    if not values:
        return None, False
    items = []
    for value in values:
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if part not in ITEMS + ("minimal",):
                raise usage(
                    f"--save {part}: choose from {', '.join(ITEMS)} or minimal.",
                    hint="qrosetta run --help",
                    reason="save_set",
                )
            items.append(part)
    if "minimal" in items:
        if len(items) > 1:
            raise usage("--save minimal stands alone.", hint="qrosetta run --help", reason="save_set")
        return set(), True
    return set(items), False


def gated(conn):
    return conn.local and conn.has(GATED_FEATURE)


def save_set(conn, args):
    """(items, minimal, note): --save, else the default for this server, then --crate/--no-crate."""
    items, minimal = parse_items(getattr(args, "save", None))
    note = None
    if items is None:
        items = {"report", "summary"}
        if gated(conn):
            items.add("crate")
        elif conn.local and getattr(args, "crate", None) is None and not minimal:
            note = (
                "This server offers no gated saves, so the crate is not built by default (a crate built "
                "now could overlap other runs); --crate builds it."
            )
    if getattr(args, "crate", None) is True:
        items.add("crate")
        minimal = False
    elif getattr(args, "crate", None) is False:
        items.discard("crate")
    if "circuits" in items and not conn.has(CIRCUIT_TEXTS_FEATURE):
        raise CliError(
            "--save circuits needs a server with GET /jobs/{id}/circuit-texts.",
            Exit.INCOMPATIBLE,
            "feature_missing",
            hint="drop circuits from --save",
        )
    return items, minimal, note


def crate_options(args):
    """The POST /jobs/{id}/export body from the crate flags."""
    body: dict = {}
    if getattr(args, "statevectors", False):
        body["include_statevectors"] = True
    for flag, field in (
        ("author", "author_name"),
        ("affiliation", "author_affiliation"),
        ("name", "name"),
        ("circuit_name", "circuit_name"),
    ):
        if getattr(args, flag, None):
            body[field] = getattr(args, flag)
    items: list = []
    for spec in getattr(args, "item", None) or []:
        if spec.startswith("@"):
            try:
                with open(spec[1:], encoding="utf-8") as fh:
                    loaded = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                raise usage(f"--item {spec}: {exc}", hint="qrosetta run --help", reason="crate_item") from None
            items += loaded if isinstance(loaded, list) else loaded.get("items", [])
            continue
        view, sep, formats = spec.rpartition("=")
        if not sep or not view or not formats:
            raise usage(
                f"--item takes VIEW=FMT[,FMT] or @FILE, not {spec!r}.", hint="qrosetta run --help", reason="crate_item"
            )
        items.append({"view": view, "formats": [f for f in formats.split(",") if f]})
    if items:
        body["publication_artifacts"] = {"items": items}
    return body


def _gate_busy(exc):
    return exc.http_status == 409 and "gate_busy" in json.dumps(exc.detail, default=str)


def _epoch(utc_text):
    try:
        return calendar.timegm(time.strptime(utc_text, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


class Saver:
    """Saves jobs of one server with one save set. `patient` (wait) keeps a busy gate's
    crate deferred until its deadline; otherwise (run) a busy gate defers it at once."""

    def __init__(self, conn, items, minimal=False, crate_body=None, confirm_large=None, patient=False):
        self.conn = conn
        self.items = set(items)
        self.minimal = minimal
        self.crate_body = crate_body or {}
        self.confirm_large = confirm_large
        self.patient = patient

    def _in_flight(self):
        try:
            return self.conn.dispatches_in_flight(self.conn.refresh_config())
        except CliError:
            return 0

    def _download(self, method, path, dest, payload=None, gate_wait=None, fallback=False):
        """(saved, concurrent). With `gate_wait` (seconds) the request is gated; when the gate
        stays busy that long it is sent ungated if `fallback`, else saved is False."""
        if gate_wait is not None:
            start = waiting.clock()
            attempt = 0
            while True:
                delay = BACKOFF_SEC[min(attempt, len(BACKOFF_SEC) - 1)]
                attempt += 1
                try:
                    self.conn.download(
                        method, path, dest, payload, query={"gated": "true"}, confirm_large=self.confirm_large
                    )
                    return True, False
                except CliError as exc:
                    if not _gate_busy(exc):
                        raise
                left = gate_wait - (waiting.clock() - start)
                if left <= 0:
                    if fallback:
                        break
                    return False, False
                output.progress(
                    f"{os.path.basename(dest)} waiting for an idle server: {self._in_flight()} runs in flight."
                )
                waiting.pause(min(delay, left))
        concurrent = self._in_flight() > 0
        self.conn.download(method, path, dest, payload, confirm_large=self.confirm_large)
        return True, concurrent

    def save(self, job_dir, job_id, kind, final_env, previous=None):
        """Save one finished job; returns {status, files, summary, crate, concurrent, partial}."""
        previous = previous or {}
        ttl = self.conn.limit("job_ttl_sec")
        failed = final_env.get("status") == "failed"
        record = {k: v for k, v in final_env.items() if k != "results"}
        record.update(
            {
                "server": self.conn.url,
                "saved_by": f"qrosetta {__version__}",
                "job_ttl_sec": ttl,
                "concurrent_with_other_jobs": bool(previous.get("concurrent_with_other_jobs")),
                "crate_deferred_sec": previous.get("crate_deferred_sec"),
                "crate_deferred_since": previous.get("crate_deferred_since"),
            }
        )
        files, partial, summary, crate = {}, [], None, "not requested"
        has_report = not (failed and final_env.get("results") is None)

        def note_failure(name, exc):
            reason = "expired-before-save" if exc.code == Exit.NOT_FOUND else "download-failed"
            partial.append(f"{name} {reason}")
            output.warn(f"{name} not saved: {exc.message}", "save_failed")

        def fetch(item, method, path, payload=None, gate_wait=None, fallback=False):
            name = FILES[item]
            if os.path.isfile(os.path.join(job_dir, name)):
                files[item] = name
                return True
            try:
                saved, concurrent = self._download(
                    method, path, os.path.join(job_dir, name), payload, gate_wait, fallback
                )
            except CliError as exc:
                if exc.http_status == 409 and failed:
                    return True
                note_failure(name, exc)
                return True
            except OSError as exc:
                partial.append(f"{name} download-failed")
                output.warn(f"{name} not saved: {exc.strerror or exc}.", "save_failed")
                return True
            if saved:
                files[item] = name
                record["concurrent_with_other_jobs"] = record["concurrent_with_other_jobs"] or concurrent
            return saved

        use_gate = gated(self.conn) and "crate" in self.items
        if not self.minimal and has_report:
            if kind == "experiment":
                fetch("bundle", "GET", f"/experiments/{job_id}/bundle")
            else:
                if "report" in self.items:
                    fetch(
                        "report",
                        "GET",
                        f"/jobs/{job_id}/report",
                        gate_wait=REPORT_GATE_WAIT_SEC if use_gate else None,
                        fallback=True,
                    )
                if "summary" in self.items:
                    fetch("summary", "GET", f"/jobs/{job_id}/summary")
                if "circuits" in self.items:
                    fetch("circuits", "GET", f"/jobs/{job_id}/circuit-texts")
                if "crate" in self.items:
                    crate = self._crate(job_dir, job_id, record, ttl, fetch, use_gate)
        if "summary" in files:
            summary = results.read_json(os.path.join(job_dir, FILES["summary"]))
        results.write_json(os.path.join(job_dir, "job.json"), record)
        results.write_sums(job_dir)
        if failed:
            token = results.JOB_FAILED
        elif partial:
            token = "partial: " + "; ".join(partial)
        elif crate == "deferred":
            token = results.CRATE_DEFERRED
        elif self.minimal:
            token = results.COMPLETE_MINIMAL
        else:
            token = results.COMPLETE
        results.write_status(job_dir, token)
        return {
            "status": token,
            "files": files,
            "summary": summary,
            "crate": crate,
            "concurrent": record["concurrent_with_other_jobs"],
            "partial": partial,
            "record": record,
        }

    def _crate(self, job_dir, job_id, record, ttl, fetch, use_gate):
        path = os.path.join(job_dir, FILES["crate"])
        if not use_gate:
            fetch("crate", "POST", f"/jobs/{job_id}/export", self.crate_body)
            return "saved" if os.path.isfile(path) else "failed"
        since = record.get("crate_deferred_since") or output.utc_now()
        start = _epoch(since) or time.time()
        deadline = start + (ttl or 1800) - DEFER_MARGIN_SEC
        wait = max(0, deadline - time.time()) if self.patient else CRATE_GATE_WAIT_SEC
        if fetch("crate", "POST", f"/jobs/{job_id}/export", self.crate_body, gate_wait=wait):
            if record.get("crate_deferred_since"):
                record["crate_deferred_sec"] = round(time.time() - start, 1)
            return "saved" if os.path.isfile(path) else "failed"
        if self.patient:
            output.progress(
                "The server stayed busy until 10 minutes before the job expires; building the crate "
                "now, beside the runs in flight (recorded in job.json)."
            )
            fetch("crate", "POST", f"/jobs/{job_id}/export", self.crate_body)
            record["crate_deferred_sec"] = round(time.time() - start, 1)
            return "saved" if os.path.isfile(path) else "failed"
        record["crate_deferred_since"] = since
        return "deferred"
