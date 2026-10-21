"""Run one seeded 7-qubit measured job and save its divergence report and counts, to compare two API versions.

Usage: python save_report.py <base_url> <out.json>
"""
import httpx
BASE, out = sys.argv[1], sys.argv[2]
rng = random.Random(11); n = 7
lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{n}];", f"creg c[{n}];"]
for _ in range(60):
    a, b = rng.sample(range(n), 2)
    lines.append(rng.choice([f"h q[{a}];", f"cx q[{a}],q[{b}];", f"rz({rng.uniform(-3,3):.5f}) q[{a}];", f"ry({rng.uniform(-3,3):.5f}) q[{a}];"]))
body = {"qasm_string": "\n".join(lines) + "\nmeasure q -> c;\n", "seed": 5, "n_shots": 8200}
job = httpx.post(f"{BASE}/compare_measured", json=body, timeout=60).json()["job_id"]
while httpx.get(f"{BASE}/jobs/{job}", timeout=60).json()["status"] not in ("completed", "failed"):
    time.sleep(0.5)
rep = httpx.get(f"{BASE}/jobs/{job}/report", timeout=300).json()
json.dump({"divergence_report": rep["divergence_report"], "counts": {r["simulator"]: r.get("counts") for r in rep["raw_results"]}}, open(out, "w"), sort_keys=True)
print("saved", out)
