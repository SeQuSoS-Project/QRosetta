"""What qrosetta may act on, and `act`, the only function that runs a destructive engine command.

A container or network is this stack's when it carries this compose project's label and the
qrosetta label (org.qrosetta.project) for the same project. An image is when it carries
org.qrosetta.image.project and org.qrosetta.service for the service it is named after, and no
other tag. A volume is when it has the name compose gives it and the compose project and volume
labels: compose asks to recreate (and empty) a volume whose labels change, so the qrosetta label
is not added to volumes. Pods are this stack's when every container in them is. Everything else
is reported with the command that would remove it, and never touched."""

import json
from dataclasses import dataclass, field

from qrosetta_cli.stack import project as st

PROJECT_LABEL = "com.docker.compose.project"
SERVICE_LABEL = "com.docker.compose.service"
VOLUME_LABEL = "com.docker.compose.volume"
QR_LABEL = "org.qrosetta.project"
QR_IMAGE_PROJECT = "org.qrosetta.image.project"
QR_SERVICE = "org.qrosetta.service"
ACTIVE_STATES = ("running", "stopping", "paused", "restarting")

_TOKEN = object()


@dataclass(frozen=True)
class Target:
    """An object the ownership checks accepted; only this module creates them."""
    kind: str
    id: str
    name: str
    size: int = 0
    token: object = field(default=None, repr=False, compare=False)


def _target(kind, ident, name, size=0):
    return Target(kind, ident, name, size, _TOKEN)


COMMANDS = {
    ("container", "stop"): ["stop"],
    ("container", "remove"): ["rm", "-f"],
    ("pod", "stop"): ["pod", "stop"],
    ("pod", "remove"): ["pod", "rm"],
    ("network", "remove"): ["network", "rm"],
    ("volume", "remove"): ["volume", "rm"],
    ("image", "remove"): ["rmi"],
}


def act(engine, kind, action, targets):
    """Run one destructive command on targets from the ownership scan, by ID."""
    targets = list(targets)
    if not targets:
        return None
    for t in targets:
        if not isinstance(t, Target) or t.token is not _TOKEN or t.kind != kind:
            raise RuntimeError(f"refusing to {action} {t!r}: not from the ownership scan")
    return engine.cli(*COMMANDS[(kind, action)], *[t.id for t in targets])


@dataclass
class Container:
    id: str
    name: str
    project: str
    service: str
    running: bool
    pod: str = ""
    target: Target = None


@dataclass
class Scan:
    containers: list = field(default_factory=list)
    legacy: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    networks: list = field(default_factory=list)
    legacy_networks: list = field(default_factory=list)
    volumes: list = field(default_factory=list)
    foreign_volumes: list = field(default_factory=list)
    pods: list = field(default_factory=list)
    shared_pods: list = field(default_factory=list)

    def running(self):
        return [c for c in self.containers + self.legacy if c.running]


def _json(out):
    try:
        data = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else [data]


def _inspect(engine, kind, ids):
    return _json(engine.cli(kind, "inspect", *ids)) if ids else []


def _get(item, key):
    return item.get(key, item.get(key.lower()))


def _containers(engine, ids):
    result = []
    for item in _inspect(engine, "container", sorted(set(ids))):
        labels = (item.get("Config") or {}).get("Labels") or {}
        state = item.get("State") or {}
        result.append((item, labels, Container(
            id=item.get("Id", ""), name=(item.get("Name") or "").lstrip("/"),
            project=labels.get(PROJECT_LABEL, ""), service=labels.get(SERVICE_LABEL, ""),
            running=bool(state.get("Running")) or state.get("Status") in ACTIVE_STATES,
            pod=item.get("Pod") or "")))
    return result


def scan(engine, stack):
    p = stack.name
    s = Scan()
    ids = engine.cli("ps", "-a", "-q", "--filter", f"label={PROJECT_LABEL}={p}").stdout.split()
    for _, labels, c in _containers(engine, ids):
        if c.project != p:
            continue
        if labels.get(QR_LABEL) == p:
            c.target = _target("container", c.id, c.name)
            s.containers.append(c)
        else:
            s.legacy.append(c)

    names = {svc.container_name for svc in stack.services.values() if svc.container_name}
    if names:
        filters = [x for n in sorted(names) for x in ("--filter", f"name={n}")]
        ids = engine.cli("ps", "-a", "-q", *filters).stdout.split()
        s.conflicts = [c for _, _, c in _containers(engine, ids) if c.name in names and c.project != p]

    net_ids = engine.cli("network", "ls", "-q", "--filter", f"label={PROJECT_LABEL}={p}").stdout.split()
    for item in _inspect(engine, "network", net_ids):
        labels = _get(item, "Labels") or {}
        name = _get(item, "Name") or ""
        if labels.get(PROJECT_LABEL) != p:
            continue
        if labels.get(QR_LABEL) == p:
            s.networks.append(_target("network", _get(item, "Id") or name, name))
        else:
            s.legacy_networks.append(name)

    wanted = {name: key for key, name in stack.volume_names.items()}
    for item in _inspect(engine, "volume", sorted(wanted)):
        name = _get(item, "Name") or ""
        labels = _get(item, "Labels") or {}
        if name in wanted and labels.get(PROJECT_LABEL) == p and labels.get(VOLUME_LABEL) == wanted[name]:
            s.volumes.append(_target("volume", name, name))
        elif name:
            s.foreign_volumes.append(name)

    pod_ids = sorted({c.pod for c in s.containers + s.legacy if c.pod})
    if engine.name == "podman" and pod_ids:
        ours = {c.id for c in s.containers}
        for item in _inspect(engine, "pod", pod_ids):
            infra = _get(item, "InfraContainerID") or ""
            members = [(m.get("Id", ""), m.get("Name", "")) for m in (_get(item, "Containers") or [])]
            others = [n or i for i, n in members if i != infra and i not in ours]
            name = _get(item, "Name") or _get(item, "Id")
            if others:
                s.shared_pods.append((name, others))
            else:
                s.pods.append(_target("pod", _get(item, "Id") or name, name))
    for group in (s.containers, s.legacy, s.conflicts):
        group.sort(key=lambda c: c.name)
    return s


def image_scan(engine, stack):
    """(images qrosetta may remove, [(ref, reason, built here)] for the rest), from the images
    named after the stack's services. `built here` is False for an `image:` set in a compose file
    (a public image, for example), which the user is never told to remove."""
    refs = {stack.image_for(svc): svc for svc in stack.services}
    owned, refused, seen = [], [], set()
    for ref, img in st.find_images(engine, list(refs)).items():
        service = refs[ref]
        built = ref == f"{stack.name}-{service}"
        other = [t for t in img.tags if st.normalise_tag(t) != st.normalise_tag(ref)]
        if img.labels.get(QR_IMAGE_PROJECT) != stack.name or img.labels.get(QR_SERVICE) != service:
            refused.append((ref, "has no qrosetta label for this service", built))
        elif other:
            refused.append((ref, f"is also tagged {', '.join(other)}", built))
        elif img.id not in seen:
            seen.add(img.id)
            owned.append(_target("image", img.id, ref, img.size))
    return owned, refused


def blockers(engine, s):
    """Lines naming what `start` would collide with and how to remove it."""
    lines = []
    if s.conflicts:
        held = ", ".join(f"{c.name} ({'project ' + c.project if c.project else 'no compose project'}, "
                         f"{'running' if c.running else 'stopped'})" for c in s.conflicts)
        lines.append(f"Containers of another project use this stack's container names: {held}. "
                     f"To remove them (this stops any that run): {engine.name} rm -f "
                     + " ".join(c.name for c in s.conflicts))
    if s.legacy:
        lines.append(f"Containers labelled with compose project {s.legacy[0].project} but without the "
                     f"qrosetta label (made by an older script or by hand): "
                     f"{', '.join(c.name for c in s.legacy)}. To remove them (this stops any that "
                     f"run; images and data stay): {engine.name} rm -f " + " ".join(c.name for c in s.legacy))
    if s.legacy_networks:
        lines.append(f"Networks without the qrosetta label: {', '.join(s.legacy_networks)}. "
                     f"To remove them once their containers are gone: {engine.name} network rm "
                     + " ".join(s.legacy_networks))
    if s.foreign_volumes:
        lines.append(f"Volumes with this stack's volume names that compose did not create for this "
                     f"project: {', '.join(s.foreign_volumes)}. qrosetta does not use or remove them.")
    return lines


def leftovers(engine, s, shared_pods=()):
    """Lines naming what qrosetta left alone after stop or remove; `shared_pods` adds pods found
    before the command, which a removal of this stack's containers hides from a later scan."""
    lines = blockers(engine, s)
    for name, others in list(shared_pods) + [p for p in s.shared_pods if p not in shared_pods]:
        lines.append(f"Pod {name} also holds containers that are not this stack's ({', '.join(others)}); "
                     "left alone.")
    return ["qrosetta leaves these alone. " + lines[0]] + lines[1:] if lines else []
