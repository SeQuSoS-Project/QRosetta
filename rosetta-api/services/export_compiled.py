"""RO-Crate entries for compile-only output: the circuit the compilers received, each
compiler's output circuit, and the pinned environment of each compiler used."""

import os


def compile_input_path(task_id) -> str:
    return "compile_input.qasm" if task_id is None else f"compile_inputs/{task_id}.qasm"


def compiled_circuit_files(report: dict, task_id, label, scoped_path) -> list:
    """``[{path, name, qasm, description}]`` for a report's compile input and every compiled
    circuit that has text. ``scoped_path(folder, key)`` places a per-key file."""
    suffix = f" for '{label}'." if task_id is not None else "."
    files = []
    compile_input = report.get("compile_input")
    if isinstance(compile_input, dict) and isinstance(compile_input.get("qasm"), str):
        notes = [n for n in compile_input.get("api_preprocessing_applied") or [] if isinstance(n, str)]
        files.append({
            "path": compile_input_path(task_id),
            "name": "compile_input.qasm" if task_id is None else f"{task_id}.qasm",
            "qasm": compile_input["qasm"],
            "description": ("The circuit every compile-only service received" + suffix
                            + (" API-side changes from the input circuit: " + "; ".join(notes)
                               if notes else " Identical to the input circuit.")),
        })
    for record in report.get("compiled_circuits") or []:
        if not isinstance(record, dict) or not isinstance(record.get("transpiled_qasm"), str):
            continue
        key = str(record.get("compiler"))
        passes = [p for p in record.get("passes_applied") or [] if isinstance(p, str)]
        files.append({
            "path": scoped_path("compiled_circuits", key),
            "name": f"{key}.qasm",
            "qasm": record["transpiled_qasm"],
            "description": (f"The output circuit of the {key} compile-only service at "
                            f"optimization level {record.get('optimization_level')}" + suffix
                            + " Not simulated." + (" Passes: " + "; ".join(passes) if passes else "")),
        })
    return files


def compiler_keys(report: dict) -> list:
    return [str(r.get("compiler")) for r in report.get("compiled_circuits") or []
            if isinstance(r, dict) and r.get("compiler") is not None]


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


def compiler_lock_files(reports: list, compiler_services: dict) -> dict:
    """``{crate path: bytes}`` of requirements.lock for each compiler the reports used, where
    the file is on disk (compilers/<name>/requirements.lock beside the API source)."""
    out = {}
    for report in reports:
        for record in report.get("compiled_circuits") or [] if isinstance(report, dict) else []:
            svc = compiler_services.get(record.get("compiler_id")) if isinstance(record, dict) else None
            if not svc:
                continue
            name = _compiler_dir(svc["base_url"])
            crate_path = f"compilers/{name}/requirements.lock"
            if crate_path in out:
                continue
            for base in (os.getcwd(), os.path.join(os.getcwd(), "..")):
                path = os.path.join(base, "compilers", name, "requirements.lock")
                if os.path.isfile(path):
                    with open(path, "rb") as fh:
                        out[crate_path] = fh.read()
                    break
    return out


def compiler_lock_entity(crate_path: str) -> dict:
    name = crate_path.split("/")[1]
    return {"@id": crate_path, "@type": "File", "name": "requirements.lock",
            "description": (f"Full pinned Python environment (pip freeze) of the {name} image, as "
                            "committed in the exporting server's source tree."),
            "encodingFormat": "text/plain"}
