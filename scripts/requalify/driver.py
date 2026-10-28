"""Runs inside a runner or compiler image (no network) for the requalification harness.

python driver.py corpus <runner|compiler> <in-dir> <out-dir>
    Every case of <in-dir>/corpus.jsonl through the function the image's CLI path calls
    (runner: run_with_uniform_measurement(process_run[_measured], payload); compiler:
    process_compile(payload)), in this one process. Writes results.jsonl (statevectors as sha256
    and byte length), vectors.jsonl (statevectors as sent), selftest.txt (``main.py
    --self-test``), cli.jsonl (the cases listed in cli_cases.json through ``main.py --endpoint``
    in a process each) and environment.json (Python, installed distributions).
python driver.py timing <runner> <in-dir> <out-dir>
    Each <in-dir>/timing/*.json payload through ``main.py --endpoint`` in a process each.
python driver.py imports <runner|compiler> <in-dir> <out-dir>
    Imports ``main`` and every top-level module of the SDK distributions in <in-dir>/sdk.json;
    writes imports.json ({module: null, or the end of the traceback}).
"""

import base64
import hashlib
import importlib
import importlib.metadata
import json
import logging
import os
import platform
import re
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

APP = Path.cwd()
CASE_TIMEOUT_SEC = int(os.environ.get("REQUAL_CASE_TIMEOUT_SEC", "300"))


def _digest(result):
    if not isinstance(result, dict):
        return result, None
    result = dict(result)
    vector = result.get("statevector")
    if isinstance(vector, str):
        raw = base64.b64decode(vector)
        result["statevector"] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        return result, vector
    if vector is not None:
        text = json.dumps(vector, sort_keys=True).encode()
        result["statevector"] = {"sha256": hashlib.sha256(text).hexdigest(), "bytes": len(text), "json": True}
        return result, vector
    return result, None


class _CaseTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise _CaseTimeout(f"case exceeded {CASE_TIMEOUT_SEC} s")


def _cli(endpoint, payload, workdir, env=None):
    payload_file = workdir / "payload.json"
    result_file = workdir / "result.json"
    payload_file.write_text(json.dumps(payload))
    if result_file.exists():
        result_file.unlink()
    proc = subprocess.run([sys.executable, "main.py", "--endpoint", endpoint, "--payload-file", str(payload_file),
                           "--result-file", str(result_file)], cwd=APP, capture_output=True, text=True,
                          env=env, timeout=CASE_TIMEOUT_SEC * 3)
    if not result_file.exists():
        return {"harness_error": f"exit {proc.returncode}", "stderr_tail": proc.stderr[-2000:]}
    return json.loads(result_file.read_text())


def _environment():
    dists = sorted({(d.metadata["Name"] or "?", d.version) for d in importlib.metadata.distributions()},
                   key=lambda x: x[0].lower())
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "libc": platform.libc_ver(), "distributions": [f"{n}=={v}" for n, v in dists]}


def _normalise(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def sdk_modules(distributions):
    """Top-level import names of ``distributions`` (private names left out), sorted."""
    wanted = {_normalise(d) for d in distributions}
    found = set()
    for module, dists in importlib.metadata.packages_distributions().items():
        if not module.startswith("_") and wanted & {_normalise(d) for d in dists}:
            found.add(module)
    return sorted(found)


def import_check(distributions, app):
    """{module: None if it imports, else the last lines of its traceback} for ``main`` (from
    ``app``) and the top-level modules of ``distributions``."""
    logging.disable(logging.CRITICAL)
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))
    results = {}
    for name in ["main", *sdk_modules(distributions)]:
        try:
            importlib.import_module(name)
            results[name] = None
        except BaseException:
            results[name] = "".join(traceback.format_exc().splitlines(keepends=True)[-12:])
    return results


def corpus(kind, in_dir, out_dir):
    logging.disable(logging.CRITICAL)
    sys.path.insert(0, str(APP))
    (out_dir / "environment.json").write_text(json.dumps(_environment(), indent=1))
    proc = subprocess.run([sys.executable, "main.py", "--self-test"], cwd=APP, capture_output=True, text=True,
                          timeout=3600)
    (out_dir / "selftest.txt").write_text(f"exit {proc.returncode}\n{proc.stdout}")

    import main
    if kind == "runner":
        from qrosetta_commons.helpers import run_with_uniform_measurement

        def run(case):
            func = main.process_run_measured if case["endpoint"] == "run_measured" else main.process_run
            return run_with_uniform_measurement(func, dict(case["payload"]))
    else:
        def run(case):
            return main.process_compile(dict(case["payload"]))

    signal.signal(signal.SIGALRM, _alarm)
    with open(in_dir / "corpus.jsonl") as cases, open(out_dir / "results.jsonl", "w") as results, \
            open(out_dir / "vectors.jsonl", "w") as vectors:
        for line in cases:
            case = json.loads(line)
            started = time.monotonic()
            signal.alarm(CASE_TIMEOUT_SEC)
            try:
                result = run(case)
            except _CaseTimeout as exc:
                result = {"harness_error": str(exc)}
            except Exception as exc:
                result = {"harness_error": f"{type(exc).__name__}: {exc}"}
            finally:
                signal.alarm(0)
            result, raw = _digest(result)
            results.write(json.dumps({"id": case["id"], "wall_sec": time.monotonic() - started,
                                      "result": result}) + "\n")
            if raw is not None:
                vectors.write(json.dumps({"id": case["id"], "statevector": raw}) + "\n")

    cli_ids = set(json.loads((in_dir / "cli_cases.json").read_text()))
    work = out_dir / "cli-work"
    work.mkdir()
    with open(in_dir / "corpus.jsonl") as cases, open(out_dir / "cli.jsonl", "w") as out:
        for line in cases:
            case = json.loads(line)
            if case["id"] in cli_ids:
                endpoint = case["endpoint"] if kind == "runner" else "compile"
                result, _ = _digest(_cli(endpoint, case["payload"], work))
                out.write(json.dumps({"id": case["id"], "result": result}) + "\n")


def timing(in_dir, out_dir):
    work = out_dir / "work"
    work.mkdir()
    for path in sorted((in_dir / "timing").glob("*.json")):
        spec = json.loads(path.read_text())
        result, _ = _digest(_cli(spec["endpoint"], spec["payload"], work))
        (out_dir / path.name).write_text(json.dumps(result))


if __name__ == "__main__":
    mode, kind_or_runner, in_dir, out_dir = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    out_dir.mkdir(parents=True, exist_ok=True)
    if mode == "corpus":
        corpus(kind_or_runner, in_dir, out_dir)
    elif mode == "imports":
        sdk = json.loads((in_dir / "sdk.json").read_text())
        (out_dir / "imports.json").write_text(json.dumps(import_check(sdk, APP), indent=1))
    else:
        timing(in_dir, out_dir)
