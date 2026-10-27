"""The circuit texts of a run report, and nothing else: the subset a read-only share link
serves (fields keep their report names, so the Circuits view reads either), and the same texts
as the Circuits view's panes for GET /jobs/{id}/circuit-texts (circuit_panes mirrors
static/js/circuit_panes.js circuitPanes; test_circuit_texts_route.py compares them)."""

_RESULT_TEXT_FIELDS = ("simulator", "dispatch_group", "transpiled_qasm", "gate_metrics_basis",
                       "dispatch_status")
_RESULT_NUMBER_FIELDS = ("gate_count", "circuit_depth")


def _strings(value) -> list:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _result_texts(result: dict) -> dict:
    out = {key: result[key] for key in _RESULT_TEXT_FIELDS if isinstance(result.get(key), str)}
    out.update({key: result[key] for key in _RESULT_NUMBER_FIELDS
                if isinstance(result.get(key), int) and not isinstance(result.get(key), bool)})
    out["preprocessing_applied"] = _strings(result.get("preprocessing_applied"))
    versions = result.get("sdk_versions")
    if isinstance(versions, dict):
        out["sdk_versions"] = {k: v for k, v in versions.items() if isinstance(k, str) and isinstance(v, str)}
    return out


_COMPILED_TEXT_FIELDS = ("compiler", "compiler_id", "compiler_name", "transpiled_qasm",
                         "gate_metrics_basis", "dispatch_status", "refusal", "refusal_kind")


def _compiled_texts(record: dict) -> dict:
    out = {key: record[key] for key in _COMPILED_TEXT_FIELDS if isinstance(record.get(key), str)}
    numbers = ("optimization_level", "multi_qubit_gate_count") + _RESULT_NUMBER_FIELDS
    out.update({key: record[key] for key in numbers
                if isinstance(record.get(key), int) and not isinstance(record.get(key), bool)})
    counts = record.get("gate_counts")
    if isinstance(counts, dict):
        out["gate_counts"] = {k: v for k, v in counts.items() if isinstance(k, str) and isinstance(v, int)
                              and not isinstance(v, bool)}
    out["passes_applied"] = _strings(record.get("passes_applied"))
    versions = record.get("sdk_versions")
    if isinstance(versions, dict):
        out["sdk_versions"] = {k: v for k, v in versions.items() if isinstance(k, str) and isinstance(v, str)}
    components = record.get("native_components")
    if isinstance(components, list):
        out["native_components"] = [
            {k: v for k, v in entry.items() if isinstance(k, str) and (
                isinstance(v, str) or (isinstance(v, list) and all(isinstance(x, str) for x in v)))}
            for entry in components if isinstance(entry, dict)]
    if record.get("dispatch_status") == "skipped" and isinstance(record.get("error"), str):
        out["error"] = record["error"]
    return out


def _dispatched_texts(record: dict) -> dict:
    return {"group": record["group"], "qasm": record["qasm"],
            "api_preprocessing_applied": _strings(record.get("api_preprocessing_applied")),
            "runners": _strings(record.get("runners"))}


def single_circuit_texts(report: dict) -> dict:
    """Submitted, dispatched and executed circuit texts of one circuit's report, with each
    executed circuit's gate metrics, transforms and SDK versions, and the compile-only
    input and outputs when the run had any. Error text, timings, outputs and run
    configuration are left out."""
    out = {}
    if isinstance(report.get("input_qasm"), str):
        out["input_qasm"] = report["input_qasm"]
    out["dispatched_circuits"] = [
        _dispatched_texts(record) for record in report.get("dispatched_circuits") or []
        if isinstance(record, dict) and isinstance(record.get("group"), str)
        and isinstance(record.get("qasm"), str)]
    out["raw_results"] = [_result_texts(result) for result in report.get("raw_results") or []
                          if isinstance(result, dict)]
    compile_input = report.get("compile_input")
    if isinstance(compile_input, dict) and isinstance(compile_input.get("qasm"), str):
        out["compile_input"] = {"qasm": compile_input["qasm"],
                                "api_preprocessing_applied": _strings(compile_input.get("api_preprocessing_applied"))}
    if isinstance(report.get("compiled_circuits"), list):
        out["compiled_circuits"] = [_compiled_texts(record) for record in report["compiled_circuits"]
                                    if isinstance(record, dict)]
    return out


def _object(value) -> bool:
    """A JSON object or array: what the Circuits view treats as a record."""
    return isinstance(value, (dict, list))


def _field(record, key):
    return record.get(key) if isinstance(record, dict) else None


def _text(value):
    return value if isinstance(value, str) else None


def _key(record, field: str, fallback: str) -> str:
    value = _field(record, field)
    return value if isinstance(value, str) else fallback


def circuit_panes(report) -> list:
    """The panes of one circuit's report, in the Circuits view's order and with its ids
    (static/js/circuit_panes.js ``circuitPanes``): ``input``, ``dispatched:<group>``,
    ``executed:<key>``, ``compile-input`` and ``compiled:<key>``. Each has id, kind, key,
    group and text, plus the share-link allowlist's fields of its record."""
    if not isinstance(report, dict):
        return []
    panes = []
    if isinstance(report.get("input_qasm"), str):
        panes.append({"id": "input", "kind": "input", "key": None, "group": None,
                      "text": report["input_qasm"]})
    dispatched = report.get("dispatched_circuits")
    for record in dispatched if isinstance(dispatched, list) else []:
        if not (isinstance(record, dict) and isinstance(record.get("group"), str)
                and isinstance(record.get("qasm"), str)):
            continue
        texts = _dispatched_texts(record)
        panes.append({"id": f"dispatched:{record['group']}", "kind": "dispatched", "key": None,
                      "group": record["group"], "text": record["qasm"],
                      "api_preprocessing_applied": texts["api_preprocessing_applied"],
                      "runners": texts["runners"]})
    results = report.get("raw_results")
    for index, result in enumerate(results if isinstance(results, list) else []):
        if not _object(result):
            continue
        key = _key(result, "simulator", f"result {index + 1}")
        texts = _result_texts(result) if isinstance(result, dict) else {"preprocessing_applied": []}
        panes.append({"id": f"executed:{key}", "kind": "executed", "key": key,
                      "group": _text(_field(result, "dispatch_group")),
                      "text": _text(_field(result, "transpiled_qasm")),
                      **{k: v for k, v in texts.items()
                         if k not in ("simulator", "dispatch_group", "transpiled_qasm")}})
    compile_input = report.get("compile_input")
    if isinstance(compile_input, dict) and isinstance(compile_input.get("qasm"), str):
        panes.append({"id": "compile-input", "kind": "compile-input", "key": None, "group": None,
                      "text": compile_input["qasm"],
                      "api_preprocessing_applied": _strings(compile_input.get("api_preprocessing_applied"))})
    compiled = report.get("compiled_circuits")
    for index, record in enumerate(compiled if isinstance(compiled, list) else []):
        if not _object(record):
            continue
        key = _key(record, "compiler", f"compiler {index + 1}")
        texts = _compiled_texts(record) if isinstance(record, dict) else {"passes_applied": []}
        panes.append({"id": f"compiled:{key}", "kind": "compiled", "key": key, "group": None,
                      "text": _text(_field(record, "transpiled_qasm")),
                      **{k: v for k, v in texts.items() if k not in ("compiler", "transpiled_qasm")}})
    return panes


def task_panes(task, index=None) -> dict:
    """``{task, task_name, panes}`` of one circuit's report; ``index`` is its playlist index."""
    name = task.get("task_name") if isinstance(task, dict) else None
    return {"task": index, "task_name": name if isinstance(name, str) else None,
            "panes": circuit_panes(task)}


def report_circuits(report) -> list:
    """``task_panes`` of a single-circuit report, or of every task of a playlist report whose
    tasks may already be ``task_panes`` results (``job_store.full_report``'s each_task)."""
    if not isinstance(report, dict):
        return []
    tasks = report.get("benchmark_summary")
    if not isinstance(tasks, list):
        return [task_panes(report)]
    return [{**task, "task": i} if isinstance(task, dict) and "panes" in task else task_panes(task, i)
            for i, task in enumerate(tasks)]


def circuit_texts(report) -> dict:
    """``single_circuit_texts`` for a single-circuit report; for a batch report,
    ``{"benchmark_summary": [...]}`` with one entry per task, each with its ``task_name``."""
    if not isinstance(report, dict):
        return {}
    summary = report.get("benchmark_summary")
    if isinstance(summary, list):
        tasks = []
        for task in summary:
            if not isinstance(task, dict):
                continue
            entry = single_circuit_texts(task)
            if isinstance(task.get("task_name"), str):
                entry["task_name"] = task["task_name"]
            tasks.append(entry)
        return {"benchmark_summary": tasks}
    return single_circuit_texts(report)
