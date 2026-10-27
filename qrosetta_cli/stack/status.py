"""`qrosetta status`: services, state, memory, image provenance and URL (spec §6.4); exits 0
whatever the stack's state. Provenance is that of the image each container was created from,
with the image now under the service's tag when that is another."""

from qrosetta_cli.errors import CliError
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import actions
from qrosetta_cli.stack import ownership as own
from qrosetta_cli.stack import project as st
from qrosetta_cli.stack.actions import human_bytes, parse_size
from qrosetta_cli.stack.serve import published


def memory_by_container(engine, names):
    """Container name -> (bytes used, limit in bytes) from one `stats --no-stream` sample."""
    if not names:
        return {}
    out = engine.cli("stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}", *names)
    found = {}
    for line in out.stdout.splitlines():
        name, _, usage = line.partition("\t")
        used, _, limit = usage.partition("/")
        found[name.strip().lstrip("/")] = (parse_size(used), parse_size(limit))
    return found


def image_record(engine, stack, service, images):
    """The image block of one service: state, ref, digest, image id, baked commit, release, for
    the image now under the service's tag."""
    ref = stack.image_for(service)
    img = images.get(ref)
    if img is None:
        return {"state": "missing", "ref": ref, "digest": None, "image_id": None, "git_sha": None, "release": None}
    return classify(stack, ref, img)


def classify(stack, ref, img):
    """Classification uses the baked commit or the release manifest's digest, never tags. In
    installed mode an image is `pulled` when it carries the digest the manifest names; otherwise
    an image with a baked commit is `built`, one without is `unknown`."""
    sha = img.git_sha
    if stack.release and "@" in ref and ref in img.digests:
        return {"state": "pulled", "ref": ref, "digest": ref.split("@", 1)[1], "image_id": img.id,
                "git_sha": sha, "release": stack.release.get("platform_version")}
    digest = next((d.split("@", 1)[1] for d in img.digests if "@" in d), None)
    state = "built" if sha != "unknown" else "unknown"
    return {"state": state, "ref": ref, "digest": digest, "image_id": img.id, "git_sha": sha, "release": None}


def container_image_record(stack, service, container, tagged, by_id):
    """The image block of the image the service's container was created from, plus `current`:
    whether it is the image now under the tag (None when the engine does not report the
    container's image). An image that no longer exists is `missing` with its id."""
    ref = stack.image_for(service)
    if not container.image:
        return {"state": "unknown", "ref": ref, "digest": None, "image_id": None, "git_sha": None, "release": None,
                "current": None}
    img = by_id.get(st.image_key(container.image))
    record = classify(stack, ref, img) if img else {
        "state": "missing", "ref": ref, "digest": None, "image_id": container.image, "git_sha": None,
        "release": None}
    record["current"] = bool(tagged["image_id"]) and st.image_key(tagged["image_id"]) == st.image_key(container.image)
    return record


def image_text(record):
    if record["state"] == "missing":
        return "missing"
    if record["state"] == "pulled":
        return f"pulled {record['release']} {record['digest'].split(':')[-1][:12]}"
    sha = record["git_sha"] or "unknown"
    if record["state"] == "built":
        return f"built from {sha}" + (" (source not identifiable)" if sha.endswith("-dirty") else "")
    ident = (record["digest"] or record["image_id"] or "").split(":")[-1][:12]
    return f"unknown {ident}".strip()


def row_image_text(row):
    """The image the container runs, and the one under the tag when that is another."""
    running, tagged = row.get("container_image"), row["image"]
    if not running or running["current"] is not False:
        return image_text(tagged)
    ran = (f"image {st.image_key(running['image_id'])[:12]} (removed)" if running["state"] == "missing"
           else image_text(running))
    if tagged["state"] == "missing":
        return f"{ran}; no image under its tag"
    return f"{ran}; newer image {image_text(tagged)}"


def collect(engine, stack, found):
    containers = {c.service: c for c in found.containers + found.legacy}
    running = [c for c in containers.values() if c.running]
    memory = memory_by_container(engine, [c.name for c in running])
    images = st.find_images(engine, [stack.image_for(s) for s in stack.services])
    by_id = st.images_by_id(engine, [c.image for c in containers.values()])
    rows = []
    for service, svc in stack.services.items():
        c = containers.get(service)
        used, limit = memory.get(c.name, (None, None)) if c else (None, None)
        state = "running" if c and c.running else "stopped" if c else "not created"
        tagged = image_record(engine, stack, service, images)
        rows.append({"id": svc.id, "backend": None, "version": None, "kind": stack.kind_of(service),
                     "compose_service": service, "container": c.name if c else svc.container_name or None,
                     "state": state, "qrosetta_label": c is None or c not in found.legacy,
                     "memory_bytes": used, "limit_bytes": limit, "image": tagged,
                     "container_image": container_image_record(stack, service, c, tagged, by_id) if c else None})
    return rows, images, memory


def status(ctx, engine, stack, mode):
    found = own.scan(engine, stack)
    rows, images, memory = collect(engine, stack, found)
    running = [r for r in rows if r["state"] == "running"]
    url, address = published(engine, stack) if running else (None, None)
    block = None
    if url:
        from qrosetta_cli.client import handshake, servers
        try:
            server = servers.Server("local", url, "compose port")
            block = handshake.server_block(handshake.fetch_config(ctx.transport(server=server, timeout=5)))
            ctx._server = server
            ctx.note_handshake(block)
        except CliError:
            block = None
        result(f"Quantum Rosetta is running at {url} ({_server_text(block)})")
    elif rows and any(r["state"] == "stopped" for r in rows):
        result(f"Quantum Rosetta is on standby: {sum(r['state'] == 'stopped' for r in rows)} containers stopped.")
    else:
        result("Quantum Rosetta is not created: no containers.")
    result(f"Project {stack.name}, engine {engine.describe()}, {mode.name} mode ({stack.project_dir})\n")

    table = [("SERVICE", "KIND", "STATE", "MEMORY", "LIMIT", "IMAGE")]
    for r in rows:
        state = r["state"] + ("" if r["qrosetta_label"] else " (no qrosetta label)")
        table.append((r["id"], r["kind"], state,
                      human_bytes(r["memory_bytes"]) if r["memory_bytes"] is not None else "",
                      human_bytes(r["limit_bytes"]) if r["limit_bytes"] else "", row_image_text(r)))
    widths = [max(len(row[i]) for row in table) for i in range(len(table[0]))]
    for row in table:
        result("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())

    outdated = [r for r in rows if r["qrosetta_label"] and r["container_image"]
                and r["container_image"]["current"] is False and r["image"]["state"] != "missing"]
    if outdated:
        command = f"`qrosetta start -d {' '.join(r['id'] for r in outdated)}`"
        result("\n1 container was created from an image other than the one now under its tag; "
               f"{command} recreates it on that image." if len(outdated) == 1 else
               f"\n{len(outdated)} containers were created from images other than the ones now under their tags; "
               f"{command} recreates them on those images.")
    for line in own.leftovers(engine, found):
        progress("\n" + line)
    total = sum(u for u, _ in memory.values() if u)
    if running:
        result(f"\nMemory in use: {human_bytes(total)} across {len(running)} running containers")
    size = sum({img.id: img.size for img in images.values()}.values())
    removable = len(own.image_scan(engine, stack)[0])
    result(f"Images: {len(images)} of {len(stack.services)} present, up to {human_bytes(size)} "
           "(layers shared between images counted once per image); "
           f"{removable} removable by `qrosetta remove --images`")
    volumes = found.volumes
    sizes = actions.volume_sizes(engine) if volumes else {}
    result("Data: " + (", ".join(f"{v.name} {human_bytes(sizes.get(v.name))}" for v in volumes) if volumes else "none"))
    return {"url": url, "published": address, "project": stack.name, "project_dir": stack.project_dir,
            "mode": mode.name, "engine": {"name": engine.name, "version": engine.version or None,
                                          "rootless": engine.rootless if engine.info else None},
            "server": block, "services": rows,
            "data_volumes": [{"name": v.name, "bytes": sizes.get(v.name)} for v in volumes],
            "foreign": own.leftovers(engine, found)}


def _server_text(block):
    from qrosetta_cli.client import handshake
    return handshake.describe(block)
