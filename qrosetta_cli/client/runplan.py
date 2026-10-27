"""What `qrosetta run` asks POST /plan for (spec §6.18): circuits from references or a playlist
file, modes, preprocessing, compilers, a name, and only the settings given on the command line
(flags, --set) or copied from a saved run (--request), each with its source. The server plans;
this module never builds a run request."""

import difflib
import json
import os
import re

from qrosetta_cli import output
from qrosetta_cli.client import refs
from qrosetta_cli.client.commands import parse_value
from qrosetta_cli.errors import CliError, Exit, usage

RUN_ENDPOINTS = {"/compare": "compare", "/compare_measured": "compare_measured",
                 "/run_batch_suite": "run_batch_suite", "/experiments": "experiments"}
PLANNER_FIELDS = ("qasm_string", "tasks", "circuits", "mode", "simulate", "compilers", "apply_preprocessing",
                  "preprocessing_modes", "label")
FLAG_FIELDS = {
    "n_shots": "--shots", "seed": "--seed", "target_simulators": "--backends", "optimization_level": "--opt-level",
    "runner_config": "--opt-level KEY=N", "timeout_seconds": "--timeout", "timing_repeats": "--repeats",
    "exclusive": "--exclusive", "thresholds": "--threshold", "runner_phases": "--order",
    "execution_target": "--execution-target", "bypass_limits": "--bypass-limits",
    "keep_statevectors": "--keep-statevectors",
}
MODES = ("statevector", "measured", "compile")
_DURATION = re.compile(r"(\d+(?:\.\d+)?)([hms]?)")

PROBLEM_TEXT = {
    "playlist_too_long": lambda p: f"{p.get('circuits')} circuits; the server runs at most {p.get('max')} per run. "
                                   "Split the playlist file.",
    "experiment_too_many_cells": lambda p: f"{p.get('circuits')} circuits x {p.get('settings')} settings = "
                                           f"{p.get('cells')} runs; the server allows {p.get('max')}. Use "
                                           "--preprocessing on or off, or fewer circuits.",
    "circuit_too_large": lambda p: f"{p.get('circuit') or 'the circuit'}: {p.get('characters')} characters; "
                                   f"the server accepts {p.get('max')}.",
    "bundled_over_prep_limit": lambda p: f"{', '.join(_bundled(c) for c in p.get('circuits') or [])}: preparation "
                                         "with preprocessing on exceeds the server's memory limit. Use "
                                         "--preprocessing off or remove them.",
    "request_too_large": lambda p: f"this run's request is {p.get('bytes')} bytes; the server accepts "
                                   f"{p.get('max')}. Split the playlist.",
    "compile_only_needs_one_setting": lambda p: "--mode compile needs --preprocessing on or off.",
    "bypass_needs_account": lambda p: "--bypass-limits needs `qrosetta login` on this server.",
}


def _bundled(c):
    return f"{c.get('source')}:{c.get('algorithm')}" + (f":{c['qubits']}" if c.get("qubits") else "")


def problem_text(problem, circuits=None):
    """The CLI's wording of a POST /plan problem; the server's message for an unknown code."""
    code, params = problem.get("code"), problem.get("params") or {}
    if code == "circuit_refused":
        index = problem.get("circuit_index")
        name = "the circuit"
        if isinstance(index, int) and circuits and index < len(circuits):
            name = circuits[index].get("name") or circuits[index].get("algorithm") or f"circuit {index + 1}"
        line = f" line {problem['line']}" if problem.get("line") else ""
        return f"{name}{line}: {params.get('detail') or problem.get('message')}"
    if code in PROBLEM_TEXT:
        return PROBLEM_TEXT[code](params)
    return problem.get("message") or code


def parse_duration(text, flag):
    """Seconds from 90, 90s, 5m, 1h30m."""
    text = (text or "").strip().lower()
    pos, total = 0, 0.0
    for m in _DURATION.finditer(text):
        if m.start() != pos:
            break
        total += float(m.group(1)) * {"h": 3600, "m": 60, "s": 1, "": 1}[m.group(2)]
        pos = m.end()
    if not text or pos != len(text):
        raise usage(f"{flag} {text!r}: write a duration such as 90, 90s, 5m or 1h30m.", hint="qrosetta run --help",
                    reason="bad_duration")
    return total


def _split(values):
    out = []
    for value in values or []:
        out += [v.strip() for v in value.split(",") if v.strip()]
    return out


def _int(text, flag):
    try:
        return int(text)
    except (TypeError, ValueError):
        raise usage(f"{flag}: {text!r} is not a whole number.", hint="qrosetta run --help", reason="bad_value") from None


def _key_value(pair, flag):
    key, sep, value = pair.rpartition("=")
    if not sep or not key:
        raise usage(f"{flag} takes KEY=VALUE, not {pair!r}.", hint="qrosetta run --help", reason="bad_value")
    return key, value


def _check_keys(keys, known, flag):
    for key in keys:
        if key not in known:
            close = difflib.get_close_matches(key, list(known), n=1)
            raise usage(f"{flag} {key}: no such key on this server" + (f"; did you mean {close[0]}?" if close else "."),
                        hint="qrosetta api GET /runners", reason="unknown_key")


class Settings:
    """Explicit settings with their source and the flag that set them."""

    def __init__(self):
        self.values = {}
        self.flags = {}

    def put(self, name, value, flag, source="flag"):
        if name in self.values:
            raise usage(f"{flag}: {name} is already set by {self.flags[name]}.", hint="qrosetta run --help",
                        reason="setting_twice")
        self.values[name] = {"value": value, "source": source}
        self.flags[name] = flag

    def as_plan(self):
        return {k: dict(v) for k, v in self.values.items()}


def _runner_ids(conn, cache):
    if "runners" not in cache:
        cache["runners"] = conn.get("/runners")
    return cache["runners"]


def settings_from_args(args, conn):
    """The settings the flags give, nothing else (spec P6)."""
    s, cache = Settings(), {}
    if args.shots is not None:
        s.put("n_shots", args.shots, "--shots")
    if args.seed is not None:
        s.put("seed", args.seed, "--seed")
    if args.timeout is not None:
        s.put("timeout_seconds", int(round(parse_duration(args.timeout, "--timeout"))), "--timeout")
    if args.repeats is not None:
        s.put("timing_repeats", args.repeats, "--repeats")
    if args.exclusive is not None:
        s.put("exclusive", args.exclusive, "--exclusive" if args.exclusive else "--no-exclusive")
    if args.bypass_limits is not None:
        s.put("bypass_limits", args.bypass_limits, "--bypass-limits" if args.bypass_limits else "--no-bypass-limits")
    if args.execution_target is not None:
        s.put("execution_target", args.execution_target, "--execution-target")
    if args.keep_statevectors:
        s.put("keep_statevectors", True, "--keep-statevectors")
    backends, skip = _split(args.backends), _split(args.skip)
    if backends or skip:
        rows = _runner_ids(conn, cache)
        known = {r.get("id") for r in rows}
        if backends == ["all"]:
            chosen = [r["id"] for r in rows if r.get("available")]
            left = [r["id"] for r in rows if r.get("enabled") and not r.get("available")]
            if left:
                output.progress(f"-b all: not available on this server, left out: {', '.join(left)}")
        elif backends:
            _check_keys(backends, known, "-b")
            chosen = backends
        else:
            chosen = [r["id"] for r in rows if r.get("default_selected") and r.get("available")]
        _check_keys(skip, known, "--skip")
        s.put("target_simulators", [b for b in chosen if b not in skip], "-b/--skip")
    runner_config = {}
    for value in args.opt_level or []:
        if "=" in value:
            key, levels = _key_value(value, "-O")
            parsed = [_int(v, "-O") for v in levels.split(",") if v != ""]
            runner_config[key] = parsed[0] if len(parsed) == 1 else parsed
        else:
            s.put("optimization_level", _int(value, "-O"), "-O")
    if runner_config:
        _check_keys(runner_config, {r.get("id") for r in _runner_ids(conn, cache)}, "-O")
        s.put("runner_config", runner_config, "-O KEY=N")
    if args.threshold:
        names = (conn.config.get("agreement_threshold_defaults") or {}).keys()
        thresholds = {}
        for pair in args.threshold:
            key, value = _key_value(pair, "--threshold")
            if names and key not in names:
                close = difflib.get_close_matches(key, list(names), n=1)
                raise usage(f"--threshold {key}: the server's thresholds are {', '.join(names)}"
                            + (f"; did you mean {close[0]}?" if close else "."), hint="qrosetta run --help",
                            reason="unknown_threshold")
            try:
                thresholds[key] = float(value)
            except ValueError:
                raise usage(f"--threshold {pair}: {value!r} is not a number.", hint="qrosetta run --help",
                            reason="bad_value") from None
        s.put("thresholds", thresholds, "--threshold")
    if args.order:
        phases = {}
        for pair in args.order:
            key, value = _key_value(pair, "--order")
            phases[key] = _int(value, "--order")
        _check_keys(phases, {r.get("id") for r in _runner_ids(conn, cache)}, "--order")
        s.put("runner_phases", phases, "--order")
    seen = set()
    for pair in args.set or []:
        key, value = _key_value(pair, "--set")
        if key in FLAG_FIELDS or key in PLANNER_FIELDS:
            flag = FLAG_FIELDS.get(key) or "the circuit, --mode, --preprocessing, --compiler or --name"
            raise usage(f"--set {key}: that field has its own option ({flag}).", hint="qrosetta run --help",
                        reason="set_has_flag")
        if key in seen:
            raise usage(f"--set {key} is given twice.", hint="qrosetta run --help", reason="setting_twice")
        seen.add(key)
        s.put(key, parse_value(value), f"--set {key}", source="set")
    return s


def compilers_from_args(args, conn):
    out = {}
    if not args.compiler:
        return out
    rows = {r.get("id"): r for r in conn.get("/compilers")}
    for pair in args.compiler:
        key, levels = _key_value(pair, "--compiler")
        _check_keys([key], rows, "--compiler")
        if levels == "all":
            out[key] = sorted(int(k) for k in (rows[key].get("optimization_levels") or {}))
        else:
            out[key] = [_int(v, "--compiler") for v in levels.split(",") if v != ""]
    return out


def modes_from_args(args):
    """(modes, compile_only, source)."""
    modes = _split(args.mode)
    if args.compile_only:
        modes.append("compile")
    for m in modes:
        if m not in MODES:
            raise usage(f"--mode {m}: choose statevector, measured or compile.", hint="qrosetta run --help",
                        reason="bad_mode")
    if "compile" in modes:
        if len(set(modes)) > 1:
            raise usage("--mode compile runs no simulation, so it cannot be combined with another mode.",
                        hint="qrosetta run --help", reason="bad_mode")
        if not args.compiler:
            raise usage("--mode compile needs at least one --compiler KEY=L.", hint="qrosetta compilers",
                        reason="bad_mode")
        return [], True, "flag"
    if not modes:
        return ["statevector"], False, "cli_default"
    return list(dict.fromkeys(modes)), False, "flag"


def _read_playlist(path):
    try:
        with open(path, encoding="utf-8") as fh:
            items = json.load(fh)
    except OSError as exc:
        raise CliError(f"Cannot read {path}: {exc.strerror}.", Exit.NOT_FOUND, "input_missing",
                       hint="qrosetta run --playlist FILE") from None
    except json.JSONDecodeError as exc:
        raise usage(f"{path} is not JSON: {exc}.", hint="qrosetta run --playlist FILE, with FILE the page's playlist "
                    "format", reason="playlist_invalid") from None
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise usage(f"{path}: a playlist file is a JSON array of objects.", hint="qrosetta run --help",
                    reason="playlist_invalid")
    return items


def circuits_from_args(args, conn, stdin):
    """(source, circuits, name) for the plan."""
    tokens = list(args.circuits or [])
    parsed = [refs.parse(t) for t in tokens]
    if sum(1 for r in parsed if r.kind == "stdin") > 1:
        raise usage("Only one circuit can come from stdin.", hint="qrosetta run --help", reason="stdin_twice")
    if args.playlist or len(parsed) > 1:
        items = _read_playlist(args.playlist) if args.playlist else []
        items += [refs.playlist_item(conn, r, stdin) for r in parsed]
        name = (os.path.splitext(os.path.basename(args.playlist))[0] if args.playlist else "playlist")
        return "playlist", items, name
    if not parsed:
        raise usage("Name a circuit: a file, -, or a reference such as algorithm:ghz:3.",
                    hint="qrosetta run algorithm:ghz:3", reason="no_circuit")
    name, qasm = refs.text(conn, parsed[0], stdin)
    return "single", [{"qasm_string": qasm, "name": name}], name


def build(args, conn, stdin):
    """(plan request, Settings, planner sources, slug name) from the command line."""
    settings = settings_from_args(args, conn)
    modes, compile_only, mode_source = modes_from_args(args)
    compilers = compilers_from_args(args, conn)
    source, circuits, circuit_name = circuits_from_args(args, conn, stdin)
    req = {"source": source, "circuits": circuits, "modes": modes, "compilers": compilers,
           "settings": settings.as_plan(), "check_circuits": False}
    if args.preprocessing is not None:
        req["preprocessing"] = args.preprocessing
    if args.name:
        req["name"] = args.name
    planner = {"modes": mode_source, "preprocessing": "flag" if args.preprocessing else "server_default",
               "compilers": "flag" if compilers else "none", "name": "flag" if args.name else "none"}
    return req, settings, planner, args.name or circuit_name


def request_fields(conn):
    """Every field the run routes' request models list in /openapi.json."""
    doc = conn.get("/openapi.json")
    schemas = (doc.get("components") or {}).get("schemas") or {}
    fields = set()
    for endpoint in RUN_ENDPOINTS:
        op = ((doc.get("paths") or {}).get(endpoint) or {}).get("post") or {}
        schema = (((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
        ref = schema.get("$ref", "")
        model = schemas.get(ref.rsplit("/", 1)[-1], {}) if ref else schema
        fields |= set((model.get("properties") or {}).keys())
    return fields


def check_server_fields(conn, settings):
    """Exit 12 naming the flag when the server's request models do not list a setting."""
    if not settings.values:
        return
    listed = request_fields(conn)
    for name in settings.values:
        if name not in listed:
            raise CliError(f"{settings.flags[name]}: this server's run requests have no {name} field.",
                           Exit.INCOMPATIBLE, "field_missing", hint=f"drop {settings.flags[name]}, or upgrade the server")


def defaults_for(conn, endpoint):
    """{field: default} the server fills for a run route (request_defaults in /config)."""
    kind = RUN_ENDPOINTS.get(endpoint)
    spec = ((conn.config.get("request_defaults") or {}).get("requests") or {}).get(kind) or {}
    return {name: entry.get("default") for name, entry in (spec.get("fields") or {}).items()
            if entry.get("server_fills")}


def request_record(conn, run, planner, job_id):
    """request.json: the payload sent, each field's source (flag, set, replay, circuit,
    server_default, plan) and the defaults of the fields left to the server."""
    payload = run["payload"]
    sources = {}
    for name, src in (run.get("sources") or {}).items():
        if src != "plan":
            sources[name] = src
        elif name in ("qasm_string", "tasks", "circuits"):
            sources[name] = "circuit"
        elif name in ("apply_preprocessing", "preprocessing_modes"):
            sources[name] = planner.get("preprocessing", "plan")
        elif name in ("mode", "simulate"):
            sources[name] = planner.get("modes", "plan")
        elif name == "compilers":
            sources[name] = "flag" if payload.get("compilers") else "plan"
        elif name == "label":
            sources[name] = planner.get("name", "plan")
        elif payload.get(name) is None or name == "bypass_limits":
            sources[name] = "server_default"
        else:
            sources[name] = "plan"
    omitted = {k: v for k, v in defaults_for(conn, run["endpoint"]).items() if k not in payload}
    for name in omitted:
        sources[name] = "server_default"
    return {"job_id": job_id, "endpoint": run["endpoint"], "kind": run.get("kind"), "mode": run.get("mode"),
            "title": run.get("title"), "payload": payload, "sources": sources, "server_defaults": omitted}


def differing_settings(conn, plan_settings, endpoint):
    """`name=value (source)` for every explicit setting whose value is not the server default."""
    defaults = defaults_for(conn, endpoint)
    out = []
    for name, s in plan_settings.items():
        if name not in defaults or defaults[name] != s["value"]:
            out.append(f"{name}={json.dumps(s['value'], ensure_ascii=False)} ({s['source']})")
    return out
