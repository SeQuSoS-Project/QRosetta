"""The release manifest a wheel carries (release/manifest.json, written by
scripts/release/make_manifest.py): the release's services and the image digests it published."""

import json
import os
import re

from qrosetta_cli.errors import CliError, Exit

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "release", "manifest.json")
SCHEMA = "qrosetta.release-manifest@1"
DIGEST_REF = re.compile(r"^[a-z0-9][^@\s]*@sha256:[0-9a-f]{64}$")
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
OIDC_ISSUER = "https://token.actions.githubusercontent.com"


def load(path=None):
    """The manifest, or None when the package carries none."""
    path = path or PATH
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise CliError(
            f"The release manifest {path} cannot be read: {exc}",
            Exit.INTERNAL,
            "manifest_invalid",
            hint="reinstall qrosetta",
        ) from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("services"), dict):
        raise CliError(
            f"{path} is not a {SCHEMA} release manifest.", Exit.INTERNAL, "manifest_invalid", hint="reinstall qrosetta"
        )
    return data


def published_refs(manifest):
    """{service id: image reference by digest} for every service the release published."""
    services = (manifest or {}).get("services") or {}
    return {
        sid: svc["ref"]
        for sid, svc in services.items()
        if isinstance(svc, dict) and isinstance(svc.get("ref"), str) and DIGEST_REF.match(svc["ref"])
    }


def images_published(manifest):
    """True when the manifest says its images are published and names a digest for every
    distributable service and for no other."""
    if not manifest or manifest.get("images_published") is not True:
        return False
    refs = published_refs(manifest)
    services = manifest["services"]
    return bool(services) and all((sid in refs) == (svc.get("distributable") is True) for sid, svc in services.items())


def describe(manifest):
    """One line for `qrosetta version`."""
    if manifest is None:
        return "none in this package"
    state = "images published" if images_published(manifest) else "images not published"
    return f"release {manifest.get('platform_version', '?')} ({state})"


def image_id_key(ident):
    """An image id or digest as `sha256:<hex>`, whether the engine wrote the prefix or not."""
    ident = (ident or "").strip()
    if re.fullmatch(r"[0-9a-f]{64}", ident):
        return "sha256:" + ident
    return ident


def release_ids(manifest, service_id):
    """The ids an image of `service_id` from this release may carry: the config digest the
    release recorded (`image_id`) and its registry digest (engines that key images by manifest
    digest report that as the id)."""
    svc = ((manifest or {}).get("services") or {}).get(service_id) or {}
    ids = set()
    if isinstance(svc.get("image_id"), str) and IMAGE_ID.match(svc["image_id"]):
        ids.add(svc["image_id"])
    ref = published_refs(manifest).get(service_id)
    if ref:
        ids.add(ref.split("@", 1)[1])
    return ids


def by_compose_service(manifest):
    """{compose service: service id} of every service the manifest lists."""
    return {
        svc.get("compose_service"): sid
        for sid, svc in ((manifest or {}).get("services") or {}).items()
        if isinstance(svc, dict) and svc.get("compose_service")
    }


def not_distributable(manifest):
    """{service id: reason} for the services the release never publishes."""
    return {
        sid: svc.get("not_distributable_reason") or "its licence does not allow the project to publish it"
        for sid, svc in ((manifest or {}).get("services") or {}).items()
        if isinstance(svc, dict) and svc.get("distributable") is False
    }


NOT_INCLUDED_VAR = "QROSETTA_NOT_INCLUDED"
NOT_INCLUDED = "not included in this release"


def not_included(manifest):
    """The sorted ids of the services `manifest` publishes no image of; [] without a manifest.
    `start` passes them to the API as QROSETTA_NOT_INCLUDED, which reports them unavailable with
    the reason NOT_INCLUDED."""
    return sorted(not_distributable(manifest))


def not_included_text(ids):
    """What the CLI says of the services `ids` (one or several) that this release does not include;
    it begins with NOT_INCLUDED, which `selftest` groups by."""
    return NOT_INCLUDED


def loaded_tag(project, compose_service, release):
    """The local tag `qrosetta images load` gives a release image: the image has no registry
    digest after a load, so the generated compose file names it by this tag."""
    return f"{project}-{compose_service}:{release}"


def signer(manifest):
    """(certificate identity, OIDC issuer) the release's cosign signatures must carry, or None
    when the manifest does not name the workflow that signed them."""
    signing = (manifest or {}).get("signing") or {}
    identity, issuer = signing.get("identity"), signing.get("issuer")
    if isinstance(identity, str) and identity.startswith("https://") and issuer == OIDC_ISSUER:
        return identity, issuer
    return None
