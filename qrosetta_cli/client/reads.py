"""`qrosetta info`, `backends`, `compilers` and `circuits` (spec §6.12, §6.13): the server's
handshake, limits and defaults, its runner and compiler lists, and its circuit catalogs, shown
as tables or embedded verbatim under --json."""

import difflib
import os

from qrosetta_cli import manifest as mf, output
from qrosetta_cli.client import handshake, refs, servers
from qrosetta_cli.client.conn import Conn
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage

COMMAND_FEATURES = (
    ("run", "plan", 1),
    ("run", "summary", 1),
    ("wait", "summary", 1),
    ("selftest", "plan", 1),
    ("selftest", "selftest", 1),
    ("selftest", "summary", 1),
    ("show summary", "summary", 1),
    ("backends --fresh", "fresh_probes", 1),
    ("compilers --fresh", "fresh_probes", 1),
)
DEFAULT_FIELDS = (
    ("n_shots", "shots"),
    ("timeout_seconds", "timeout (s)"),
    ("timing_repeats", "repeats"),
    ("optimization_level", "opt level"),
    ("apply_preprocessing", "preprocessing"),
    ("exclusive", "exclusive"),
)
CATALOGS = {
    "algorithms": ("/algorithms", "algorithm:ID:QUBITS[,seed=S]", "qrosetta circuits get algorithm:ghz:3"),
    "examples": ("/examples", "example:NAME", "qrosetta circuits get example:rotation_1q"),
    "mqt": ("/benchmarks/mqt/list", "mqt:ALGORITHM:QUBITS", "qrosetta circuits get mqt:ghz:4"),
    "qasmbench": ("/benchmarks/qasmbench/list", "qasmbench:NAME", "qrosetta circuits get qasmbench:adder_n4"),
}


def table(headers, rows):
    """Left-aligned columns separated by two spaces; the last column is not padded."""
    cells = [[str(c) for c in row] for row in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(headers)]
    lines = []
    for row in [list(headers)] + cells:
        padded = [c.ljust(w) for c, w in zip(row[:-1], widths)] + [row[-1]]
        lines.append("  ".join(padded).rstrip())
    return "\n".join(lines)


def _yes(value):
    return "yes" if value else "no"


def _ranges(numbers):
    """[0, 1, 2, 5] -> '0-2,5'."""
    nums = sorted(set(numbers))
    parts, start = [], None
    for i, n in enumerate(nums):
        if start is None:
            start = n
        if i + 1 == len(nums) or nums[i + 1] != n + 1:
            parts.append(str(start) if start == n else f"{start}-{n}")
            start = None
    return ",".join(parts) or "-"


def _levels(entry):
    keys = []
    for key in entry.get("optimization_levels") or {}:
        try:
            keys.append(int(key))
        except (TypeError, ValueError):
            return ",".join(sorted(entry["optimization_levels"]))
    return _ranges(keys)


def _per_endpoint(value):
    if not isinstance(value, dict):
        return "-" if value is None else str(value)
    sv, m = value.get("statevector"), value.get("measured")
    if sv == m:
        return sv or "per run"
    return f"sv {sv or 'per run'}, m {m or 'per run'}"


def _fmt_seconds(value):
    try:
        sec = float(value)
    except (TypeError, ValueError):
        return "-"
    if sec >= 3600 and sec % 3600 == 0:
        return f"{int(sec // 3600)} h"
    if sec >= 60 and sec % 60 == 0:
        return f"{int(sec // 60)} min"
    return f"{sec:g} s"


def _jobs_kept(lim):
    """'up to 24 h after they finish; over 200 finished or 512 MiB of memory, the oldest go from
    30 min on'."""
    text = f"up to {_fmt_seconds(lim.get('job_ttl_sec'))} after they finish"
    ttl, evictable = lim.get("job_ttl_sec"), lim.get("job_evictable_after_sec")
    shorter = isinstance(evictable, (int, float)) and (not isinstance(ttl, (int, float)) or evictable < ttl)
    if lim.get("job_max_kept") and shorter:
        over = f"{lim['job_max_kept']} finished"
        if lim.get("job_memory_max_mib"):
            over += f" or {lim['job_memory_max_mib']} MiB of memory"
        text += f"; over {over}, the oldest go from {_fmt_seconds(lim['job_evictable_after_sec'])} on"
    return text


def _fmt_bytes(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "-"
    for unit, size in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if n >= size:
            return f"{n / size:g} {unit}"
    return f"{n} B"


def _default_of(config, field):
    for spec in ((config.get("request_defaults") or {}).get("requests") or {}).values():
        entry = (spec.get("fields") or {}).get(field)
        if isinstance(entry, dict) and "default" in entry:
            return entry["default"]
    return None


def compatibility(config):
    """data.compatibility of `info`: the API levels on both sides, whether they overlap, and
    the features a command of this CLI needs that the server does not offer."""
    block = handshake.server_block(config)
    levels = handshake.levels(block)
    cli = handshake.CLI_API_LEVELS
    ok = bool(levels) and not (levels[1] < cli[0] or levels[0] > cli[1])
    offered = (block or {}).get("features") or {}
    missing: list = []
    needed_by: dict = {}
    for command, name, version in COMMAND_FEATURES:
        have = offered.get(name)
        if not isinstance(have, int) or have < version:
            key = f"{name}@{version}"
            if key not in needed_by:
                missing.append(key)
            needed_by.setdefault(key, []).append(command)
    return {
        "cli_api_levels": list(cli),
        "server_api_levels": list(levels) if levels else None,
        "ok": ok,
        "missing_features": missing,
    }, needed_by


def _gate_line(gate):
    if not gate:
        return "not published"
    parts = ["exclusive runs " + ("enabled" if gate.get("enabled") else "disabled")]
    if gate.get("exclusive_running"):
        parts.append("an exclusive run holds the server")
    parts.append(f"{int(gate.get('shared_running') or 0)} shared dispatches in flight")
    if gate.get("exclusive_waiting"):
        parts.append(f"{gate['exclusive_waiting']} exclusive jobs waiting")
    return ", ".join(parts)


def cmd_info(ctx):
    server = ctx.server()
    transport = ctx.transport(with_token=False)
    config = handshake.fetch_config(transport)
    block = handshake.server_block(config)
    ctx.note_handshake(block)
    compat, needed_by = compatibility(config)
    cli = handshake.CLI_API_LEVELS
    rows = [("Server", f"{server.url} ({server.source})")]
    if block is None:
        rows.append(("Version", "this server predates the version handshake (platform before 2.0.0)"))
    else:
        lv = compat["server_api_levels"]
        levels = f"API levels {lv[0]}-{lv[1]}" if lv else "no API levels"
        rows += [
            (
                "Platform",
                f"{block.get('platform_version', '?')}, {levels} (this CLI speaks {cli[0]}-{cli[1]}: "
                f"{'compatible' if compat['ok'] else 'incompatible'})",
            ),
            ("Analysis", block.get("analysis_version") or "-"),
            ("Commit", block.get("git_sha") or "-"),
            ("Features", ", ".join(f"{k} {v}" for k, v in sorted((block.get("features") or {}).items())) or "none"),
        ]
    rows += [("Mode", config.get("execution_mode") or "-"), ("Run gate", _gate_line(config.get("exclusive")))]
    defaults = []
    for field, label in DEFAULT_FIELDS:
        value = _default_of(config, field)
        if value is not None:
            defaults.append(f"{label} {('on' if value else 'off') if isinstance(value, bool) else value}")
    if defaults:
        rows.append(("Defaults", ", ".join(defaults)))
    thresholds = (
        (config.get("request_defaults") or {}).get("agreement_thresholds")
        or config.get("agreement_threshold_defaults")
        or {}
    )
    if thresholds:
        rows.append(("Thresholds", ", ".join(f"{k} {v}" for k, v in thresholds.items())))
    lim = config.get("limits") or {}
    rows += [
        (
            "Qubits",
            f"statevector {lim.get('max_qubits_statevector', '-')}, measured "
            f"{lim.get('max_qubits_measured', '-')}, compile-only {lim.get('max_qubits_compile', '-')}",
        ),
        ("Shots", f"{lim.get('shots_min', '-')} to {lim.get('shots_max', '-')}"),
        ("Timeout", f"{_fmt_seconds(lim.get('timeout_min'))} to {_fmt_seconds(lim.get('timeout_max'))}"),
        ("Repeats", f"up to {lim.get('timing_repeats_max', '-')}"),
        (
            "Requests",
            f"{_fmt_bytes(lim.get('max_request_bytes'))} per body, "
            f"{lim.get('max_batch_tasks', '-')} circuits per playlist, "
            f"{lim.get('max_qasm_gate_statements', '-')} gate statements per circuit",
        ),
        ("Jobs kept", _jobs_kept(lim)),
    ]
    width = max(len(k) for k, _ in rows)
    for key, value in rows:
        output.result(f"{key:<{width}}  {value}")
    for key in compat["missing_features"]:
        output.warn(
            f"this server does not offer {key}, which `qrosetta {', '.join(needed_by[key])}` needs.", "feature_missing"
        )
    data = {"config": config, "compatibility": compat}
    if block is None:
        raise CliError(
            "This server predates the CLI; it needs platform 2.0.0 or later.",
            Exit.INCOMPATIBLE,
            "server_too_old",
            hint=handshake.UPGRADE_HINT,
            data=data,
        )
    if not compat["ok"]:
        raise CliError(
            f"This server serves API levels {compat['server_api_levels']}; this CLI speaks {cli[0]}-{cli[1]}.",
            Exit.INCOMPATIBLE,
            "api_levels",
            hint=handshake.UPGRADE_HINT,
            data=data,
        )
    return Result(0, data)


def _service_list(ctx, path, what):
    """(entries, fresh) from GET /runners or /compilers, with the fresh-probe rules (spec S8):
    needs a token and the fresh_probes feature; a busy service reads available and was not
    probed; during an exclusive run the cached values come back with fresh false."""
    fresh = bool(ctx.opt("fresh"))
    if fresh:
        server = ctx.server()
        if not servers.token_for(server, ctx.cfg, ctx.env):
            raise CliError(
                f"--fresh needs a signed-in account on {server.url} (or the local lifecycle token).",
                Exit.AUTH,
                "not_signed_in",
                hint=f"qrosetta login{_server_flag(ctx)}",
            )
        conn = Conn(ctx, features=("fresh_probes",), with_token=True)
    else:
        conn = Conn(ctx, with_token=False)
    entries = conn.get(path, query={"fresh": "true"} if fresh else None, what=f"GET {path}", hint=f"qrosetta {what}")
    if not isinstance(entries, list):
        raise CliError(
            f"GET {path} answered with {type(entries).__name__}, not a list.",
            Exit.INCOMPATIBLE,
            "unexpected_response",
            hint="qrosetta info",
        )
    if fresh and any(isinstance(e, dict) and e.get("reason") == "exclusive_run" for e in entries):
        output.warn(
            "an exclusive run holds the server, so it was not probed; these are the values cached before the run.",
            "exclusive_run",
        )
    return entries, fresh


def _server_flag(ctx):
    flag = ctx.opt("server")
    return f" --server {flag}" if flag else ""


def _note(entry):
    notes = []
    if entry.get("reason") == "busy":
        notes.append("busy: a run is using it (not probed)")
    elif entry.get("reason") == "exclusive_run":
        notes.append("cached")
    if not entry.get("available"):
        why = entry.get("unavailable_reason") or "unavailable"
        notes.append(mf.not_included_text([entry.get("id")]) if why == mf.NOT_INCLUDED else why)
    if entry.get("error_kind"):
        notes.append(f"no answer ({entry['error_kind']})")
    if not entry.get("enabled", True) and "disabled" not in notes:
        notes.append("disabled")
    return "; ".join(dict.fromkeys(notes)) or "-"


def _print_levels(entries):
    for entry in entries:
        output.result(entry.get("id", "?"))
        for level, text in (entry.get("optimization_levels") or {}).items():
            output.result(f"  {level}  {text}")


def cmd_backends(ctx):
    entries, fresh = _service_list(ctx, "/runners", "backends")
    ids = [e["id"] for e in entries if isinstance(e, dict) and e.get("available") and e.get("default_selected")]
    if ctx.opt("ids"):
        for key in ids:
            output.result(key)
    elif ctx.opt("levels"):
        _print_levels(entries)
    else:
        rows = [
            (
                e.get("id", "?"),
                _yes(e.get("available")),
                _yes(e.get("default_selected")),
                _levels(e),
                e.get("device") or "-",
                _per_endpoint(e.get("precision")),
                _per_endpoint(e.get("qubit_ordering")),
                ",".join(e.get("profiles") or []) or "-",
                _note(e),
            )
            for e in entries
        ]
        output.result(
            table(("ID", "AVAILABLE", "DEFAULT", "LEVELS", "DEVICE", "PRECISION", "ORDER", "PROFILES", "NOTE"), rows)
        )
        output.progress(
            f"{len(ids)} of {len(entries)} backends available and selected by default"
            f"{' (probed now)' if fresh else ' (availability cached up to 60 s)'}."
        )
    return Result(0, {"runners": entries, "fresh": fresh, "default_ids": ids})


def _versions(entry):
    v = entry.get("versions")
    if not isinstance(v, dict):
        return "-"
    parts = [f"{k} {val}" for k, val in sorted((v.get("sdk_versions") or {}).items())]
    parts += [
        f"{c.get('name', '?')} {c.get('version', '?')}" for c in v.get("native_components") or [] if isinstance(c, dict)
    ]
    return ", ".join(parts) or "-"


def cmd_compilers(ctx):
    entries, fresh = _service_list(ctx, "/compilers", "compilers")
    ids = [e["id"] for e in entries if isinstance(e, dict) and e.get("available")]
    if ctx.opt("ids"):
        for key in ids:
            output.result(key)
    elif ctx.opt("levels"):
        _print_levels(entries)
    else:
        rows = [
            (
                e.get("id", "?"),
                e.get("name") or "-",
                _yes(e.get("available")),
                _levels(e),
                ",".join(e.get("profiles") or []) or "-",
                _note(e),
                _versions(e),
            )
            for e in entries
        ]
        output.result(table(("ID", "NAME", "AVAILABLE", "LEVELS", "PROFILES", "NOTE", "VERSIONS"), rows))
        output.progress(
            f"{len(ids)} of {len(entries)} compile-only services available"
            f"{' (probed now)' if fresh else ' (availability cached up to 60 s)'}; a run uses one only "
            "when --compiler names it."
        )
    return Result(0, {"compilers": entries, "fresh": fresh, "available_ids": ids})


def _matches(text, needle):
    return needle is None or needle.lower() in text.lower()


def _filter(catalog, items, max_qubits, needle):
    if catalog == "algorithms":
        return [
            a
            for a in items
            if (max_qubits is None or a.get("min_qubits", 0) <= max_qubits)
            and _matches(" ".join(str(a.get(k, "")) for k in ("id", "name", "description")), needle)
        ]
    if catalog == "examples":
        return [
            e
            for e in items
            if (max_qubits is None or (e.get("qubits") or 0) <= max_qubits)
            and _matches(" ".join(str(e.get(k, "")) for k in ("name", "title", "description", "mode")), needle)
        ]
    if catalog == "mqt":
        out = {}
        for algo, sizes in items.items():
            kept = [s for s in sizes if max_qubits is None or s <= max_qubits]
            if kept and _matches(algo, needle):
                out[algo] = kept
        return out
    return [n for n in items if _matches(n, needle)]


def _print_catalog(catalog, items):
    if catalog == "algorithms":
        rows: list[tuple] = [
            (
                a.get("id", "?"),
                f"{a.get('min_qubits', '?')}-{a.get('max_qubits', '?')}",
                a.get("max_qubits_statevector", "-"),
                a.get("max_qubits_measured", "-"),
                a.get("default_qubits", "-"),
                a.get("name") or "-",
            )
            for a in items
        ]
        output.result(table(("ID", "QUBITS", "SV MAX", "MEASURED MAX", "DEFAULT", "NAME"), rows))
    elif catalog == "examples":
        rows = [
            (
                e.get("name", "?")[:-5] if e.get("name", "").endswith(".qasm") else e.get("name", "?"),
                e.get("qubits", "-"),
                e.get("mode") or "-",
                e.get("title") or "-",
            )
            for e in items
        ]
        output.result(table(("NAME", "QUBITS", "MODE", "TITLE"), rows))
    elif catalog == "mqt":
        output.result(table(("ALGORITHM", "QUBITS"), [(algo, _ranges(sizes)) for algo, sizes in items.items()]))
    else:
        output.result(table(("NAME",), [(n,) for n in items]))


def cmd_circuits(ctx):
    catalog = ctx.opt("catalog")
    path, form, example = CATALOGS[catalog]
    max_qubits, needle = ctx.opt("max_qubits"), ctx.opt("filter")
    if catalog == "qasmbench" and max_qubits is not None:
        raise usage(
            "The QASMBench list holds names only, so --max-qubits cannot filter it.",
            hint="qrosetta circuits qasmbench --filter adder",
        )
    conn = Conn(ctx, with_token=False)
    items = conn.get(path, what=f"GET {path}", hint="qrosetta info")
    shown = _filter(catalog, items, max_qubits, needle)
    total = len(items)
    if not shown:
        output.result(f"No {catalog} entry matches." if (max_qubits is not None or needle) else f"No {catalog}.")
    else:
        _print_catalog(catalog, shown)
    output.progress(f"{len(shown)} of {total} shown. Reference: {form}, e.g. `{example}`.")
    return Result(
        0,
        {
            "catalog": catalog,
            "path": path,
            "items": shown,
            "total": total,
            "filter": {"max_qubits": max_qubits, "text": needle},
        },
    )


def _suggest(name, names):
    close = difflib.get_close_matches(name, list(names), n=3)
    return f"; did you mean {', '.join(close)}?" if close else "."


def _not_found(ref, conn):
    """The exit-14 error for a reference the server does not have, with close names."""
    if ref.kind == "example":
        names = [e["name"][:-5] for e in conn.get("/examples") if str(e.get("name", "")).endswith(".qasm")]
        return CliError(
            f"No bundled example {ref.name!r}{_suggest(ref.name, names)}",
            Exit.NOT_FOUND,
            "unknown_example",
            hint="qrosetta circuits examples",
        )
    if ref.kind == "mqt":
        index = conn.get("/benchmarks/mqt/list")
        if ref.name in index:
            return CliError(
                f"MQT Bench has {ref.name} at {_ranges(index[ref.name])} qubits, not {ref.qubits}.",
                Exit.NOT_FOUND,
                "unknown_size",
                hint=f"qrosetta circuits mqt --filter {ref.name}",
            )
        return CliError(
            f"No MQT Bench algorithm {ref.name!r}{_suggest(ref.name, index)}",
            Exit.NOT_FOUND,
            "unknown_algorithm",
            hint="qrosetta circuits mqt",
        )
    names = conn.get("/benchmarks/qasmbench/list")
    return CliError(
        f"No QASMBench circuit {ref.name!r}{_suggest(ref.name, names)}",
        Exit.NOT_FOUND,
        "unknown_circuit",
        hint="qrosetta circuits qasmbench",
    )


def _write_text(path, text):
    part = path + ".part"
    try:
        with open(part, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(part, path)
    except OSError as exc:
        if os.path.exists(part):
            os.unlink(part)
        raise CliError(
            f"Cannot write {path}: {exc.strerror}.",
            Exit.REFUSED,
            "write_failed",
            hint="qrosetta circuits get REF -o PATH, with PATH in a writable directory",
        ) from None


def cmd_circuits_get(ctx):
    ref = refs.parse(ctx.args.ref)
    conn = None
    if ref.kind not in ("file", "stdin"):
        conn = Conn(ctx, with_token=False)
        if ref.kind == "algorithm":
            known = [a.get("id") for a in conn.get("/algorithms")]
            if ref.name not in known:
                raise CliError(
                    f"No algorithm {ref.name!r}{_suggest(ref.name, known)}",
                    Exit.NOT_FOUND,
                    "unknown_algorithm",
                    hint="qrosetta circuits algorithms",
                )
    try:
        name, qasm = refs.text(conn, ref, ctx.stdin)
    except CliError as exc:
        if exc.code == Exit.NOT_FOUND and conn is not None and ref.kind in ("example", "mqt", "qasmbench"):
            raise _not_found(ref, conn) from None
        if exc.code == Exit.REFUSED and conn is not None and exc.http_status == 400:
            catalog = "algorithms" if ref.kind == "algorithm" else ref.kind
            exc.hint = f"qrosetta circuits {catalog}" + (f" --filter {ref.name}" if ref.kind != "algorithm" else "")
        raise
    dest = ctx.opt("output")
    data = {"ref": ref.token, "kind": ref.kind, "name": name, "qasm": qasm, "path": None}
    if dest and dest != "-":
        path = os.path.abspath(dest)
        _write_text(path, qasm)
        data["path"] = path
        output.progress(f"Wrote {name} to {path}")
    elif not output.json_mode():
        output.raw(qasm if qasm.endswith("\n") else qasm + "\n")
    return Result(0, data)
