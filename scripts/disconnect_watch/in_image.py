"""Runs inside a runner or compiler image (no network) for the disconnect-watcher evidence
(DESIGN_DECISIONS.md "A request whose caller went away"). Starts the image's own server command
(gunicorn, one uvicorn worker) on 127.0.0.1:8000 and sends it requests over HTTP.

python in_image.py outputs <in-dir> <out-dir>
    Every case of corpus.jsonl; writes results.jsonl and vectors.jsonl as the requalification
    harness does (statevectors as sha256 and byte length).
python in_image.py timing <in-dir> <out-dir>
    Each timing/*.json payload ``count`` times in turn; per request the result, the wall time
    and the CPU time of the serving worker process (its own threads, not the run's child).
python in_image.py disconnect <in-dir> <out-dir>
    disconnect.json: a ``slow`` request dropped while its child runs, then a ``fast`` one; a
    ``medium`` request kept, a ``fast`` one dropped while queued behind it, then another
    ``fast`` one. Records when the dropped run's child ended, whether the dropped queued
    request started, and the next requests' queue_wait_sec. Stdlib only.
"""

import base64
import hashlib
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

APP = Path.cwd()
PORT = 8000


def start_server():
    proc = subprocess.Popen(
        [shutil.which("gunicorn") or "/usr/local/bin/gunicorn", "main:app", "--workers", "1",
         "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", f"127.0.0.1:{PORT}", "--timeout", "330"],
        cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1) as resp:
                if resp.status == 200:
                    break
        except OSError:
            time.sleep(0.2)
    else:
        raise SystemExit("server did not start")
    return proc, worker_pid(proc.pid)


def children(pid):
    out = []
    for task in Path(f"/proc/{pid}/task").iterdir():
        try:
            out += [int(x) for x in (task / "children").read_text().split()]
        except OSError:
            pass
    return out


def worker_pid(master):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        kids = children(master)
        if kids:
            return kids[0]
        time.sleep(0.1)
    raise SystemExit("no gunicorn worker")


def cmdline(pid):
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
    except OSError:
        return ""


def alive(pid):
    try:
        return not Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].startswith("Z")
    except OSError:
        return False


def run_children(worker):
    return [p for p in children(worker)
            if "multiprocessing" in cmdline(p) and "resource_tracker" not in cmdline(p) and alive(p)]


def cpu_sec(pid):
    """Run time of every thread of ``pid`` (schedstat, nanoseconds), in seconds."""
    total = 0
    for task in Path(f"/proc/{pid}/task").iterdir():
        try:
            total += int((task / "schedstat").read_text().split()[0])
        except OSError:
            pass
    return total / 1e9


def send(endpoint, payload):
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=3600)
    conn.request("POST", f"/{endpoint}", body=json.dumps(payload), headers={"Content-Type": "application/json"})
    return conn


def read(conn):
    try:
        return json.loads(conn.getresponse().read())
    finally:
        conn.close()


def digest(result):
    if not isinstance(result, dict):
        return result, None
    result = dict(result)
    vector = result.get("statevector")
    if isinstance(vector, str):
        raw = base64.b64decode(vector)
        result["statevector"] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        return result, vector
    return result, None


def outputs(in_dir, out_dir):
    with open(in_dir / "corpus.jsonl") as cases, open(out_dir / "results.jsonl", "w") as results, \
            open(out_dir / "vectors.jsonl", "w") as vectors:
        for line in cases:
            case = json.loads(line)
            started = time.monotonic()
            result, raw = digest(read(send(case["endpoint"], case["payload"])))
            results.write(json.dumps({"id": case["id"], "wall_sec": time.monotonic() - started,
                                      "result": result}) + "\n")
            if raw is not None:
                vectors.write(json.dumps({"id": case["id"], "statevector": raw}) + "\n")


def timing(in_dir, out_dir, worker):
    for path in sorted((in_dir / "timing").glob("*.json")):
        spec = json.loads(path.read_text())
        with open(out_dir / (path.stem + ".jsonl"), "w") as out:
            for _ in range(spec["count"]):
                cpu0, t0 = cpu_sec(worker), time.monotonic()
                result, _ = digest(read(send(spec["endpoint"], spec["payload"])))
                out.write(json.dumps({"wall_sec": time.monotonic() - t0, "worker_cpu_sec": cpu_sec(worker) - cpu0,
                                      "result": result}) + "\n")


def wait_child(worker, lived, seconds=600):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        for pid in run_children(worker):
            age = time.time() - (os.stat(f"/proc/{pid}").st_mtime)
            if age >= lived:
                return pid
        time.sleep(0.05)
    raise SystemExit("the run's child did not appear")


def disconnect(in_dir, out_dir, worker):
    spec = json.loads((in_dir / "disconnect.json").read_text())
    report = {}
    conn = send(spec["slow"]["endpoint"], spec["slow"]["payload"])
    child = wait_child(worker, spec.get("drop_after_sec", 3.0))
    t0 = time.monotonic()
    conn.close()
    while alive(child) and time.monotonic() - t0 < 900:
        time.sleep(0.02)
    report["mid_run"] = {"child_ended_after_sec": round(time.monotonic() - t0, 3)}
    after = read(send(spec["fast"]["endpoint"], spec["fast"]["payload"]))
    report["mid_run"]["next_queue_wait_sec"] = after.get("queue_wait_sec")
    report["mid_run"]["next_error"] = after.get("error")

    kept = send(spec["medium"]["endpoint"], spec["medium"]["payload"])
    first = wait_child(worker, 0.2)
    queued = send(spec["fast"]["endpoint"], spec["fast"]["payload"])
    time.sleep(0.5)
    queued.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\0\0\0\0\0\0\0")
    queued.close()
    kept_result = read(kept)
    seen = set()
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        seen.update(p for p in run_children(worker) if p != first)
        time.sleep(0.02)
    after = read(send(spec["fast"]["endpoint"], spec["fast"]["payload"]))
    report["queued"] = {"kept_error": kept_result.get("error"), "dropped_request_started": bool(seen),
                        "next_queue_wait_sec": after.get("queue_wait_sec"), "next_error": after.get("error")}
    (out_dir / "disconnect.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    mode, in_dir, out_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)
    server, worker = start_server()
    try:
        if mode == "outputs":
            outputs(in_dir, out_dir)
        elif mode == "timing":
            timing(in_dir, out_dir, worker)
        else:
            disconnect(in_dir, out_dir, worker)
    finally:
        server.terminate()
        server.wait(30)
