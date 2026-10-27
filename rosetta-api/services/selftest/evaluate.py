"""Evaluation of a finished self-test job: each backend's result for each plan circuit
against the pinned expected answer (never against another backend), the job's recorded
settings against the plan, and the environment checks, each PASS, WARN, FAIL or SKIP."""

from services.selftest.circuits import (
    CIRCUIT_KINDS, CIRCUIT_PARTS, CIRCUITS, circuit_text, expected_file_sha256, load_expected,
)
from services.selftest.environment import FAIL, PASS, SKIP, VM_CAVEAT, WARN, result_environment
from services.selftest.known_answer import KNOWN_ANSWER, SHOWN, row as _row, run_problem
from services.selftest.plan import N_SHOTS, SEED, SELFTEST_VERSION, THRESHOLDS

RESULT_SCHEMA = "qrosetta.selftest_result@1"
_RANK = {SKIP: 0, PASS: 1, WARN: 2, FAIL: 3}


class NotSelftestJob(ValueError):
    """The job is not a run of a self-test plan part."""


def _worst(statuses) -> str:
    return max(statuses, key=_RANK.__getitem__, default=SKIP)


def _circuit_of(task: dict):
    qasm = task.get("input_qasm")
    for name, _part, _kind, _what in CIRCUITS:
        if qasm is not None and circuit_text(name) == qasm:
            return name
    requested = (task.get("task_request") or {}).get("name") if isinstance(task.get("task_request"), dict) else None
    return requested if requested in CIRCUIT_PARTS and qasm is None else None


def _settings_differences(task: dict, part: str) -> list:
    wanted = {"optimization_level": 0, "apply_preprocessing": True, "timing_repeats": 1,
              "runner_config": {}, "agreement_thresholds": THRESHOLDS}
    if part == "measured":
        wanted.update(n_shots=N_SHOTS, seed=SEED)
    return [f"{field} {task.get(field)!r}, plan {value!r}" for field, value in wanted.items()
            if task.get(field) != value]


def evaluate_task(task) -> dict:
    """The compact evaluation of one task report: its plan circuit, settings differences,
    known-answer rows per requested backend, and each result's environment values. No
    statevector is kept."""
    task = task if isinstance(task, dict) else {}
    name = _circuit_of(task)
    out = {"circuit": name, "task_name": task.get("task_name"), "settings": [], "known_answer": [],
           "environment": []}
    if name is None:
        return out
    part = CIRCUIT_PARTS[name]
    out["settings"] = _settings_differences(task, part) if "input_qasm" in task else []
    raw = [r for r in task.get("raw_results") or [] if isinstance(r, dict)]
    if not raw and task.get("error"):
        out["known_answer"].append(_row(CIRCUIT_KINDS[name], FAIL, f"the task failed: {str(task['error'])[:SHOWN]}",
                                        None, name))
        return out
    entry = load_expected()["circuits"][name]
    seen = set()
    for result in raw:
        key = str(result.get("simulator"))
        seen.add(key)
        problem = run_problem(result)
        if problem:
            out["known_answer"].append(_row(CIRCUIT_KINDS[name], FAIL, problem, key, name))
            continue
        out["known_answer"].append(KNOWN_ANSWER[CIRCUIT_KINDS[name]](key, result, name, entry, part))
        out["environment"].append((key, result_environment(result, key, part)))
    requested = _dict(task.get("resolved_runners")).get("requested") or []
    for key in requested:
        if key not in seen:
            out["known_answer"].append(_row(CIRCUIT_KINDS[name], FAIL, "no result for a backend named in target_simulators", key, name))
    return out


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _plan_rows(part, tasks: list, report: dict) -> list:
    rows = []
    planned = [n for n, p, _k, _w in CIRCUITS if p == part]
    ran = [t["circuit"] for t in tasks]
    for task in tasks:
        if task["circuit"] is None:
            rows.append(_row("plan", FAIL, f"task {task['task_name']!r} is not a circuit of the plan's {part} part"))
        elif CIRCUIT_PARTS[task["circuit"]] != part:
            rows.append(_row("plan", FAIL, f"circuit belongs to the {CIRCUIT_PARTS[task['circuit']]} part", circuit=task["circuit"]))
        elif task["settings"]:
            rows.append(_row("plan", FAIL, "settings differ from the plan: " + "; ".join(task["settings"]), circuit=task["circuit"]))
    missing = [n for n in planned if n not in ran]
    if missing:
        rows.append(_row("plan", FAIL, "plan circuits not run: " + ", ".join(missing)))
    if part == "measured" and report.get("seed") != SEED:
        rows.append(_row("plan", FAIL, f"master seed {report.get('seed')!r}, plan {SEED}"))
    if not rows:
        rows.append(_row("plan", PASS, f"the {len(planned)} {part} circuits ran with the plan's settings"))
    return rows


def _coverage_rows(tasks: list) -> list:
    """FAIL rows for a plan circuit no backend ran and for a backend that has a result for
    some circuits of the job but none for another."""
    backends = {r["backend"] for t in tasks for r in t["known_answer"] if r["backend"] is not None}
    rows = []
    for task in tasks:
        name = task["circuit"]
        if name is None:
            continue
        kind = CIRCUIT_KINDS[name]
        if not task["known_answer"]:
            rows.append(_row(kind, FAIL, "no backend returned a result for this circuit", None, name))
        present = {r["backend"] for r in task["known_answer"]}
        for key in sorted(backends - present):
            rows.append(_row(kind, FAIL, "no result for this circuit, although the backend ran "
                                         "other circuits of the job", key, name))
    return rows


def _environment_rows(tasks: list) -> list:
    merged = {}
    for task in tasks:
        for key, checks in task["environment"]:
            for check, status, reason, value in checks:
                slot = merged.setdefault((key, check), {"statuses": [], "reasons": [], "values": []})
                slot["statuses"].append(status)
                if reason not in slot["reasons"]:
                    slot["reasons"].append(reason)
                if value not in slot["values"]:
                    slot["values"].append(value)
    rows = []
    for (key, check), slot in sorted(merged.items()):
        status = _worst(slot["statuses"])
        reasons = [r for r, s in zip(slot["reasons"], slot["statuses"]) if s == status] or slot["reasons"]
        rows.append(_row(check, status, "; ".join(reasons), key, values=slot["values"]))
    return rows


def evaluate_report(report: dict, job_id: str = None) -> dict:
    """The self-test result of a job report whose tasks went through ``evaluate_task``.
    Raises NotSelftestJob for a report that is not a playlist of a plan part."""
    tasks = report.get("benchmark_summary") if isinstance(report, dict) else None
    part = report.get("mode") if isinstance(report, dict) else None
    if not isinstance(tasks, list) or part not in ("statevector", "measured"):
        raise NotSelftestJob("the job is not a statevector or measured playlist")
    if not any(t["circuit"] is not None for t in tasks):
        raise NotSelftestJob("none of the job's circuits is a self-test circuit")
    plan_rows = _plan_rows(part, tasks, report)
    known = [r for t in tasks for r in t["known_answer"]] + _coverage_rows(tasks)
    environment = _environment_rows(tasks)
    rows = plan_rows + known + environment
    backends = {}
    for row in known + environment:
        if row["backend"] is not None:
            backends[row["backend"]] = _worst([backends.get(row["backend"], SKIP), row["status"]])
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in (PASS, WARN, FAIL, SKIP)}
    caveats = [VM_CAVEAT] if any(r["check"] == "host_virtualisation" and r["status"] == WARN
                                 for r in environment) else []
    return {
        "schema": RESULT_SCHEMA,
        "selftest_version": SELFTEST_VERSION,
        "expected_sha256": expected_file_sha256(),
        "job_id": job_id,
        "part": part,
        "report_source": "server_job",
        "status": _worst([r["status"] for r in rows] + [PASS]),
        "counts": counts,
        "backends": dict(sorted(backends.items())),
        "plan": plan_rows,
        "known_answer": known,
        "environment_checks": environment,
        "caveats": caveats,
    }
