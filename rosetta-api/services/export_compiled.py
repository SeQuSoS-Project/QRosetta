"""RO-Crate entries for compile-only output: the circuit the compilers received, each
compiler's output circuit, one CreateAction per compile, and the pinned environment of
each compiler that ran."""

import os
import re

ACTION_COMPLETED = "http://schema.org/CompletedActionStatus"
ACTION_FAILED = "http://schema.org/FailedActionStatus"
_PIN = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s;#]+)")


def compile_input_path(task_id) -> str:
    return "compile_input.qasm" if task_id is None else f"compile_inputs/{task_id}.qasm"


def _records(report: dict) -> list:
    records = report.get("compiled_circuits") if isinstance(report, dict) else None
    return [r for r in records if isinstance(r, dict)] if isinstance(records, list) else []


def _versions(record: dict) -> dict:
    versions = record.get("sdk_versions")
    return {str(k): str(v) for k, v in versions.items()} if isinstance(versions, dict) else {}


def _label(record: dict, services: dict = None) -> str:
    registered = (services or {}).get(record.get("compiler_id"), {}).get("name")
    name = registered or record.get("compiler_id") or record.get("compiler")
    return f"{name} at optimization level {record.get('optimization_level')}"


def compiled_circuit_files(report: dict, task_id, label, scoped_path) -> list:
    """``[{path, name, qasm, description, record}]`` for a report's compile input (record
    None) and every compiled circuit that has text. ``scoped_path(folder, key)`` places a
    per-key file."""
    suffix = f" for task '{label}' ({task_id})." if task_id is not None else "."
    files = []
    compile_input = report.get("compile_input")
    if isinstance(compile_input, dict) and isinstance(compile_input.get("qasm"), str):
        notes = [n for n in compile_input.get("api_preprocessing_applied") or [] if isinstance(n, str)]
        files.append({
            "path": compile_input_path(task_id),
            "name": "compile_input.qasm" if task_id is None else f"{task_id}.qasm",
            "qasm": compile_input["qasm"],
            "record": None,
            "description": ("The circuit every compile-only service received" + suffix
                            + (" API-side changes from the input circuit: " + "; ".join(notes)
                               if notes else " Identical to the input circuit.")),
        })
    for record in _records(report):
        if not isinstance(record.get("transpiled_qasm"), str):
            continue
        key = str(record.get("compiler"))
        passes = [p for p in record.get("passes_applied") or [] if isinstance(p, str)]
        files.append({
            "path": scoped_path("compiled_circuits", key),
            "name": f"{key}.qasm",
            "qasm": record["transpiled_qasm"],
            "record": record,
            "description": (f"The output circuit of {_label(record)} (key {key})" + suffix
                            + " Not simulated." + (" Passes: " + "; ".join(passes) if passes else "")),
        })
    return files


def compile_actions(report: dict, task_id, label, files: list, services: dict = None) -> list:
    """One CreateAction per compile record, from the compile input to its output file (or
    failed, with the reason), with the compiler as instrument."""
    suffix = f" for task '{label}' ({task_id})" if task_id is not None else ""
    input_ids = [f["path"] for f in files if f["record"] is None]
    output_by_key = {str(f["record"].get("compiler")): f["path"] for f in files if f["record"] is not None}
    frag = f"{task_id}-" if task_id is not None else ""
    actions = []
    for record in _records(report):
        key = str(record.get("compiler"))
        output = output_by_key.get(key)
        action = {
            "@id": f"#compile-{frag}{key}",
            "@type": "CreateAction",
            "name": f"Compilation by {_label(record, services)}{suffix}",
            "instrument": {"@id": f"#compiler-{record.get('compiler_id')}"},
            "actionStatus": ACTION_COMPLETED if output else ACTION_FAILED,
        }
        if input_ids:
            action["object"] = {"@id": input_ids[0]}
        if output:
            action["result"] = {"@id": output}
        else:
            action["error"] = f"{record.get('dispatch_status')}: {record.get('error') or 'no output recorded'}"
        for field, prop in (("dispatched_at", "startTime"), ("completed_at", "endTime")):
            if record.get(field):
                action[prop] = record[field]
        actions.append(action)
    return actions


def compiler_applications(reports: list, services: dict = None) -> list:
    """One SoftwareApplication per compiler used, named from the exporting server's
    registry, with the SDK versions and code hashes its records report."""
    seen = {}
    for report in reports:
        for record in _records(report):
            cid = record.get("compiler_id")
            entry = seen.setdefault(cid, {"name": (services or {}).get(cid, {}).get("name") or cid,
                                          "versions": set(), "hashes": set()})
            for pkg, ver in _versions(record).items():
                entry["versions"].add(f"{pkg}=={ver}")
            if record.get("compiler_code_sha256"):
                entry["hashes"].add(record["compiler_code_sha256"])
    return [{"@id": f"#compiler-{cid}", "@type": "SoftwareApplication",
             "name": f"{entry['name']} compile-only service",
             "softwareRequirements": sorted(entry["versions"]),
             **({"identifier": sorted(entry["hashes"])} if entry["hashes"] else {})}
            for cid, entry in seen.items()]


def compile_provenance(reports_by_task: list) -> list:
    """``[{task, compiler, compiler_id, optimization_level, dispatch_status, sdk_versions,
    compiler_code_sha256, passes_applied, error}]`` for provenance.json."""
    rows = []
    for task, report in reports_by_task:
        for record in _records(report):
            rows.append({"task": task, **{field: record.get(field) for field in (
                "compiler", "compiler_id", "optimization_level", "dispatch_status", "sdk_versions",
                "compiler_code_sha256", "passes_applied", "error")}})
    return rows


def compiler_keys(report: dict) -> list:
    """The ``compiler`` key of every compiled record, ``""`` for a record without a string key."""
    return [r.get("compiler") if isinstance(r.get("compiler"), str) else "" for r in _records(report)]


def strip_compiled_text(report: dict) -> None:
    """Remove the circuit texts that the crate stores as files from a results.json copy."""
    compile_input = report.get("compile_input")
    if isinstance(compile_input, dict):
        compile_input.pop("qasm", None)
    for record in report.get("compiled_circuits") or []:
        if isinstance(record, dict):
            record.pop("transpiled_qasm", None)


def _compiler_dir(base_url: str) -> str:
    return base_url.split("://", 1)[-1].split(":", 1)[0].split("/", 1)[0]


def _pins(lock_bytes: bytes) -> dict:
    pins = {}
    for line in lock_bytes.decode("utf-8", "replace").splitlines():
        m = _PIN.match(line.strip())
        if m:
            pins[re.sub(r"[-_.]+", "-", m.group(1)).lower()] = m.group(2)
    return pins


def compiler_lock_files(reports: list, compiler_services: dict) -> dict:
    """``{crate path: bytes}`` of requirements.lock for each compiler that produced output
    in the reports, read from compilers/<name>/ beside the API source. A lock is left out
    when it pins a version other than one the compiler's records report, since it would
    then not describe the environment that ran."""
    used = {}
    for report in reports:
        for record in _records(report):
            versions = _versions(record)
            if (record.get("dispatch_status") == "ok" and versions
                    and record.get("compiler_id") in compiler_services):
                used.setdefault(record["compiler_id"], []).append(versions)
    out = {}
    for cid, version_sets in used.items():
        name = _compiler_dir(compiler_services[cid]["base_url"])
        for base in (os.getcwd(), os.path.join(os.getcwd(), "..")):
            path = os.path.join(base, "compilers", name, "requirements.lock")
            if not os.path.isfile(path):
                continue
            with open(path, "rb") as fh:
                data = fh.read()
            pins = _pins(data)
            if all(pins.get(re.sub(r"[-_.]+", "-", pkg).lower()) == ver
                   for versions in version_sets for pkg, ver in versions.items()):
                out[f"compilers/{name}/requirements.lock"] = data
            break
    return out


def compiler_lock_entity(crate_path: str) -> dict:
    name = crate_path.split("/")[1]
    return {"@id": crate_path, "@type": "File", "name": "requirements.lock",
            "description": (f"Full pinned Python environment (pip freeze) of the {name} image, as "
                            "committed in the exporting server's source tree; included because "
                            "its pins match the SDK versions recorded in the report."),
            "encodingFormat": "text/plain"}
