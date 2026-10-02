"""Median compilation/simulation/total time of the old and new adapter (statevector)."""
import json, logging, math, random, statistics, sys
logging.disable(logging.CRITICAL)
sys.path.insert(0, ".")
import main_old, main

def qft(n):
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";', f"qreg q[{n}];"]
    for i in range(n):
        lines.append(f"h q[{i}];")
        for j in range(i + 1, n):
            lines.append(f"cu1(pi/{2 ** (j - i)}) q[{j}],q[{i}];")
    return "\n".join(lines) + "\n"

def deep(n, gates, seed):
    rng = random.Random(seed)
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";', f"qreg q[{n}];"]
    for _ in range(gates):
        if rng.random() < 0.5:
            lines.append(f"rz({rng.uniform(-3, 3)!r}) q[{rng.randrange(n)}];")
        else:
            a, b = rng.sample(range(n), 2)
            lines.append(f"cx q[{a}],q[{b}];")
    return "\n".join(lines) + "\n"

cases = {"qft16": qft(16), "4q_2200g": deep(4, 2200, 1), "16q_400g": deep(16, 400, 2)}
out = {}
for name, qasm in cases.items():
    rows = {"old": [], "new": []}
    for mod in (main_old, main):
        mod.process_run({"circuit_data": qasm})
    for rep in range(7):
        for label, mod in (("old", main_old), ("new", main)):
            r = mod.process_run({"circuit_data": qasm})
            rows[label].append((r["compilation_time_sec"], r["simulation_time_sec"], r["execution_time_sec"]))
    out[name] = {label: [round(statistics.median(x[k] for x in v) * 1000, 2) for k in range(3)]
                 for label, v in rows.items()}
print(json.dumps(out))
