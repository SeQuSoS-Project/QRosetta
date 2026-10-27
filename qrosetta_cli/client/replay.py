"""`run --request FILE` (spec §6.18, R6): a saved plan.json or request.json planned again through
POST /plan, with every field sent explicitly. Fields the original left to the server are
filled from the run context its saved report records, so a newer server's defaults cannot
fill a gap; all of them carry source `replay`."""

import os
import re

from qrosetta_cli import output
from qrosetta_cli.client import handshake, results
from qrosetta_cli.client.runplan import Settings
from qrosetta_cli.errors import CliError, Exit, usage

CONTEXT_FIELDS = (("optimization_level", "optimization_level"), ("runner_config", "runner_config"),
                  ("runner_phases", "runner_phases"), ("timeout_seconds", "timeout_seconds"),
                  ("timing_repeats", "timing_repeats"), ("thresholds", "agreement_thresholds"),
                  ("exclusive", "exclusive"))
MEASURED_FIELDS = ("n_shots", "seed")


def _first_task(report):
    tasks = report.get("benchmark_summary")
    if isinstance(tasks, list):
        return next((t for t in tasks if isinstance(t, dict) and "optimization_level" in t), {})
    return report


def run_context(report):
    """The request fields a saved report records, by request field name."""
    if not isinstance(report, dict):
        return {}
    base = _first_task(report)
    out = {field: base[key] for field, key in CONTEXT_FIELDS if key in base}
    dispatched = (base.get("resolved_runners") or {}).get("dispatched")
    if isinstance(dispatched, list) and dispatched:
        out["target_simulators"] = list(dispatched)
    if "apply_preprocessing" in base:
        out["apply_preprocessing"] = base["apply_preprocessing"]
    n_shots = report.get("n_shots", base.get("n_shots"))
    if n_shots is not None:
        out["n_shots"] = n_shots
    if report.get("seed") is not None:
        out["seed"] = report["seed"]
    return out


def _plan_from_request(doc):
    """A plan request for the one job a request.json records."""
    payload = dict(doc.get("payload") or {})
    endpoint = doc.get("endpoint")
    req = {"compilers": payload.get("compilers") or {}, "check_circuits": False}
    if endpoint in ("/compare", "/compare_measured"):
        req.update(source="single", circuits=[{"qasm_string": payload.get("qasm_string"),
                                               "name": doc.get("title") or "circuit"}])
    elif endpoint == "/run_batch_suite":
        req.update(source="playlist", circuits=list(payload.get("tasks") or []))
    elif endpoint == "/experiments":
        req.update(source="playlist", circuits=list(payload.get("circuits") or []), preprocessing="both")
    else:
        raise usage(f"{endpoint!r} is not a run route this CLI replays.", hint="qrosetta run --request plan.json",
                    reason="replay_invalid")
    simulate = payload.get("simulate", True) is not False
    req["modes"] = [] if not simulate else [doc.get("mode") or ("measured" if endpoint == "/compare_measured"
                                                                 else payload.get("mode") or "statevector")]
    if "apply_preprocessing" in payload and endpoint != "/experiments":
        req["preprocessing"] = "on" if payload["apply_preprocessing"] else "off"
    if payload.get("label"):
        req["name"] = payload["label"]
    skip = {"qasm_string", "tasks", "circuits", "mode", "simulate", "compilers", "apply_preprocessing",
            "preprocessing_modes", "label"}
    req["settings"] = {k: {"value": v, "source": "replay"} for k, v in payload.items()
                       if k not in skip and v is not None}
    return req


def load(path):
    """(plan request, original server block, original API level, report paths) of a saved file."""
    path = os.path.abspath(path)
    doc = results.read_json(path)
    if not isinstance(doc, dict):
        raise CliError(f"Cannot read {path} as JSON.", Exit.NOT_FOUND, "input_missing",
                       hint="qrosetta run --request DIR/plan.json")
    here = os.path.dirname(path)
    if isinstance(doc.get("plan_request"), dict):
        req = dict(doc["plan_request"])
        req["settings"] = {k: {"value": s.get("value"), "source": "replay"}
                           for k, s in (req.get("settings") or {}).items()}
        reports = [os.path.join(here, d, "report.json") for d in doc.get("job_dirs") or []]
        return req, doc.get("server") or {}, doc.get("api_level"), reports
    if "endpoint" in doc and "payload" in doc:
        plan = results.read_json(os.path.join(os.path.dirname(here), results.PLAN_FILE)) or {}
        return _plan_from_request(doc), plan.get("server") or {}, plan.get("api_level"), [
            os.path.join(here, "report.json")]
    raise usage(f"{path} is neither a plan.json nor a request.json.", hint="qrosetta run --request DIR/plan.json",
                reason="replay_invalid")


def original_slug(path):
    """The slug of the invocation a saved plan.json or request.json belongs to."""
    here = os.path.dirname(os.path.abspath(path))
    if os.path.basename(path) != results.PLAN_FILE:
        here = os.path.dirname(here)
    name = os.path.basename(here)
    m = re.match(r"^\d{8}-\d{6}Z-(.+?)(?:-\d+)?$", name)
    return m.group(1) if m else name


def check_versions(conn, original, api_level, force):
    """Exit 12 when this server no longer serves the original's API level (unless --force);
    a different platform or analysis version is a warning."""
    levels = handshake.levels(conn.block)
    if api_level is not None and levels and not levels[0] <= api_level <= levels[1]:
        if not force:
            raise CliError(f"The original ran at API level {api_level}; this server serves {levels[0]}-{levels[1]}.",
                           Exit.INCOMPATIBLE, "replay_api_level", hint="add --force to replay anyway (recorded)")
        output.warn(f"Replaying across API levels ({api_level} -> {levels[0]}-{levels[1]}) with --force.",
                    "replay_forced")
    for key, label in (("platform_version", "platform"), ("analysis_version", "analysis")):
        was, now = original.get(key), conn.block.get(key)
        if was and now and was != now:
            output.warn(f"The original ran on {label} {was}; this server has {now}.", "replay_version")


def fill(req, reports, settings_out):
    """Fill every setting and the preprocessing choice the original left to the server from
    its saved reports; returns the names filled. Missing reports leave a warning."""
    contexts = [run_context(results.read_json(p)) for p in reports if os.path.isfile(p)]
    if not contexts:
        output.warn("The original's report.json is not saved, so settings it left to the server stay unset and "
                    "this server's defaults apply.", "replay_without_report")
        return []
    measured = "measured" in (req.get("modes") or [])
    filled = []
    first = contexts[0]
    for name in ("optimization_level", "runner_config", "runner_phases", "timeout_seconds", "timing_repeats",
                 "thresholds", "exclusive", "target_simulators") + (MEASURED_FIELDS if measured else ()):
        if name in req["settings"]:
            continue
        ctx = next((c for c in contexts if name in c), None) if name in MEASURED_FIELDS else first
        if ctx and name in ctx and ctx[name] is not None:
            req["settings"][name] = {"value": ctx[name], "source": "replay"}
            filled.append(name)
    if "preprocessing" not in req and "apply_preprocessing" in first:
        req["preprocessing"] = "on" if first["apply_preprocessing"] else "off"
        filled.append("apply_preprocessing")
    for name, s in req["settings"].items():
        settings_out.values[name] = s
        settings_out.flags[name] = f"--request ({name})"
    return filled


def settings_of(req):
    s = Settings()
    for name, value in (req.get("settings") or {}).items():
        s.values[name] = value
        s.flags[name] = f"--request ({name})"
    return s
