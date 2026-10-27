#!/usr/bin/env python3
"""Prints the OCI annotation labels (org.opencontainers.image.*) of one service image, one
key=value per line, for `--label` arguments: scripts/safe_boot.sh and scripts/release/image.sh.
Standard library only.

    oci_labels.py DOCKERFILE --revision SHA [--version V] [--source URL]

DOCKERFILE is the path of one of the repository's Dockerfiles; --version defaults to
qrosetta_cli.__version__, --source to $QROSETTA_REPOSITORY_URL or the public repository."""

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PUBLIC_REPOSITORY = "https://github.com/SeQuSoS-Project/QRosetta"
LICENSES = "Apache-2.0"
THIRD_PARTY = ("The image also contains third-party software under other licences "
               "(THIRD_PARTY_NOTICES.md in the source repository).")


def _runner(name, sdk):
    return (f"Quantum Rosetta {name} runner",
            f"Quantum Rosetta runner: executes OpenQASM 2.0 circuits with {sdk} and returns statevectors "
            "or counts with split timing.")


def _compiler(name, sdk):
    return (f"Quantum Rosetta {name} compiler",
            f"Quantum Rosetta compile-only service: compiles OpenQASM 2.0 circuits with {sdk}; its "
            "outputs are never simulated or timed.")


SERVICES = {
    "nginx/Dockerfile": (
        "Quantum Rosetta web front end",
        "Quantum Rosetta's nginx reverse proxy: serves the browser page and forwards API requests."),
    "infra/Dockerfile.frontend": (
        "Quantum Rosetta Cloud Run front end",
        "Quantum Rosetta's browser page served by nginx on Google Cloud Run, forwarding API requests to "
        "a remote Quantum Rosetta API."),
    "rosetta-api/Dockerfile": (
        "Quantum Rosetta API",
        "Quantum Rosetta's API: validates circuits, dispatches them to the simulator runners, compares "
        "their results and exports RO-Crate bundles."),
    "runners/pytket-qiskit-runner/Dockerfile": _runner("Qiskit", "Qiskit Aer (pytket-qiskit)"),
    "runners/pytket-cirq-runner/Dockerfile": _runner("Cirq", "Cirq (pytket-cirq)"),
    "runners/pytket-qulacs-runner/Dockerfile": _runner("Qulacs", "Qulacs (pytket-qulacs)"),
    "runners/pytket-quest-runner/Dockerfile": _runner("QuEST", "QuEST (pytket-quest)"),
    "runners/pytket-braket-runner/Dockerfile": _runner("Braket", "the Amazon Braket local simulator (pytket-braket)"),
    "runners/pytket-projectq-runner/Dockerfile": _runner("ProjectQ", "ProjectQ (pytket-projectq)"),
    "runners/pennylane-lightning-runner/Dockerfile": _runner("PennyLane Lightning", "PennyLane lightning.qubit"),
    "runners/pennylane-default-runner/Dockerfile": _runner("PennyLane default", "PennyLane default.qubit"),
    "runners/qsim-cirq-runner/Dockerfile": _runner("qsim", "qsim (qsimcirq)"),
    "runners/pyquil-runner/Dockerfile": _runner("pyQuil", "pyQuil (pytket-pyquil)"),
    "runners/myqlm-runner/Dockerfile": _runner("myQLM", "myQLM"),
    "runners/qibo-runner/Dockerfile": _runner("Qibo", "Qibo"),
    "runners/qrisp-runner/Dockerfile": _runner("Qrisp", "Qrisp"),
    "runners/torch-quantum-runner/Dockerfile": _runner("TorchQuantum", "TorchQuantum"),
    "runners/quimb-runner/Dockerfile": _runner("quimb", "quimb"),
    "runners/cuquantum-runner/Dockerfile": _runner("cuQuantum", "Qiskit Aer GPU with cuStateVec on an NVIDIA GPU"),
    "compilers/bqskit-compiler/Dockerfile": _compiler("BQSKit", "BQSKit"),
    "compilers/pyzx-compiler/Dockerfile": _compiler("PyZX", "PyZX"),
    "compilers/qmap-compiler/Dockerfile": _compiler("QMAP", "MQT QMAP"),
    "compilers/cirq-compiler/Dockerfile": _compiler("Cirq", "Cirq transformers"),
    "compilers/staq-compiler/Dockerfile": _compiler("staq", "staq"),
    "compilers/qsynth-compiler/Dockerfile": _compiler("Q-Synth", "Q-Synth"),
    "compilers/quartz-compiler/Dockerfile": _compiler("Quartz", "Quartz"),
    "compilers/synthetiq-compiler/Dockerfile": _compiler("Synthetiq", "Synthetiq"),
}


def platform_version(repo=REPO):
    text = (repo / "qrosetta_cli" / "__init__.py").read_text()
    return re.search(r'^__version__ = "([^"]+)"$', text, re.M).group(1)


def service_key(dockerfile, repo=REPO):
    """The SERVICES key of a Dockerfile: its path relative to the repository root."""
    path = Path(dockerfile)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve().relative_to(repo.resolve()).as_posix()


def labels(dockerfile, revision, version=None, source=None, repo=REPO):
    key = service_key(dockerfile, repo)
    if key not in SERVICES:
        raise ValueError(f"{key} has no OCI title and description in scripts/release/oci_labels.py")
    title, description = SERVICES[key]
    source = (source or os.environ.get("QROSETTA_REPOSITORY_URL") or PUBLIC_REPOSITORY).rstrip("/")
    return {
        "org.opencontainers.image.title": title,
        "org.opencontainers.image.description": f"{description} {THIRD_PARTY}",
        "org.opencontainers.image.licenses": LICENSES,
        "org.opencontainers.image.source": source,
        "org.opencontainers.image.revision": revision,
        "org.opencontainers.image.version": version or platform_version(repo),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dockerfile")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--version")
    parser.add_argument("--source")
    args = parser.parse_args(argv)
    if not args.revision.strip():
        print("oci_labels.py: --revision is empty", file=sys.stderr)
        return 1
    try:
        found = labels(args.dockerfile, args.revision, args.version, args.source)
    except ValueError as exc:
        print(f"oci_labels.py: {exc}", file=sys.stderr)
        return 1
    for key, value in found.items():
        if "\n" in value:
            print(f"oci_labels.py: {key} contains a newline", file=sys.stderr)
            return 1
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
