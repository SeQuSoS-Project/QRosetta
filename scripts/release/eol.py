#!/usr/bin/env python3
"""End-of-life guard for the container images. Reads every Dockerfile in the repository (multi-stage
builds, ARG-defaulted base images, digests) and the dates in release/eol.json, and judges each image's
final stage by its Python and its base OS: an image is inside the window from `window_months` before
the earlier of the two end-of-life dates. Build stages and the Qiskit series pinned in the image's
requirements.lock are reported, not judged. `python scripts/release/eol.py [--today YYYY-MM-DD]`
prints one line per image and exits 1 when any image is inside the window. Stdlib only."""

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "release" / "eol.json"
SKIP_DIRS = {"node_modules", "__pycache__", "build", "dist"}

_VAR = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)(?::?-([^}]*))?\}|([A-Za-z_][A-Za-z0-9_]*))")
_INSTALLED_PYTHON = re.compile(r"\bpython(3\.\d+)\b")
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;#]+)")


@dataclass
class Stage:
    name: str | None
    ref: str
    parent: "Stage | None"
    run_text: str = ""


@dataclass
class Base:
    ref: str
    repository: str
    tag: str | None
    digest: str | None
    python: str | None
    python_basis: str
    os_family: str | None
    os_release: str | None
    os_basis: str


@dataclass
class Finding:
    component: str
    eol: dt.date | None
    window_start: dt.date | None
    problem: str | None = None


@dataclass
class Image:
    path: str
    final: Base
    build_stages: list = field(default_factory=list)
    lock: dict = field(default_factory=dict)


def load_table(path=TABLE):
    return json.loads(Path(path).read_text())


def parse_date(text):
    parts = [int(p) for p in text.split("-")]
    return dt.date(parts[0], parts[1], parts[2] if len(parts) > 2 else 1)


def minus_months(day, months):
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    last = (dt.date(year + month // 12, month % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(year, month, min(day.day, last))


def find_dockerfiles(root=REPO):
    found = []
    for path in sorted(Path(root).rglob("*")):
        rel = path.relative_to(root)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        name = path.name
        if path.is_file() and (name == "Dockerfile" or name.startswith("Dockerfile.") or name.endswith(".Dockerfile")):
            found.append(path)
    return found


def _instructions(text):
    lines, current = [], ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not current and (not stripped or stripped.startswith("#")):
            continue
        if current and stripped.startswith("#"):
            continue
        if stripped.endswith("\\"):
            current += stripped[:-1] + " "
            continue
        current += stripped
        lines.append(current)
        current = ""
    if current:
        lines.append(current)
    return lines


def _substitute(text, values):
    def repl(match):
        name = match.group(1) or match.group(3)
        default = match.group(2)
        value = values.get(name)
        if value:
            return value
        return default or ""
    return _VAR.sub(repl, text)


def _arg_value(spec):
    name, _, default = spec.partition("=")
    return name.strip(), default.strip().strip('"').strip("'")


def parse_dockerfile(text, build_args=None):
    """Stages in order, each with its base reference resolved against global ARG defaults."""
    global_args = {}
    stages = []
    for line in _instructions(text):
        keyword, _, rest = line.partition(" ")
        keyword = keyword.upper()
        rest = rest.strip()
        if keyword == "ARG" and not stages:
            name, default = _arg_value(rest)
            global_args[name] = (build_args or {}).get(name, _substitute(default, global_args))
        elif keyword == "FROM":
            words = [w for w in rest.split() if not w.startswith("--")]
            ref = _substitute(words[0], global_args)
            name = words[2] if len(words) >= 3 and words[1].upper() == "AS" else None
            parent = next((s for s in stages if s.name and s.name.lower() == ref.lower()), None)
            stages.append(Stage(name=name, ref=ref, parent=parent))
        elif keyword == "RUN" and stages:
            stages[-1].run_text += rest + "\n"
    return stages


def split_ref(ref):
    image, _, digest = ref.partition("@")
    last = image.rsplit("/", 1)[-1]
    tag = None
    if ":" in last:
        image, tag = image.rsplit(":", 1)
    parts = image.split("/")
    if len(parts) > 1 and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
        parts = parts[1:]
    if parts[0] == "library":
        parts = parts[1:]
    return "/".join(parts), tag, digest or None


def _os_from_tag(tag, table):
    if not tag:
        return None, None
    for release, entry in table["os"]["debian"]["releases"].items():
        if re.search(rf"(^|-){entry['codename']}($|-)", tag):
            return "debian", release
    match = re.search(r"alpine(\d+\.\d+)", tag)
    if match:
        return "alpine", match.group(1)
    return None, None


def classify(stage, table):
    """The base image of a stage: Python and OS, and where each was read from."""
    run_text = ""
    while stage.parent is not None:
        run_text = stage.run_text + run_text
        stage = stage.parent
    run_text = stage.run_text + run_text
    repository, tag, digest = split_ref(stage.ref)
    known = table["base_images"].get(digest or "", {})
    if repository == "python" and tag and re.match(r"\d+\.\d+", tag):
        python = re.match(r"(\d+\.\d+)", tag).group(1)
        python_basis = "base image tag"
    elif _INSTALLED_PYTHON.search(run_text):
        python = _INSTALLED_PYTHON.search(run_text).group(1)
        python_basis = "installed by the Dockerfile"
    elif known.get("python"):
        python = ".".join(known["python"].split(".")[:2])
        python_basis = "release/eol.json base_images"
    else:
        python, python_basis = None, "no Python"
    if known.get("os"):
        family, release = known["os"]["family"], known["os"]["release"]
        os_basis = "release/eol.json base_images (digest)"
    else:
        family, release = _os_from_tag(tag, table)
        os_basis = "base image tag" if family else "unknown"
    return Base(ref=stage.ref, repository=repository, tag=tag, digest=digest, python=python,
                python_basis=python_basis, os_family=family, os_release=release, os_basis=os_basis)


def read_lock(path):
    pins = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            match = _PIN.match(line.strip())
            if match:
                pins[match.group(1).lower().replace("_", "-")] = match.group(2)
    return pins


def load_images(root=REPO, table=None):
    table = table or load_table()
    images = []
    for path in find_dockerfiles(root):
        stages = parse_dockerfile(path.read_text())
        if not stages:
            continue
        final = classify(stages[-1], table)
        build = [(s.name, classify(s, table)) for s in stages[:-1] if s.parent is None]
        images.append(Image(path=path.relative_to(root).as_posix(), final=final, build_stages=build,
                            lock=read_lock(path.parent / "requirements.lock")))
    return images


def findings(base, table):
    """Python and OS end-of-life dates of one base image, with the date each enters the window."""
    months = table["window_months"]
    result = []
    if base.python is not None:
        entry = table["python"]["branches"].get(base.python)
        if entry is None:
            result.append(Finding(f"Python {base.python}", None, None, "not in release/eol.json"))
        else:
            eol = parse_date(entry["eol"])
            result.append(Finding(f"Python {base.python}", eol, minus_months(eol, months)))
    if base.os_family is None:
        result.append(Finding(f"base OS of {base.ref}", None, None,
                              "unknown: add the digest to base_images in release/eol.json"))
    else:
        entry = table["os"].get(base.os_family, {}).get("releases", {}).get(base.os_release)
        label = f"{base.os_family} {base.os_release}"
        if entry is None:
            result.append(Finding(label, None, None, "not in release/eol.json"))
        else:
            eol = parse_date(entry["eol"])
            result.append(Finding(label, eol, minus_months(eol, months)))
    return result


def violations(base, table, today):
    """Messages for each finding inside the window on `today`, or that cannot be judged."""
    out = []
    for f in findings(base, table):
        if f.problem:
            out.append(f"{f.component}: {f.problem}")
        elif today >= f.window_start:
            state = "reached end of life" if today >= f.eol else "reaches end of life"
            out.append(f"{f.component} {state} on {f.eol.isoformat()} "
                       f"(inside the {table['window_months']}-month window since {f.window_start.isoformat()})")
    return out


def sdk_notes(image, table, today):
    """Reported support status of each pinned package with a published support window."""
    notes = []
    for name, info in table["packages"].items():
        version = image.lock.get(name)
        if version is None:
            continue
        major = version.split(".")[0]
        series = info["series"].get(major)
        if series is None:
            notes.append(f"{name} {version}: series {major}.x not in release/eol.json")
        elif series.get("security_end_at_least"):
            end = series["security_end_at_least"]
            passed = " (passed)" if today >= parse_date(end) else ""
            notes.append(f"{name} {version}: {major}.x series, security fixes guaranteed until {end}{passed}")
        else:
            notes.append(f"{name} {version}: {major}.x series supported, patch releases only for {series['latest_minor']}")
    return notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    args = parser.parse_args(argv)
    table = load_table()
    failing = 0
    for image in load_images(table=table):
        bad = violations(image.final, table, args.today)
        failing += bool(bad)
        dates = ", ".join(f"{f.component} {f.eol}" if f.eol else f"{f.component} ?" for f in findings(image.final, table))
        print(f"{'FAIL' if bad else 'ok  '} {image.path}: {image.final.ref.split('@')[0]} ({dates})")
        for message in bad:
            print(f"       {message}")
        for name, base in image.build_stages:
            stage_bad = violations(base, table, args.today)
            print(f"       build stage {name}: {base.ref.split('@')[0]}{' - ' + '; '.join(stage_bad) if stage_bad else ''}")
        for note in sdk_notes(image, table, args.today):
            print(f"       {note}")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
