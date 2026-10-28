"""Old-vs-new comparison of the requalification harness. Every result field is compared except
the measurements listed in EXCLUDED (timings, memory, CPU, process times) and the provenance
fields in PROVENANCE, whose differences are expected with a new Python and are listed apart;
``sdk_versions`` is compared, since the SDK pins must not move.
Statevectors are compared by sha256 of their bytes; a difference is reported with 1 - F and the
largest amplitude change. Stdlib only."""

import base64
import json
import re
import struct
from collections import Counter, defaultdict

EXCLUDED = (
    "execution_time_sec", "compilation_time_sec", "simulation_time_sec", "simulation_cpu_time_sec",
    "simulation_cgroup_cpu_time_sec", "compilation_throttled_sec", "simulation_throttled_sec",
    "simulation_involuntary_switches", "simulation_cpus", "memory_usage_mb", "process_peak_mb",
    "process_peak_rss_mb", "cpu_time_sec", "cpu_environment", "queue_wait_sec",
    "process_started_at", "process_finished_at",
)
EXCLUDED_PATTERNS = (r".*_samples$", r".*_sec_(mean|median|stdev)$")
PROVENANCE = (
    "runtime_environment", "image_identity", "build_files", "image_git_sha", "specimen",
    "native_components",
)
FIDELITY_TOLERANCE = {"cirq": 1e-15}


def excluded(key):
    return key in EXCLUDED or any(re.fullmatch(p, key) for p in EXCLUDED_PATTERNS)


def exclusion_text():
    return ("Not compared (measurements): " + ", ".join(EXCLUDED) + "; and every key matching "
            + ", ".join(f"`{p}`" for p in EXCLUDED_PATTERNS) + ". Compared but listed apart (provenance): "
            + ", ".join(PROVENANCE) + ".")


def load(path):
    rows = {}
    with open(path) as fh:
        for line in fh:
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


def _amplitudes(b64, precision):
    raw = base64.b64decode(b64)
    fmt, size = ("ff", 8) if precision == "complex64" else ("dd", 16)
    return [complex(*struct.unpack_from(fmt, raw, i)) for i in range(0, len(raw), size)]


def statevector_distance(old_b64, new_b64, precision):
    """(1 - F, max |delta amplitude|) of two encoded statevectors of equal length."""
    a, b = _amplitudes(old_b64, precision), _amplitudes(new_b64, precision)
    if len(a) != len(b):
        return None, None
    inner = sum(x.conjugate() * y for x, y in zip(a, b, strict=True))
    na = sum(abs(x) ** 2 for x in a)
    nb = sum(abs(y) ** 2 for y in b)
    fidelity = abs(inner) ** 2 / (na * nb) if na and nb else 0.0
    return 1 - fidelity, max((abs(x - y) for x, y in zip(a, b, strict=True)), default=0.0)


def compare_results(old, new):
    """(differing output keys, differing provenance keys) of two result dicts."""
    if not isinstance(old, dict) or not isinstance(new, dict):
        return (["<result>"] if old != new else []), []
    outputs, provenance = [], []
    for key in sorted(set(old) | set(new)):
        if excluded(key) or old.get(key) == new.get(key):
            continue
        (provenance if key in PROVENANCE else outputs).append(key)
    return outputs, provenance


def compare_corpus(old_dir, new_dir, cases, service, vectors=True):
    """Summary dict of the corpus comparison."""
    old, new = load(old_dir / "results.jsonl"), load(new_dir / "results.jsonl")
    old_vec = load(old_dir / "vectors.jsonl") if vectors else {}
    new_vec = load(new_dir / "vectors.jsonl") if vectors else {}
    kinds = {c["id"]: c["kind"] for c in cases}
    by_kind = defaultdict(Counter)
    differences, provenance = [], defaultdict(Counter)
    tolerance = FIDELITY_TOLERANCE.get(service)
    for case in cases:
        cid = case["id"]
        a, b = old.get(cid, {}).get("result"), new.get(cid, {}).get("result")
        kind = kinds[cid]
        by_kind[kind]["cases"] += 1
        if a is None or b is None:
            differences.append({"id": cid, "kind": kind, "keys": ["<missing>"], "class": "missing"})
            by_kind[kind]["different"] += 1
            continue
        if isinstance(a, dict) and (a.get("error") or a.get("harness_error")):
            by_kind[kind]["errors_old"] += 1
        outputs, prov = compare_results(a, b)
        for key in prov:
            provenance[key][(json.dumps(a.get(key), sort_keys=True), json.dumps(b.get(key), sort_keys=True))] += 1
        if not outputs:
            by_kind[kind]["identical"] += 1
            continue
        entry = {"id": cid, "kind": kind, "level": case["level"], "pre": case["pre"], "keys": outputs,
                 "class": "output"}
        if outputs == ["statevector"] and cid in old_vec and cid in new_vec:
            infidelity, delta = statevector_distance(old_vec[cid]["statevector"], new_vec[cid]["statevector"],
                                                     a.get("precision"))
            entry.update(infidelity=infidelity, max_amplitude_delta=delta)
            if tolerance is not None and delta is not None and delta <= tolerance:
                entry["class"] = "known_jitter"
        for key in outputs:
            entry.setdefault("values", {})[key] = {"old": _short(a.get(key)), "new": _short(b.get(key))}
        differences.append(entry)
        by_kind[kind]["different" if entry["class"] == "output" else "known_jitter"] += 1
    return {
        "by_kind": {k: dict(v) for k, v in by_kind.items()},
        "differences": differences,
        "provenance": {k: [{"old": json.loads(o), "new": json.loads(n), "cases": c} for (o, n), c in v.items()]
                       for k, v in provenance.items()},
    }


def _short(value, limit=400):
    text = json.dumps(value, sort_keys=True)
    return text if len(text) <= limit else text[:limit] + f"... ({len(text)} chars)"


def compare_cli(driver_dir, label):
    """Cases run both in the driver and through ``main.py --endpoint``: differing output keys."""
    driver = load(driver_dir / "results.jsonl")
    cli = load(driver_dir / "cli.jsonl")
    rows = []
    for cid, row in cli.items():
        outputs, _ = compare_results(driver[cid]["result"], row["result"])
        outputs = [k for k in outputs if k not in ("runner_code_sha256",)]
        rows.append({"image": label, "id": cid, "keys": outputs})
    return rows


def selftest_lines(text):
    """The exit status and the PASS/FAIL and summary lines of a ``--self-test`` run (log lines,
    which carry timestamps, left out)."""
    keep = [line for line in text.splitlines()
            if re.match(r"^(exit -?\d+|PASS |FAIL |\d+ of \d+ probe|\d+ failure)", line)]
    return "\n".join(keep)


def distribution_moves(old_env, new_env):
    def pins(env):
        return {d.split("==")[0].lower(): d.split("==", 1)[1] for d in env["distributions"]}
    a, b = pins(old_env), pins(new_env)
    return [{"name": k, "old": a.get(k), "new": b.get(k)} for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
