"""Run the old and new adapter on one corpus inside a runner container and compare outputs.

Usage (inside the container): python compare_paths.py <n_circuits> [measured] [levels]
main_old.py and main.py must sit in the working directory."""
import base64
import json
import random
import sys
import logging

logging.disable(logging.CRITICAL)
sys.path.insert(0, ".")
import importlib
old = importlib.import_module("main_old")
new = importlib.import_module("main")

ONE = ["x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx"]
ONE_P = ["rx", "ry", "rz", "u1"]
TWO = ["cx", "cz", "cy", "swap", "ch"]
TWO_P = ["crz", "cu1", "cry", "crx"]
THREE = ["ccx", "cswap"]


def angle(rng):
    return rng.choice([f"{rng.uniform(-6.3, 6.3)!r}", "pi/4", "-pi/2", "0.3*pi", f"{rng.uniform(-1, 1)!r}"])


def random_circuit(rng, measured):
    import os
    regs = ([rng.randint(1, 10)] if os.environ.get("SINGLE_REGISTER")
            else rng.choice([[rng.randint(1, 8)], [rng.randint(1, 4), rng.randint(1, 4)]]))
    names = ["q", "r"][:len(regs)]
    wires = [(n, i) for n, size in zip(names, regs) for i in range(size)]
    idle = set(rng.sample(wires, k=min(len(wires) - 1, rng.randint(0, 1)))) if len(wires) > 1 else set()
    live = [w for w in wires if w not in idle] or wires
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";'] + [f"qreg {n}[{s}];" for n, s in zip(names, regs)]
    if measured:
        lines.append(f"creg c[{len(wires)}];")
    for _ in range(rng.randint(1, 40)):
        k = rng.choice([1, 1, 2, 2, 3]) if len(live) >= 3 else (rng.choice([1, 2]) if len(live) >= 2 else 1)
        ws = rng.sample(live, k)
        args = ",".join(f"{n}[{i}]" for n, i in ws)
        if k == 1:
            g = rng.choice(ONE + ONE_P + ["u3"])
            g = f"{g}({angle(rng)})" if g in ONE_P else (f"u3({angle(rng)},{angle(rng)},{angle(rng)})" if g == "u3" else g)
        elif k == 2:
            g = rng.choice(TWO + TWO_P + ["cu3"])
            g = f"{g}({angle(rng)})" if g in TWO_P else (f"cu3({angle(rng)},{angle(rng)},{angle(rng)})" if g == "cu3" else g)
        else:
            g = rng.choice(THREE)
        lines.append(f"{g} {args};")
        if measured and rng.random() < 0.04:
            n, i = rng.choice(live)
            lines.append(f"measure {n}[{i}] -> c[{rng.randrange(len(wires))}];")
    if measured:
        order = list(range(len(wires)))
        rng.shuffle(order)
        for c in order[:rng.randint(1, len(wires))]:
            n, i = wires[rng.randrange(len(wires))]
            lines.append(f"measure {n}[{i}] -> c[{c}];")
    return "\n".join(lines) + "\n"


def strip(result):
    keep = ("error", "statevector", "counts", "transpiled_qasm", "gate_count", "circuit_depth",
            "qubit_ordering", "precision")
    return {k: result.get(k) for k in keep}


def main():
    n = int(sys.argv[1])
    measured = len(sys.argv) > 2 and sys.argv[2] == "measured"
    levels = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [0]
    rng = random.Random(20261002)
    mismatches, ok, errors = [], 0, 0
    for k in range(n):
        qasm = random_circuit(rng, measured)
        for level in levels:
            for pre in (True, False):
                payload = {"circuit_data": qasm, "optimization_level": level, "apply_preprocessing": pre}
                if measured:
                    payload.update(n_shots=rng.choice([1, 17, 1000]), seed=rng.choice([0, 7, 123456789]))
                fn = "process_run_measured" if measured else "process_run"
                a = strip(getattr(old, fn)(dict(payload)))
                b = strip(getattr(new, fn)(dict(payload)))
                if a == b:
                    ok += 1
                    errors += a["error"] is not None
                else:
                    diff = [key for key in a if a[key] != b[key]]
                    mismatches.append({"case": k, "level": level, "pre": pre, "diff": diff,
                                       "old_error": a["error"], "new_error": b["error"], "qasm": qasm})
    print(json.dumps({"compared": ok + len(mismatches), "identical": ok, "identical_errors": errors,
                      "mismatches": mismatches[:5], "n_mismatches": len(mismatches)}))


if __name__ == "__main__":
    main()
