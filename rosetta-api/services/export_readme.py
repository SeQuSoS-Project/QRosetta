"""README.txt at the root of every RO-Crate: what the crate is, where each kind of file is and
how to check it, written from the crate's own ro-crate-metadata.json."""

import re
import textwrap
from typing import Dict, List, Optional

README_PATH = "README.txt"
README_DESCRIPTION = ("Plain-text guide to this crate for a reader without the Quantum Rosetta "
                      "documentation, written from ro-crate-metadata.json.")
LISTED_PER_FOLDER = 40
WIDTH = 78

FOLDERS = {
    "circuits": "The input circuits of the playlist, one per circuit, as submitted.",
    "dispatched_circuits": ("The exact OpenQASM text the API sent to each backend. The API-side "
                            "changes from the input are listed in each file's description in "
                            "ro-crate-metadata.json."),
    "transpiled_circuits": ("The circuit each backend adapter reported executing, after its own "
                            "transforms (listed in results.json, raw_results[].preprocessing_applied)."),
    "compile_inputs": "The circuit every compile-only service received, one per playlist circuit.",
    "compiled_circuits": "The output circuit of each compile-only service. These were not simulated.",
    "figures": ("Figures made from results.json; each figure has a .spec.json with its view and "
                "parameters."),
    "tables": "Tables made from results.json; each table's caption is in its description.",
    "reference": "Reference text, such as the glossary of the agreement labels.",
    "runners": ("Each runner image's pinned Python environment (requirements.lock), included only "
                "when its sha256 equals the hash the image reported for itself."),
    "compilers": "Build files of each compile-only service whose image ran.",
}

CHECK_COMMAND = (
    "python3 -c \"import json,hashlib; [print(e['@id'], 'ok' if hashlib.sha256(open(e['@id'],'rb')"
    ".read()).hexdigest() == e['sha256'] else 'DIFFERS') for e in json.load(open("
    "'ro-crate-metadata.json'))['@graph'] if e.get('sha256')]\"")


def readme_entity() -> dict:
    """The File entity of README.txt; its sha256 and contentSize are added with the others."""
    return {"@id": README_PATH, "@type": "File", "name": README_PATH,
            "description": README_DESCRIPTION, "encodingFormat": "text/plain"}


def add_readme_entity(metadata: dict) -> None:
    """Add README.txt to the graph and first in the root's hasPart."""
    graph = metadata["@graph"]
    graph.append(readme_entity())
    root = _by_id(graph).get("./")
    if root is not None:
        root["hasPart"] = [{"@id": README_PATH}] + list(root.get("hasPart") or [])


def _by_id(graph: List[dict]) -> Dict[str, dict]:
    return {e.get("@id"): e for e in graph if isinstance(e, dict)}


def _para(text: str, indent: str = "") -> List[str]:
    return textwrap.wrap(str(text), WIDTH, initial_indent=indent, subsequent_indent=indent,
                         break_long_words=False, break_on_hyphens=False) or [indent.rstrip()]


def _property(nodes: dict, node_id: str, heading: str) -> List[str]:
    node = nodes.get(node_id)
    if not node:
        return []
    return _para(f"{heading}: {node.get('value')}") + _para(node.get("description", ""), "  ") + [""]


def _commit(url: Optional[str]) -> Optional[str]:
    m = re.search(r"/commit/([0-9a-f]{7,40})$", url or "")
    return m.group(1) if m else None


def _software(nodes: dict, platform_note: str) -> List[str]:
    node = nodes.get("#quantum-rosetta") or {}
    version = node.get("softwareVersion")
    lines = ["Software"]
    lines += _para(f"Quantum Rosetta {version}." if version else
                   "Quantum Rosetta; the platform version is not asserted by this crate (see "
                   "report source).", "  ")
    commit = _commit(node.get("url"))
    lines += _para(f"Source{f' commit {commit}' if commit else ''}: "
                   f"{node.get('url') or node.get('codeRepository')}", "  ")
    if platform_note:
        lines += _para(platform_note.strip(), "  ")
    lines += _para("Each backend's SDK versions are in its entity in ro-crate-metadata.json and in "
                   "provenance.json; the analysis version is in provenance.json.", "  ")
    return lines + [""]


def _what(nodes: dict, files: List[dict]) -> List[str]:
    root = nodes.get("./") or {}
    runs = [e for e in nodes.values() if e.get("@type") == "CreateAction"
            and str(e.get("@id", "")).startswith("#run-")]
    compiles = [e for e in nodes.values() if e.get("@type") == "CreateAction"
                and str(e.get("@id", "")).startswith("#compile-")]
    circuits = [f for f in files if f["@id"] == "circuit.qasm" or f["@id"].startswith("circuits/")]
    lines = ["What this is"]
    summary = (f"A record of one Quantum Rosetta run, exported {root.get('datePublished')}: "
               f"{len(circuits)} input circuit{'s' if len(circuits) != 1 else ''}, "
               f"{len(runs)} backend execution{'s' if len(runs) != 1 else ''}"
               + (f" and {len(compiles)} compile-only record{'s' if len(compiles) != 1 else ''}"
                  if compiles else "") + ".")
    lines += _para(summary, "  ")
    lines += _para("It is an RO-Crate 1.1 following the Process Run Crate profile 0.5. "
                   "ro-crate-metadata.json is the machine-readable description of every file, "
                   "every backend execution (a CreateAction) and every parameter.", "  ")
    author = nodes.get("#author")
    if author:
        lines += _para(f"Author: {author.get('name')}"
                       + (f", {nodes['#affiliation'].get('name')}" if "#affiliation" in nodes else "")
                       + ".", "  ")
    return lines + [""]


def _file_lines(entity: dict, indent: str) -> List[str]:
    return _para(entity["@id"], indent) + _para(entity.get("description", ""), indent + "    ")


def _layout(files: List[dict]) -> List[str]:
    lines = ["Where things are"]
    top = sorted((f for f in files if "/" not in f["@id"]), key=lambda f: f["@id"] != README_PATH)
    folders: Dict[str, List[str]] = {}
    for f in files:
        if "/" in f["@id"]:
            folder, rest = f["@id"].split("/", 1)
            folders.setdefault(folder, []).append(rest)
    lines += _para("ro-crate-metadata.json", "  ") + _para(
        "The crate's metadata: each file below with its sha256, size and description, the backend "
        "executions, the analysis and its parameters, and the software.", "      ")
    for f in top:
        lines += _file_lines(f, "  ")
    for name, members in folders.items():
        lines.append("")
        lines += _para(f"{name}/ ({len(members)} file{'s' if len(members) != 1 else ''})", "  ")
        if name in FOLDERS:
            lines += _para(FOLDERS[name], "      ")
        if len(members) <= LISTED_PER_FOLDER:
            lines += _para(", ".join(members), "      ")
    if folders:
        lines += [""] + _para("Each file's own description is in ro-crate-metadata.json.", "  ")
    return lines + [""]


def _checking() -> List[str]:
    lines = ["Checking the files"]
    lines += _para("ro-crate-metadata.json gives every file's sha256 and contentSize (bytes), "
                   "README.txt included; the metadata file itself carries no hash. From this "
                   "directory, sha256sum results.json prints one file's hash to compare with its "
                   "\"sha256\" entry. This command checks them all:", "  ")
    lines.append("")
    lines.append("    " + CHECK_COMMAND)
    return lines + [""]


def crate_readme(metadata: dict, crate_dir: str, platform_note: str = "") -> str:
    """README.txt for the crate described by ``metadata`` (whose graph already holds the
    README's own entity), in the ZIP's top-level directory ``crate_dir``. ``platform_note`` is
    the part of the platform entity's description that says what its source links point at."""
    graph = [e for e in metadata.get("@graph") or [] if isinstance(e, dict)]
    nodes = _by_id(graph)
    files = [e for e in graph if e.get("@type") == "File" and isinstance(e.get("@id"), str)]
    title = (nodes.get("./") or {}).get("name") or "Quantum Rosetta RO-Crate"
    lines = [title, "=" * min(len(title), WIDTH), ""]
    lines += _para(f"This file describes {crate_dir}/, the directory it is in.") + [""]
    lines += _what(nodes, files)
    lines += _property(nodes, "#report-source", "Report source")
    lines += _property(nodes, "#run-completeness", "Completeness")
    lines += _property(nodes, "#specimens", "Specimens (the images that ran)")
    lines += _property(nodes, "#timing-caveats", "Timing caveats")
    lines += _layout(files)
    lines += _checking()
    lines += _software(nodes, platform_note)
    return "\n".join(lines).rstrip() + "\n"
