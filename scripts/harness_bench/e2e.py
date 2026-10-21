"""Submit one job through nginx and time submit -> completed and the time after the last runner finished.

Usage: python e2e.py <base_url> <n_qubits> [measured|statevector]
"""
import json, random, sys, time
import httpx
BASE = sys.argv[1]; n = int(sys.argv[2]); kind = sys.argv[3] if len(sys.argv) > 3 else "measured"
rng = random.Random(11)
lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{n}];", f"creg c[{n}];"]
for _ in range(60):
    a, b = rng.sample(range(n), 2)
    lines.append(rng.choice([f"h q[{a}];", f"cx q[{a}],q[{b}];", f"rz({rng.uniform(-3,3):.5f}) q[{a}];", f"ry({rng.uniform(-3,3):.5f}) q[{a}];"]))
qasm = "\n".join(lines) + "\n"
runners = [r for r, v in httpx.get(f"{BASE}/runners", timeout=30).json().items() if v.get("available") and v.get("enabled", True)] if isinstance(httpx.get(f"{BASE}/runners", timeout=30).json(), dict) else None
body = {"qasm_string": qasm + (f"measure q -> c;\n" if kind == "measured" else ""), "seed": 5}
if kind == "measured":
    body["n_shots"] = 8200
    path = "/compare_measured"
else:
    body["qasm_string"] = "\n".join(l for l in lines if not l.startswith("creg")) + "\n"
    path = "/compare"
    body.pop("seed")
t0 = time.perf_counter()
job = httpx.post(f"{BASE}{path}", json=body, timeout=60).json()["job_id"]
while True:
    s = httpx.get(f"{BASE}/jobs/{job}", timeout=60).json()
    if s["status"] in ("completed", "failed"):
        break
    time.sleep(0.5)
t1 = time.perf_counter()
import datetime
done_at = datetime.datetime.now(datetime.timezone.utc)
rep = httpx.get(f"{BASE}/jobs/{job}/report", timeout=300).json()
raw = rep.get("raw_results", [])
ok = [r for r in raw if r.get("dispatch_status") == "ok"]
last_finish = max((r.get("process_finished_at") or "") for r in raw) if raw else None
print(json.dumps({"status": s["status"], "wall_submit_to_done_sec": round(t1 - t0, 2), "backends_ok": len(ok), "backends": len(raw),
                  "pairs": len(rep.get("divergence_report", {}).get("pairwise_agreement", [])), "job_id": job, "last_process_finished_at": last_finish,
                  "git_sha": rep.get("git_sha"),
                  "after_last_runner_sec": round((done_at - datetime.datetime.fromisoformat(last_finish.replace("Z", "+00:00"))).total_seconds(), 2) if last_finish else None}))
