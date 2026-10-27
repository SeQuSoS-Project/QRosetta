"""Licences of the bundled benchmark circuits (MQT Bench, QASMBench), written into every RO-Crate and
experiment bundle that carries one of those circuits."""

from pathlib import Path
from typing import Iterable, Optional

_BENCHMARKS = Path(__file__).resolve().parents[1] / "benchmarks"

BUNDLED = {
    "mqt": {
        "name": "MQT Bench",
        "origin": ("generated with mqt.bench 1.1.9, Chair for Design Automation, Technical University "
                   "of Munich"),
        "licence": "MIT licence",
        "url": "https://www.cda.cit.tum.de/mqtbench/",
        "source_file": _BENCHMARKS / "mqtbench" / "LICENSE",
        "path": "licenses/MQT-Bench-LICENSE.txt",
    },
    "qasmbench": {
        "name": "QASMBench",
        "origin": ("pnnl/QASMBench at commit 357b942396d5c2b7cbc1c229c585a6ef5ccaebac, Battelle Memorial "
                   "Institute / Pacific Northwest National Laboratory"),
        "licence": "QASMBench licence of the Battelle Memorial Institute",
        "url": "https://github.com/pnnl/QASMBench",
        "source_file": _BENCHMARKS / "qasmbench" / "LICENSE",
        "path": "licenses/QASMBench-LICENSE.txt",
    },
}


def bundled_source(request) -> Optional[str]:
    """``mqt`` or ``qasmbench`` when a task request names a bundled circuit, else None."""
    if not isinstance(request, dict) or request.get("literal_qasm"):
        return None
    source = request.get("source")
    return source if source in BUNDLED else None


def licence_files(sources: Iterable[Optional[str]]) -> dict:
    """{path in the archive: licence text} for each bundled source named in ``sources``."""
    return {BUNDLED[s]["path"]: BUNDLED[s]["source_file"].read_bytes()
            for s in sorted({s for s in sources if s in BUNDLED})}


def circuit_note(source: str) -> str:
    """One sentence for a circuit file's description: where it comes from and its licence."""
    entry = BUNDLED[source]
    return (f" A {entry['name']} circuit ({entry['origin']}), under the {entry['licence']}; the licence "
            f"text is {entry['path']}.")
