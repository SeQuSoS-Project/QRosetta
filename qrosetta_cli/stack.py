"""The Quantum Rosetta compose project: where it lives, its services, volumes and images."""

import json
import os
from dataclasses import dataclass, field

from qrosetta_cli.engine import CliError, compose_files


def find_project_dir(flag=None, env=None, checkout=None):
    """The directory holding the compose file: --project-dir, else QROSETTA_HOME, else the
    checkout the `qrosetta` script lives in."""
    env = os.environ if env is None else env
    for source, path in (("--project-dir", flag), ("QROSETTA_HOME", env.get("QROSETTA_HOME")),
                         ("this checkout", checkout)):
        if not path:
            continue
        path = os.path.abspath(os.path.expanduser(path))
        try:
            compose_files(path)
        except CliError:
            raise CliError(f"No compose file in {path} (from {source}).") from None
        return path
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
    volume_names: dict

    @property
    def volume_keys(self):
        return list(self.volume_names)

    def image_for(self, service):
        return self.services[service].image or f"{self.name}-{service}"

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
    """The compose configuration, refused unless compose reports the project qrosetta asked for."""
    out = engine.compose("config", "--format", "json", check=True)
    try:
        cfg = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise CliError(f"`{engine.name} compose config` did not return JSON: {exc}") from exc
    if cfg.get("name") != engine.project:
        raise CliError(f"Compose reports project {cfg.get('name')!r}, not {engine.project!r}; "
                       "nothing was done.")
    services = {}
    for name, svc in cfg.get("services", {}).items():
        deps = svc.get("depends_on") or {}
        services[name] = Service(
            name=name, container_name=svc.get("container_name") or "",
            image=svc.get("image") or "", ports=svc.get("ports") or [],
            depends_on=list(deps) if isinstance(deps, (dict, list)) else [])
    volumes = {key: (v or {}).get("name") or f"{cfg['name']}_{key}"
               for key, v in (cfg.get("volumes") or {}).items()}
    return Stack(name=cfg["name"], project_dir=engine.project_dir, services=services,
                 volume_names=volumes)


@dataclass
class Image:
    ref: str
    id: str
    size: int
    tags: list
    env: dict
    labels: dict


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
        config = item.get("Config") or {}
        env = dict(e.split("=", 1) for e in (config.get("Env") or []) if "=" in e)
        for ref in refs:
            if normalise_tag(ref) in normal:
                found[ref] = Image(ref=ref, id=item.get("Id", ""), size=int(item.get("Size") or 0),
                                   tags=tags, env=env, labels=config.get("Labels") or item.get("Labels") or {})
    return found
