"""`qrosetta show circuits` and `qrosetta show diff` (spec §6.20, experimental): the circuit texts
of the page's Circuits view, from the job's saved circuit-texts.json, else GET
/jobs/{id}/circuit-texts (kept in the job's directory), else the saved crate's circuit files.
The diff is Python's difflib unified diff, for display only."""

import difflib
import json
import os
import re
import zipfile

from qrosetta_cli import output
from qrosetta_cli.client import results
from qrosetta_cli.client.conn import Conn
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage

FEATURE = "circuit_texts"
TEXTS_FILE = "circuit-texts.json"
CRATES = ("ro-crate.zip", "ro-crate.client-supplied.zip")
IGNORABLE = ("comments", "header", "whitespace")
SOURCE_TEXT = {"server_job": "server job", "saved_run": "saved run", "client_supplied": "client-supplied report"}
_HEADER = (re.compile(r"^\s*OPENQASM\s+2\.0\s*;\s*$"), re.compile(r'^\s*include\s+"qelib1\.inc"\s*;\s*$'))


class Server:
    """The selected server, connected on first use (offline views never connect)."""

    def __init__(self, ctx):
        self.ctx = ctx
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = Conn(self.ctx)
        return self._conn


def one_job(ctx, server):
    """The one job `--result` (and `--job MODE`) names."""
    ref = ctx.opt("result")
    target = results.resolve(ctx, ref, server.conn.url if (ref or "").startswith("job:") else None)
    jobs = target.jobs
    if ctx.opt("job"):
        jobs = [j for j in jobs if (j.mode() or "compile") == ctx.opt("job")]
    if len(jobs) != 1:
        modes = ", ".join(j.mode() or "compile" for j in target.jobs) or "none"
        raise usage(
            f"This result holds {len(target.jobs)} jobs ({modes}); choose one with --job MODE.",
            hint="qrosetta show circuits --job statevector",
            reason="several_jobs",
        )
    return jobs[0]


def keep(job_dir, name, data):
    """Write `name` into a saved job's directory and refresh its SHA256SUMS."""
    results.write_bytes(os.path.join(job_dir, name), data)
    results.write_sums(job_dir)


def _crate_file(job_dir):
    for name in CRATES:
        path = os.path.join(job_dir or "", name)
        if job_dir and os.path.isfile(path):
            return path
    return None


def _pane(pane_id, kind, key, text):
    return {"id": pane_id, "kind": kind, "key": key, "group": None, "text": text}


MAX_CRATE_MEMBERS = 65_535
MAX_CRATE_DIRECTORY_BYTES = 64 << 20
MAX_CRATE_METADATA_BYTES = 256 << 20
MAX_CRATE_TEXT_BYTES = 1 << 30
_EOCD = b"PK\x05\x06"


def _crate_error(path, why):
    return CliError(
        f"{path} cannot be read as an RO-Crate: {why}.",
        Exit.INCOMPATIBLE,
        "crate_unreadable",
        hint="qrosetta export crate",
    )


def _check_directory(path):
    """Refuse a ZIP whose end record declares more members or a larger central directory than
    a crate has, before zipfile reads that directory."""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - (1 << 16) - 22))
        tail = fh.read()
    at = tail.rfind(_EOCD)
    if at < 0 or len(tail) - at < 22:
        raise _crate_error(path, "it is not a ZIP file")
    entries = int.from_bytes(tail[at + 10 : at + 12], "little")
    directory = int.from_bytes(tail[at + 12 : at + 16], "little")
    if entries >= MAX_CRATE_MEMBERS or directory > MAX_CRATE_DIRECTORY_BYTES:
        raise _crate_error(
            path,
            f"it declares more than {MAX_CRATE_MEMBERS - 1} files or a file list over "
            f"{MAX_CRATE_DIRECTORY_BYTES >> 20} MiB",
        )


def _read_member(zf, info, limit, path):
    if info.file_size > limit:
        raise _crate_error(path, f"{info.filename} is larger than {limit >> 20} MiB")
    return zf.read(info)


def crate_texts(path):
    """The panes a crate's circuit files give, per circuit: circuit.qasm (circuits/<task>.qasm),
    dispatched_circuits/ and transpiled_circuits/ per backend, the compile input and
    compiled_circuits/. Dispatched panes are per backend, since a crate names no groups. A
    ZIP with too many files, a metadata file or circuit texts over the size caps, or no
    ro-crate-metadata.json is refused (exit 12) before its contents are read."""
    _check_directory(path)
    try:
        with zipfile.ZipFile(path) as zf:
            infos = {i.filename: i for i in zf.infolist()}
            if len(infos) >= MAX_CRATE_MEMBERS:
                raise _crate_error(path, f"it holds more than {MAX_CRATE_MEMBERS - 1} files")
            meta_name = next((n for n in infos if n.endswith("/ro-crate-metadata.json")), None)
            if meta_name is None:
                raise _crate_error(path, "it has no ro-crate-metadata.json")
            top = meta_name.split("/", 1)[0]
            metadata = json.loads(_read_member(zf, infos[meta_name], MAX_CRATE_METADATA_BYTES, path))
            entities = metadata.get("@graph", []) if isinstance(metadata, dict) else []
            graph = {e.get("@id"): e for e in entities if isinstance(e, dict)}
            parts = [p.get("@id") for p in (graph.get("./") or {}).get("hasPart", []) if isinstance(p, dict)]
            wanted = [
                infos[f"{top}/{p}"]
                for p in dict.fromkeys(parts)
                if isinstance(p, str) and p.endswith(".qasm") and f"{top}/{p}" in infos
            ]
            if sum(i.file_size for i in wanted) > MAX_CRATE_TEXT_BYTES:
                raise _crate_error(path, f"its circuit files hold more than {MAX_CRATE_TEXT_BYTES >> 30} GiB")
            texts = {i.filename[len(top) + 1 :]: zf.read(i).decode("utf-8") for i in wanted}
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, OSError, EOFError) as exc:
        raise _crate_error(path, f"{type(exc).__name__}") from None
    tasks = [p[len("circuits/") : -len(".qasm")] for p in parts if isinstance(p, str) and p.startswith("circuits/")]

    def panes(task):
        scope = f"{task}/" if task else ""
        out = []
        inp = f"circuits/{task}.qasm" if task else "circuit.qasm"
        if inp in texts:
            out.append(_pane("input", "input", None, texts[inp]))
        for folder, kind in (("dispatched_circuits", "dispatched"), ("transpiled_circuits", "executed")):
            prefix = f"{folder}/{scope}"
            for p in texts:
                if p.startswith(prefix) and "/" not in p[len(prefix) :]:
                    key = p[len(prefix) : -len(".qasm")]
                    if kind == "dispatched":
                        out.append({**_pane(f"dispatched:{key}", kind, None, texts[p]), "runners": [key]})
                    else:
                        out.append(_pane(f"executed:{key}", kind, key, texts[p]))
        cinp = f"compile_inputs/{task}.qasm" if task else "compile_input.qasm"
        if cinp in texts:
            out.append(_pane("compile-input", "compile-input", None, texts[cinp]))
        prefix = f"compiled_circuits/{scope}"
        for p in texts:
            if p.startswith(prefix) and "/" not in p[len(prefix) :]:
                key = p[len(prefix) : -len(".qasm")]
                out.append(_pane(f"compiled:{key}", "compiled", key, texts[p]))
        return out

    source = (graph.get("#report-source") or {}).get("value")
    circuits = (
        [{"task": i, "task_name": t, "panes": panes(t)} for i, t in enumerate(tasks)]
        if tasks
        else [{"task": None, "task_name": None, "panes": panes(None)}]
    )
    return {"report_source": source, "circuits": circuits}


def circuit_texts(server, job):
    """(texts, where they came from) for one job."""
    if job.dir:
        saved = results.read_json(os.path.join(job.dir, TEXTS_FILE))
        if isinstance(saved, dict) and isinstance(saved.get("circuits"), list):
            return saved, f"saved {TEXTS_FILE}"
    crate = _crate_file(job.dir)
    try:
        conn = server.conn
        if conn.has(FEATURE):
            resp = conn.request(
                "GET", f"/jobs/{job.job_id}/circuit-texts", what=f"circuit texts of job {job.job_id[:8]}"
            )
            if job.dir:
                keep(job.dir, TEXTS_FILE, resp.body)
            return resp.json(), "the server's job"
        reason = "this server has no GET /jobs/{id}/circuit-texts"
    except CliError as exc:
        if exc.code not in (Exit.NOT_FOUND, Exit.UNREACHABLE) or not crate:
            raise
        reason = exc.message
    if crate:
        return crate_texts(crate), f"saved {os.path.basename(crate)}"
    raise CliError(
        f"No circuit texts for job {job.job_id[:8]}: {reason}; no {TEXTS_FILE} or crate is saved.",
        Exit.INCOMPATIBLE,
        "feature_missing",
        hint="qrosetta export crate",
    )


def header(job, texts, where):
    status = results.read_status(job.dir) if job.dir else None
    source = SOURCE_TEXT.get(texts.get("report_source"), texts.get("report_source") or "unknown source")
    return (
        f"{job.request().get('title') or 'Job'} (job {job.job_id[:8]}): saved {status or 'not saved'}; "
        f"{source}, read from {where}"
    )


def select(texts, task, need_one):
    circuits = [c for c in texts.get("circuits") or [] if isinstance(c, dict)]
    if task is not None:
        chosen = [c for c in circuits if c.get("task") == task]
        if not chosen:
            raise usage(
                f"--task {task}: this result has {len(circuits)} circuit(s)"
                + ("" if any(c.get("task") is not None for c in circuits) else " and is not a playlist")
                + ".",
                hint="qrosetta show circuits",
                reason="bad_task",
            )
        return chosen
    if need_one and len(circuits) != 1:
        raise usage(
            f"This playlist has {len(circuits)} circuits; choose one with --task N.",
            hint="qrosetta show circuits",
            reason="bad_task",
        )
    return circuits


def find_pane(panes, name):
    """The pane named by its id, or by a result or compile key that names one pane."""
    for p in panes:
        if p.get("id") == name:
            return p
    matches = [p for p in panes if p.get("key") == name]
    if len(matches) != 1:
        matches = [p for p in panes if str(p.get("id", "")).endswith(f":{name}")]
    if len(matches) == 1:
        return matches[0]
    ids = [p.get("id") for p in panes]
    close = difflib.get_close_matches(name, ids, n=1)
    raise usage(
        f"No pane {name!r}"
        + (f" (several match: {', '.join(p['id'] for p in matches)})" if matches else "")
        + f"; this circuit has {', '.join(ids) or 'none'}.",
        hint=f"qrosetta show diff {close[0]}" if close else "qrosetta show circuits",
        reason="pane_unknown",
    )


def source_pane(pane, panes):
    """The pane `pane`'s text was derived from, as the Circuits view's Change column counts it."""
    ids = {p.get("id"): p for p in panes if p.get("text") is not None}
    if pane.get("kind") == "compiled" and "compile-input" in ids:
        return ids["compile-input"]
    if pane.get("kind") == "executed":
        for candidate in (f"dispatched:{pane.get('group')}", f"dispatched:{pane.get('key')}"):
            if candidate in ids:
                return ids[candidate]
    if pane.get("kind") != "input" and "input" in ids:
        return ids["input"]
    return None


def _rows(panes):
    rows = [("PANE", "LINES", "GATES", "STATUS")]
    for p in panes:
        text = p.get("text")
        if p.get("refusal_kind"):
            status = f"refused ({p['refusal_kind']})"
        else:
            status = p.get("dispatch_status") or ("" if isinstance(text, str) else "no text")
        rows.append(
            (
                p.get("id", ""),
                str(len(text.splitlines())) if isinstance(text, str) else "-",
                str(p["gate_count"]) if isinstance(p.get("gate_count"), int) else "-",
                status,
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    return [f"{r[0]:<{widths[0]}}  {r[1]:>{widths[1]}}  {r[2]:>{widths[2]}}  {r[3]}".rstrip() for r in rows]


def cmd_show_circuits(ctx):
    server = Server(ctx)
    job = one_job(ctx, server)
    texts, where = circuit_texts(server, job)
    line = header(job, texts, where)
    pane_name = ctx.opt("pane")
    circuits = select(texts, ctx.opt("task"), need_one=bool(pane_name))
    data = {"job_id": job.job_id, "dir": job.dir, "source": where, "report_source": texts.get("report_source")}
    if pane_name:
        pane = find_pane(circuits[0].get("panes") or [], pane_name)
        output.progress(line)
        if pane.get("text") is None:
            raise CliError(
                f"Pane {pane['id']} recorded no text.",
                Exit.NOT_FOUND,
                "pane_without_text",
                hint="qrosetta show circuits",
            )
        if not output.json_mode():
            output.raw(pane["text"] if pane["text"].endswith("\n") else pane["text"] + "\n")
        return Result(0, {**data, "task": circuits[0].get("task"), "pane": pane})
    output.result(line)
    for circuit in circuits:
        if circuit.get("task") is not None:
            output.result(f"Circuit {circuit['task']}: {circuit.get('task_name') or ''}".rstrip())
        for row in _rows(circuit.get("panes") or []):
            output.result(f"  {row}")
    output.progress("One text: qrosetta show circuits --pane ID; two compared: qrosetta show diff A B")
    return Result(0, {**data, "circuits": circuits})


def _ignored(values):
    chosen = []
    for value in values or []:
        for part in value.split(","):
            part = part.strip()
            if part and part not in IGNORABLE:
                raise usage(
                    f"--ignore {part}: choose from {', '.join(IGNORABLE)}.",
                    hint="qrosetta show diff --help",
                    reason="ignore_unknown",
                )
            if part and part not in chosen:
                chosen.append(part)
    return chosen


def lines_of(text, ignore):
    out = []
    for line in text.splitlines():
        if "comments" in ignore:
            line = re.sub(r"//.*$", "", line)
        if "header" in ignore and any(p.match(line) for p in _HEADER):
            continue
        if "whitespace" in ignore:
            line = " ".join(line.split())
            if not line:
                continue
        out.append(line)
    return out


def cmd_show_diff(ctx):
    names = ctx.opt("panes") or []
    if len(names) > 2:
        raise usage(
            "show diff compares two panes: A and B.", hint="qrosetta show diff input executed:qiskit", reason="usage"
        )
    ignore = _ignored(ctx.opt("ignore"))
    server = Server(ctx)
    job = one_job(ctx, server)
    texts, where = circuit_texts(server, job)
    panes = select(texts, ctx.opt("task"), need_one=True)[0].get("panes") or []
    with_text = [p for p in panes if p.get("text") is not None]
    if len(names) == 2:
        a, b = find_pane(panes, names[0]), find_pane(panes, names[1])
    elif len(names) == 1:
        b = find_pane(panes, names[0])
        a = source_pane(b, panes)
        if a is None:
            raise usage(
                f"{b['id']} is derived from no other pane; name two.",
                hint=f"qrosetta show diff {b['id']} B",
                reason="pane_without_source",
            )
    else:
        b = next((p for p in with_text if source_pane(p, panes) is not None), None)
        a = source_pane(b, panes) if b else None
        if a is None:
            raise usage(
                "This circuit has fewer than two texts to compare.",
                hint="qrosetta show circuits",
                reason="pane_without_source",
            )
    for p in (a, b):
        if p.get("text") is None:
            raise CliError(
                f"Pane {p['id']} recorded no text.", Exit.NOT_FOUND, "pane_without_text", hint="qrosetta show circuits"
            )
    diff = list(
        difflib.unified_diff(
            lines_of(a["text"], ignore), lines_of(b["text"], ignore), fromfile=a["id"], tofile=b["id"], lineterm=""
        )
    )
    output.progress(header(job, texts, where))
    if not diff:
        output.progress(
            f"{a['id']} and {b['id']}: the same text" + (f" (ignoring {', '.join(ignore)})" if ignore else "") + "."
        )
    for line in diff:
        output.result(line)
    return Result(
        0,
        {
            "job_id": job.job_id,
            "source": where,
            "a": a["id"],
            "b": b["id"],
            "ignore": ignore,
            "identical": not diff,
            "diff": "\n".join(diff),
        },
    )
