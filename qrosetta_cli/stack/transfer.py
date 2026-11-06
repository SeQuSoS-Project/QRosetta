"""`qrosetta images save|load`: this stack's images to and from a directory of `<engine> save`
archives with an index, for machines without registry access (offline HPC nodes, the Zenodo
record). `save` writes only images that pass the ownership checks. `load` reads each archive's
image configuration before loading it and refuses anything that is not a qrosetta image of a
known service (in installed mode: an image the release manifest records), then tags it where
the stack looks for it. Nothing is ever deleted."""

import os
import time

from qrosetta_cli import __version__, manifest as mf
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import archive, guard, hostload, serve
from qrosetta_cli.stack import ownership as own
from qrosetta_cli.stack import project as st
from qrosetta_cli.stack.actions import human_bytes
from qrosetta_cli.stack.pull import cache_tmp


def _busy_guard(ctx, engine, stack, command, effect):
    url = serve.stack_url(engine, stack) if any(c.running for c in own.scan(engine, stack).containers) else None
    if url:
        guard.refuse_if_busy(ctx, url, command, "--yes", ctx.args.yes, effect)
    return url


def cmd_images_save(ctx):
    from qrosetta_cli.stack.commands import open_stack

    args = ctx.args
    mode, engine, stack = open_stack(ctx)
    directory = os.path.abspath(os.path.expanduser(args.output))
    if os.path.exists(os.path.join(directory, archive.INDEX)):
        raise usage(
            f"{directory} already holds {archive.INDEX}; qrosetta does not overwrite an archive.",
            hint="qrosetta images save -o NEW_DIRECTORY",
            reason="archive_exists",
        )
    wanted = serve.requested_services(stack, args.services, args.profile, ctx.cfg) or list(stack.services)
    owned, refused = own.owned_images(engine, stack)
    owned = {service: img for service, img in owned if service in wanted}
    refused = [(ref, why) for ref, why, _ in refused if any(stack.image_for(s) == ref for s in wanted)]
    missing = [
        stack.services[s].id
        for s in wanted
        if s not in owned and not any(ref == stack.image_for(s) for ref, _ in refused)
    ]
    for ref, why in refused:
        progress(f"{ref} {why}; not saved.")
    if missing and (args.services or args.profile):
        raise CliError(
            f"No image for {', '.join(missing)}.",
            Exit.NOT_FOUND,
            "image_missing",
            hint=("qrosetta pull " if stack.release else "qrosetta build ") + " ".join(missing),
        )
    if not owned:
        raise CliError(
            "No image of this stack passes the ownership checks; nothing to save.",
            Exit.NOT_FOUND,
            "nothing_to_save",
            hint="qrosetta images",
        )
    url = _busy_guard(
        ctx, engine, stack, "images save", "saving images now loads the host's disks beside their timed windows"
    )
    os.makedirs(directory, mode=0o755, exist_ok=True)
    engine.env["TMPDIR"] = cache_tmp(ctx.env)
    entries = []
    with (
        guard.engine_lock(ctx.env, "images save"),
        hostload.notice(ctx, url, "save", [stack.services[s].id for s in owned]),
    ):
        for n, (service, img) in enumerate(owned.items(), 1):
            sid = stack.services[service].id
            path = os.path.join(directory, f"{sid}.tar")
            progress(f"{sid} ({n}/{len(owned)}): {human_bytes(img.size)} to {path}")
            out = engine.cli("save", "-o", path, img.id)
            if out.returncode != 0:
                from qrosetta_cli.stack.explain import engine_error

                raise engine_error(out.stderr or out.stdout, f"saving {sid}")
            config_digest, _ = archive.read_archive(path)
            digest = next(
                (
                    d.split("@", 1)[1]
                    for d in img.digests
                    if "@" in d and stack.release and d == mf.published_refs(stack.release).get(sid)
                ),
                None,
            )
            entries.append(
                {
                    "service": sid,
                    "compose_service": service,
                    "file": os.path.basename(path),
                    "image_id": mf.image_id_key(img.id),
                    "config_digest": config_digest,
                    "git_sha": img.git_sha,
                    "digest": digest,
                    "sha256": archive.sha256_file(path),
                    "bytes": os.path.getsize(path),
                }
            )
    index = {
        "schema": archive.SCHEMA,
        "project": stack.name,
        "mode": mode.name,
        "release": (stack.release or {}).get("platform_version"),
        "created_by": f"qrosetta {__version__}",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine": engine.name,
        "images": entries,
    }
    path = archive.write_index(directory, index)
    result(
        f"Saved {len(entries)} images to {directory} ({human_bytes(sum(e['bytes'] for e in entries))}); "
        f"index {path}. On the other machine: qrosetta images load {directory}"
    )
    return Result(
        0,
        {
            "directory": directory,
            "index": path,
            "images": entries,
            "not_saved": [{"ref": ref, "reason": why} for ref, why in refused],
        },
    )


def _expected(stack, entry):
    """(compose service, tag, release ids or None) for an index entry, or a refusal reason."""
    sid = entry["service"]
    by_id = stack.by_id()
    if stack.release:
        svc = (stack.release.get("services") or {}).get(sid)
        if not svc or svc.get("compose_service") != entry["compose_service"]:
            return f"{sid} is not a service of release {stack.release.get('platform_version')}"
        if svc.get("distributable") is not True:
            return f"{sid} is not published by the release"
        ids = mf.release_ids(stack.release, sid)
        if not svc.get("image_id"):
            return (
                f"the release manifest records no image id for {sid}, so a loaded image cannot be checked "
                "against it; `qrosetta pull` fetches it by digest"
            )
        tag = mf.loaded_tag(stack.name, entry["compose_service"], stack.release.get("platform_version"))
        return entry["compose_service"], tag, ids
    svc = by_id.get(sid)
    if svc is None or svc.name != entry["compose_service"]:
        return f"{sid} is not a service of this stack"
    return svc.name, stack.image_for(svc.name), None


def check_entry(stack, directory, entry):
    """(compose service, tag, config digest) for an archive that may be loaded, or a CliError."""
    expected = _expected(stack, entry)
    if isinstance(expected, str):
        raise CliError(expected + "; not loaded.", Exit.ENGINE, "archive_refused", hint="qrosetta images")
    service, tag, ids = expected
    path = os.path.join(directory, entry["file"])
    if not os.path.isfile(path):
        raise CliError(f"{path} is missing.", Exit.NOT_FOUND, "archive_file_missing", hint="qrosetta images load DIR")
    if archive.sha256_file(path) != entry["sha256"]:
        raise CliError(
            f"{path} does not have the sha256 its index records (a damaged or altered copy).",
            Exit.ENGINE,
            "archive_corrupt",
            hint="download the archive again",
        )
    config_digest, config = archive.read_archive(path)
    facts = archive.config_facts(config)
    labels = facts["labels"]
    problems = []
    if config_digest != entry["config_digest"]:
        problems.append(f"image id {config_digest}, index says {entry['config_digest']}")
    if labels.get(own.QR_SERVICE) != service:
        problems.append(f"labelled org.qrosetta.service={labels.get(own.QR_SERVICE)!r}, not {service}")
    if not stack.release and labels.get(own.QR_IMAGE_PROJECT) != stack.name:
        problems.append(f"labelled for compose project {labels.get(own.QR_IMAGE_PROJECT)!r}, not {stack.name!r}")
    if ids is not None and config_digest not in ids:
        problems.append(
            f"image id {config_digest} is not the one release {stack.release.get('platform_version')} records"
        )
    foreign = sorted({t for t in archive.embedded_tags(path) if st.normalise_tag(t) != st.normalise_tag(tag)})
    if foreign:
        problems.append(f"the archive would tag the image {', '.join(foreign)} on load; qrosetta applies only {tag}")
    if problems:
        raise CliError(
            f"{entry['service']}: {'; '.join(problems)}; not loaded.",
            Exit.ENGINE,
            "archive_refused",
            hint="qrosetta images save -o DIR (on the machine that has the images)",
        )
    return service, tag, config_digest


def _tag_holder(engine, stack, service, tag, config_digest):
    """None when `tag` is free or holds this image or one of this stack's own; else the reason."""
    img = st.find_images(engine, [tag]).get(tag)
    if img is None or mf.image_id_key(img.id) == config_digest:
        return None
    return (
        own.image_refusal(stack, service, tag, img)
        if not stack.release
        else (None if img.labels.get(own.QR_SERVICE) == service else "has no qrosetta label for this service")
    )


def _load_one(engine, stack, directory, entry):
    service, tag, config_digest = check_entry(stack, directory, entry)
    holder = _tag_holder(engine, stack, service, tag, config_digest)
    if holder:
        raise CliError(
            f"{tag} {holder}; qrosetta leaves it alone, so {entry['service']} was not loaded.",
            Exit.ENGINE,
            "tag_held",
            hint=f"{engine.name} image inspect {tag}",
        )
    present = st.images_by_id(engine, [config_digest]).get(st.image_key(config_digest))
    if present is None:
        out = engine.cli("load", "-i", os.path.join(directory, entry["file"]))
        if out.returncode != 0:
            from qrosetta_cli.stack.explain import engine_error

            raise engine_error(out.stderr or out.stdout, f"loading {entry['file']}")
        present = st.images_by_id(engine, [config_digest]).get(st.image_key(config_digest))
        if present is None:
            raise CliError(
                f"{entry['file']} loaded, but the engine shows no image {config_digest}.",
                Exit.ENGINE,
                "loaded_image_missing",
                hint="qrosetta doctor",
            )
    out = engine.cli("tag", present.id, tag)
    if out.returncode != 0:
        from qrosetta_cli.stack.explain import engine_error

        raise engine_error(out.stderr or out.stdout, f"tagging {entry['service']}")
    return {"id": entry["service"], "tag": tag, "image_id": present.id, "git_sha": entry.get("git_sha")}


def cmd_images_load(ctx):
    from qrosetta_cli.stack.commands import open_stack

    args = ctx.args
    directory, index = archive.read_index(args.path)
    _, engine, stack = open_stack(ctx)
    entries = [e for e in index["images"] if not args.services or e["service"] in args.services]
    unknown = sorted(set(args.services or []) - {e["service"] for e in index["images"]})
    if unknown:
        raise CliError(
            f"The archive has no image for {', '.join(unknown)}.",
            Exit.NOT_FOUND,
            "image_missing",
            hint=f"qrosetta images load {directory}",
        )
    url = _busy_guard(ctx, engine, stack, "images load", "loading images now loads the host beside their timed windows")
    engine.env["TMPDIR"] = cache_tmp(ctx.env)
    loaded, failed = [], []
    with guard.engine_lock(ctx.env, "images load"), hostload.notice(ctx, url, "load", [e["service"] for e in entries]):
        for n, entry in enumerate(entries, 1):
            progress(f"{entry['service']} ({n}/{len(entries)}): {entry['file']}")
            try:
                loaded.append(_load_one(engine, stack, directory, entry))
            except CliError as exc:
                progress(f"  {exc.message}")
                failed.append({"id": entry["service"], "reason": exc.reason, "message": exc.message})
    data = {"directory": directory, "loaded": loaded, "failed": failed}
    if stack.release:
        from qrosetta_cli.stack import buildkit

        switched = buildkit.forget(ctx.env, stack.name, [e["id"] for e in loaded])
        if switched:
            progress(f"{', '.join(switched)}: the stack runs the loaded release images now, not the build-kit ones.")
    if loaded:
        result(
            f"Loaded {len(loaded)} images: {', '.join(e['id'] for e in loaded)}. `qrosetta images verify` "
            "checks them; `qrosetta start -d` starts them."
        )
    if failed:
        raise CliError(
            f"{len(failed)} of {len(entries)} images were not loaded: {', '.join(f['id'] for f in failed)}.",
            Exit.ENGINE,
            failed[0]["reason"],
            data=data,
            hint="qrosetta images verify",
        )
    return Result(0, data)
