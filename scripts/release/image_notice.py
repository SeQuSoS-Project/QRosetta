#!/usr/bin/env python3
"""Writes the source notice of one release image: every Debian or Alpine source package in the
image, at the version installed, with the address of its source.

    image_notice.py --image REF [--engine docker] --dockerfile PATH [--id ID] [--notices-url URL]
    image_notice.py --root DIR --dockerfile PATH ...      (an image filesystem already on disk)

--image copies the package databases out of a created, never started container and removes it.
The Debian archive dates come from the image's apt sources: the base image's build date (a comment
in Debian's official images) and the snapshot.debian.org archive its Dockerfile installed from, if
one is configured; --snapshot names the latter when the image does not record it. Stdlib only.
"""

import argparse
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.parse

SNAPSHOT_RE = re.compile(r"snapshot\.debian\.org/archive/debian/(\d{8}T\d{6}Z)")
COPIED_PATHS = (
    "var/lib/dpkg/status",
    "lib/apk/db/installed",
    "etc/os-release",
    "usr/lib/os-release",
    "etc/apt",
)


def parse_dpkg_status(text):
    """Installed packages of a dpkg status file: name, version, source name, source version."""
    packages = []
    for stanza in re.split(r"\n\s*\n", text):
        fields = {}
        key = None
        for line in stanza.splitlines():
            if line[:1] in (" ", "\t"):
                continue
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip()
        if "install ok installed" not in fields.get("Status", ""):
            continue
        name, version = fields.get("Package"), fields.get("Version")
        if not name or not version:
            continue
        source, source_version = name, version
        if fields.get("Source"):
            m = re.fullmatch(r"(\S+)(?:\s+\((\S+)\))?", fields["Source"])
            if m:
                source = m.group(1)
                source_version = m.group(2) or version
        packages.append({"package": name, "version": version, "source": source,
                         "source_version": source_version})
    return packages


def parse_apk_installed(text):
    """Installed packages of an Alpine apk database: name, version, origin, aports commit, licence,
    project URL and packager."""
    packages = []
    for stanza in re.split(r"\n\s*\n", text):
        fields = {}
        for line in stanza.splitlines():
            if len(line) > 2 and line[1] == ":" and line[0] not in fields:
                fields[line[0]] = line[2:]
        if "P" in fields and "V" in fields:
            packages.append({"package": fields["P"], "version": fields["V"],
                             "origin": fields.get("o", fields["P"]), "commit": fields.get("c", ""),
                             "licence": fields.get("L", ""), "url": fields.get("U", ""),
                             "maintainer": fields.get("m", "")})
    return packages


def final_base(dockerfile_text):
    """Image reference of the final stage's FROM, following references to earlier stages."""
    stages = {}
    last = None
    for line in dockerfile_text.splitlines():
        words = line.split()
        if not words or words[0].upper() != "FROM":
            continue
        words = [w for w in words[1:] if not w.startswith("--")]
        ref = words[0]
        name = words[2] if len(words) >= 3 and words[1].upper() == "AS" else None
        resolved = stages.get(ref, ref)
        if name:
            stages[name] = resolved
        last = resolved
    return last


def os_name(root):
    for rel in ("etc/os-release", "usr/lib/os-release"):
        path = root / rel
        if path.is_file():
            m = re.search(r'^PRETTY_NAME="?([^"\n]+)"?$', path.read_text(errors="replace"), re.M)
            if m:
                return m.group(1)
    return None


def apt_snapshots(root):
    """(base, install): the snapshot.debian.org timestamps in the image's apt sources. Debian's
    official images name their own build date in a comment; a source line that apt reads names the
    archive the Dockerfile installed from."""
    apt = root / "etc" / "apt"
    files = [apt / "sources.list"] + sorted((apt / "sources.list.d").glob("*")) if apt.is_dir() else []
    base, install = set(), set()
    for path in files:
        if not path.is_file():
            continue
        for line in path.read_text(errors="replace").splitlines():
            stamps = SNAPSHOT_RE.findall(line)
            (base if line.lstrip().startswith("#") else install).update(stamps)
    return (max(base) if base else None), (max(install) if install else None)


def snapshot_url(source, version):
    return (f"https://snapshot.debian.org/package/{urllib.parse.quote(source, safe='')}/"
            f"{urllib.parse.quote(version, safe='')}/")


def debian_section(packages, base_snapshot, install_snapshot):
    by_source = {}
    for p in packages:
        by_source.setdefault((p["source"], p["source_version"]), []).append(p["package"])
    archive = []
    if base_snapshot:
        archive.append(f"The base image's Debian packages are those of the Debian archive as of {base_snapshot} "
                       f"(https://snapshot.debian.org/archive/debian/{base_snapshot}/).")
    if install_snapshot:
        archive.append(f"Packages the Dockerfile adds were installed from the Debian archive as of "
                       f"{install_snapshot} (https://snapshot.debian.org/archive/debian/{install_snapshot}/).")
    else:
        archive.append("Packages the Dockerfile adds, if any, were installed from deb.debian.org when the "
                       "image was built; the image records no archive date for them.")
    lines = [
        " ".join(archive),
        "",
        f"The image contains {len(packages)} Debian binary packages built from {len(by_source)} source "
        "packages. The source of each, at the version installed in the image:",
        "",
    ]
    for (source, version), binaries in sorted(by_source.items()):
        lines.append(f"{source} {version}")
        lines.append(f"    {snapshot_url(source, version)}")
        lines.append(f"    binary packages: {', '.join(sorted(binaries))}")
    lines += ["", "The licence of each Debian package is in /usr/share/doc/<package>/copyright inside the image."]
    return lines


def alpine_section(packages):
    by_origin = {}
    for p in packages:
        by_origin.setdefault((p["origin"], p["version"], p["commit"]), []).append(p)
    lines = [
        f"The image contains {len(packages)} Alpine packages built from {len(by_origin)} source packages "
        "(aports origins). The build recipe of each, at the aports commit that built it, names its "
        "upstream source:",
        "",
    ]
    for (origin, version, commit), pkgs in sorted(by_origin.items()):
        licences = sorted({p["licence"] for p in pkgs if p["licence"]})
        lines.append(f"{origin} {version}" + (f" ({'; '.join(licences)})" if licences else ""))
        if commit:
            lines.append(f"    https://gitlab.alpinelinux.org/alpine/aports/-/tree/{commit} (main/{origin} "
                         f"or community/{origin})")
        else:
            first = pkgs[0]
            lines.append(f"    not built from aports; packaged by {first['maintainer'] or 'an unnamed packager'}, "
                         f"project {first['url'] or 'not recorded'}")
        lines.append(f"    binary packages: {', '.join(sorted(p['package'] for p in pkgs))}")
    return lines


def notice(root, *, image, image_id, dockerfile, dockerfile_text, notices_url, snapshot=None):
    root = pathlib.Path(root)
    dpkg = root / "var" / "lib" / "dpkg" / "status"
    apk = root / "lib" / "apk" / "db" / "installed"
    if not dpkg.is_file() and not apk.is_file():
        raise SystemExit("image_notice.py: the image has neither a dpkg status file nor an apk database")
    lines = [
        f"Source notice for the Quantum Rosetta image {image}" + (f" ({image_id})" if image_id else ""),
        "",
        f"Built from {dockerfile}. Base image of its final stage: {final_base(dockerfile_text) or 'not found'}.",
        f"Operating system: {os_name(root) or 'not recorded in the image'}.",
        "",
    ]
    if dpkg.is_file():
        base_snapshot, install_snapshot = apt_snapshots(root)
        lines += debian_section(parse_dpkg_status(dpkg.read_text(errors="replace")), base_snapshot,
                                snapshot or install_snapshot)
    if apk.is_file():
        if dpkg.is_file():
            lines.append("")
        lines += alpine_section(parse_apk_installed(apk.read_text(errors="replace")))
    lines += [
        "",
        "Python packages, the libraries their wheels bundle, programs built from source, and the written "
        "offer for the source of every GPL- or LGPL-licensed component:",
        f"    {notices_url}",
    ]
    return "\n".join(lines) + "\n"


def copy_from_image(engine, image, dest):
    """Copies COPIED_PATHS out of a created (never started) container of IMAGE, then removes it."""
    cid = subprocess.run([engine, "create", image, "true"], check=True, capture_output=True,
                         text=True).stdout.strip()
    try:
        for rel in COPIED_PATHS:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([engine, "cp", f"{cid}:/{rel}", str(target)], capture_output=True)
    finally:
        subprocess.run([engine, "rm", cid], check=True, capture_output=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", help="image reference; read through a created container")
    source.add_argument("--root", type=pathlib.Path, help="an image filesystem on disk")
    parser.add_argument("--engine", default="docker")
    parser.add_argument("--dockerfile", required=True, type=pathlib.Path)
    parser.add_argument("--name", help="image name printed in the notice (default: --image)")
    parser.add_argument("--id", dest="image_id", help="image id or digest printed in the notice")
    parser.add_argument("--notices-url", default="THIRD_PARTY_NOTICES.md")
    parser.add_argument("--snapshot",
                        help="snapshot.debian.org timestamp the Dockerfile installed from, YYYYMMDDTHHMMSSZ")
    args = parser.parse_args(argv)
    if args.snapshot and not re.fullmatch(r"\d{8}T\d{6}Z", args.snapshot):
        parser.error("--snapshot must look like 20261027T000000Z")
    kwargs = dict(image=args.name or args.image or str(args.root), image_id=args.image_id,
                  dockerfile=args.dockerfile.as_posix(), dockerfile_text=args.dockerfile.read_text(),
                  notices_url=args.notices_url, snapshot=args.snapshot)
    if args.root:
        sys.stdout.write(notice(args.root, **kwargs))
        return 0
    base = os.environ.get("TMPDIR") or os.environ.get("RUNNER_TEMP") or None
    with tempfile.TemporaryDirectory(prefix="image-notice-", dir=base) as tmp:
        copy_from_image(args.engine, args.image, pathlib.Path(tmp))
        sys.stdout.write(notice(tmp, **kwargs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
