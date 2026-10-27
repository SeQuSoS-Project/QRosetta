"""Checkout or installed mode, and the directory whose compose file the stack commands use
(spec Q13)."""

import os
from dataclasses import dataclass

from qrosetta_cli import output
from qrosetta_cli.errors import usage

BASE_FILES = ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml")
PACKAGE_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def compose_file(directory):
    """The base compose file in `directory`, or None."""
    for base in BASE_FILES:
        path = os.path.join(directory, base)
        if os.path.isfile(path):
            return path
    return None


@dataclass(frozen=True)
class Mode:
    name: str
    project_dir: str
    source: str


def is_checkout(directory):
    return bool(directory and compose_file(directory) and os.path.isdir(os.path.join(directory, "rosetta-api")))


def detect(flag=None, env=None, checkout=None):
    """--project-dir, else QROSETTA_PROJECT_DIR (QROSETTA_HOME is a deprecated alias), else the
    checkout this package lives in; otherwise installed mode, with no project directory."""
    env = os.environ if env is None else env
    named = [("--project-dir", flag), ("QROSETTA_PROJECT_DIR", env.get("QROSETTA_PROJECT_DIR"))]
    if env.get("QROSETTA_HOME") and not env.get("QROSETTA_PROJECT_DIR"):
        named.append(("QROSETTA_HOME", env["QROSETTA_HOME"]))
    for source, path in named:
        if not path:
            continue
        if source == "QROSETTA_HOME":
            output.warn("QROSETTA_HOME is deprecated; set QROSETTA_PROJECT_DIR instead.", "deprecated")
        path = os.path.abspath(os.path.expanduser(path))
        if not compose_file(path):
            raise usage(
                f"No compose file in {path} (from {source}).",
                hint="qrosetta --project-dir DIR status, with DIR a Quantum Rosetta checkout",
                reason="project_dir_invalid",
            )
        return Mode("checkout", path, source)
    if checkout and compose_file(checkout):
        return Mode("checkout", os.path.abspath(checkout), "this checkout")
    if is_checkout(PACKAGE_PARENT):
        return Mode("checkout", PACKAGE_PARENT, "this checkout")
    return Mode("installed", "", "installed package")
