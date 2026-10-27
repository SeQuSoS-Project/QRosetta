"""Cosign verification of release images (spec Q14): keyless signatures made by the release
workflow, checked against the certificate identity and issuer the release manifest names."""

import os
import re
import shutil
import subprocess

from qrosetta_cli import manifest as mf

INSTALL = "https://docs.sigstore.dev/cosign/system_config/installation/"
_REJECTED = re.compile(r"no matching signatures|no signatures found|invalid signature|certificate|"
                       r"identity|issuer|signature.*mismatch", re.I)


def cosign_path(env):
    return shutil.which("cosign", path=(env or os.environ).get("PATH"))


def verify(engine, manifest, ref, env):
    """(status, detail): status is `verified`, `rejected` (cosign checked and refused),
    `unchecked` (cosign could not check: offline, registry error) or `unavailable` (no cosign,
    or the manifest names no signer)."""
    signer = mf.signer(manifest)
    if signer is None:
        return "unavailable", "the release manifest names no signing workflow"
    path = cosign_path(env)
    if not path:
        return "unavailable", f"cosign is not installed ({INSTALL})"
    identity, issuer = signer
    try:
        out = engine.tool(path, "verify", "--certificate-identity", identity, "--certificate-oidc-issuer", issuer,
                          ref, timeout=300)
    except subprocess.TimeoutExpired:
        return "unchecked", "cosign did not finish within 300 s"
    text = (out.stderr or out.stdout or "").strip()
    last = text.splitlines()[-1] if text else "no output"
    if out.returncode == 0:
        return "verified", f"signed by {identity}"
    if _REJECTED.search(text):
        return "rejected", last
    return "unchecked", last
