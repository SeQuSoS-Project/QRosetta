"""`qrosetta pull`: installed mode pulls the release manifest's images by digest (TMPDIR under
$XDG_CACHE_HOME/qrosetta/tmp), checks each image's repo digests and qrosetta labels, and checks
its cosign signature first when cosign is installed (--require-signature makes it mandatory).
A checkout builds its images instead. Services the release does not publish are named with
the reason and the command that builds them."""

import os
import re
import time

from qrosetta_cli import config as cfgmod, manifest as mf, mode as modes
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import guard, hostload, installed, serve, signatures
from qrosetta_cli.stack import ownership as own
from qrosetta_cli.stack import project as st
from qrosetta_cli.stack.actions import human_bytes
from qrosetta_cli.stack.explain import engine_error

RETRY_AFTER_SEC = 5
_TRANSIENT = re.compile(
    r"toomanyrequests|connection reset|connection refused|i/o timeout|tls handshake timeout|"
    r"timed out|timeout exceeded|unexpected eof|\beof\b|temporary failure|no such host|"
    r"network is unreachable|50[0234] |service unavailable|bad gateway",
    re.I,
)
_sleep = time.sleep


def cache_tmp(env):
    """$XDG_CACHE_HOME/qrosetta/tmp, created 0700: the engine's TMPDIR for pull, save and load."""
    path = os.path.join(cfgmod.qr_dir("cache", env), "tmp")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def _checkout_refusal(names):
    release = mf.load()
    keys = " ".join(names) if names else "--profile minimal"
    why = (
        "a checkout runs the images it builds, and its compose file names no release images"
        if mf.images_published(release)
        else "this checkout carries no release manifest with published image digests"
    )
    raise CliError(
        f"`qrosetta pull` fetches the published images of a release; {why}. Build the images here "
        "instead, or install a release (pip install qrosetta), whose images are pulled.",
        Exit.INCOMPATIBLE,
        "checkout_builds_images",
        hint=f"qrosetta build {keys}",
    )


def targets(stack, manifest, args, cfg):
    """(compose services to pull, [(service id, reason)] the release does not publish)."""
    withheld = mf.not_distributable(manifest)
    skipped = [(n, withheld[n]) for n in args.services if n in withheld]
    names = [n for n in args.services if n not in withheld]
    if not (names or args.profile or args.core or args.all or skipped):
        profiles = ", ".join(sorted({p for s in stack.services.values() for p in s.profiles})) or "none"
        raise usage(
            f"Name the services to pull, a profile ({profiles}), --core or --all.",
            hint="qrosetta pull --profile minimal",
            reason="nothing_named",
        )
    if args.all:
        return list(stack.services), list(withheld.items())
    wanted = serve.requested_services(stack, names, args.profile, cfg) or []
    if args.core or args.profile:
        core = stack.core_services() + [s for s in stack.services if stack.kind_of(s) == "core"]
        wanted += [c for c in dict.fromkeys(core) if c not in wanted]
    return wanted, skipped


def _pull_once(engine, ref):
    return engine.cli("pull", ref)


def pull_ref(engine, ref):
    """Pull by digest, retrying once after a transient registry or network error."""
    out = _pull_once(engine, ref)
    if out.returncode != 0 and _TRANSIENT.search(out.stderr or out.stdout or ""):
        progress(
            f"  network or registry error ({(out.stderr or out.stdout).strip().splitlines()[-1]}); "
            f"retrying in {RETRY_AFTER_SEC} s"
        )
        _sleep(RETRY_AFTER_SEC)
        out = _pull_once(engine, ref)
    if out.returncode != 0:
        raise engine_error(out.stderr or out.stdout, f"pulling {ref}")


def check_pulled(stack, service, ref, img):
    """Problems with a pulled image: the digest and the labels for its service."""
    problems = []
    if img is None or ref not in img.digests:
        problems.append(f"no image with repo digest {ref} after the pull")
        return problems
    if img.labels.get(own.QR_SERVICE) != service:
        problems.append(f"labelled org.qrosetta.service={img.labels.get(own.QR_SERVICE)!r}, not {service}")
    return problems


def _one(engine, stack, manifest, service, ref, require_signature, env, n, total):
    sid = stack.services[service].id
    present = st.find_images(engine, [ref]).get(ref)
    if present is not None and not check_pulled(stack, service, ref, present):
        progress(f"{sid} ({n}/{total}): already present ({ref.split('@')[1][:19]})")
        return {"id": sid, "ref": ref, "state": "present", "signature": None, "size_bytes": present.size}
    progress(f"{sid} ({n}/{total}): {ref}")
    status, detail = signatures.verify(engine, manifest, ref, env)
    if status == "rejected" or (require_signature and status != "verified"):
        raise CliError(
            f"{sid}: signature not verified ({detail}); nothing was pulled for it.",
            Exit.ENGINE,
            "signature_not_verified",
            hint="qrosetta images verify --require-signature",
        )
    if status != "verified":
        progress(f"  signature not checked: {detail}")
    started = time.monotonic()
    pull_ref(engine, ref)
    img = st.find_images(engine, [ref]).get(ref)
    problems = check_pulled(stack, service, ref, img)
    if problems:
        raise CliError(
            f"{sid}: {'; '.join(problems)}.", Exit.ENGINE, "pulled_image_mismatch", hint="qrosetta images verify"
        )
    if img.labels.get(own.QR_IMAGE_PROJECT) != stack.name:
        progress(
            f"  labelled for compose project {img.labels.get(own.QR_IMAGE_PROJECT)!r}, not {stack.name!r}: "
            "qrosetta reports this image but never removes it"
        )
    progress(
        f"  pulled, {human_bytes(img.size)}, {time.monotonic() - started:.0f} s"
        + (f"; {detail}" if status == "verified" else "")
    )
    return {"id": sid, "ref": ref, "state": "pulled", "signature": status, "size_bytes": img.size}


def cmd_pull(ctx):
    args = ctx.args
    mode = modes.detect(ctx.opt("project_dir"), ctx.env, ctx.checkout)
    if mode.name == "checkout":
        _checkout_refusal(args.services)
    manifest = installed.require_published()
    from qrosetta_cli.stack.commands import open_stack

    _, engine, stack = open_stack(ctx)
    wanted, skipped = targets(stack, manifest, args, ctx.cfg)
    for sid, reason in skipped:
        progress(f"{sid}: not published ({reason}). `qrosetta build {sid}` in a checkout of this release builds it.")
    refs = mf.published_refs(manifest)
    by_service = mf.by_compose_service(manifest)
    jobs = [(s, refs[by_service[s]]) for s in wanted if by_service.get(s) in refs]
    if args.require_signature and mf.signer(manifest) is None:
        raise CliError(
            "--require-signature: this release's manifest names no signing workflow.",
            Exit.ENGINE,
            "signature_not_verified",
            hint="qrosetta pull without --require-signature",
        )
    url = serve.stack_url(engine, stack) if any(c.running for c in own.scan(engine, stack).containers) else None
    if jobs and url:
        guard.refuse_if_busy(
            ctx, url, "pull", "--yes", args.yes, "a pull now loads the host beside their timed windows"
        )
    engine.env["TMPDIR"] = cache_tmp(ctx.env)
    pulled, failed = [], []
    with (
        guard.engine_lock(ctx.env, "pull"),
        hostload.notice(ctx, url if jobs else None, "pull", [stack.services[s].id for s, _ in jobs]),
    ):
        for n, (service, ref) in enumerate(jobs, 1):
            try:
                pulled.append(
                    _one(engine, stack, manifest, service, ref, args.require_signature, ctx.env, n, len(jobs))
                )
            except CliError as exc:
                progress(f"  {exc.message}")
                failed.append(
                    {"id": stack.services[service].id, "ref": ref, "reason": exc.reason, "message": exc.message}
                )
            except KeyboardInterrupt:
                progress(
                    "qrosetta: interrupted; finished images and layers are kept; rerun the same command to continue."
                )
                return Result(int(Exit.SIGINT), {"pulled": pulled, "failed": failed})
    data = {
        "release": manifest.get("platform_version"),
        "pulled": pulled,
        "failed": failed,
        "not_published": [{"id": sid, "reason": reason} for sid, reason in skipped],
    }
    if pulled:
        total = sum(p["size_bytes"] or 0 for p in pulled)
        result(
            f"{len(pulled)} images of Quantum Rosetta {data['release']} present ({human_bytes(total)}); "
            "`qrosetta start -d` starts them."
        )
    if failed:
        raise CliError(
            f"{len(failed)} of {len(jobs)} images were not pulled: {', '.join(f['id'] for f in failed)}.",
            Exit.ENGINE,
            failed[0]["reason"],
            hint=f"qrosetta pull {' '.join(f['id'] for f in failed)}",
            data=data,
        )
    return Result(0, data)
