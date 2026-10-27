"""A fake docker/podman engine and a fake Quantum Rosetta server for the qrosetta_cli tests: the
engine answers listing, inspect and destructive commands from an in-memory state and records
every call; the server answers /config, /runners and /compilers from dicts."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from qrosetta_cli import manifest as mf  # noqa: E402
from qrosetta_cli.client.transport import Response  # noqa: E402
from qrosetta_cli.stack import ownership as own  # noqa: E402
from qrosetta_cli.stack import project as st  # noqa: E402

PROJECT = "qr"


def _labels(key, kind, profiles=""):
    labels = {"org.qrosetta.project": PROJECT, "org.qrosetta.id": key, "org.qrosetta.kind": kind}
    return dict(labels, **({"org.qrosetta.profiles": profiles} if profiles else {}))


CONFIG = {
    "services": {
        "nginx": {"container_name": "nginx-reverse-proxy", "depends_on": {"api": {}},
                  "ports": [{"target": 80, "published": "8080"}], "labels": _labels("nginx", "core")},
        "api": {"container_name": "rosetta-api", "labels": _labels("api", "core")},
        "qiskit_runner": {"container_name": "qiskit-runner", "labels": _labels("qiskit", "runner", "minimal,cpu,full")},
        "braket_runner": {"container_name": "braket-runner", "labels": _labels("braket", "runner")},
    },
    "volumes": {"db": {"name": "qr_db"}},
}

RELEASE_DIGEST = "sha256:" + "ab" * 32
REGISTRY = "ghcr.io/sequsos-project"


def _release_service(sid, kind, compose_service, container, distributable=True, published=True):
    repository = f"{REGISTRY}/qrosetta-{container}" if distributable else None
    ref = f"{repository}@{RELEASE_DIGEST}" if distributable and published else None
    return {"kind": kind, "ids": [sid], "compose_service": compose_service, "infra_host": container,
            "distributable": distributable, "requires_gpu": False, "profiles": [], "sdk_versions": {},
            "repository": repository, "ref": ref,
            "compose": {"labels": {"org.qrosetta.project": "${QROSETTA_PROJECT:-qsimulators}",
                                   "org.qrosetta.id": sid, "org.qrosetta.kind": kind},
                        "container_name": container, "networks": ["isolated_net"]}}


def release_manifest(published=True):
    """A release manifest for the fake stack: nginx, api and qiskit published by digest, myqlm
    not distributable."""
    services = {
        "nginx": _release_service("nginx", "core", "nginx", "nginx-reverse-proxy", published=published),
        "api": _release_service("api", "core", "api", "rosetta-api", published=published),
        "qiskit": _release_service("qiskit", "runner", "qiskit_runner", "qiskit-runner", published=published),
        "myqlm": _release_service("myqlm", "runner", "myqlm_runner", "myqlm-runner", distributable=False),
    }
    services["api"]["compose"].update(volumes=["rosetta_db_data:/home/appuser/app/data"], secrets=["lifecycle_token"])
    return {"schema": mf.SCHEMA, "platform_version": "9.9.9", "git_sha": "abc123", "registry": REGISTRY,
            "images_published": published,
            "compose": {"name": "${QROSETTA_PROJECT:-qsimulators}",
                        "networks": {"isolated_net": {"internal": True}}, "volumes": {"rosetta_db_data": None},
                        "secrets": {"lifecycle_token": {
                            "file": "${QROSETTA_LIFECYCLE_TOKEN_PATH:-./infra/lifecycle-token.none}"}}},
            "services": services}


DESTRUCTIVE = {("stop",), ("kill",), ("rm",), ("rmi",), ("pod", "stop"), ("pod", "rm"), ("pod", "kill"),
               ("network", "rm"), ("volume", "rm"), ("container", "rm"), ("container", "stop"),
               ("image", "rm"), ("system", "prune"), ("network", "prune"), ("volume", "prune"),
               ("image", "prune"), ("container", "prune"), ("pod", "prune")}
INFO = {"version": {"Version": "5.8.2"}, "host": {"security": {"rootless": True}},
        "store": {"graphRoot": "/home/u/.local/share/containers/storage"}}


def ours(service=""):
    return {own.PROJECT_LABEL: PROJECT, own.QR_LABEL: PROJECT, own.SERVICE_LABEL: service}


def image_labels(service):
    return {own.QR_IMAGE_PROJECT: PROJECT, own.QR_SERVICE: service}


class FakeProcess:
    pid = None

    def __init__(self, code=0, err=""):
        self.code = code
        self.qr_tail = [err] if err else []

    def wait(self, timeout=None):
        return self.code

    def poll(self):
        return self.code


class FakeEngine:
    def __init__(self, engine="podman"):
        self.engine = engine
        self.calls = []
        self.containers = {}
        self.networks = {}
        self.volumes = {}
        self.images = {}
        self.pods = {}
        self.port = "127.0.0.1:8080"
        self.config_name = None
        self.extra_services = {}
        self.up_error = ""

    def add(self, name, labels, running=True, pod=""):
        cid = "c-" + name
        self.containers[cid] = {"Id": cid, "Name": name, "Pod": pod, "State": {"Running": running},
                                "Config": {"Labels": dict(labels)}}
        if pod:
            self.pods.setdefault(pod, {"Id": pod, "Name": "pod-" + pod, "InfraContainerID": "",
                                       "Containers": []})["Containers"].append({"Id": cid, "Name": name})
        return cid

    def add_network(self, name, labels):
        self.networks["n-" + name] = {"Id": "n-" + name, "Name": name, "Labels": dict(labels)}

    def add_volume(self, name, labels):
        self.volumes[name] = {"Name": name, "Labels": dict(labels)}

    def add_image(self, ident, tags, labels, size=100, sha="abc123", digests=()):
        self.images[ident] = {"Id": ident, "Size": size, "RepoTags": list(tags), "RepoDigests": list(digests),
                              "Config": {"Labels": dict(labels), "Env": [f"QROSETTA_IMAGE_GIT_SHA={sha}"]}}

    def standard(self):
        """This stack, owned: running API and nginx, its network, volume and images."""
        self.add("rosetta-api", ours("api"))
        self.add("nginx-reverse-proxy", ours("nginx"))
        self.add_network("qr_isolated_net", {own.PROJECT_LABEL: PROJECT, own.QR_LABEL: PROJECT})
        self.add_volume("qr_db", {own.PROJECT_LABEL: PROJECT, own.VOLUME_LABEL: "db"})
        self.add_image("i-nginx", ["localhost/qr-nginx:latest"], image_labels("nginx"))
        self.add_image("i-api", ["localhost/qr-api:latest"], image_labels("api"), size=700)
        self.add_image("i-qiskit", ["localhost/qr-qiskit_runner:latest"], image_labels("qiskit_runner"), size=900)
        return self

    def __call__(self, cmd, **kwargs):
        self.calls.append((list(cmd), dict(kwargs.get("env") or {})))
        out, rc = self._answer(list(cmd[1:]))
        return subprocess.CompletedProcess(cmd, rc, out, "" if rc == 0 else "error")

    def popen(self, cmd, **kwargs):
        """Popen stand-in: records the call, applies `up` to the state, exits as the engine would."""
        self.calls.append((list(cmd), dict(kwargs.get("env") or {})))
        args = list(cmd[1:])
        if args[0] == "compose" and "up" in args:
            if self.up_error:
                return FakeProcess(1, self.up_error)
            for service in args[args.index("up") + 1:]:
                if service.startswith("-"):
                    continue
                name = CONFIG["services"].get(service, {}).get("container_name") or service
                cid = "c-" + name
                if cid in self.containers:
                    self.containers[cid]["State"]["Running"] = True
                else:
                    self.add(name, ours(service))
        return FakeProcess()

    def _filters(self, args):
        return [args[i + 1] for i, a in enumerate(args) if a == "--filter"]

    def _answer(self, a):
        if a[0] == "compose":
            project = a[a.index("-p") + 1]
            j = 1
            while a[j] in ("-p", "-f", "--project-directory"):
                j += 2
            rest = a[j:]
            if rest[:1] == ["version"]:
                return "Docker Compose version v2.30.0\n", 0
            if rest[:1] == ["config"]:
                services = dict(CONFIG["services"], **self.extra_services)
                return json.dumps(dict(CONFIG, services=services, name=self.config_name or project)), 0
            if rest[:1] == ["port"]:
                return (self.port + "\n", 0) if self.port else ("", 1)
            return "", 0
        if a[:1] == ["info"]:
            return json.dumps(INFO), 0
        if a[:2] == ["ps", "-a"]:
            filters = self._filters(a)
            labels = [f[len("label="):] for f in filters if f.startswith("label=")]
            names = [f[len("name="):] for f in filters if f.startswith("name=")]
            hits = []
            for c in self.containers.values():
                cl = c["Config"]["Labels"]
                if any(cl.get(k) != v for k, v in (x.split("=", 1) for x in labels)):
                    continue
                if names and not any(n in c["Name"] for n in names):
                    continue
                hits.append(c["Id"])
            return "\n".join(hits), 0
        if a[:2] == ["container", "inspect"]:
            return json.dumps([c for c in self.containers.values() if c["Id"] in a[2:]]), 0
        if a[0] == "stop":
            for cid in a[1:]:
                self.containers[cid]["State"]["Running"] = False
            return "", 0
        if a[:2] == ["rm", "-f"]:
            for cid in a[2:]:
                self.containers.pop(cid, None)
                for pod in self.pods.values():
                    pod["Containers"] = [m for m in pod["Containers"] if m["Id"] != cid]
            return "", 0
        if a[:2] == ["network", "ls"]:
            k, v = self._filters(a)[0][len("label="):].split("=", 1)
            return "\n".join(n["Id"] for n in self.networks.values() if n["Labels"].get(k) == v), 0
        if a[:2] == ["network", "inspect"]:
            return json.dumps([n for n in self.networks.values() if n["Id"] in a[2:]]), 0
        if a[:2] == ["network", "rm"]:
            for n in a[2:]:
                self.networks.pop(n)
            return "", 0
        if a[:2] == ["volume", "inspect"]:
            found = [self.volumes[v] for v in a[2:] if v in self.volumes]
            return json.dumps(found), 0 if len(found) == len(a) - 2 else 125
        if a[:2] == ["volume", "rm"]:
            for v in a[2:]:
                self.volumes.pop(v)
            return "", 0
        if a[:2] == ["image", "inspect"]:
            items = [i for i in self.images.values()
                     if {st.normalise_tag(t) for t in i["RepoTags"]} & {st.normalise_tag(r) for r in a[2:]}
                     or set(i["RepoDigests"]) & set(a[2:])]
            return json.dumps(items), 0
        if a[0] == "rmi":
            for i in a[1:]:
                self.images.pop(i)
            return "", 0
        if a[:2] == ["pod", "inspect"]:
            return json.dumps([p for p in self.pods.values() if p["Id"] in a[2:]]), 0
        if a[:2] in (["pod", "stop"], ["pod", "rm"]):
            if a[1] == "rm":
                for p in a[2:]:
                    self.pods.pop(p)
            return "", 0
        if a[:2] == ["system", "df"]:
            return ("Local Volumes space usage:\n\nVOLUME NAME  LINKS  SIZE\nqr_db  1  34.48MB\n"
                    "other_db  0  81.92kB\n"), 0
        if a[0] == "stats":
            return "", 0
        return "", 0

    def commands(self, *verb):
        """Engine calls starting with `verb`, with their arguments after the verb sorted."""
        n = len(verb)
        return [[*c[1:1 + n], *sorted(c[1 + n:])] for c, _ in self.calls if c[1:1 + n] == list(verb)]

    def compose_calls(self, verb):
        return [c for c, _ in self.calls if c[1:2] == ["compose"] and verb in c]

    def destructive_calls(self):
        out = []
        for cmd, _ in self.calls:
            args = cmd[1:]
            if args and args[0] != "compose" and (tuple(args[:1]) in DESTRUCTIVE or tuple(args[:2]) in DESTRUCTIVE):
                out.append(args)
        return out


class FakeServer:
    """A Transport stand-in (and its factory) answering /config, /runners and /compilers."""

    kind = "http"

    def __init__(self, url="http://localhost:8080", gate=None, runners=None, compilers=None, block=None,
                 fresh=None, status=None):
        self.url = url
        self.gate = gate if gate is not None else {"enabled": True, "exclusive_running": False,
                                                    "exclusive_waiting": 0, "shared_running": 0}
        self.runners = runners if runners is not None else [{"id": "qiskit", "enabled": True, "available": True}]
        self.compilers = compilers if compilers is not None else []
        self.block = block
        self.fresh = fresh
        self.status = status or {}
        self.requests = []
        self.tokens = []

    def __call__(self, server, token=None, timeout=None):
        self.tokens.append(token)
        self.url = server.url
        return self

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        self.requests.append((method, path, query, body))
        if path in self.status:
            code, payload = self.status[path]
            return Response(code, {"content-type": "application/json"}, json.dumps(payload).encode())
        if path == "/config":
            data = {"limits": {}, "exclusive": self.gate}
            if self.block is not None:
                data["server"] = self.block
            return Response(200, {"content-type": "application/json"}, json.dumps(data).encode())
        if path in ("/runners", "/compilers"):
            entries = [dict(e) for e in (self.runners if path == "/runners" else self.compilers)]
            if query and query.get("fresh") and self.fresh is not None:
                if self.fresh == "unauthorised":
                    return Response(401, {}, b'{"detail": "Not authenticated"}')
                for e in entries:
                    e["fresh"] = True
            return Response(200, {"content-type": "application/json"}, json.dumps(entries).encode())
        return Response(404, {"content-type": "application/json"}, b'{"detail": "Not Found"}')


class Unreachable:
    """A transport factory whose server never answers."""

    def __call__(self, server, token=None, timeout=None):
        self.url = server.url
        return self

    def request(self, *args, **kwargs):
        from qrosetta_cli.errors import CliError, Exit
        raise CliError(f"No answer from {self.url}.", Exit.UNREACHABLE, "unreachable", hint="qrosetta status")
