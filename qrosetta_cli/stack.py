"""The Quantum Rosetta compose project: where it lives, its services, and what exists on the
engine (containers, pods, networks, volumes, images) that belongs to it."""

import json
import os
from dataclasses import dataclass, field

from qrosetta_cli.engine import CliError

COMPOSE_FILES = ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml")
PROJECT_LABEL = "com.docker.compose.project"
SERVICE_LABEL = "com.docker.compose.service"
VOLUME_LABEL = "com.docker.compose.volume"
ACTIVE_STATES = ("running", "stopping", "paused", "restarting")


def find_project_dir(flag=None, env=None, checkout=None):
    """The directory holding the compose file: --project-dir, else QROSETTA_HOME, else the
    checkout the `qrosetta` script lives in."""
    env = os.environ if env is None else env
    for source, path in (("--project-dir", flag), ("QROSETTA_HOME", env.get("QROSETTA_HOME")),
                         ("this checkout", checkout)):
        if not path:
            continue
        path = os.path.abspath(os.path.expanduser(path))
        if any(os.path.isfile(os.path.join(path, name)) for name in COMPOSE_FILES):
            return path
        raise CliError(f"No compose file in {path} (from {source}).")
    raise CliError("Cannot find the Quantum Rosetta directory: pass --project-dir or set QROSETTA_HOME.")


@dataclass
class Service:
    name: str
    container_name: str
    image: str
    ports: list = field(default_factory=list)
    depends_on: list = field(default_factory=list)


@dataclass
class Stack:
    name: str
    project_dir: str
    services: dict
    volume_keys: list

    def image_for(self, service, project=None):
        svc = self.services[service]
        if svc.image and project in (None, self.name):
            return svc.image
        return f"{project or self.name}-{service}"

    def core_services(self):
        """Services that publish a port, plus everything they depend on."""
        core = [s for s, svc in self.services.items() if svc.ports]
        i = 0
        while i < len(core):
            for dep in self.services[core[i]].depends_on:
                if dep not in core:
                    core.append(dep)
            i += 1
        return core

    def resolve_service(self, name):
        """A compose service name, or the container name of one."""
        if name in self.services:
            return name
        for svc in self.services.values():
            if svc.container_name == name:
                return svc.name
        raise CliError(f"Unknown service {name!r}. Services: {', '.join(self.services)}.")


def load_stack(engine):
    out = engine.compose("config", "--format", "json", check=True)
    try:
        cfg = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise CliError(f"`{engine.name} compose config` did not return JSON: {exc}") from exc
    services = {}
    for name, svc in cfg.get("services", {}).items():
        deps = svc.get("depends_on") or {}
        services[name] = Service(
            name=name, container_name=svc.get("container_name") or "",
            image=svc.get("image") or "", ports=svc.get("ports") or [],
            depends_on=list(deps) if isinstance(deps, (dict, list)) else [])
    return Stack(name=cfg["name"], project_dir=engine.project_dir, services=services,
                 volume_keys=list(cfg.get("volumes") or {}))


@dataclass
class Container:
    id: str
    name: str
    project: str
    service: str
    running: bool
    pod: str = ""


def _inspect(engine, kind, ids):
    if not ids:
        return []
    out = engine.cli(kind, "inspect", *ids)
    try:
        return json.loads(out.stdout or "[]") or []
    except json.JSONDecodeError:
        return []


def find_containers(engine, stack):
    """Containers of this compose project, and of any other project whose containers use this
    stack's container names (stacks started from another checkout or an older script)."""
    ids = engine.cli("ps", "-a", "-q", "--filter", f"label={PROJECT_LABEL}").stdout.split()
    found = []
    by_name = {svc.container_name: svc.name for svc in stack.services.values() if svc.container_name}
    for item in _inspect(engine, "container", ids):
        labels = (item.get("Config") or {}).get("Labels") or {}
        name = (item.get("Name") or "").lstrip("/")
        project = labels.get(PROJECT_LABEL, "")
        service = labels.get(SERVICE_LABEL, "")
        if project != stack.name and by_name.get(name) != service:
            continue
        state = item.get("State") or {}
        running = bool(state.get("Running")) or state.get("Status") in ACTIVE_STATES
        found.append(Container(id=item.get("Id", ""), name=name, project=project, service=service,
                               running=running, pod=item.get("Pod") or ""))
    return sorted(found, key=lambda c: (c.project != stack.name, c.project, c.name))


def projects_of(stack, containers):
    return sorted({stack.name} | {c.project for c in containers},
                  key=lambda p: (p != stack.name, p))


def find_pods(engine, projects, containers):
    """Podman pods holding the stack (podman-compose creates `pod_<project>`)."""
    if engine.name != "podman":
        return []
    pods = {c.pod for c in containers if c.pod}
    for project in projects:
        pods.update(engine.cli("pod", "ps", "-q", "--filter", f"name=^pod_{project}$").stdout.split())
    return sorted(pods)


def find_networks(engine, projects):
    nets = []
    for project in projects:
        out = engine.cli("network", "ls", "--filter", f"label={PROJECT_LABEL}={project}",
                         "--format", "{{.Name}}")
        nets += [n for n in out.stdout.split() if n not in nets]
    return nets


@dataclass
class Volume:
    name: str
    project: str
    key: str


def find_volumes(engine, stack):
    """Named volumes created for this stack's volume keys by any compose project."""
    vols = []
    for key in stack.volume_keys:
        names = engine.cli("volume", "ls", "-q", "--filter", f"label={VOLUME_LABEL}={key}").stdout.split()
        for item in _inspect(engine, "volume", names):
            labels = item.get("Labels") or {}
            vols.append(Volume(name=item.get("Name", ""), project=labels.get(PROJECT_LABEL, ""), key=key))
    return vols


@dataclass
class Image:
    ref: str
    id: str
    size: int
    tags: list
    env: dict


def normalise_tag(tag):
    for prefix in ("localhost/", "docker.io/library/"):
        if tag.startswith(prefix):
            tag = tag[len(prefix):]
    return tag if ":" in tag.rsplit("/", 1)[-1] else tag + ":latest"


def find_images(engine, refs):
    """The images among `refs` that exist, keyed by ref."""
    if not refs:
        return {}
    out = engine.cli("image", "inspect", *refs)
    try:
        items = json.loads(out.stdout or "[]") or []
    except json.JSONDecodeError:
        items = []
    found = {}
    for item in items:
        tags = item.get("RepoTags") or []
        normal = {normalise_tag(t) for t in tags}
        env = dict(e.split("=", 1) for e in ((item.get("Config") or {}).get("Env") or []) if "=" in e)
        for ref in refs:
            if normalise_tag(ref) in normal:
                found[ref] = Image(ref=ref, id=item.get("Id", ""), size=int(item.get("Size") or 0),
                                   tags=tags, env=env)
    return found
