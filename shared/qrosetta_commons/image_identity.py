"""The image a runner or compiler process runs from, as the process itself can see it: the
identity file baked at build (source, release, commit), the sha256 of the build files the
image copied, the container engine's view, and whether the host CPU reports a hypervisor.

The serving process reads these at startup (``load``) and adds them to a result after the
run's child process has returned (``stamp``)."""

import copy
import functools
import hashlib
import os
from pathlib import Path

NOT_RECORDED = "not recorded"
IMAGE_SOURCES = ("release", "built_locally")
IDENTITY_FILE = Path(os.getenv("QROSETTA_IMAGE_IDENTITY_FILE",
                               "/usr/local/share/qrosetta-image/identity"))
BUILD_FILES_DIR = Path(os.getenv("QROSETTA_BUILD_FILES_DIR", "/usr/local/share/qrosetta-build"))
_CONTAINERENV = Path("/run/.containerenv")
_DOCKERENV = Path("/.dockerenv")
_CPUINFO = Path("/proc/cpuinfo")
_CONTAINERENV_KEYS = {"engine": "engine", "image": "image", "imageid": "image_id",
                      "name": "container_name", "id": "container_id"}


def _key_values(text: str) -> dict:
    """``key=value`` lines (values optionally in double quotes) as a dict."""
    out = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip():
            out[key.strip()] = value.strip().strip('"')
    return out


def _read_text(path: Path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def baked_identity() -> dict:
    """``source`` (``release``, ``built_locally`` or "not recorded"), ``release`` and
    ``git_sha`` from the identity file the image wrote at build; ``identity_file`` says
    whether the file was there."""
    text = _read_text(IDENTITY_FILE)
    if text is None:
        return {"source": NOT_RECORDED, "release": None, "git_sha": NOT_RECORDED,
                "identity_file": "absent (image built before images recorded their source)"}
    values = _key_values(text)
    source = values.get("source", "")
    return {"source": source if source in IMAGE_SOURCES else NOT_RECORDED,
            "release": values.get("release") or None,
            "git_sha": values.get("git_sha") or NOT_RECORDED,
            "identity_file": "present"}


def container_view() -> dict:
    """What the container runtime tells the process about its image: Apptainer's image path
    and the sha256 its launch script passes, podman's /run/.containerenv fields (image and
    image id only for privileged containers), or that Docker or Kubernetes started it."""
    if os.environ.get("APPTAINER_CONTAINER"):
        view = {"engine": "apptainer", "image": os.environ["APPTAINER_CONTAINER"]}
        if os.environ.get("QROSETTA_IMAGE_SHA256"):
            view["image_sha256"] = os.environ["QROSETTA_IMAGE_SHA256"]
        return view
    view = {}
    text = _read_text(_CONTAINERENV)
    if text is not None:
        values = _key_values(text)
        view = {field: values[key] for key, field in _CONTAINERENV_KEYS.items() if values.get(key)}
        view.setdefault("engine", "podman")
    elif _DOCKERENV.exists():
        view = {"engine": "docker"}
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        view["orchestrator"] = "kubernetes"
    return view or {"engine": NOT_RECORDED}


def hypervisor_cpu_flag():
    """True when /proc/cpuinfo lists the ``hypervisor`` flag (a virtual machine), False when
    it lists flags without it, None when unreadable or without a flags line (non-x86)."""
    text = _read_text(_CPUINFO)
    if text is None:
        return None
    for line in text.splitlines():
        if line.startswith("flags"):
            return "hypervisor" in line.split(":", 1)[-1].split()
    return None


@functools.lru_cache(maxsize=None)
def _identity() -> dict:
    return {**baked_identity(), "container": container_view(),
            "host_hypervisor_cpu_flag": hypervisor_cpu_flag()}


@functools.lru_cache(maxsize=None)
def build_file_hashes() -> dict:
    """sha256 of each file the image copied into BUILD_FILES_DIR; empty when absent."""
    if not BUILD_FILES_DIR.is_dir():
        return {}
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(BUILD_FILES_DIR.iterdir()) if path.is_file()}


def image_identity() -> dict:
    """A copy of this process's image identity (see ``baked_identity``, ``container_view``)."""
    return copy.deepcopy(_identity())


def load() -> None:
    """Read the identity and build-file hashes once, so later stamps do no I/O."""
    _identity()
    build_file_hashes()


def stamp(result) -> None:
    """Add ``image_identity`` and, when the image copied build files, ``build_files`` to a
    result dict (fields already set are kept)."""
    if not isinstance(result, dict):
        return
    result.setdefault("image_identity", image_identity())
    files = build_file_hashes()
    if files:
        result.setdefault("build_files", dict(files))
