"""RO-Crate entries for compile-only output: the circuit the compilers received, each
compiler's output circuit, one CreateAction per compile, the native components each
compiler image built from source, and the build files of each compiler that ran."""

import csv
import hashlib
import io
import json
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


def _native_components(record: dict) -> list:
    components = record.get("native_components")
    if not isinstance(components, list):
        return []
    out = []
    for entry in components:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) for k in ("name", "version")):
            continue
        out.append({str(k): (v if isinstance(v, str) else [str(x) for x in v])
                    for k, v in entry.items() if isinstance(v, str) or isinstance(v, list)})
    return out


def _native_id(component: dict) -> str:
    return f"#native-{re.sub(r'[^A-Za-z0-9._-]+', '-', component['name'])}-{re.sub(r'[^A-Za-z0-9._-]+', '-', component['version'])}"


def _native_entity(component: dict, trusted: bool = True) -> dict:
    details = {k: v for k, v in component.items()
               if k not in ("name", "version", "source_url", "source_sha256")}
    lead = ("Built from source in the compiler image, as the image's compile records report" if trusted
            else "Built from source in the compiler image, as the supplied report states (not checked by this server)")
    entity = {"@id": _native_id(component), "@type": "SoftwareApplication",
              "name": component["name"], "softwareVersion": component["version"],
              "description": (lead
                              + "".join(f"; {k.replace('_', ' ')}: "
                                        f"{', '.join(v) if isinstance(v, list) else v}"
                                        for k, v in sorted(details.items())) + ".")}
    if component.get("source_url"):
        entity["downloadUrl"] = component["source_url"]
    if component.get("source_sha256"):
        entity["identifier"] = f"sha256:{component['source_sha256']}"
    return entity


def compiler_applications(reports: list, services: dict = None, trusted: bool = True,
                          build_paths=()) -> list:
    """One SoftwareApplication per compiler used, named from the exporting server's
    registry, with the pip SDK versions and code hashes its records report, a reference to
    each native component (built from source, its own entity) and ``hasPart`` links to the
    crate's build files of that compiler (``build_paths``)."""
    seen, natives = {}, {}
    for report in reports:
        for record in _records(report):
            cid = record.get("compiler_id")
            entry = seen.setdefault(cid, {"name": (services or {}).get(cid, {}).get("name") or cid,
                                          "versions": set(), "hashes": set(), "natives": set()})
            native_names = set()
            for component in _native_components(record):
                natives.setdefault(_native_id(component), component)
                entry["natives"].add(_native_id(component))
                native_names.add(component["name"])
            for pkg, ver in _versions(record).items():
                if pkg not in native_names:
                    entry["versions"].add(f"{pkg}=={ver}")
            if record.get("compiler_code_sha256"):
                entry["hashes"].add(record["compiler_code_sha256"])
    def parts(cid):
        svc = (services or {}).get(cid) or {}
        prefix = f"compilers/{_compiler_dir(svc['base_url'])}/" if svc.get("base_url") else None
        return [{"@id": p} for p in sorted(build_paths) if prefix and p.startswith(prefix)]

    apps = [{"@id": f"#compiler-{cid}", "@type": "SoftwareApplication",
             "name": f"{entry['name']} compile-only service",
             "softwareRequirements": sorted(entry["versions"]) + [{"@id": n} for n in sorted(entry["natives"])],
             **({"identifier": sorted(entry["hashes"])} if entry["hashes"] else {}),
             **({"hasPart": parts(cid)} if parts(cid) else {})}
            for cid, entry in seen.items()]
    return apps + [_native_entity(natives[n], trusted) for n in sorted(natives)]


def compile_provenance(reports_by_task: list) -> list:
    """``[{task, compiler, compiler_id, optimization_level, dispatch_status, gate metrics,
    sdk_versions, image_git_sha, compiler_code_sha256, passes_applied, error}]`` for
    provenance.json."""
    rows = []
    for task, report in reports_by_task:
        for record in _records(report):
            rows.append({"task": task, **{field: record.get(field) for field in (
                "compiler", "compiler_id", "optimization_level", "dispatch_status", "gate_count",
                "multi_qubit_gate_count", "circuit_depth", "gate_counts", "gate_metrics_basis",
                "sdk_versions", "native_components", "build_files", "image_git_sha",
                "compiler_code_sha256", "passes_applied", "error", "refusal", "refusal_kind")}})
    return rows


COMPILED_METRICS_PATH = "tables/compiled_circuits.csv"
_RECORD_FIELDS = ("compiler", "compiler_id", "optimization_level", "dispatch_status",
                  "refusal_kind", "refusal", "gate_count", "multi_qubit_gate_count",
                  "circuit_depth")
_METRIC_FIELDS = ("task",) + _RECORD_FIELDS + ("gate_counts", "file")


def compiled_metrics_csv(reports_by_task: list, file_paths: dict) -> str:
    """One CSV row per compile record; ``refusal_kind`` (input, output_check) and ``refusal`` are
    set for a compile the adapter refused or whose output failed its check and empty for
    other errors; ``gate_counts`` as sorted-key JSON, ``file`` the crate path of its output
    (``file_paths[(task, compiler key)]``), empty when it has none."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_METRIC_FIELDS, lineterminator="\n")
    writer.writeheader()
    for task, report in reports_by_task:
        for record in _records(report):
            counts = record.get("gate_counts")
            writer.writerow({
                "task": "" if task is None else task,
                **{field: "" if record.get(field) is None else record.get(field)
                   for field in _RECORD_FIELDS},
                "gate_counts": json.dumps(counts, sort_keys=True) if isinstance(counts, dict) else "",
                "file": file_paths.get((task, record.get("compiler")), ""),
            })
    return buf.getvalue()


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


def _build_hashes(record: dict) -> dict:
    files = record.get("build_files")
    return ({str(k): str(v) for k, v in files.items() if isinstance(v, str)}
            if isinstance(files, dict) else {})


def _source_file(name: str, filename: str):
    if "/" in filename or filename in ("", ".", ".."):
        return None
    for base in (os.getcwd(), os.path.join(os.getcwd(), "..")):
        path = os.path.join(base, "compilers", name, filename)
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                return fh.read()
    return None


_BUILD_COPY = re.compile(r"^COPY\s+(?:--from=\S+\s+)?(.+?)\s+/usr/local/share/qrosetta-build/\s*$", re.M)


def _known_build_files(name: str) -> set:
    """The file names the server's copy of the compiler's Dockerfile puts in its build-files
    directory."""
    dockerfile = _source_file(name, "Dockerfile")
    if dockerfile is None:
        return set()
    return {os.path.basename(src) for line in _BUILD_COPY.findall(dockerfile.decode("utf-8", "replace"))
            for src in line.split()}


def compiler_build_files(reports: list, compiler_services: dict, trusted: bool = True) -> dict:
    """``{crate path: (bytes, check)}`` of the build files (Dockerfile, requirements.lock,
    patches, build sources, generated data) of each compiler whose image ran a compile of
    the reports (refusals included), read from compilers/<name>/ beside the API source.
    ``check`` is ``sha256`` when the file's sha256 equals the one every record of that
    compiler reports for its image and its name is one the server's Dockerfile copies, or
    ``lock_pins`` when records report no build files and the lock pins every recorded
    package at the recorded version. Nothing is included unless ``trusted`` (the report is
    the server's own job)."""
    if not trusted:
        return {}
    hashed, legacy = {}, {}
    for report in reports:
        for record in _records(report):
            cid = record.get("compiler_id")
            if cid not in compiler_services:
                continue
            if _build_hashes(record):
                hashed.setdefault(cid, []).append(_build_hashes(record))
            elif record.get("dispatch_status") == "ok" and _versions(record):
                legacy.setdefault(cid, []).append(_versions(record))
    out = {}
    for cid, hash_sets in hashed.items():
        name = _compiler_dir(compiler_services[cid]["base_url"])
        known = _known_build_files(name)
        for filename in sorted({f for hashes in hash_sets for f in hashes} & known):
            reported = {hashes.get(filename) for hashes in hash_sets}
            data = _source_file(name, filename)
            if data is not None and reported == {hashlib.sha256(data).hexdigest()}:
                out[f"compilers/{name}/{filename}"] = (data, "sha256")
    for cid, version_sets in legacy.items():
        name = _compiler_dir(compiler_services[cid]["base_url"])
        path = f"compilers/{name}/requirements.lock"
        data = None if path in out else _source_file(name, "requirements.lock")
        if data is None:
            continue
        pins = _pins(data)
        if all(pins.get(re.sub(r"[-_.]+", "-", pkg).lower()) == ver
               for versions in version_sets for pkg, ver in versions.items()):
            out[path] = (data, "lock_pins")
    return out


_BUILD_FILE_DESCRIPTIONS = (
    ("requirements.lock", "text/plain", "Full pinned Python environment (pip freeze) of the {name} image"),
    ("build-requirements.txt", "text/plain", "Python packages installed in the build stage of the {name} image"),
    ("Dockerfile", "text/plain", "Dockerfile the {name} image was built from"),
    (".patch", "text/x-diff", "Patch applied to a native component's source when the {name} image was built"),
    (".cpp", "text/x-c++src", "C++ source compiled in the build stage of the {name} image"),
    (".json", "application/json", "Data file generated when the {name} image was built (for Quartz, the ECC set it rewrites with)"),
)
_CHECKS = {
    "sha256": ("included because its sha256 equals the one the compiler's records report for the "
               "image that ran"),
    "lock_pins": ("included because the compiler's records (from an image that reports no build-file "
                  "hashes) list SDK versions that this lock pins exactly"),
}


def compiler_build_entity(crate_path: str, data: bytes, check: str) -> dict:
    name, filename = crate_path.split("/")[1], crate_path.split("/")[-1]
    fmt, text = "text/plain", "Build file of the {name} image"
    for suffix, suffix_fmt, suffix_text in _BUILD_FILE_DESCRIPTIONS:
        if filename.endswith(suffix):
            fmt, text = suffix_fmt, suffix_text
            break
    return {"@id": crate_path, "@type": "File", "name": filename,
            "description": (text.format(name=name) + ", as committed in the exporting server's "
                            f"source tree; {_CHECKS[check]}."),
            "sha256": hashlib.sha256(data).hexdigest(),
            "encodingFormat": fmt}
