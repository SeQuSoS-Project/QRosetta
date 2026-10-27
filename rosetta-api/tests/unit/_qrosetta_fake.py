"""A fake docker/podman engine for the qrosetta_cli tests: answers the listing, inspect and
destructive commands from an in-memory state and records every call."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from qrosetta_cli import ownership as own  # noqa: E402
from qrosetta_cli import stack as st  # noqa: E402

PROJECT = "qr"
CONFIG = {
    "services": {
        "nginx": {"container_name": "nginx-reverse-proxy", "depends_on": {"api": {}},
                  "ports": [{"target": 80, "published": "8080"}]},
        "api": {"container_name": "rosetta-api"},
        "qiskit_runner": {"container_name": "qiskit-runner"},
        "braket_runner": {"container_name": "braket-runner"},
    },
    "volumes": {"db": {"name": "qr_db"}},
}
DESTRUCTIVE = {("stop",), ("kill",), ("rm",), ("rmi",), ("pod", "stop"), ("pod", "rm"), ("pod", "kill"),
               ("network", "rm"), ("volume", "rm"), ("container", "rm"), ("container", "stop"),
               ("image", "rm"), ("system", "prune"), ("network", "prune"), ("volume", "prune"),
               ("image", "prune"), ("container", "prune"), ("pod", "prune")}


def ours(service=""):
    return {own.PROJECT_LABEL: PROJECT, own.QR_LABEL: PROJECT, own.SERVICE_LABEL: service}


def image_labels(service):
    return {own.QR_IMAGE_PROJECT: PROJECT, own.QR_SERVICE: service}


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

    def add_image(self, ident, tags, labels, size=100, sha="abc123"):
        self.images[ident] = {"Id": ident, "Size": size, "RepoTags": list(tags),
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
                     if {st.normalise_tag(t) for t in i["RepoTags"]} & {st.normalise_tag(r) for r in a[2:]}]
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

    def destructive_calls(self):
        out = []
        for cmd, _ in self.calls:
            args = cmd[1:]
            if args and args[0] != "compose" and (tuple(args[:1]) in DESTRUCTIVE or tuple(args[:2]) in DESTRUCTIVE):
                out.append(args)
        return out
