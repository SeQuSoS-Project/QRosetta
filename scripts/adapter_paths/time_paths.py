"""Median compilation/simulation/total time of the old and new adapter, statevector or (with
argument ``measured``, 8200 shots, seed 1) measured mode."""
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

measured = len(sys.argv) > 1 and sys.argv[1] == "measured"
cases = {"qft16": qft(16), "4q_2200g": deep(4, 2200, 1), "16q_400g": deep(16, 400, 2)}
if measured:
    cases = {k: v.replace("qreg q[", "creg c[" + v.split("qreg q[")[1].split("]")[0] + "];\nqreg q[", 1)
             + "measure q -> c;\n" for k, v in cases.items()}
fn = "process_run_measured" if measured else "process_run"
extra = {"n_shots": 8200, "seed": 1} if measured else {}
out = {}
for name, qasm in cases.items():
    rows = {"old": [], "new": []}
    for mod in (main_old, main):
        getattr(mod, fn)({"circuit_data": qasm, **extra})
    for rep in range(7):
        for label, mod in (("old", main_old), ("new", main)):
            r = getattr(mod, fn)({"circuit_data": qasm, **extra})
            rows[label].append((r["compilation_time_sec"], r["simulation_time_sec"], r["execution_time_sec"]))
    out[name] = {label: [round(statistics.median(x[k] for x in v) * 1000, 2) for k in range(3)]
                 for label, v in rows.items()}
print(json.dumps(out))
