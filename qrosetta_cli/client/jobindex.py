"""The job index (spec §6.19): $XDG_STATE_HOME/qrosetta/jobs.jsonl, one JSON line per event,
appended under an exclusive flock where fcntl exists. A job's state is its lines merged in
order; every entry names the server origin and absolute paths."""

import json
import os

from qrosetta_cli import config as cfgmod, output
from qrosetta_cli.client.transport import origin
from qrosetta_cli.errors import usage

try:
    import fcntl
except ImportError:
    fcntl = None


def path(env):
    return os.path.join(cfgmod.qr_dir("state", env), "jobs.jsonl")


def append(env, entry):
    """Add one line; the index is a record, so a failure to write it warns and goes on."""
    p = path(env)
    line = json.dumps({**entry, "at": output.utc_now()}, ensure_ascii=False) + "\n"
    try:
        os.makedirs(os.path.dirname(p), mode=0o700, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(line)
                fh.flush()
            finally:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        output.warn(f"Could not write the job index {p}: {exc.strerror}.", "job_index")


def entries(env):
    """Every job, its lines merged, in the order of first appearance."""
    merged = {}
    try:
        with open(path(env), encoding="utf-8") as fh:
            for line in fh:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and isinstance(item.get("job_id"), str):
                    merged.setdefault(item["job_id"], {}).update(item)
    except OSError:
        return []
    return list(merged.values())


def find(env, job_id, server_url=None):
    """The entry whose id is `job_id` or starts with it (8 characters or more), on `server_url`'s
    origin when given; None when there is none. Ambiguous prefixes are a usage error."""
    want = origin(server_url) if server_url else None
    hits = [e for e in entries(env)
            if (e["job_id"] == job_id or (len(job_id) >= 8 and e["job_id"].startswith(job_id)))
            and (want is None or e.get("server") == want)]
    exact = [e for e in hits if e["job_id"] == job_id]
    if exact:
        return exact[-1]
    if len(hits) > 1:
        raise usage(f"job:{job_id} matches {len(hits)} jobs; give more of the id.", hint="qrosetta jobs",
                    reason="ambiguous_job")
    return hits[0] if hits else None
