"""Image archives of `qrosetta images save|load` (one `<engine> save` tar per image beside an
index, qrosetta-images.json) and the image identity read from build history: the step that
wrote /usr/local/share/qrosetta-image/identity records the build arguments it was given, in the
image's own configuration, so no container is run to read it."""

import hashlib
import json
import os
import re
import tarfile

from qrosetta_cli.errors import CliError, Exit, usage

INDEX = "qrosetta-images.json"
SCHEMA = "qrosetta.image-archive@1"
IDENTITY_PATH = "/usr/local/share/qrosetta-image/identity"
IDENTITY_ARGS = {"QROSETTA_IMAGE_SOURCE": "source", "QROSETTA_RELEASE": "release", "QROSETTA_GIT_SHA": "git_sha"}
_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.tar$")
_ARGS = re.compile(r"\|(\d+)\s+(.*)$", re.S)
_MAX_CONFIG_BYTES = 16 * 1024 * 1024


def identity_from_history(steps):
    """{source, release, git_sha} from the build step that wrote the identity file, or None when
    no step did (an image built before images recorded their source, or a core image)."""
    for step in steps:
        if IDENTITY_PATH not in (step or ""):
            continue
        m = _ARGS.search(step.split(IDENTITY_PATH)[0])
        if not m:
            return {"source": None, "release": None, "git_sha": None}
        tokens = m.group(2).split()[:int(m.group(1))]
        args = dict(t.split("=", 1) for t in tokens if "=" in t)
        return {name: (args.get(arg) or None) for arg, name in IDENTITY_ARGS.items()}
    return None


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def read_archive(path):
    """(config digest, image configuration) of the one image in a `<engine> save` tar, read
    without loading it: manifest.json names the configuration blob, whose sha256 is the image id."""
    try:
        with tarfile.open(path, "r:*") as tar:
            manifest = json.loads(_member(tar, "manifest.json"))
            if not isinstance(manifest, list) or len(manifest) != 1 or not isinstance(manifest[0], dict):
                raise ValueError("manifest.json does not describe exactly one image")
            data = _member(tar, str(manifest[0].get("Config") or ""))
    except (OSError, tarfile.TarError, ValueError, KeyError) as exc:
        raise CliError(f"{path} is not an image archive of `docker save` or `podman save`: {exc}", Exit.ENGINE,
                       "archive_invalid", hint="qrosetta images save -o DIR (on the machine that has the images)")
    config = json.loads(data)
    if not isinstance(config, dict):
        raise CliError(f"{path}: the image configuration is not an object.", Exit.ENGINE, "archive_invalid",
                       hint="qrosetta images save -o DIR")
    return "sha256:" + hashlib.sha256(data).hexdigest(), config


def _member(tar, name):
    info = tar.getmember(name)
    if not info.isfile() or info.size > _MAX_CONFIG_BYTES:
        raise ValueError(f"{name} is not a regular file of at most 16 MiB")
    return tar.extractfile(info).read()


def config_facts(config):
    """Labels, baked commit and identity of an image configuration as `save` writes it."""
    inner = config.get("config") or {}
    env = dict(e.split("=", 1) for e in inner.get("Env") or [] if "=" in e)
    history = [h.get("created_by") or "" for h in config.get("history") or [] if isinstance(h, dict)]
    return {"labels": inner.get("Labels") or {}, "git_sha": env.get("QROSETTA_IMAGE_GIT_SHA") or "unknown",
            "version": env.get("QROSETTA_VERSION"), "identity": identity_from_history(history)}


def index_path(path):
    """The index of an archive directory, given the directory or the index file itself."""
    path = os.path.abspath(os.path.expanduser(path))
    return path if os.path.basename(path) == INDEX else os.path.join(path, INDEX)


def read_index(path):
    """The index, checked: its schema, and every entry naming a tar file in its directory."""
    path = index_path(path)
    try:
        with open(path, encoding="utf-8") as fh:
            index = json.load(fh)
    except FileNotFoundError:
        raise CliError(f"No {INDEX} at {os.path.dirname(path)}.", Exit.NOT_FOUND, "archive_index_missing",
                       hint="qrosetta images load DIR, with DIR the directory `qrosetta images save` wrote") from None
    except (OSError, ValueError) as exc:
        raise usage(f"{path} cannot be read as JSON: {exc}", hint="qrosetta images save -o DIR",
                    reason="archive_index_invalid") from exc
    entries = index.get("images") if isinstance(index, dict) else None
    if not isinstance(index, dict) or index.get("schema") != SCHEMA or not isinstance(entries, list) or not entries:
        raise usage(f"{path} is not a {SCHEMA} index.", hint="qrosetta images save -o DIR",
                    reason="archive_index_invalid")
    for entry in entries:
        if not isinstance(entry, dict) or not _FILE_NAME.match(str(entry.get("file") or "")) or not all(
                isinstance(entry.get(k), str) for k in ("service", "compose_service", "config_digest", "sha256")):
            raise usage(f"{path}: an entry lacks service, compose_service, config_digest, sha256 or a plain "
                        f"file name: {entry!r}", hint="qrosetta images save -o DIR", reason="archive_index_invalid")
    return os.path.dirname(path), index


def write_index(directory, index):
    path = os.path.join(directory, INDEX)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
    return path
