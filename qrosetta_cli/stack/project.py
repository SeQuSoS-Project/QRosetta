"""The Quantum Rosetta compose project: its services (keyed by org.qrosetta.id), profiles,
volumes and images."""

import difflib
import json
from dataclasses import dataclass, field

from qrosetta_cli.errors import CliError, Exit, usage

ID_LABEL = "org.qrosetta.id"
KIND_LABEL = "org.qrosetta.kind"
PROFILES_LABEL = "org.qrosetta.profiles"
KINDS = ("core", "runner", "compiler")


@dataclass
class Service:
    name: str
    container_name: str
    image: str
    ports: list = field(default_factory=list)
    depends_on: list = field(default_factory=list)
    labels: dict = field(default_factory=dict)

    @property
    def id(self):
        """The service key (S15 org.qrosetta.id), else the compose service name."""
        return self.labels.get(ID_LABEL) or self.name

    @property
    def kind(self):
        return self.labels.get(KIND_LABEL) or "unknown"

    @property
    def profiles(self):
        return [p for p in (self.labels.get(PROFILES_LABEL) or "").split(",") if p]


@dataclass
class Stack:
    name: str
    project_dir: str
    services: dict
    volume_names: dict
    release: dict = None

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

    def by_id(self):
        return {svc.id: svc for svc in self.services.values()}

    def kind_of(self, service):
        svc = self.services[service]
        if svc.kind != "unknown":
            return svc.kind
        return "core" if service in self.core_services() else "unknown"

    def resolve_service(self, name):
        """The compose service for a service key (org.qrosetta.id); compose service names and
        container names are accepted as aliases."""
        for svc in self.services.values():
            if svc.id == name:
                return svc.name
        if name in self.services:
            return name
        for svc in self.services.values():
            if svc.container_name == name:
                return svc.name
        keys = sorted(self.by_id())
        close = difflib.get_close_matches(name, keys + list(self.services), n=1)
        hint = f"did you mean {close[0]}?" if close else "qrosetta status lists the services"
        raise usage(f"Unknown service {name!r}. Services: {', '.join(keys)}.", hint=hint, reason="unknown_service")


def load_stack(engine):
    """The compose configuration, refused unless compose reports the project qrosetta asked for."""
    out = engine.compose("config", "--format", "json", check=True)
    try:
        cfg = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise CliError(f"`{engine.name} compose config` did not return JSON: {exc}", Exit.ENGINE,
                       "compose_config", hint="qrosetta doctor") from exc
    if cfg.get("name") != engine.project:
        raise CliError(f"Compose reports project {cfg.get('name')!r}, not {engine.project!r}; "
                       "nothing was done.", Exit.ENGINE, "project_mismatch",
                       hint=f"set name: ${{QROSETTA_PROJECT:-qsimulators}} in {engine.files[0]}")
    services = {}
    for name, svc in cfg.get("services", {}).items():
        deps = svc.get("depends_on") or {}
        services[name] = Service(
            name=name, container_name=svc.get("container_name") or "",
            image=svc.get("image") or "", ports=svc.get("ports") or [],
            depends_on=list(deps) if isinstance(deps, (dict, list)) else [],
            labels=_labels(svc.get("labels")))
    volumes = {key: (v or {}).get("name") or f"{cfg['name']}_{key}"
               for key, v in (cfg.get("volumes") or {}).items()}
    return Stack(name=cfg["name"], project_dir=engine.project_dir, services=services,
                 volume_names=volumes)


def _labels(raw):
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return dict(str(item).split("=", 1) for item in raw if "=" in str(item))
    return {}


def profile_members(stack, name):
    """Compose services whose org.qrosetta.profiles label lists `name`."""
    return [s for s, svc in stack.services.items() if name in svc.profiles]


@dataclass
class Image:
    ref: str
    id: str
    size: int
    tags: list
    env: dict
    labels: dict
    digests: list = field(default_factory=list)

    @property
    def git_sha(self):
        return self.env.get("QROSETTA_IMAGE_GIT_SHA") or "unknown"


def normalise_tag(tag):
    for prefix in ("localhost/", "docker.io/library/"):
        if tag.startswith(prefix):
            tag = tag[len(prefix):]
    return tag if ":" in tag.rsplit("/", 1)[-1] else tag + ":latest"


def image_key(ident):
    """An image ID without the `sha256:` prefix docker writes and podman leaves out."""
    return (ident or "").split(":", 1)[-1] if (ident or "").startswith("sha256:") else (ident or "")


def _image(ref, item):
    config = item.get("Config") or {}
    env = dict(e.split("=", 1) for e in (config.get("Env") or []) if "=" in e)
    return Image(ref=ref, id=item.get("Id", ""), size=int(item.get("Size") or 0), tags=item.get("RepoTags") or [],
                 env=env, labels=config.get("Labels") or item.get("Labels") or {},
                 digests=item.get("RepoDigests") or [])


def _inspect_images(engine, refs):
    out = engine.cli("image", "inspect", *refs)
    try:
        return json.loads(out.stdout or "[]") or []
    except json.JSONDecodeError:
        return []


def images_by_id(engine, ids):
    """The images among `ids` that exist, keyed by `image_key` of their ID."""
    ids = sorted({i for i in ids if i})
    keys = {image_key(i) for i in ids}
    return {image_key(item.get("Id")): _image(item.get("Id", ""), item)
            for item in (_inspect_images(engine, ids) if ids else []) if image_key(item.get("Id")) in keys}


def find_images(engine, refs):
    """The images among `refs` that exist, keyed by ref; a ref by digest matches the image's
    repo digests, any other ref its tags."""
    if not refs:
        return {}
    found = {}
    for item in _inspect_images(engine, refs):
        normal = {normalise_tag(t) for t in item.get("RepoTags") or []}
        digests = set(item.get("RepoDigests") or [])
        for ref in refs:
            if (ref in digests) if "@" in ref else (normalise_tag(ref) in normal):
                found[ref] = _image(ref, item)
    return found
