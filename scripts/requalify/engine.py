"""Container engine calls of the requalification harness. Images are tagged
localhost/qr-requal-<service>:old|new with label org.qrosetta.image.project=requal; containers run
with --network none; everything created is removed by ID. Stdlib only."""

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from registry import REPO

ENGINE = os.environ.get("ENGINE", "podman")
LABEL = "org.qrosetta.image.project=requal"
CONTEXT_LABEL = "org.qrosetta.requal.context"
THREAD_ENV = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
              "NUMBA_NUM_THREADS")


def device_args(devices):
    """``--device`` options for every device name in ``devices``."""
    return [arg for device in devices for arg in ("--device", device)]


def run(args, check=True, capture=True, env=None, timeout=None, prefix=()):
    return subprocess.run([*prefix, ENGINE, *args], check=check, text=True, env=env, timeout=timeout,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def image_id(ref):
    proc = run(["image", "inspect", "--format", "{{.Id}}", ref], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def image_label(ref, label):
    proc = run(["image", "inspect", "--format", f'{{{{index .Labels "{label}"}}}}', ref], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def image_size(ref):
    return int(run(["image", "inspect", "--format", "{{.Size}}", ref]).stdout.strip())


def overlay_names(overlay_dir):
    """The files of a candidate directory that go over the service directory: every regular file
    except the harness's own ``prepare.json`` (a build stage's hash-pinned requirements, for one)."""
    return sorted(p.name for p in Path(overlay_dir).iterdir() if p.is_file() and p.name != "prepare.json")


def stage_context(dest, overlay_dir=None, service_dir=None):
    """Copy the working tree (tracked and untracked, not ignored) to ``dest``, then the files of
    ``overlay_dir`` over ``service_dir``. Returns the sha256 of the staged tree."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    listing = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z", "-co", "--exclude-standard"],
                             check=True, capture_output=True).stdout.decode().split("\0")
    for rel in filter(None, listing):
        src = REPO / rel
        if not src.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    if overlay_dir is not None:
        for name in overlay_names(overlay_dir):
            shutil.copy2(overlay_dir / name, dest / service_dir / name)
    digest = hashlib.sha256()
    for path in sorted(p for p in dest.rglob("*") if p.is_file()):
        digest.update(path.relative_to(dest).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def base_refs(dockerfile_text):
    """External images a Dockerfile builds FROM (stage names excluded)."""
    stages, refs = set(), []
    for line in dockerfile_text.splitlines():
        parts = line.split()
        if parts and parts[0].upper() == "FROM":
            parts = [p for p in parts[1:] if not p.startswith("--platform=")]
            if parts[0] not in stages:
                refs.append(parts[0])
            if len(parts) >= 3 and parts[1].upper() == "AS":
                stages.add(parts[2])
    return refs


def build(tag, context, service_dir, context_hash, build_args, log_path):
    """Build ``tag`` from ``context`` unless an image with that tag, context hash and build
    arguments exists."""
    context_hash = hashlib.sha256((context_hash + json.dumps(build_args, sort_keys=True)).encode()).hexdigest()
    if image_label(tag, CONTEXT_LABEL) == context_hash:
        return image_id(tag), False
    env = dict(os.environ, TMPDIR=str(Path.home() / ".tmp" / "podman-build"))
    Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    args = ["build", "--layers=false", "--pull=missing", "-f", str(context / service_dir / "Dockerfile"),
            "-t", tag, "--label", LABEL, "--label", f"{CONTEXT_LABEL}={context_hash}"]
    for key, value in build_args.items():
        args += ["--build-arg", f"{key}={value}"]
    with open(log_path, "w") as log:
        proc = subprocess.run([ENGINE, *args, str(context)], env=env, stdout=log, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SystemExit(f"build of {tag} failed; log: {log_path}")
    return image_id(tag), True


def run_in_container(image, command, in_dir, out_dir, log_path, memory, extra=(), env=None, prefix=(),
                     timeout=None):
    """Create a container with no network, copy ``in_dir`` to /home/appuser/requal-in, run
    ``command``, copy /home/appuser/requal-out back to ``out_dir`` and remove the container."""
    args = ["create", "--network", "none", "--memory", memory, *extra]
    for key in THREAD_ENV:
        args += ["--env", f"{key}=1"]
    for key, value in (env or {}).items():
        args += ["--env", f"{key}={value}"]
    cid = run([*args, image, *command]).stdout.strip()
    try:
        run(["cp", str(in_dir), f"{cid}:/home/appuser/requal-in"])
        started = time.monotonic()
        with open(log_path, "w") as log:
            proc = subprocess.run([*prefix, ENGINE, "start", "-a", cid], stdout=log, stderr=subprocess.STDOUT,
                                  timeout=timeout)
        elapsed = time.monotonic() - started
        if out_dir.exists():
            shutil.rmtree(out_dir)
        run(["cp", f"{cid}:/home/appuser/requal-out", str(out_dir)])
        return proc.returncode, elapsed
    finally:
        run(["rm", "-f", cid], check=False)


def remove_images(ids):
    removed = []
    for iid in ids:
        if iid and run(["rmi", iid], check=False).returncode == 0:
            removed.append(iid)
    return removed


def inspect_env(image, key):
    proc = run(["image", "inspect", "--format", "{{json .Config.Env}}", image], check=False)
    for item in json.loads(proc.stdout or "[]") or []:
        if item.startswith(key + "="):
            return item.split("=", 1)[1]
    return None
