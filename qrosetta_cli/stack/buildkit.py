"""The build kit an installed qrosetta carries (release/buildkit.tar.gz with release/buildkit.json,
written by scripts/release/make_buildkit.py): the files of the release commit that building the
images needs. `qrosetta build` in installed mode checks the archive's sha256, unpacks it into
$XDG_CACHE_HOME/qrosetta/buildkit/<version>-<sha12>/ and builds there through
scripts/safe_boot.sh, as a checkout does. Each image is tagged <project>-<service>:<version>-buildkit,
bakes the commit <kit commit>+buildkit and records source built_locally with the release. The
services that run their local build are a stack setting (`built_locally`); a pull or a load of
a service ends it."""

import hashlib
import json
import os
import shutil
import sys
import tarfile

from qrosetta_cli import __version__, config as cfgmod, localstack, manifest as mf
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import project as st

ARCHIVE = "buildkit.tar.gz"
META = "buildkit.json"
SCHEMA = "qrosetta.buildkit@1"
MARKER = ".qrosetta-buildkit.json"
SUFFIX = "+buildkit"
SETTING = "built_locally"
GPU_NOTE = "it needs an NVIDIA GPU to run"


def paths():
    """(archive, metadata) paths inside the installed package."""
    directory = os.path.dirname(mf.PATH)
    return os.path.join(directory, ARCHIVE), os.path.join(directory, META)


def load():
    """The kit's metadata, or None when the package carries no build kit."""
    archive, meta_path = paths()
    if not (os.path.isfile(archive) and os.path.isfile(meta_path)):
        return None
    try:
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError) as exc:
        raise CliError(
            f"The build kit metadata {meta_path} cannot be read: {exc}",
            Exit.INTERNAL,
            "buildkit_invalid",
            hint="reinstall qrosetta",
        ) from exc
    if not isinstance(meta, dict) or meta.get("schema") != SCHEMA or not isinstance(meta.get("sha256"), str):
        raise CliError(
            f"{meta_path} is not {SCHEMA} metadata.", Exit.INTERNAL, "buildkit_invalid", hint="reinstall qrosetta"
        )
    return meta


def describe(meta):
    if meta is None:
        return "none in this package"
    return (
        f"{meta.get('size', 0) / 1e6:.1f} MB, {meta.get('files', '?')} files, "
        f"commit {str(meta.get('commit', '?'))[:12]}"
    )


def tag(project, compose_service):
    return f"{project}-{compose_service}:{__version__}-buildkit"


def baked_commit(meta):
    return f"{meta['commit']}{SUFFIX}"


def is_kit_commit(sha):
    return isinstance(sha, str) and sha.endswith(SUFFIX)


def tags(manifest, project):
    """{service id: build-kit tag} of every service of the release."""
    return {
        sid: tag(project, svc["compose_service"])
        for sid, svc in ((manifest or {}).get("services") or {}).items()
        if isinstance(svc, dict) and svc.get("compose_service")
    }


def missing_kit(manifest):
    release = (manifest or {}).get("platform_version") or __version__
    return CliError(
        f"This qrosetta {__version__} package carries no build kit, so it cannot build images of "
        f"Quantum Rosetta {release}. Install a release (pip install qrosetta), whose package carries "
        "one, or build from a source checkout.",
        Exit.INCOMPATIBLE,
        "buildkit_missing",
        hint="git clone https://github.com/SeQuSoS-Project/QRosetta && cd QRosetta && ./qrosetta build",
    )


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _members(tar):
    """The archive's regular files, refused when any entry could leave the directory."""
    out = []
    for m in tar.getmembers():
        name = m.name
        parts = name.split("/")
        if not m.isfile() or name.startswith("/") or ".." in parts or "" in parts or name == MARKER:
            raise CliError(
                f"The build kit holds an entry qrosetta does not unpack: {name!r}.",
                Exit.INTERNAL,
                "buildkit_invalid",
                hint="reinstall qrosetta",
            )
        out.append(m)
    return out


def _unpacked_ok(directory, meta):
    """Whether `directory` holds this kit as unpacked: the marker names the archive's sha256 and
    every file still has the sha256 recorded at unpacking."""
    try:
        with open(os.path.join(directory, MARKER), encoding="utf-8") as fh:
            marker = json.load(fh)
        if marker.get("sha256") != meta["sha256"]:
            return False
        return all(_sha256(os.path.join(directory, name)) == digest for name, digest in marker["files"].items())
    except (OSError, ValueError, KeyError, AttributeError, TypeError):
        return False


def unpack(env, meta):
    """The directory holding the unpacked kit, reused when it still matches; the archive's sha256
    is checked against the metadata first."""
    archive, _ = paths()
    digest = _sha256(archive)
    if digest != meta["sha256"]:
        raise CliError(
            f"The build kit {archive} has sha256 {digest}, its metadata records {meta['sha256']}.",
            Exit.INTERNAL,
            "buildkit_corrupt",
            hint="reinstall qrosetta",
        )
    base = os.path.join(cfgmod.qr_dir("cache", env), "buildkit")
    target = os.path.join(base, f"{__version__}-{digest[:12]}")
    if _unpacked_ok(target, meta):
        return target
    os.makedirs(base, mode=0o700, exist_ok=True)
    staging = f"{target}.unpacking-{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    files = {}
    with tarfile.open(archive, "r:gz") as tar:
        for m in _members(tar):
            dest = os.path.join(staging, *m.name.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            member = tar.extractfile(m)
            data = member.read() if member is not None else b""
            with open(dest, "wb") as fh:
                fh.write(data)
            os.chmod(dest, 0o755 if m.mode & 0o111 else 0o644)
            files[m.name] = hashlib.sha256(data).hexdigest()
    with open(os.path.join(staging, MARKER), "w", encoding="utf-8") as fh:
        json.dump({"sha256": digest, "commit": meta.get("commit"), "files": files}, fh, indent=1, sort_keys=True)
    if os.path.isdir(target) and os.path.isfile(os.path.join(target, MARKER)):
        shutil.rmtree(target)
    os.replace(staging, target)
    return target


def recorded(env, project):
    """{service id: tag} of the services whose build-kit image the stack runs."""
    entry = localstack.stack_settings(env, project).get(SETTING)
    return {k: v for k, v in entry.items() if isinstance(v, str)} if isinstance(entry, dict) else {}


def record(env, project, built):
    """Add {service id: tag} to the services that run their build-kit image."""
    old = localstack.stack_settings(env, project)
    values = dict(old, **{SETTING: dict(sorted({**recorded(env, project), **built}.items()))})
    if values != old:
        localstack.write_stack_settings(env, project, values)


def forget(env, project, sids):
    """Stop running the build-kit images of `sids`; the ids that did."""
    current = recorded(env, project)
    gone = [s for s in sids if s in current]
    if gone:
        old = localstack.stack_settings(env, project)
        rest = {k: v for k, v in current.items() if k not in gone}
        values = {k: v for k, v in old.items() if k != SETTING}
        if rest:
            values[SETTING] = rest
        localstack.write_stack_settings(env, project, values)
    return gone


def local_images(engine, manifest, env):
    """{service id: tag} of the recorded build-kit images of this version that exist with this
    project's labels for their service."""
    project = engine.project
    want = {sid: t for sid, t in recorded(env, project).items() if tags(manifest, project).get(sid) == t}
    found = st.find_images(engine, list(want.values()))
    services = manifest.get("services") or {}
    out = {}
    for sid, t in want.items():
        img = found.get(t)
        cs = (services.get(sid) or {}).get("compose_service")
        if (
            img is not None
            and img.labels.get("org.qrosetta.image.project") == project
            and (img.labels.get("org.qrosetta.service") == cs)
        ):
            out[sid] = t
    return out


def annotate(stack, manifest, env):
    """Give an installed stack the build-kit tags of all its services, which `remove --images`
    also removes, and the release it was built from."""
    if load() is None:
        return
    by_service = mf.by_compose_service(manifest)
    stack.extra_image_refs = {tag(stack.name, cs): cs for cs in stack.services if cs in by_service}


def _split(stack, sids):
    """(services to pull, services to build): a service of the release without a published image
    is built, every other one pulled."""
    services = stack.release.get("services") or {}
    refs = mf.published_refs(stack.release)
    build = [s for s in sids if s in services and s not in refs]
    return [s for s in sids if s not in build], build


def get_command(stack, sids):
    """`qrosetta pull ...` for services the release publishes, `qrosetta build ...` for the others
    (or every service, in a checkout); one string, the pull first."""
    if not stack.release:
        return f"qrosetta build {' '.join(sids)}"
    pull, build = _split(stack, sids)
    parts = ([f"qrosetta pull {' '.join(pull)}"] if pull else []) + (
        [f"qrosetta build {' '.join(build)}"] if build else []
    )
    return " && ".join(parts)


def missing_lines(stack, sids):
    """The sentences `start` prints for services it leaves out for lack of an image."""
    names = ", ".join(sids)
    if not stack.release:
        return [f"Not started (no image): {names}. `qrosetta build {' '.join(sids)}` builds them."]
    pull, build = _split(stack, sids)
    lines = [f"Not started (no image): {names}."]
    if pull:
        lines.append(
            f"`qrosetta pull {' '.join(pull)}` pulls them; `qrosetta images load DIR` loads them from "
            "the release's image archives."
        )
    if build:
        lines.append(f"{', '.join(build)}: {mf.not_included_text(build)}.")
    return lines


def manifest_stack(manifest, project):
    """A Stack of every service of the release, each image under its build-kit tag."""
    services = {}
    for sid, svc in (manifest.get("services") or {}).items():
        compose = svc.get("compose") or {}
        labels = {k: str(v) for k, v in (compose.get("labels") or {}).items()}
        labels.update({st.ID_LABEL: sid, st.KIND_LABEL: svc.get("kind") or "unknown"})
        if svc.get("profiles"):
            labels[st.PROFILES_LABEL] = ",".join(svc["profiles"])
        cs = svc["compose_service"]
        deps = compose.get("depends_on") or {}
        services[cs] = st.Service(
            name=cs,
            container_name=compose.get("container_name") or "",
            image=tag(project, cs),
            ports=compose.get("ports") or [],
            depends_on=list(deps),
            labels=labels,
        )
    return st.Stack(name=project, project_dir="", services=services, volume_names={}, release=manifest)


def cmd_build(ctx):
    """`qrosetta build` in installed mode: the named services, a profile with core, or every
    service of the release, from the package's build kit."""
    from qrosetta_cli.stack import serve
    from qrosetta_cli.stack.commands import make_engine, run_build

    args = ctx.args
    manifest = mf.load()
    meta = load()
    if manifest is None or meta is None:
        raise missing_kit(manifest)
    project = localstack.project(ctx.env)
    kit_stack = manifest_stack(manifest, project)
    requested = serve.requested_services(kit_stack, args.services, args.profile, ctx.cfg) or list(kit_stack.services)
    if args.profile:
        requested += [s for s in kit_stack.services if kit_stack.kind_of(s) == "core" and s not in requested]
    if not requested:
        raise usage("Nothing to build.", hint="qrosetta build --profile minimal", reason="nothing_named")
    directory = unpack(ctx.env, meta)
    progress(f"Build kit of Quantum Rosetta {__version__} (commit {meta['commit'][:12]}) in {directory}")
    engine = make_engine(ctx, directory)
    engine.check_compose()
    baked = baked_commit(meta)
    log_dir = os.path.join(cfgmod.qr_dir("cache", ctx.env), "build-logs")
    built = run_build(
        ctx,
        engine,
        kit_stack,
        os.path.join(directory, "scripts", "safe_boot.sh"),
        requested,
        requested,
        {
            "QR_GIT_SHA": baked,
            "QR_IMAGE_TAG": f"{__version__}-buildkit",
            "QR_PYTHON": sys.executable or "python3",
            "QR_BUILD_LOG_DIR": log_dir,
            "QROSETTA_IMAGE_SOURCE": "built_locally",
            "QROSETTA_RELEASE": __version__,
        },
        expected_sha=baked,
    )
    if built is None:
        return Result(int(Exit.SIGINT), None)
    ids = [kit_stack.services[s].id for s in built]
    record(ctx.env, project, {sid: tag(project, manifest["services"][sid]["compose_service"]) for sid in ids})
    refs = mf.published_refs(manifest)
    replaced = [s for s in ids if s in refs]
    result(f"Built {len(ids)} images from the build kit: {', '.join(ids)}.")
    if replaced:
        result(
            f"{', '.join(replaced)}: the stack runs these local builds instead of the published images; "
            f"`qrosetta pull {' '.join(replaced)}` goes back to the published ones."
        )
    gpu = [s for s in ids if (manifest["services"][s] or {}).get("requires_gpu")]
    if gpu:
        result(f"{', '.join(gpu)}: {GPU_NOTE}.")
    result("`qrosetta start -d` starts them.")
    return Result(0, {"built": ids, "source": "build kit", "commit": baked, "release": __version__})
