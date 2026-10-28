"""Candidate image files for a requalification: the Dockerfile with a new Python base, the apt
snapshot and hash-checked pip installs; a wheel check of the current lock against the new Python
on PyPI; the lock regenerated inside the new base by scripts/release/compile_lock.sh; and the
list of pins that moved. Stdlib only."""

import json
import re
import subprocess
import urllib.request
from pathlib import Path

from registry import REPO

SNAPSHOT_FILE = REPO / "release" / "debian-snapshot.conf"

SNAPSHOT_BLOCK = r'''

# apt reads the Debian archive as of DEBIAN_SNAPSHOT (default from release/debian-snapshot.conf).
ARG DEBIAN_SNAPSHOT={snapshot}
RUN sed -i \
      -e "s|^URIs: http://deb.debian.org/debian\$|URIs: https://snapshot.debian.org/archive/debian/${{DEBIAN_SNAPSHOT}}|" \
      -e "s|^URIs: http://deb.debian.org/debian-security\$|URIs: https://snapshot.debian.org/archive/debian-security/${{DEBIAN_SNAPSHOT}}|" \
      -e "s|^Signed-By:|Check-Valid-Until: no\nSigned-By:|" \
      /etc/apt/sources.list.d/debian.sources && \
    test "$(grep -c "^URIs: https://snapshot.debian.org/archive/debian[a-z-]*/${{DEBIAN_SNAPSHOT}}\$" /etc/apt/sources.list.d/debian.sources)" = 2
'''

_FROM = re.compile(r"^FROM([ \t]+--platform=\S+)?[ \t]+(python:\S+)((?:[ \t]+AS[ \t]+\S+)?)[ \t]*$", re.I | re.M)
_LOCK_INSTALL = re.compile(r"pip install((?:\s+--?[\w-]+(?:=\S+)?)*)\s+-r\s+requirements\.lock")
_SHARED_INSTALL = re.compile(r"^RUN pip install /tmp/shared-src(?:[ \t]*&&[ \t]*rm -rf /tmp/shared-src)?[ \t]*$", re.M)
_SHARED_REPLACEMENT = ("RUN pip install --no-cache-dir --no-deps --no-build-isolation --no-index /tmp/shared-src && \\\n"
                       "    rm -rf /tmp/shared-src")
_PIP = re.compile(r"pip3?\s+install\b[^\n&;|]*")


def snapshot_default():
    for line in SNAPSHOT_FILE.read_text().splitlines():
        if line.startswith("DEBIAN_SNAPSHOT="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"no DEBIAN_SNAPSHOT in {SNAPSHOT_FILE}")


def python_bases(dockerfile_text):
    return [m.group(2) for m in _FROM.finditer(dockerfile_text)]


def python_of_tag(image):
    match = re.match(r"python:(\d+)\.(\d+)", image)
    return (int(match.group(1)), int(match.group(2))) if match else None


def rewrite_dockerfile(text, new_base, snapshot):
    """(new text, changes, manual): every python FROM moved to ``new_base`` and followed by the
    apt snapshot block, the lock installed with --require-hashes, shared/ installed offline
    without dependencies. ``manual`` lists pip installs the rules do not cover."""
    changes, manual = [], []

    def _from(match):
        changes.append(f"FROM {match.group(2)} -> {new_base}{match.group(3)}")
        line = f"FROM{match.group(1) or ''} {new_base}{match.group(3)}"
        return line + SNAPSHOT_BLOCK.format(snapshot=snapshot).rstrip("\n")

    if "DEBIAN_SNAPSHOT" in text:
        raise ValueError("Dockerfile already declares DEBIAN_SNAPSHOT; edit the candidate by hand")
    text = _FROM.sub(_from, text)

    def _lock(match):
        if "--require-hashes" in match.group(1):
            return match.group(0)
        changes.append("pip install -r requirements.lock: --require-hashes added")
        return f"pip install{match.group(1)} --require-hashes -r requirements.lock"

    text = _LOCK_INSTALL.sub(_lock, text)
    text, n = _SHARED_INSTALL.subn(_SHARED_REPLACEMENT, text)
    if n:
        changes.append("shared/ installed with --no-deps --no-build-isolation --no-index, source removed")
    for line in text.splitlines():
        for cmd in _PIP.findall(line):
            args = cmd.split()
            if "--require-hashes" not in args and not {"--no-deps", "--no-index"} <= set(args):
                manual.append(cmd.strip())
    return text, changes, manual


def parse_lock(text):
    """{normalised name: (name, version)} of the ``name==version`` lines of a lock."""
    pins = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip().rstrip("\\").strip()
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==(\S+)$", line)
        if match:
            pins[normalise(match.group(1))] = (match.group(1), match.group(2))
    return pins


def normalise(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def wheel_fits(filename, python, glibc=(2, 41), machine="x86_64"):
    """Whether a wheel installs on CPython ``python`` (major, minor) on manylinux ``glibc``."""
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return False
    py_tags, abi_tags, plat_tags = (p.split(".") for p in parts[-3:])
    cp = f"cp{python[0]}{python[1]}"
    plat_ok = False
    for plat in plat_tags:
        if plat == "any":
            plat_ok = True
        match = re.match(rf"manylinux_(\d+)_(\d+)_{machine}$", plat)
        if match and (int(match.group(1)), int(match.group(2))) <= glibc:
            plat_ok = True
        legacy = {"manylinux1": (2, 5), "manylinux2010": (2, 12), "manylinux2014": (2, 17)}
        for name, version in legacy.items():
            if plat == f"{name}_{machine}" and version <= glibc:
                plat_ok = True
    if not plat_ok:
        return False
    for py in py_tags:
        for abi in abi_tags:
            if py == cp and abi in (cp, "none", "abi3"):
                return True
            if abi == "abi3" and re.fullmatch(r"cp3\d+", py) and int(py[3:]) <= python[1]:
                return True
            if abi == "none" and re.fullmatch(r"py3\d*", py) and (py == "py3" or int(py[3:]) <= python[1]):
                return True
    return False


class PyPI:
    """PyPI JSON API with an on-disk cache."""

    def __init__(self, cache_dir):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)

    def _get(self, path):
        cached = self.cache / (path.strip("/").replace("/", "__") + ".json")
        if cached.exists():
            return json.loads(cached.read_text())
        with urllib.request.urlopen(f"https://pypi.org/pypi/{path}/json", timeout=60) as response:
            data = json.loads(response.read())
        cached.write_text(json.dumps(data))
        return data

    def files(self, name, version):
        return [u["filename"] for u in self._get(f"{name}/{version}")["urls"]]

    def releases(self, name):
        return self._get(name)["releases"]


def _version_key(version):
    return [int(x) for x in re.findall(r"\d+", version)]


def _is_final(version):
    return re.fullmatch(r"\d+(\.\d+)*(\.post\d+)?", version) is not None


def wheel_check(pins, old_python, new_python, sdk, pypi, glibc=(2, 41)):
    """Per pinned package: whether a build exists for the old and new Python, and for a non-SDK
    package without a build for the new Python, the nearest later final release with one."""
    rows = []
    for key, (name, version) in sorted(pins.items()):
        files = pypi.files(name, version)
        wheels = [f for f in files if f.endswith(".whl")]
        has_sdist = any(f.endswith((".tar.gz", ".zip")) for f in files)
        old_ok = any(wheel_fits(f, old_python, glibc) for f in wheels)
        new_ok = any(wheel_fits(f, new_python, glibc) for f in wheels)
        row = {"name": name, "version": version, "old_wheel": old_ok, "new_wheel": new_ok,
               "sdist": has_sdist, "sdk": key in sdk, "nearest": None}
        if old_ok and not new_ok and key not in sdk:
            for candidate in sorted(pypi.releases(name), key=_version_key):
                if _version_key(candidate) <= _version_key(version) or not _is_final(candidate):
                    continue
                if any(wheel_fits(f["filename"], new_python, glibc)
                       for f in pypi.releases(name)[candidate] if f["filename"].endswith(".whl")):
                    row["nearest"] = candidate
                    break
        rows.append(row)
    return rows


def lock_moves(old_pins, new_pins):
    """Pins that changed, appeared or disappeared between two locks."""
    moves = []
    for key in sorted(set(old_pins) | set(new_pins)):
        old = old_pins.get(key, (None, None))[1]
        new = new_pins.get(key, (None, None))[1]
        if old != new:
            name = (new_pins.get(key) or old_pins.get(key))[0]
            moves.append({"name": name, "old": old, "new": new})
    return moves


def write_constraints(candidate_dir, service_dir, replacements, relax):
    """Copy requirements.txt and the current lock into ``candidate_dir`` as compile_lock.sh's
    input, with pins replaced (``replacements`` name -> version) or dropped (``relax``)."""
    candidate_dir.mkdir(parents=True, exist_ok=True)
    keys = {normalise(n): v for n, v in replacements.items()}
    dropped = {normalise(n) for n in relax}
    for filename in ("requirements.txt", "requirements.lock"):
        lines = []
        for line in (service_dir / filename).read_text().splitlines():
            match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)((?:\[[^\]]*\])?)==(\S+)", line)
            key = normalise(match.group(1)) if match else None
            if key in dropped and filename == "requirements.lock":
                continue
            if key in keys:
                line = f"{match.group(1)}{match.group(2)}=={keys[key]}"
            lines.append(line)
        (candidate_dir / filename).write_text("\n".join(lines) + "\n")


def compile_lock(candidate_dir, base, env):
    subprocess.run([str(REPO / "scripts" / "release" / "compile_lock.sh"), str(candidate_dir), base],
                   check=True, env=env)

