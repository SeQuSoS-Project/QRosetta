#!/usr/bin/env python3
"""Checks the sdist and wheel in a dist directory before they are published: the wheel holds
qrosetta_cli and its metadata only, its version is the expected one, it has no dependencies, and
it carries the licence files, the JSON schemas, (with --require-manifest) the release manifest and
(with --require-buildkit) a build kit whose sha256 and size match its metadata.
`--prerelease VERSION` prints whether a canonical PEP 440 version is a pre-release (aN, bN, rcN
or .devN; the release workflow sends those to TestPyPI only) and refuses any other spelling.
Stdlib only."""

import argparse
import email.parser
import hashlib
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SDIST_ALLOWED_TOP = {"qrosetta_cli", "qrosetta.egg-info", "pyproject.toml", "README.md", "LICENSE",
                     "THIRD_PARTY_NOTICES.md", "PKG-INFO", "setup.cfg"}
CANONICAL = re.compile(r"^(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*((a|b|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?"
                       r"(\.dev(0|[1-9][0-9]*))?$")


def is_prerelease(version):
    """True for a pre-release or development version, False for a final or post release; a
    version that is not canonical PEP 440 is a ValueError."""
    m = CANONICAL.match(version or "")
    if not m:
        raise ValueError(f"{version!r} is not a canonical PEP 440 version")
    return bool(m.group(4) or m.group(9))


def _metadata(text):
    return email.parser.Parser().parsestr(text)


BUILDKIT_MAX_BYTES = 15 * 1024 * 1024


def check_buildkit(zf, names):
    """Problems with the build kit inside a wheel."""
    kit, meta_name = "qrosetta_cli/release/buildkit.tar.gz", "qrosetta_cli/release/buildkit.json"
    if kit not in names or meta_name not in names:
        return [f"no {kit} with {meta_name}"]
    data = zf.read(kit)
    try:
        meta = json.loads(zf.read(meta_name))
    except ValueError as exc:
        return [f"{meta_name} is not JSON: {exc}"]
    problems = []
    if meta.get("sha256") != hashlib.sha256(data).hexdigest() or meta.get("size") != len(data):
        problems.append(f"{kit} does not match the sha256 and size {meta_name} records")
    if len(data) > BUILDKIT_MAX_BYTES:
        problems.append(f"{kit} is {len(data)} bytes, over {BUILDKIT_MAX_BYTES}")
    return problems


def check_wheel(path, version, require_manifest=False, require_buildkit=False):
    """A list of problems with the wheel at `path`; empty when it is fit to publish."""
    problems = []
    dist_info = f"qrosetta-{version}.dist-info/"
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        stray = [n for n in names if not (n.startswith("qrosetta_cli/") or n.startswith(dist_info))]
        if stray:
            problems.append(f"files outside qrosetta_cli/ and {dist_info}: {', '.join(sorted(stray)[:10])}")
        if dist_info + "METADATA" not in names:
            return problems + [f"no {dist_info}METADATA (is the wheel's version {version}?)"]
        meta = _metadata(zf.read(dist_info + "METADATA").decode())
        if meta["Name"] != "qrosetta" or meta["Version"] != version:
            problems.append(f"metadata names {meta['Name']} {meta['Version']}, expected qrosetta {version}")
        if meta.get_all("Requires-Dist"):
            problems.append(f"dependencies declared: {meta.get_all('Requires-Dist')}")
        if meta["Requires-Python"] != ">=3.11":
            problems.append(f"Requires-Python is {meta['Requires-Python']}, expected >=3.11")
        if meta["License-Expression"] != "Apache-2.0":
            problems.append(f"License-Expression is {meta['License-Expression']}, expected Apache-2.0")
        for licence in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            if dist_info + "licenses/" + licence not in names:
                problems.append(f"{licence} is not in {dist_info}licenses/")
        entry_points = ""
        if dist_info + "entry_points.txt" in names:
            entry_points = zf.read(dist_info + "entry_points.txt").decode()
        if "qrosetta = qrosetta_cli.cli:main" not in entry_points:
            problems.append("no console script qrosetta = qrosetta_cli.cli:main")
        schemas = {p.name for p in (REPO / "qrosetta_cli" / "schemas").glob("*.json")}
        shipped = {n.rsplit("/", 1)[1] for n in names if n.startswith("qrosetta_cli/schemas/") and n.endswith(".json")}
        if schemas - shipped:
            problems.append(f"schemas missing: {', '.join(sorted(schemas - shipped))}")
        modules = {str(p.relative_to(REPO)).replace("\\", "/") for p in (REPO / "qrosetta_cli").rglob("*.py")}
        if modules - set(names):
            problems.append(f"modules missing: {', '.join(sorted(modules - set(names)))}")
        if require_manifest and "qrosetta_cli/release/manifest.json" not in names:
            problems.append("no qrosetta_cli/release/manifest.json")
        if require_buildkit:
            problems += check_buildkit(zf, names)
    return problems


def check_sdist(path, version):
    problems = []
    root = f"qrosetta-{version}"
    with tarfile.open(path) as tf:
        for member in tf.getnames():
            top, _, rest = member.partition("/")
            if top != root:
                problems.append(f"{member} is outside {root}/")
            elif rest and rest.split("/", 1)[0] not in SDIST_ALLOWED_TOP:
                problems.append(f"unexpected file in the sdist: {member}")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dist", nargs="?", help="directory holding one .whl and one .tar.gz")
    parser.add_argument("--version", help="the version both must carry")
    parser.add_argument("--require-manifest", action="store_true")
    parser.add_argument("--require-buildkit", action="store_true")
    parser.add_argument("--prerelease", metavar="VERSION", help="print true or false and exit")
    args = parser.parse_args(argv)
    if args.prerelease is not None:
        try:
            print("true" if is_prerelease(args.prerelease) else "false")
        except ValueError as exc:
            print(f"check_dist: {exc}", file=sys.stderr)
            return 1
        return 0
    if not args.dist or not args.version:
        parser.error("dist and --version are required")
    dist = Path(args.dist)
    wheels, sdists = sorted(dist.glob("*.whl")), sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        print(f"check_dist: expected one wheel and one sdist in {dist}, found {len(wheels)} and {len(sdists)}",
              file=sys.stderr)
        return 1
    problems = check_wheel(wheels[0], args.version, args.require_manifest, args.require_buildkit) + check_sdist(
        sdists[0], args.version)
    for problem in problems:
        print(f"check_dist: {problem}", file=sys.stderr)
    if not problems:
        print(f"check_dist: {wheels[0].name} and {sdists[0].name} hold qrosetta {args.version} only.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
