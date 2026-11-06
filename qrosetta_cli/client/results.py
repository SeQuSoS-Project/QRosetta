"""Results on disk (spec Q6): the results directory, one invocation directory per command with
plan.json, one directory per job with request.json, job.json, the saved server files,
SHA256SUMS and STATUS (written last, by rename), the invocation's SHA256SUMS over plan.json and
`latest`, both written only once every job of the invocation is saved. Result references (spec §5) resolve to these."""

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field

from qrosetta_cli import config as cfgmod, output
from qrosetta_cli.client import jobindex
from qrosetta_cli.errors import CliError, Exit, usage

DEFAULT_DIR = "./qrosetta-results"
LATEST = "latest"
COMPLETE = "complete"
COMPLETE_MINIMAL = "complete: minimal"
CRATE_DEFERRED = "crate-deferred"
JOB_FAILED = "job-failed"
JOB_LOST = "job-lost"
STATUS_FILE = "STATUS"
SUMS_FILE = "SHA256SUMS"
PLAN_FILE = "plan.json"
SELFTEST_FILE = "selftest.json"


def parent_dir(ctx):
    """--results-dir, else QROSETTA_RESULTS_DIR, else [results] dir, else ./qrosetta-results; absolute."""
    value = ctx.opt("results_dir") or ctx.env.get("QROSETTA_RESULTS_DIR") or ctx.cfg.get("results", "dir")
    return os.path.abspath(cfgmod.expand(value or DEFAULT_DIR, ctx.env))


def slugify(text, limit=40):
    """Lowercase ASCII letters, digits and hyphens, at most `limit` characters."""
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:limit].rstrip("-") or "run"


def stamp(now=None):
    return time.strftime("%Y%m%d-%H%M%SZ", time.gmtime(now))


def new_invocation(parent, slug, exact=None):
    """Create the invocation directory exclusively: `exact` (-o), else <stamp>-<slug> under
    `parent`, with -2, -3, ... on a clash."""
    if exact:
        path = os.path.abspath(exact)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            os.mkdir(path)
        except FileExistsError:
            if os.listdir(path):
                raise usage(
                    f"{path} already exists and is not empty.", hint="choose a new -o DIR", reason="output_exists"
                ) from None
        return path
    os.makedirs(parent, exist_ok=True)
    base = os.path.join(parent, f"{stamp()}-{slug}")
    for n in range(1, 1000):
        path = base if n == 1 else f"{base}-{n}"
        try:
            os.mkdir(path)
            return path
        except FileExistsError:
            continue
    raise CliError(f"Could not create a directory under {parent}.", Exit.INTERNAL, "results_dir")


def server_job_id(env, what):
    """The job id a server returned, when it is a canonical UUID; it names files and directories."""
    value = env.get("job_id") if isinstance(env, dict) else None
    try:
        valid = isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise CliError(
            f"{what} answered without a valid job id; nothing was written for it.",
            Exit.INCOMPATIBLE,
            "bad_job_id",
            hint="qrosetta info",
        )
    return value


def job_dir_name(kind, mode, job_id):
    """<mode|experiment-MODE|compile>-<first 8 characters of the job id>."""
    label = mode or "compile"
    if kind == "experiment":
        label = f"experiment-{mode}"
    return f"{label}-{job_id[:8]}"


def write_bytes(path, data):
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def write_json(path, obj):
    write_bytes(path, (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def write_status(job_dir, token):
    write_bytes(os.path.join(job_dir, STATUS_FILE), (token + "\n").encode("utf-8"))


def read_status(job_dir):
    try:
        with open(os.path.join(job_dir, STATUS_FILE), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_sums(directory):
    """SHA256SUMS in GNU format over the files directly in `directory`, other than STATUS and
    partial downloads."""
    names = sorted(
        n
        for n in os.listdir(directory)
        if n not in (STATUS_FILE, SUMS_FILE)
        and ".tmp" not in n
        and not n.endswith(".part")
        and os.path.isfile(os.path.join(directory, n))
    )
    lines = [f"{_sha256(os.path.join(directory, n))}  {n}" for n in names]
    write_bytes(os.path.join(directory, SUMS_FILE), ("\n".join(lines) + "\n").encode("utf-8"))


def write_sums(job_dir):
    """The job directory's SHA256SUMS: every file in it. plan.json, which each later job of the
    invocation rewrites, is in the invocation's own SHA256SUMS (`finish_invocation`)."""
    _write_sums(job_dir)


def job_dirs(invocation):
    """The job directories of an invocation, in the order their jobs were submitted."""
    plan = read_json(os.path.join(invocation, PLAN_FILE)) or {}
    order = [d for d in plan.get("job_dirs") or [] if os.path.isdir(os.path.join(invocation, d))]
    rest = sorted(
        d
        for d in os.listdir(invocation)
        if d not in order and os.path.isfile(os.path.join(invocation, d, "request.json"))
    )
    return [os.path.join(invocation, d) for d in order + rest]


def invocation_complete(invocation):
    """Every planned job was submitted and every job directory has its STATUS."""
    plan = read_json(os.path.join(invocation, PLAN_FILE)) or {}
    dirs = job_dirs(invocation)
    planned = plan.get("planned_jobs")
    if not dirs or (isinstance(planned, int) and len(dirs) < planned):
        return False
    return all(read_status(d) is not None for d in dirs)


def finish_invocation(parent, invocation):
    """Once every planned job of `invocation` is submitted and saved, write its SHA256SUMS over
    plan.json (and selftest.json), which no later step rewrites, then point `latest` at it.
    Returns whether the invocation was complete."""
    if not invocation_complete(invocation):
        return False
    _write_sums(invocation)
    update_latest(parent, invocation)
    return True


def update_latest(parent, invocation):
    """Point `latest` at `invocation` by symlink and rename(2); False where symlinks fail."""
    link = os.path.join(parent, LATEST)
    tmp = os.path.join(parent, f".{LATEST}.tmp{os.getpid()}")
    try:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        os.symlink(os.path.basename(invocation), tmp)
        os.replace(tmp, link)
        return True
    except OSError:
        return False


@dataclass
class Target:
    """What a result reference names: an invocation directory and its jobs, or one job."""

    invocation: str | None = None
    jobs: list = field(default_factory=list)
    source: str = ""


@dataclass
class JobRef:
    job_id: str
    dir: str | None = None
    entry: dict = field(default_factory=dict)

    def request(self):
        return read_json(os.path.join(self.dir, "request.json")) or {} if self.dir else self.entry

    def kind(self):
        return self.request().get("kind") or self.entry.get("kind")

    def mode(self):
        return self.request().get("mode") or self.entry.get("mode")


def job_from_dir(path):
    job = read_json(os.path.join(path, "job.json")) or {}
    req = read_json(os.path.join(path, "request.json")) or {}
    job_id = job.get("job_id") or req.get("job_id")
    if not job_id:
        raise CliError(
            f"{path} holds no job.json with a job id.", Exit.NOT_FOUND, "result_missing", hint="qrosetta jobs"
        )
    return JobRef(job_id, path)


def _from_path(path):
    path = os.path.abspath(path)
    if os.path.isfile(path):
        path = os.path.dirname(path)
    if os.path.isfile(os.path.join(path, "request.json")) or os.path.isfile(os.path.join(path, "job.json")):
        return Target(os.path.dirname(path), [job_from_dir(path)], "path")
    if os.path.isdir(path):
        dirs = job_dirs(path)
        if dirs or os.path.isfile(os.path.join(path, SELFTEST_FILE)):
            return Target(path, [job_from_dir(d) for d in dirs], "path")
    raise CliError(
        f"{path} is not a job or invocation directory.", Exit.NOT_FOUND, "result_missing", hint="qrosetta jobs"
    )


def _latest(ctx):
    parent = parent_dir(ctx)
    link = os.path.join(parent, LATEST)
    if os.path.isdir(link):
        return _from_path(os.path.realpath(link))
    candidates = []
    for entry in jobindex.entries(ctx.env):
        inv = entry.get("invocation")
        if inv and os.path.dirname(inv) == parent and os.path.isdir(inv) and invocation_complete(inv):
            candidates.append(inv)
    if not candidates:
        raise CliError(
            f"No complete results under {parent}.",
            Exit.NOT_FOUND,
            "result_missing",
            hint="qrosetta run CIRCUIT, or --result job:ID",
        )
    chosen = candidates[-1]
    output.progress(f"No {LATEST} link in {parent}; using {chosen}, the newest complete invocation in the job index.")
    return _from_path(chosen)


def resolve(ctx, ref, server_url=None):
    """The Target of a result reference: latest (default), job:ID, run:ID or a path."""
    if not ref or ref == LATEST:
        return _latest(ctx)
    if ref.startswith("run:"):
        raise usage(
            "Saved runs (run:ID) arrive with the history commands.",
            hint="qrosetta show summary --result job:ID",
            reason="run_reference_unavailable",
        )
    if ref.startswith("job:"):
        return job_target(ctx, ref[4:], server_url)
    if os.path.exists(ref):
        return _from_path(ref)
    if re.fullmatch(r"[0-9a-fA-F-]{8,}", ref):
        output.warn(f"{ref!r} is not a path; reading it as job:{ref}.", "bare_job_id")
        return job_target(ctx, ref, server_url)
    raise CliError(
        f"No result {ref!r}: not a path, latest, job:ID or run:ID.",
        Exit.NOT_FOUND,
        "result_missing",
        hint="qrosetta jobs",
    )


def job_target(ctx, job_id, server_url=None):
    entry = jobindex.find(ctx.env, job_id, server_url)
    if entry is None:
        if len(job_id) < 32:
            raise CliError(
                f"No job starting with {job_id!r} in the job index{f' for {server_url}' if server_url else ''}.",
                Exit.NOT_FOUND,
                "job_unknown",
                hint="qrosetta jobs",
            )
        return Target(None, [JobRef(job_id)], "job")
    d = entry.get("dir")
    return Target(
        entry.get("invocation"), [JobRef(entry["job_id"], d if d and os.path.isdir(d) else None, entry)], "job"
    )
