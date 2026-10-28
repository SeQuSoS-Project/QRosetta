#!/usr/bin/env python3
"""Writes qrosetta_cli/release/manifest.json (packaging plan §8.1): every service of
docker-compose.yml, checked against config.py's runner and compiler registries, with the image
digests a release pushed, their image ids (config digests, which `qrosetta images load` checks)
and the workflow identity their cosign signatures carry. --list-images prints the images a
release builds, for the workflow.

Needs PyYAML, pydantic and pydantic-settings (config.py is imported, not parsed)."""

import argparse
import ast
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SCHEMA = "qrosetta.release-manifest@1"
DEFAULT_OUT = REPO / "qrosetta_cli" / "release" / "manifest.json"
DEFAULT_REGISTRY = "ghcr.io/sequsos-project"
DEFAULT_PROJECT = "qsimulators"
NOT_INSTALLED = "not installed"
NOT_DISTRIBUTABLE = {
    "myqlm": "the myQLM licence (Bull EULA §2(b), §3(a)) allows neither third-party use nor network "
             "transfer; the image is built on the user's machine",
    "cuquantum": "NVIDIA's CUDA and cuStateVec libraries are under NVIDIA's licence terms, which have not "
                 "been reviewed for redistribution; the image is built on the user's machine",
    "bqskit": "bqskitrs 0.4.1 links NLopt (LGPL-2.1) statically and has no published source for that "
              "version; the image is built on the user's machine",
}
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
SIGNING_WORKFLOW = ".github/workflows/release-images.yml"
_DEFAULTED = re.compile(r"\$\{QROSETTA_PROJECT:-([^}]*)\}")
_SELF_TEST = {
    "runner": ["python", "main.py", "--self-test"],
    "compiler": ["python", "main.py", "--self-test"],
    "api": ["python", "-c", "import main"],
    "nginx": ["nginx", "-t"],
}


class ManifestError(Exception):
    pass


def load_settings(repo=REPO):
    spec = importlib.util.spec_from_file_location("qrosetta_release_config", repo / "rosetta-api" / "config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.settings


def load_compose(repo=REPO):
    return yaml.safe_load((repo / "docker-compose.yml").read_text())


def platform_version(repo=REPO):
    text = (repo / "qrosetta_cli" / "__init__.py").read_text()
    return re.search(r'^__version__ = "([^"]+)"$', text, re.M).group(1)


def _host(base_url):
    return base_url.split("//")[1].split(":")[0]


def _canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def declared_sdk_packages(main_py):
    """The names a service's main.py passes to declare_sdk_packages."""
    if not main_py.is_file():
        return []
    names = []
    for node in ast.walk(ast.parse(main_py.read_text())):
        name = getattr(node.func, "id", getattr(node.func, "attr", None)) if isinstance(node, ast.Call) else None
        if name == "declare_sdk_packages":
            names += [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    return names


def locked_versions(lock):
    found = {}
    if lock.is_file():
        for line in lock.read_text().splitlines():
            name, sep, version = line.split("#", 1)[0].strip().partition("==")
            version = version.split(";")[0].split()
            if sep and version:
                found[_canonical(name)] = version[0]
    return found


def sdk_versions(service_dir):
    """{package: version} for the packages the service declares, from its requirements.lock."""
    locked = locked_versions(service_dir / "requirements.lock")
    return {name: locked.get(_canonical(name), NOT_INSTALLED)
            for name in declared_sdk_packages(service_dir / "main.py")}


def _resolve_project(value):
    return _DEFAULTED.sub(lambda m: m.group(1) or DEFAULT_PROJECT, str(value))


def services(settings=None, compose=None, repo=REPO):
    """One record per compose service, in compose order, leaving out runners and compilers that
    config.py disables (safe_boot.sh does not build them either). A runner or compiler must be
    in config.py's registry under the same kind, with the compose container name as its
    base_url host, and every enabled registry entry must be a compose service."""
    settings = settings or load_settings(repo)
    compose = compose or load_compose(repo)
    registry = {sid: ("runner", entry) for sid, entry in settings.get_runner_services().items()}
    registry.update({sid: ("compiler", entry) for sid, entry in settings.get_compiler_services().items()})
    records, seen = [], set()
    for name, svc in compose["services"].items():
        labels = svc.get("labels") or {}
        sid, kind = labels.get("org.qrosetta.id"), labels.get("org.qrosetta.kind")
        infra = svc.get("container_name")
        if not sid or kind not in ("core", "runner", "compiler") or not infra:
            raise ManifestError(f"compose service {name} lacks org.qrosetta.id, org.qrosetta.kind or container_name")
        requires_gpu = False
        if kind != "core":
            if sid not in registry:
                raise ManifestError(f"compose service {name} ({sid}) is not in config.py's {kind} registry")
            reg_kind, entry = registry[sid]
            if reg_kind != kind:
                raise ManifestError(f"{sid} is a {kind} in docker-compose.yml but a {reg_kind} in config.py")
            if not entry.get("enabled", True):
                continue
            if _host(entry["base_url"]) != infra:
                raise ManifestError(f"{sid}: config.py base_url host {_host(entry['base_url'])} "
                                    f"!= container_name {infra}")
            requires_gpu = bool(entry.get("requires_gpu", False))
        build = svc.get("build") or {}
        dockerfile = os.path.normpath(build.get("dockerfile", "")).replace(os.sep, "/")
        records.append({
            "id": sid, "kind": kind, "ids": [sid], "compose_service": name, "infra_host": infra,
            "dockerfile": dockerfile,
            "profiles": [p for p in str(labels.get("org.qrosetta.profiles", "")).split(",") if p],
            "requires_gpu": requires_gpu,
            "distributable": sid not in NOT_DISTRIBUTABLE,
            "sdk_versions": sdk_versions((repo / dockerfile).parent) if kind != "core" else {},
            "image_labels": {k: _resolve_project(v) for k, v in (build.get("labels") or {}).items()},
            "compose": {k: v for k, v in svc.items() if k not in ("build", "image")},
        })
        seen.add(sid)
    absent = sorted(sid for sid, (_, entry) in registry.items() if entry.get("enabled", True) and sid not in seen)
    if absent:
        raise ManifestError(f"enabled in config.py but not in docker-compose.yml: {', '.join(absent)}")
    return records


def release_images(records):
    """The images a release builds: every distributable service, with its self-test command."""
    out = []
    for r in records:
        if not r["distributable"]:
            continue
        test = _SELF_TEST.get(r["kind"]) or _SELF_TEST[r["id"]]
        out.append({"id": r["id"], "kind": r["kind"], "compose_service": r["compose_service"],
                    "infra_host": r["infra_host"], "dockerfile": r["dockerfile"],
                    "labels": " ".join(f"{k}={v}" for k, v in r["image_labels"].items()),
                    "self_test": shlex.join(test)})
    return out


def check_image_ids(digests, image_ids):
    """Refuse an image id for a service without a digest, or a malformed one."""
    for sid, image_id in image_ids.items():
        if sid not in digests:
            raise ManifestError(f"image id for {sid}, which has no digest")
        if not DIGEST.match(str(image_id)):
            raise ManifestError(f"{sid}: image id {image_id!r} is not a sha256 digest")


def signing(version, repository, server="https://github.com"):
    """The certificate identity and issuer of the release workflow's keyless cosign signatures."""
    if not REPOSITORY.match(repository or ""):
        raise ManifestError(f"--signer-repository {repository!r} is not OWNER/REPOSITORY")
    return {"issuer": OIDC_ISSUER,
            "identity": f"{server.rstrip('/')}/{repository}/{SIGNING_WORKFLOW}@refs/tags/v{version}"}


def check_digests(records, digests):
    """Refuse a digest for a service the release does not distribute, an unknown id, a malformed
    digest, or a set that does not cover every distributable service."""
    ids = {r["id"] for r in records}
    for sid, digest in digests.items():
        if sid in NOT_DISTRIBUTABLE:
            raise ManifestError(f"refusing to emit a digest for {sid}: {NOT_DISTRIBUTABLE[sid]}")
        if sid not in ids:
            raise ManifestError(f"digest for {sid}, which is not a service of this release")
        if not DIGEST.match(str(digest)):
            raise ManifestError(f"{sid}: {digest!r} is not a sha256 digest")
    if digests:
        missing = sorted(r["id"] for r in records if r["distributable"] and r["id"] not in digests)
        if missing:
            raise ManifestError(f"no digest for {', '.join(missing)}: a release publishes every distributable image")


def build_manifest(version, git_sha, registry=DEFAULT_REGISTRY, digests=None, records=None, compose=None, repo=REPO,
                   image_ids=None, signer_repository=None, server="https://github.com"):
    compose = compose or load_compose(repo)
    records = records if records is not None else services(compose=compose, repo=repo)
    digests = dict(digests or {})
    image_ids = dict(image_ids or {})
    check_digests(records, digests)
    check_image_ids(digests, image_ids)
    entries = {}
    for r in records:
        repository = f"{registry}/qrosetta-{r['infra_host']}" if r["distributable"] else None
        entry = {k: v for k, v in r.items() if k not in ("id", "image_labels")}
        entry["repository"] = repository
        entry["ref"] = f"{repository}@{digests[r['id']]}" if r["distributable"] and r["id"] in digests else None
        entry["image_id"] = image_ids.get(r["id"]) if entry["ref"] else None
        if not r["distributable"]:
            entry["not_distributable_reason"] = NOT_DISTRIBUTABLE[r["id"]]
        entries[r["id"]] = entry
    top = {k: v for k, v in compose.items() if k != "services" and not k.startswith("x-")}
    manifest = {"schema": SCHEMA, "platform_version": version, "git_sha": git_sha, "registry": registry,
                "images_published": bool(digests), "compose": top, "services": entries}
    if digests and signer_repository:
        manifest["signing"] = signing(version, signer_repository, server)
    return manifest


def read_pushed(directory=None, pairs=()):
    """({service id: digest}, {service id: image id}) from the publish jobs' JSON files, each
    {id: digest} or {id: {"digest": ..., "image_id": ...}}, and from --digest ID=sha256:..."""
    digests, image_ids = {}, {}

    def add(sid, digest, image_id=None):
        if sid in digests and digests[sid] != digest:
            raise ManifestError(f"two digests for {sid}")
        digests[sid] = digest
        if image_id is not None:
            image_ids[sid] = image_id

    if directory:
        for path in sorted(Path(directory).glob("*.json")):
            for sid, value in json.loads(path.read_text()).items():
                if isinstance(value, dict):
                    add(sid, value.get("digest"), value.get("image_id"))
                else:
                    add(sid, value)
    for pair in pairs:
        sid, sep, digest = pair.partition("=")
        if not sep:
            raise ManifestError(f"--digest {pair!r} is not ID=sha256:...")
        add(sid, digest)
    return digests, image_ids


def read_digests(directory=None, pairs=()):
    return read_pushed(directory, pairs)[0]


def _git_sha():
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list-images", action="store_true",
                        help="print the images a release builds as a JSON list and exit")
    parser.add_argument("--version", help="the release version; must equal qrosetta_cli.__version__")
    parser.add_argument("--git-sha", help="default: $GITHUB_SHA, else `git rev-parse HEAD`")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--digests-dir", help="directory of JSON files {service id: sha256 digest}")
    parser.add_argument("--digest", action="append", default=[], metavar="ID=sha256:...")
    parser.add_argument("--signer-repository", metavar="OWNER/REPOSITORY",
                        help="the repository whose release workflow signed the images (default: none)")
    parser.add_argument("--server-url", default=os.environ.get("GITHUB_SERVER_URL") or "https://github.com")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    try:
        records = services()
        if args.list_images:
            print(json.dumps(release_images(records)))
            return 0
        version = platform_version()
        if args.version and args.version != version:
            raise ManifestError(f"--version {args.version} differs from qrosetta_cli.__version__ {version}")
        digests, image_ids = read_pushed(args.digests_dir, args.digest)
        manifest = build_manifest(version, args.git_sha or _git_sha(), args.registry, digests, records,
                                  image_ids=image_ids, signer_repository=args.signer_repository,
                                  server=args.server_url)
    except ManifestError as exc:
        print(f"make_manifest: {exc}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    published = "images published" if manifest["images_published"] else "no image digests"
    print(f"Wrote {out}: {len(manifest['services'])} services, {published}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
