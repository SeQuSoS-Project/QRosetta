#!/usr/bin/env python3
"""Writes the files a release page carries besides the distributions, SBOMs and notices:

    release_assets.py openapi --out openapi-V.json [--version V]
    release_assets.py images --manifest manifest.json --out qrosetta-V-images.txt
    release_assets.py notes --version V [--changelog CHANGELOG.md] [--repository O/R] [--out F | --check]

`openapi` imports the API from this checkout (rosetta-api/ and shared/ on sys.path, working
directory and SQLite database in a temporary directory) and writes `app.openapi()`, refusing a
document whose version is not qrosetta_cli.__version__; it needs the API's own dependencies. `images` lists every published image of a release manifest by digest,
with the cosign and `gh attestation` commands that verify it. `notes` prints the CHANGELOG.md
section of a version, which must exist and carry a date. The other subcommands use the standard
library only."""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SBOM_PREDICATE = "https://spdx.dev/Document/v2.3"
PUBLIC_REPOSITORY = "SeQuSoS-Project/QRosetta"
IDENTITY = re.compile(r"^https://[^/]+/(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/\.github/workflows/[^@]+@refs/tags/v"
                      r"(?P<version>\S+)$")


class AssetError(Exception):
    pass


def cli_version(repo=REPO):
    text = (repo / "qrosetta_cli" / "__init__.py").read_text()
    return re.search(r'^__version__ = "([^"]+)"$', text, re.M).group(1)


def openapi_spec(repo=REPO):
    """The API's OpenAPI document, from the code in `repo`."""
    for path in (repo / "shared", repo / "rosetta-api"):
        sys.path.insert(0, str(path))
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="qrosetta-openapi-") as work:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(work) / 'openapi.db'}"
        os.environ.pop("QROSETTA_VERSION", None)
        os.symlink(repo / "rosetta-api" / "static", Path(work) / "static")
        os.chdir(work)
        try:
            from main import app
            return app.openapi()
        finally:
            os.chdir(cwd)


def write_openapi(out, version=None, repo=REPO):
    spec = openapi_spec(repo)
    found = (spec.get("info") or {}).get("version")
    if version and found != version:
        raise AssetError(f"the API reports version {found}, not {version}")
    if not spec.get("paths"):
        raise AssetError("the OpenAPI document has no paths")
    Path(out).write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    return spec


def signer(manifest):
    """(identity, issuer, OWNER/REPO, tag version) of the workflow that signed the images."""
    signing = manifest.get("signing") or {}
    identity, issuer = signing.get("identity"), signing.get("issuer")
    m = IDENTITY.match(identity or "")
    if not m or not issuer:
        raise AssetError("the manifest names no signing workflow (signing.identity and signing.issuer)")
    return identity, issuer, m.group("repo"), m.group("version")


def published(manifest):
    """[(id, service record)] of the images the release published, in manifest order."""
    if not manifest.get("images_published"):
        raise AssetError("the manifest names no published images")
    rows = [(sid, svc) for sid, svc in (manifest.get("services") or {}).items() if svc.get("ref")]
    for sid, svc in rows:
        if not re.fullmatch(r"\S+@sha256:[0-9a-f]{64}", svc["ref"]):
            raise AssetError(f"{sid}: {svc['ref']!r} is not a reference by digest")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(svc.get("image_id"))):
            raise AssetError(f"{sid}: no image id")
    return rows


def verify_commands(ref, identity, issuer, repository):
    return [
        f"cosign verify --certificate-identity '{identity}' --certificate-oidc-issuer '{issuer}' {ref}",
        f"gh attestation verify oci://{ref} -R {repository}",
        f"gh attestation verify oci://{ref} -R {repository} --predicate-type {SBOM_PREDICATE}",
    ]


def images_text(manifest):
    identity, issuer, repository, tag_version = signer(manifest)
    version = manifest.get("platform_version")
    if tag_version != version:
        raise AssetError(f"the signing identity names v{tag_version}, the manifest {version}")
    rows = published(manifest)
    width = max(len(sid) for sid, _ in rows)
    lines = [
        f"Quantum Rosetta {version}: published container images",
        "",
        f"Commit: {manifest.get('git_sha')}",
        f"Signed by: {identity}",
        f"OIDC issuer: {issuer}",
        "",
        "`qrosetta pull` fetches these images by digest and checks each against the release manifest",
        "in the wheel; with cosign on the PATH it checks the signature too.",
        "",
        "Images (id, profiles, reference by digest, image id = config digest):",
        "",
    ]
    for sid, svc in rows:
        profiles = ",".join(svc.get("profiles") or []) or "core"
        lines.append(f"  {sid:<{width}}  {profiles}")
        lines.append(f"  {'':<{width}}  {svc['ref']}")
        lines.append(f"  {'':<{width}}  image id {svc['image_id']}")
    withheld = [(sid, svc.get("not_distributable_reason")) for sid, svc in (manifest.get("services") or {}).items()
                if svc.get("distributable") is False]
    if withheld:
        lines += ["", "Not published (a checkout builds these on the user's machine):", ""]
        lines += [f"  {sid}: {reason}" for sid, reason in withheld]
    lines += [
        "",
        "Verify an image with cosign 3 (the release workflow signs with cosign 3.0.6) and the GitHub",
        "CLI (`gh auth login` first; gh reads the image from the registry with your docker or podman",
        "login). The first command checks the keyless signature, the second the build provenance",
        "attestation, the third the SPDX SBOM attestation:",
        "",
    ]
    for sid, svc in rows:
        lines.append(f"# {sid}")
        lines += verify_commands(svc["ref"], identity, issuer, repository)
        lines.append("")
    return "\n".join(lines)


def changelog_section(version, text):
    """The body of `## [version] - YYYY-MM-DD` in a Keep a Changelog file."""
    heading = re.compile(r"^## \[(?P<v>[^\]]+)\](?: - (?P<date>\S+))?\s*$", re.M)
    found = [m for m in heading.finditer(text) if m.group("v") == version]
    if not found:
        raise AssetError(f"CHANGELOG.md has no section [{version}]")
    m = found[0]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", m.group("date") or ""):
        raise AssetError(f"CHANGELOG.md section [{version}] has no date (## [{version}] - YYYY-MM-DD)")
    following = heading.search(text, m.end())
    links = re.search(r"^\[[^\]]+\]: \S+\s*$", text[m.end():], re.M)
    end = min(x for x in (following.start() if following else len(text),
                          m.end() + links.start() if links else len(text)))
    body = text[m.end():end].strip()
    if not body:
        raise AssetError(f"CHANGELOG.md section [{version}] is empty")
    return body


def notes_text(version, changelog, repository=PUBLIC_REPOSITORY):
    return "\n".join([
        changelog_section(version, changelog),
        "",
        "## Files",
        "",
        f"- `qrosetta-{version}-py3-none-any.whl`, `qrosetta-{version}.tar.gz`: the files PyPI received.",
        f"- `qrosetta-{version}-images.txt`: every published image by digest, with the commands that "
        "verify its signature, provenance and SBOM.",
        "- `sbom-<id>.spdx.json`, `NOTICE-<id>.txt`: per image, the SBOM and the source notice of its "
        "operating-system packages.",
        f"- `openapi-{version}.json`: the API description of this version.",
        f"- `qrosetta-{version}.intoto.jsonl`: build provenance (Sigstore bundle) of every file listed "
        "in `SHA256SUMS`; `gh attestation verify FILE --bundle "
        f"qrosetta-{version}.intoto.jsonl -R {repository}` checks one.",
        "",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("openapi", help="write the API's OpenAPI document")
    p.add_argument("--out", required=True)
    p.add_argument("--version", help="fail unless the API reports this version (default: qrosetta_cli.__version__)")
    p = sub.add_parser("images", help="write the list of published images with their verify commands")
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("notes", help="print or check the CHANGELOG.md section of a version")
    p.add_argument("--version", required=True)
    p.add_argument("--changelog", default=str(REPO / "CHANGELOG.md"))
    p.add_argument("--repository", default=PUBLIC_REPOSITORY, metavar="OWNER/REPOSITORY")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--out")
    group.add_argument("--check", action="store_true", help="only check that the section exists and is dated")
    args = parser.parse_args(argv)
    try:
        if args.command == "openapi":
            spec = write_openapi(args.out, args.version or cli_version())
            print(f"Wrote {args.out}: {len(spec['paths'])} paths, version {spec['info']['version']}.",
                  file=sys.stderr)
        elif args.command == "images":
            text = images_text(json.loads(Path(args.manifest).read_text()))
            Path(args.out).write_text(text)
            print(f"Wrote {args.out}.", file=sys.stderr)
        else:
            text = notes_text(args.version, Path(args.changelog).read_text(), args.repository)
            if args.out:
                Path(args.out).write_text(text)
            elif not args.check:
                sys.stdout.write(text)
    except AssetError as exc:
        print(f"release_assets: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
