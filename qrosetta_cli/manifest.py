"""The release manifest a wheel carries (release/manifest.json, written by
scripts/release/make_manifest.py): the release's services and the image digests it published."""

import json
import os
import re

from qrosetta_cli.errors import CliError, Exit

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "release", "manifest.json")
SCHEMA = "qrosetta.release-manifest@1"
DIGEST_REF = re.compile(r"^[a-z0-9][^@\s]*@sha256:[0-9a-f]{64}$")


def load(path=None):
    """The manifest, or None when the package carries none."""
    path = path or PATH
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise CliError(f"The release manifest {path} cannot be read: {exc}", Exit.INTERNAL, "manifest_invalid",
                       hint="reinstall qrosetta") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("services"), dict):
        raise CliError(f"{path} is not a {SCHEMA} release manifest.", Exit.INTERNAL, "manifest_invalid",
                       hint="reinstall qrosetta")
    return data


def published_refs(manifest):
    """{service id: image reference by digest} for every service the release published."""
    services = (manifest or {}).get("services") or {}
    return {sid: svc["ref"] for sid, svc in services.items()
            if isinstance(svc, dict) and isinstance(svc.get("ref"), str) and DIGEST_REF.match(svc["ref"])}


def images_published(manifest):
    """True when the manifest says its images are published and names a digest for every
    distributable service and for no other."""
    if not manifest or manifest.get("images_published") is not True:
        return False
    refs = published_refs(manifest)
    services = manifest["services"]
    return bool(services) and all((sid in refs) == (svc.get("distributable") is True)
                                  for sid, svc in services.items())


def describe(manifest):
    """One line for `qrosetta version`."""
    if manifest is None:
        return "none in this package"
    state = "images published" if images_published(manifest) else "images not published"
    return f"release {manifest.get('platform_version', '?')} ({state})"
