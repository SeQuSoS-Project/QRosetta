"""The image a runner or compiler process runs from, as the process itself can see it: the
identity file baked at build (source, release, commit), the sha256 of the build files the
image copied, the container engine's view, whether the host CPU reports a hypervisor, and
whether the image's architecture differs from the host's (emulation).

The serving process reads these at startup (``load``) and adds them to a result after the
run's child process has returned (``stamp``). The host's OS and architecture arrive in
QROSETTA_HOST_OS and QROSETTA_HOST_ARCH (set by ``qrosetta start``); ``load`` removes them
from the process environment, so a child spawned later inherits the environment it would
have had without them."""

import copy
import functools
import hashlib
import os
import sys
from pathlib import Path

NOT_RECORDED = "not recorded"
IMAGE_SOURCES = ("release", "built_locally")
IDENTITY_FILE = Path(os.getenv("QROSETTA_IMAGE_IDENTITY_FILE",
                               "/usr/local/share/qrosetta-image/identity"))
BUILD_FILES_DIR = Path(os.getenv("QROSETTA_BUILD_FILES_DIR", "/usr/local/share/qrosetta-build"))
_CONTAINERENV = Path("/run/.containerenv")
_DOCKERENV = Path("/.dockerenv")
_CPUINFO = Path("/proc/cpuinfo")
HOST_ENV_VARS = {"os": "QROSETTA_HOST_OS", "arch": "QROSETTA_HOST_ARCH"}
_ELF_64BIT_MACHINES = {21: "ppc64", 22: "s390x", 62: "x86_64", 183: "aarch64", 243: "riscv64",
                       258: "loongarch64"}
_ARCH_ALIASES = {"amd64": "x86_64", "x64": "x86_64", "x86-64": "x86_64", "arm64": "aarch64"}
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
def take_host_environment() -> dict:
    """``{os, arch}`` from QROSETTA_HOST_OS and QROSETTA_HOST_ARCH (None when unset or
    empty), removed from this process's environment by the first call."""
    return {key: os.environ.pop(var, "").strip() or None for key, var in HOST_ENV_VARS.items()}


def normalise_arch(name):
    """A machine name as Linux ``uname -m`` writes it (``arm64`` and ``AMD64`` become
    ``aarch64`` and ``x86_64``); None for None or an empty name."""
    if not name:
        return None
    name = str(name).strip().lower()
    return _ARCH_ALIASES.get(name, name) or None


def image_architecture(executable=None):
    """The machine the image's Python interpreter is built for, from its ELF header (under
    emulation it differs from the host's; ``uname`` inside the container reports the emulated
    machine); None when the header is unreadable or is not a 64-bit machine listed in
    ``_ELF_64BIT_MACHINES`` (a 32-bit image can run natively on a 64-bit host)."""
    try:
        with open(os.path.realpath(executable or sys.executable), "rb") as fh:
            head = fh.read(20)
    except OSError:
        return None
    if len(head) < 20 or head[:4] != b"\x7fELF" or head[4] != 2 or head[5] not in (1, 2):
        return None
    little = head[5] == 1
    name = _ELF_64BIT_MACHINES.get(int.from_bytes(head[18:20], "little" if little else "big"))
    return name + "le" if name == "ppc64" and little else name


def emulation(host=None, image_arch=None) -> dict:
    """``{emulated, image_arch, host_arch, host_os, method}``: ``emulated`` is True when the
    image's architecture differs from the host's, False when they are equal, None when either
    is not recorded (the host's arrives only through ``qrosetta start``)."""
    host = take_host_environment() if host is None else host
    image = image_arch or image_architecture()
    host_arch = normalise_arch(host.get("arch"))
    if image is None:
        emulated, method = None, "not compared: the image's interpreter has no readable ELF header"
    elif host_arch is None:
        emulated, method = None, "not compared: the host architecture was not passed to the container"
    else:
        emulated = image != host_arch
        method = "image interpreter ELF machine vs host architecture from qrosetta start"
    return {"emulated": emulated, "image_arch": image, "host_arch": host_arch,
            "host_os": host.get("os"), "method": method}


@functools.lru_cache(maxsize=None)
def _identity() -> dict:
    return {**baked_identity(), "container": container_view(),
            "host_hypervisor_cpu_flag": hypervisor_cpu_flag(), "emulation": emulation()}


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


def capability_fields() -> dict:
    """What a service's GET /capabilities reports about its image: ``image_identity`` (source,
    release and commit from the identity file) and ``build_files``, as read at startup."""
    identity = _identity()
    out = {"image_identity": {key: identity.get(key) for key in ("source", "release", "git_sha")}}
    files = build_file_hashes()
    if files:
        out["build_files"] = dict(files)
    return out


def load() -> None:
    """Take the host environment and read the identity and build-file hashes once, so later
    stamps do no I/O and later children do not inherit QROSETTA_HOST_*."""
    take_host_environment()
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
