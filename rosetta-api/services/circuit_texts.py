"""The circuit texts of a run report, and nothing else: the subset a read-only share link
serves. Fields keep their report names, so the Circuits view reads either."""

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
                         "gate_metrics_basis", "dispatch_status")


def _compiled_texts(record: dict) -> dict:
    out = {key: record[key] for key in _COMPILED_TEXT_FIELDS if isinstance(record.get(key), str)}
    out.update({key: record[key] for key in ("optimization_level",) + _RESULT_NUMBER_FIELDS
                if isinstance(record.get(key), int) and not isinstance(record.get(key), bool)})
    out["passes_applied"] = _strings(record.get("passes_applied"))
    versions = record.get("sdk_versions")
    if isinstance(versions, dict):
        out["sdk_versions"] = {k: v for k, v in versions.items() if isinstance(k, str) and isinstance(v, str)}
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
