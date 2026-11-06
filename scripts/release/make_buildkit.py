#!/usr/bin/env python3
"""Writes the build kit a wheel carries (qrosetta_cli/release/buildkit.tar.gz and buildkit.json):
the tracked files of one commit that building the stack's images needs, so that an installed
qrosetta builds any service without a checkout (`qrosetta build`). The file list is derived, not
kept: docker-compose.yml and every Dockerfile its services build, each Dockerfile's COPY and ADD
sources, the compose file's relative bind-mount defaults, and scripts/safe_boot.sh with what it
calls. Paths under a `tests` directory and paths .dockerignore excludes are left out; a source
that matches no file stops the script.

The archive is reproducible: entries sorted, contents from the commit's blobs, mtime the commit
time, uid and gid 0 without names, gzip header without a name and with the commit time, so one
commit gives the same bytes with one Python and zlib. buildkit.json records the archive's sha256,
size, file count, commit and version.

Needs PyYAML."""

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "qrosetta_cli" / "release" / "buildkit.tar.gz"
SCHEMA = "qrosetta.buildkit@1"
MAX_BYTES = 15 * 1024 * 1024
BASE_FILES = (
    "docker-compose.yml",
    ".dockerignore",
    "scripts/safe_boot.sh",
    "scripts/release/oci_labels.py",
    "release/debian-snapshot.conf",
    "qrosetta_cli/__init__.py",
)
EXCLUDED_DIRS = ("tests",)
_DEFAULTED = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*:-(.+)\}$")


class KitError(Exception):
    pass


def git(repo, *args, binary=False):
    exe = shutil.which("git")
    if exe is None:
        raise KitError("git is not on PATH")
    out = subprocess.run([exe, "-C", str(repo), *args], capture_output=True, check=False)
    if out.returncode != 0:
        raise KitError(f"git {' '.join(args)}: {out.stderr.decode(errors='replace').strip()}")
    return out.stdout if binary else out.stdout.decode()


class Tree:
    """The tracked files of one commit: {path: (mode, blob sha)} and their contents."""

    def __init__(self, repo, commit):
        self.repo = repo
        self.commit = git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").strip()
        self.time = int(git(repo, "show", "-s", "--format=%ct", self.commit).strip())
        self.files = {}
        for entry in git(repo, "ls-tree", "-r", "-z", "--full-tree", self.commit).split("\0"):
            if not entry:
                continue
            meta, path = entry.split("\t", 1)
            mode, kind, sha = meta.split()
            if kind == "blob":
                self.files[path] = (mode, sha)
        self._cache = {}

    def read(self, path):
        if path not in self.files:
            raise KitError(f"{path} is not tracked at {self.commit[:12]}")
        if path not in self._cache:
            self._cache[path] = git(self.repo, "cat-file", "blob", self.files[path][1], binary=True)
        return self._cache[path]

    def text(self, path):
        return self.read(path).decode()


def instructions(dockerfile_text):
    """(instruction, arguments) of each line of a Dockerfile, continuation lines joined."""
    joined, out = "", []
    for raw in dockerfile_text.splitlines():
        line = raw.strip()
        if not joined and (not line or line.startswith("#")):
            continue
        if line.endswith("\\"):
            joined += line[:-1] + " "
            continue
        joined += line
        word, _, rest = joined.strip().partition(" ")
        out.append((word.upper(), rest.strip()))
        joined = ""
    return out


def copy_sources(dockerfile_text, where):
    """The context paths every COPY and ADD of a Dockerfile reads (none for COPY --from)."""
    sources = []
    for word, rest in instructions(dockerfile_text):
        if word not in ("COPY", "ADD"):
            continue
        if rest.startswith("["):
            args = json.loads(rest)
        else:
            args = shlex.split(rest)
        flags = [a for a in args if a.startswith("--")]
        paths = [a for a in args if not a.startswith("--")]
        if any(f.startswith("--from=") for f in flags):
            continue
        if len(paths) < 2:
            raise KitError(f"{where}: cannot read `{word} {rest}`")
        for src in paths[:-1]:
            if "://" in src or src.startswith("git@"):
                raise KitError(f"{where}: {word} of a URL ({src}) cannot be served from a build kit")
            sources.append(src)
    return sources


def _normal(path):
    path = str(PurePosixPath(path))
    return "" if path == "." else path.lstrip("/")


def matches(tree_paths, source, context=""):
    """Tracked paths a COPY source names, relative to the build context."""
    pattern = _normal(PurePosixPath(context) / source) if context else _normal(source)
    if pattern == "":
        return sorted(tree_paths)
    if any(c in pattern for c in "*?["):
        return sorted(p for p in tree_paths if _glob(pattern, p) or any(
            _glob(pattern, str(parent)) for parent in PurePosixPath(p).parents if str(parent) != "."))
    return sorted(p for p in tree_paths if p == pattern or p.startswith(pattern + "/"))


def _glob(pattern, path):
    return fnmatch.fnmatchcase(path, pattern) and pattern.count("/") == path.count("/")


def _components_match(pattern, parts):
    if not pattern:
        return not parts
    if pattern[0] == "**":
        return any(_components_match(pattern[1:], parts[i:]) for i in range(len(parts) + 1))
    return bool(parts) and fnmatch.fnmatchcase(parts[0], pattern[0]) and _components_match(pattern[1:], parts[1:])


def dockerignore_patterns(text):
    patterns = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            raise KitError(f".dockerignore exception pattern {line!r} is not supported by make_buildkit.py")
        patterns.append(_normal(line).split("/"))
    return patterns


def ignored(path, patterns):
    """Whether .dockerignore leaves `path` out of a build context at the repository root: a
    pattern matching the path or one of its parent directories."""
    parts = path.split("/")
    return any(_components_match(p, parts[:n]) for p in patterns for n in range(1, len(parts) + 1))


def excluded(path):
    return any(part in EXCLUDED_DIRS for part in path.split("/")[:-1])


def bind_sources(compose):
    """Relative default paths of the compose file's long-syntax bind mounts and file secrets."""
    found = []
    for svc in (compose.get("services") or {}).values():
        for vol in (svc or {}).get("volumes") or []:
            if isinstance(vol, dict) and vol.get("type") == "bind":
                found.append(vol.get("source") or "")
    for secret in (compose.get("secrets") or {}).values():
        found.append((secret or {}).get("file") or "")
    out = []
    for path in found:
        m = _DEFAULTED.match(path)
        path = m.group(1) if m else path
        if path and not path.startswith("$") and not path.startswith("/"):
            out.append(_normal(path))
    return out


def kit_files(tree):
    """{path: reason} of every file the kit carries; a KitError when something it needs is not
    tracked or a COPY source names no file."""
    paths = set(tree.files)
    patterns = dockerignore_patterns(tree.text(".dockerignore"))
    chosen = {}
    for path in BASE_FILES:
        tree.read(path)
        chosen[path] = "build tooling"
    compose = yaml.safe_load(tree.text("docker-compose.yml"))
    for name, svc in (compose.get("services") or {}).items():
        build = (svc or {}).get("build")
        if not build:
            continue
        if isinstance(build, str):
            build = {"context": build}
        context = _normal(build.get("context") or ".")
        if context.startswith(".."):
            raise KitError(f"service {name}: build context {context} is outside the repository")
        dockerfile = _normal(PurePosixPath(context) / (build.get("dockerfile") or "Dockerfile"))
        chosen[dockerfile] = f"Dockerfile of {name}"
        for src in copy_sources(tree.text(dockerfile), dockerfile):
            hits = [p for p in matches(paths, src, context) if not excluded(p)]
            if context == "":
                hits = [p for p in hits if not ignored(p, patterns)]
            if not hits:
                raise KitError(f"{dockerfile}: COPY source {src} matches no tracked file at {tree.commit[:12]}")
            for p in hits:
                chosen.setdefault(p, f"COPY {src} ({name})")
    for path in bind_sources(compose):
        tree.read(path)
        chosen.setdefault(path, "compose bind-mount default")
    for path in chosen:
        mode = tree.files[path][0]
        if mode not in ("100644", "100755"):
            raise KitError(f"{path} has git mode {mode}; a build kit carries regular files only")
    return chosen


def platform_version(tree):
    m = re.search(r'^__version__ = "([^"]+)"$', tree.text("qrosetta_cli/__init__.py"), re.M)
    if not m:
        raise KitError("qrosetta_cli/__init__.py has no __version__")
    return m.group(1)


def archive_bytes(tree, paths):
    """The gzip-compressed tar of `paths`, reproducible for the commit."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(paths):
            data = tree.read(path)
            info = tarfile.TarInfo(path)
            info.size = len(data)
            info.mtime = tree.time
            info.mode = 0o755 if tree.files[path][0] == "100755" else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=out, compresslevel=9, mtime=tree.time) as gz:
        gz.write(raw.getvalue())
    return out.getvalue()


def build(repo=REPO, commit="HEAD"):
    """(archive bytes, metadata) for `commit`."""
    tree = Tree(repo, commit)
    files = kit_files(tree)
    data = archive_bytes(tree, files)
    if len(data) > MAX_BYTES:
        raise KitError(f"the build kit is {len(data)} bytes, over the {MAX_BYTES}-byte limit")
    meta = {
        "schema": SCHEMA,
        "file": "buildkit.tar.gz",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "files": len(files),
        "commit": tree.commit,
        "commit_time": tree.time,
        "version": platform_version(tree),
    }
    return data, meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="the archive; buildkit.json is written beside it")
    parser.add_argument("--list", action="store_true", help="print the files and why each is included, then exit")
    args = parser.parse_args(argv)
    try:
        if args.list:
            for path, why in sorted(kit_files(Tree(REPO, args.commit)).items()):
                print(f"{path}\t{why}")
            return 0
        data, meta = build(REPO, args.commit)
    except KitError as exc:
        print(f"make_buildkit: {exc}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    (out.parent / "buildkit.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Wrote {out}: {meta['files']} files, {meta['size']} bytes, sha256 {meta['sha256']}, "
          f"commit {meta['commit'][:12]}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
