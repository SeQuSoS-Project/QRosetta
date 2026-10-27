"""POST /plan: the run requests one press of Run sends, and why the server would refuse them,
as problem codes. The page and the qrosetta command plan through this one function."""

import re

from fastapi import HTTPException
from pydantic import ValidationError

from config import settings
from schemas import BatchPayload, ExperimentPayload, MeasuredQasmPayload, QasmPayload
from services.plan_text import (
    UNDEFINED, bare_circuit_name, js_json_bytes, js_number_text, js_parse_int_or_zero,
    js_string, js_trim, js_truthy, printable_label,
)
from services.preparation_limits import bundled_over_prep_limit
from services.validator import validate_submission

MODELS = {"/compare": QasmPayload, "/compare_measured": MeasuredQasmPayload,
          "/run_batch_suite": BatchPayload, "/experiments": ExperimentPayload}

PLANNER_FIELDS = frozenset({"qasm_string", "tasks", "circuits", "mode", "simulate", "compilers",
                            "apply_preprocessing", "preprocessing_modes", "label"})

DEDICATED_FLAG_FIELDS = frozenset({
    "n_shots", "seed", "target_simulators", "optimization_level", "runner_config",
    "timeout_seconds", "timing_repeats", "exclusive", "thresholds", "runner_phases",
    "execution_target", "bypass_limits", "keep_statevectors"})

SETTING_FIELDS = frozenset(f for model in MODELS.values() for f in model.model_fields) - PLANNER_FIELDS

_MODE_LABEL = {"statevector": "Statevector", "measured": "Measured"}

MESSAGES = {
    "playlist_empty": "The playlist is empty.",
    "editor_empty": "The circuit is empty.",
    "no_mode": "No simulation mode and no compile-only service was chosen.",
    "compile_only_needs_one_setting": "A compile-only run uses one preprocessing setting: on or off.",
}


def _problem(code: str, message: str, params: dict = None, run_index=None, circuit_index=None,
             line=None) -> dict:
    return {"code": code, "params": params or {}, "message": message, "run_index": run_index,
            "circuit_index": circuit_index, "line": line}


def check_settings(request_settings: dict) -> None:
    """400 for a setting the planner does not take: an unknown field, a field the planner
    sets itself, or a field with a dedicated flag given with source 'set'."""
    for name, setting in request_settings.items():
        if name in PLANNER_FIELDS:
            raise HTTPException(status_code=400, detail=(
                f"settings.{name}: the planner sets this field from source, modes, "
                f"preprocessing, compilers and name."))
        if name not in SETTING_FIELDS:
            raise HTTPException(status_code=400, detail=(
                f"settings.{name}: not a field of any run request."))
        if setting.source == "set" and name in DEDICATED_FLAG_FIELDS:
            raise HTTPException(status_code=400, detail=(
                f"settings.{name}: this field has its own option; give it there, not as a "
                f"generic setting."))


def _get(item: dict, key: str):
    return item.get(key, UNDEFINED) if isinstance(item, dict) else UNDEFINED


def _or(*values):
    for v in values:
        if js_truthy(v):
            return v
    return values[-1]


def to_batch_task(item: dict, max_label: int) -> dict:
    """run_plan.js toBatchTask: a playlist item as a BenchmarkTask."""
    qasm = _or(_get(item, "qasm_string"), _get(item, "qasm"))
    raw_algorithm = _or(_get(item, "algorithm"), "custom")
    algorithm = (printable_label(raw_algorithm, max_label) or "custom") if js_truthy(qasm) \
        else js_string(raw_algorithm)
    task = {"algorithm": algorithm, "qubits": js_parse_int_or_zero(_get(item, "qubits"))}
    name = printable_label(bare_circuit_name(_get(item, "name")), max_label)
    if name and name != task["algorithm"]:
        task["name"] = name
    if js_truthy(qasm):
        task["qasm_string"] = qasm
    if js_truthy(_get(item, "source")):
        task["source"] = item["source"]
    return task


def to_experiment_circuit(item: dict, max_label: int) -> dict:
    """run_plan.js toExperimentCircuit: a playlist item as an ExperimentCircuit."""
    def label(text):
        return printable_label(text, max_label) or None

    source = _get(item, "source")
    qubits = js_parse_int_or_zero(_get(item, "qubits"))
    if source in ("mqt", "qasmbench"):
        out = {"source": source, "algorithm": _get(item, "algorithm"), "qubits": qubits,
               "name": label(bare_circuit_name(_get(item, "name"))) or label(_get(item, "algorithm"))}
        return {k: v for k, v in out.items() if v is not UNDEFINED}
    qasm = _or(_get(item, "qasm_string"), _get(item, "qasm"))
    if js_truthy(qasm):
        return {"source": "qasm", "qasm_string": qasm,
                "name": label(_or(bare_circuit_name(_get(item, "name")), _get(item, "algorithm"))) or "circuit",
                "qubits": qubits}
    out = {"source": "preset", "algorithm": _get(item, "algorithm"), "qubits": qubits,
           "name": label(bare_circuit_name(_get(item, "name")))}
    return {k: v for k, v in out.items() if v is not UNDEFINED}


def _setting(request_settings: dict, name: str):
    s = request_settings.get(name)
    return UNDEFINED if s is None else s.value


def plan_runs(req, max_label: int = None) -> tuple:
    """run_plan.js planRuns: ``(runs, problem)``; ``problem`` is a plan-level problem (and
    ``runs`` empty) when nothing can be planned."""
    max_label = settings.MAX_LABEL_LENGTH if max_label is None else max_label
    modes = [m for m in ("statevector", "measured") if m in req.modes]
    compilers = req.compilers if req.compilers else None
    from_list = req.source == "playlist"
    circuits = req.circuits if from_list else []
    editor = req.circuits[0] if (not from_list and req.circuits) else {}
    editor_qasm = _get(editor, "qasm_string")
    if editor_qasm is UNDEFINED:
        editor_qasm = _get(editor, "qasm")
    if from_list and not circuits:
        return [], _problem("playlist_empty", MESSAGES["playlist_empty"])
    if not from_list and not js_trim(js_string(_or(editor_qasm, ""))):
        return [], _problem("editor_empty", MESSAGES["editor_empty"])
    if not modes and not compilers:
        return [], _problem("no_mode", MESSAGES["no_mode"])
    n = len(circuits)
    what = (f"Playlist of {n} circuit{'' if n == 1 else 's'}" if from_list
            else (bare_circuit_name(_get(editor, "name")) or "Editor Run"))
    run_name = printable_label(req.name, max_label)
    base = run_name or what
    given = {k: s.value for k, s in req.settings.items()}
    source_of = {k: s.source for k, s in req.settings.items()}

    def sources(payload: dict) -> dict:
        return {k: source_of.get(k, "plan") for k in payload}

    if not modes:
        if req.preprocessing == "both":
            return [], _problem("compile_only_needs_one_setting", MESSAGES["compile_only_needs_one_setting"])
        shared = {k: given[k] for k in ("optimization_level", "timeout_seconds", "execution_target")
                  if k in given}
        shared["bypass_limits"] = js_truthy(given.get("bypass_limits", UNDEFINED))
        shared.update({"apply_preprocessing": req.preprocessing != "off", "compilers": compilers,
                       "simulate": False})
        if from_list:
            payload = {**shared, "mode": "statevector",
                       "tasks": [to_batch_task(c, max_label) for c in circuits]}
            run = {"endpoint": "/run_batch_suite", "kind": "batch", "mode": None,
                   "title": f"{base} (compile only)", "payload": payload}
        else:
            payload = {**shared, "qasm_string": editor_qasm}
            run = {"endpoint": "/compare", "kind": "single", "mode": None,
                   "title": f"{base} (compile only)", "payload": payload}
        run["sources"] = sources(run["payload"])
        return [run], None

    common = {k: v for k, v in given.items() if k not in ("n_shots", "seed")}
    shots = given.get("n_shots", UNDEFINED)
    shots_text = js_number_text(settings.DEFAULT_SHOTS) if shots is UNDEFINED else js_string(shots)
    runs = []
    for i, mode in enumerate(modes):
        measured = mode == "measured"
        payload = {**common, "compilers": compilers if (i == 0 and compilers) else {}}
        if measured:
            if shots is not UNDEFINED:
                payload["n_shots"] = shots
            payload["seed"] = given.get("seed")
        title = f"{base} ({_MODE_LABEL[mode]}{f', {shots_text} shots' if measured else ''})"
        if req.preprocessing == "both":
            items = ([to_experiment_circuit(c, max_label) for c in circuits] if from_list else
                     [{"source": "qasm", "qasm_string": editor_qasm,
                       "name": printable_label(bare_circuit_name(_get(editor, "name")), max_label) or "editor circuit"}])
            payload = {**payload, "mode": mode, "circuits": items, "preprocessing_modes": [True, False],
                       "label": printable_label(run_name, max_label) or None}
            run = {"endpoint": "/experiments", "kind": "experiment", "mode": mode,
                   "title": f"{title} · preprocessing on and off", "payload": payload}
        else:
            payload["apply_preprocessing"] = req.preprocessing != "off"
            if from_list:
                run = {"endpoint": "/run_batch_suite", "kind": "batch", "mode": mode, "title": title,
                       "payload": {**payload, "mode": mode,
                                   "tasks": [to_batch_task(c, max_label) for c in circuits]}}
            else:
                run = {"endpoint": "/compare_measured" if measured else "/compare", "kind": "single",
                       "mode": mode, "title": title, "payload": {**payload, "qasm_string": editor_qasm}}
        run["sources"] = sources(run["payload"])
        runs.append(run)
    return runs, None


def _items(payload: dict) -> list:
    items = payload.get("tasks") or payload.get("circuits") or []
    return items if isinstance(items, list) else []


def _literal_circuits(payload: dict) -> list:
    """``[(circuit_index or None, label or None, qasm)]``: run_plan.js _literalCircuits."""
    if isinstance(payload.get("qasm_string"), str):
        return [(None, None, payload["qasm_string"])]
    return [(i, js_string(_or(c.get("name", UNDEFINED), c.get("algorithm", UNDEFINED), "custom")), c["qasm_string"])
            for i, c in enumerate(_items(payload))
            if isinstance(c, dict) and isinstance(c.get("qasm_string"), str)]


def _bundled_key(source, algorithm, qubits) -> str:
    q = 0 if source == "qasmbench" else js_parse_int_or_zero(qubits)
    return f"{js_string(source)}:{js_string(algorithm)}:{q}"


def _bundled_prepared(payload: dict) -> list:
    modes = payload.get("preprocessing_modes")
    on = (True in modes) if isinstance(modes, list) else payload.get("apply_preprocessing") is not False
    if not on:
        return []
    return [(i, c) for i, c in enumerate(_items(payload))
            if isinstance(c, dict) and c.get("source") in ("mqt", "qasmbench")]


def limit_problems(runs: list) -> list:
    """run_plan.js runLimitProblems, as problem codes, in the same order per run."""
    problems = []
    over_prep = {_bundled_key(c["source"], c["algorithm"], c["qubits"]) for c in bundled_over_prep_limit()}
    for r, run in enumerate(runs):
        p = run["payload"]
        bypass = js_truthy(p.get("bypass_limits", UNDEFINED))
        tasks = _items(p)
        if run["kind"] == "batch" and not bypass and len(tasks) > settings.MAX_BATCH_TASKS:
            problems.append(_problem(
                "playlist_too_long",
                f"The playlist has {len(tasks)} circuits; the server runs at most "
                f"{settings.MAX_BATCH_TASKS} in one run.",
                {"circuits": len(tasks), "max": settings.MAX_BATCH_TASKS}, r))
        if over_prep:
            heavy = [(i, c) for i, c in _bundled_prepared(p)
                     if _bundled_key(c.get("source"), c.get("algorithm", UNDEFINED), c.get("qubits", UNDEFINED)) in over_prep]
            if heavy:
                problems.append(_problem(
                    "bundled_over_prep_limit",
                    f"With preprocessing on, preparing {len(heavy)} bundled circuit(s) takes more "
                    f"memory than the server's {settings.PREP_MAX_MIB} MiB limit.",
                    {"circuits": [{"index": i, "source": c.get("source"),
                                   "algorithm": c.get("algorithm"), "qubits": c.get("qubits")}
                                  for i, c in heavy],
                     "prep_max_mib": settings.PREP_MAX_MIB}, r))
        if run["kind"] == "experiment" and not bypass:
            n = len(p.get("circuits") or [])
            axes = len(p.get("preprocessing_modes") or [])
            if n * axes > settings.MAX_EXPERIMENT_CELLS:
                problems.append(_problem(
                    "experiment_too_many_cells",
                    f"{n} circuits x {axes} preprocessing settings make {n * axes} experiment "
                    f"runs; the server allows {settings.MAX_EXPERIMENT_CELLS}.",
                    {"circuits": n, "settings": axes, "cells": n * axes,
                     "max": settings.MAX_EXPERIMENT_CELLS}, r))
        if not (bypass and settings.EXECUTION_MODE == "local"):
            for index, label, qasm in _literal_circuits(p):
                if len(qasm) > settings.MAX_QASM_SIZE:
                    problems.append(_problem(
                        "circuit_too_large",
                        f"{'The circuit' if label is None else f'Circuit {label!r}'} has {len(qasm)} "
                        f"characters; the server accepts circuits of up to {settings.MAX_QASM_SIZE}.",
                        {"circuit": label, "characters": len(qasm), "max": settings.MAX_QASM_SIZE},
                        r, index))
        size = js_json_bytes(p)
        if size > settings.MAX_UPLOAD_BYTES:
            problems.append(_problem(
                "request_too_large",
                f"The request is {size} bytes; the server accepts at most {settings.MAX_UPLOAD_BYTES}.",
                {"bytes": size, "max": settings.MAX_UPLOAD_BYTES,
                 "literal_circuits": len(_literal_circuits(p))}, r))
    return problems


def request_problems(runs: list, signed_in: bool) -> list:
    """A planned request its route would refuse before looking at the circuits: one that does
    not match the request schema, or bypass_limits without the sign-in this server needs."""
    problems = []
    for r, run in enumerate(runs):
        try:
            MODELS[run["endpoint"]](**run["payload"])
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(x) for x in first.get("loc", ()))
            problems.append(_problem("invalid_request", f"{where}: {first.get('msg')}",
                                     {"field": where, "errors": len(exc.errors())}, r))
        if (run["payload"].get("bypass_limits") is True and settings.bypass_requires_account()
                and not signed_in):
            problems.append(_problem("bypass_needs_account",
                                     "bypass_limits needs a signed-in account on this server.", {}, r))
    return problems


_LINE = re.compile(r"\bline (\d+)", re.IGNORECASE)


def circuit_problems(runs: list) -> list:
    """The submit-time checks of the run routes on every literal circuit, as circuit_refused
    problems with the line the check names. Runs in a worker thread."""
    problems = []
    for r, run in enumerate(runs):
        p = run["payload"]
        simulate = p.get("simulate", True) is not False
        mode = (run["mode"] or "statevector") if simulate else "compile"
        modes = p.get("preprocessing_modes")
        preprocessing = (True in modes) if isinstance(modes, list) else p.get("apply_preprocessing", True) is not False
        for index, _label, qasm in _literal_circuits(p):
            try:
                validate_submission(qasm, mode, bypass_limits=p.get("bypass_limits") is True,
                                    apply_preprocessing=preprocessing,
                                    statevector=simulate and mode == "statevector")
            except HTTPException as exc:
                detail = str(exc.detail)
                match = _LINE.search(detail)
                problems.append(_problem("circuit_refused", detail,
                                         {"status": exc.status_code, "detail": detail}, r, index,
                                         int(match.group(1)) if match else None))
    return problems
