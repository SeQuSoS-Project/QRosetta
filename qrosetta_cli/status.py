"""`qrosetta status`: services and their state, memory per running container, image and data disk use."""

from qrosetta_cli import actions
from qrosetta_cli import stack as st
from qrosetta_cli.actions import human_bytes, parse_size, say
from qrosetta_cli.serve import stack_url


def memory_by_container(engine, names):
    """Container name -> (bytes used, limit in bytes) from one `stats --no-stream` sample."""
    if not names:
        return {}
    out = engine.cli("stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}", *names)
    result = {}
    for line in out.stdout.splitlines():
        name, _, usage = line.partition("\t")
        used, _, limit = usage.partition("/")
        result[name.strip().lstrip("/")] = (parse_size(used), parse_size(limit))
    return result


def status(engine, stack):
    containers = st.find_containers(engine, stack)
    running = [c for c in containers if c.running]
    memory = memory_by_container(engine, [c.name for c in running])
    url = stack_url(engine, stack) if running else None

    if url:
        say(f"Quantum Rosetta is running at {url}")
    elif running:
        say("Quantum Rosetta is partly running (no published port).")
    elif containers:
        say(f"Quantum Rosetta is on standby: {len(containers)} containers stopped.")
    else:
        say("Quantum Rosetta is not created: no containers.")
    say(f"Project {stack.name} in {stack.project_dir}, engine {engine.name}\n")

    by_service = {}
    for c in containers:
        if c.project == stack.name or c.service not in by_service:
            by_service[c.service] = c
    rows = [("SERVICE", "STATE", "MEMORY", "LIMIT")]
    for service in stack.services:
        c = by_service.get(service)
        used, limit = memory.get(c.name, (None, None)) if c else (None, None)
        state = "running" if c and c.running else "stopped" if c else "not created"
        if c and c.project != stack.name:
            state += f" (project {c.project})"
        rows.append((service, state, human_bytes(used) if used is not None else "",
                     human_bytes(limit) if limit else ""))
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    for r in rows:
        say("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())

    total = sum(u for u, _ in memory.values() if u)
    if running:
        say(f"\nMemory in use: {human_bytes(total)} across {len(running)} running containers")

    refs = [stack.image_for(s) for s in stack.services]
    images = st.find_images(engine, refs)
    size = sum({img.id: img.size for img in images.values()}.values())
    say(f"Images: {len(images)} of {len(refs)} present, up to {human_bytes(size)} "
        "(layers shared between images counted once per image)")
    volumes = st.find_volumes(engine, stack)
    if volumes:
        sizes = actions.volume_sizes(engine)
        say("Data: " + ", ".join(f"{v.name} {human_bytes(sizes.get(v.name))}" for v in volumes))
    else:
        say("Data: none")
    return 0
