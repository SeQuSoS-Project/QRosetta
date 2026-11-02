"""V8 fault injection over the verdict pipeline: one backend's output is mutated (undeclared bit
reversal, a flipped ordering label, two qubits swapped, one amplitude's sign flipped, one gate
deleted) and the server's analysis must flag a pair with that backend; a global phase, complex64
rounding and a correctly declared msb ordering must not be flagged.

    PYTHONPATH=rosetta-api:shared python scripts/verify/v8_mutation.py --out DIR
        [--sv-circuits N] [--measured-circuits N]

Three corpora: statevector mode on random circuits (create_divergence_report, 3 backends: lsb
reference, msb reference, mutant); measured mode on random circuits (create_counts_report, 13
correct backends half msb, b13 the mutant, 8200 shots); measured mode on the recorded reports in
experiments/ and examples/ (a backend with no flag in the recorded report is mutated). Truth comes
from the qelib1 reference (scripts/verify/qelib1_reference.py). A mutant whose output equals the
truth in its declared ordering (fidelity >= 1 - 1e-5, or total variation <= 1e-9 for counts) is
equivalent and left out of the score. Writes DIR/mutation.json and DIR/mutation_cases.csv."""

import argparse
import json
import math
import sys
import time
import zlib
from multiprocessing import Pool
from pathlib import Path

import v8_common as c

import numpy as np
import qelib1_reference as ref

MASTER_SEED = 20261104
REPO = Path(__file__).resolve().parents[2]
ONE_QUBIT = ["h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx"]
ONE_PARAM = ["rx", "ry", "rz"]
TWO_QUBIT = ["cx", "cz", "cy", "ch", "swap"]
MUTANTS = ("undeclared_reversal", "label_flip", "qubit_swap", "sign_flip", "deleted_gate")
CONTROLS = ("global_phase", "complex64", "declared_msb", "msb_complex64_phase")
FIDELITY_TOLERANCE = 1e-5


def random_circuit(rng, n_qubits, n_gates):
    """(header, gate lines) of a random qelib1 circuit on qreg q[n_qubits]."""
    lines = []
    for _ in range(n_gates):
        kind = rng.integers(0, 6 if n_qubits >= 3 else 5)
        q = [int(x) for x in rng.permutation(n_qubits)]
        if kind <= 1:
            lines.append(f"{ONE_QUBIT[rng.integers(len(ONE_QUBIT))]} q[{q[0]}];")
        elif kind == 2:
            lines.append(f"{ONE_PARAM[rng.integers(3)]}({rng.uniform(-math.pi, math.pi):.6f}) q[{q[0]}];")
        elif kind == 3:
            a = rng.uniform(-math.pi, math.pi, 3)
            lines.append(f"u3({a[0]:.6f},{a[1]:.6f},{a[2]:.6f}) q[{q[0]}];")
        elif kind == 4:
            lines.append(f"{TWO_QUBIT[rng.integers(len(TWO_QUBIT))]} q[{q[0]}],q[{q[1]}];")
        else:
            lines.append(f"ccx q[{q[0]}],q[{q[1]}],q[{q[2]}];")
    header = f'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[{n_qubits}];\n'
    return header, lines


def state_of(header, lines):
    return ref.statevector(header + "\n".join(lines))


def swap_qubits(state, a, b):
    n = int(round(math.log2(len(state))))
    axes = list(range(n))
    axes[n - 1 - a], axes[n - 1 - b] = axes[n - 1 - b], axes[n - 1 - a]
    return state.reshape([2] * n).transpose(axes).reshape(-1)


def mutate_state(rng, name, truth, header, lines):
    """(declared ordering, vector) a mutant or control backend returns."""
    phase = np.exp(1j * rng.uniform(0, 2 * math.pi))
    if name == "undeclared_reversal":
        return "lsb", ref.to_order(truth, "msb")
    if name == "label_flip":
        return "msb", truth
    if name == "qubit_swap":
        return "lsb", swap_qubits(truth, 0, 1)
    if name == "sign_flip":
        candidates = np.flatnonzero(np.abs(truth) ** 2 > 1e-3)
        out = truth.copy()
        out[rng.choice(candidates)] *= -1
        return "lsb", out
    if name == "deleted_gate":
        k = int(rng.integers(len(lines)))
        return "lsb", state_of(header, lines[:k] + lines[k + 1:])
    if name == "global_phase":
        return "lsb", truth * phase
    if name == "complex64":
        return "lsb", truth.astype(np.complex64).astype(np.complex128)
    if name == "declared_msb":
        return "msb", ref.to_order(truth, "msb")
    if name == "msb_complex64_phase":
        return "msb", (ref.to_order(truth, "msb") * phase).astype(np.complex64).astype(np.complex128)
    raise ValueError(name)


def _sv_result(name, ordering, vector):
    from qrosetta_commons.helpers import encode_statevector
    return {"simulator": name, "qubit_ordering": ordering, "dispatch_status": "ok",
            "statevector": encode_statevector(np.asarray(vector, dtype=np.complex128))}


def statevector_case(index):
    """All mutants and controls of one random circuit in statevector mode."""
    from services.analysis.divergence import create_divergence_report
    from services.analysis.divergence.verdicts import annotate_divergence_report
    rng = np.random.default_rng([MASTER_SEED, 1, index])
    n = int(rng.integers(2, 6))
    header, lines = random_circuit(rng, n, int(rng.integers(8, 21)))
    truth = state_of(header, lines)
    rows = []
    for variant in MUTANTS + CONTROLS:
        ordering, vector = mutate_state(rng, variant, truth, header, lines)
        expected = ref.to_order(truth, ordering)
        fidelity = ref.fidelity(expected, vector)
        results = [_sv_result("ref-lsb", "lsb", truth),
                   _sv_result("ref-msb", "msb", ref.to_order(truth, "msb")),
                   _sv_result("mutant", ordering, vector)]
        report = create_divergence_report(results)
        annotate_divergence_report(report, results)
        flagged, control_flag, verdicts = _flags(report["pairwise_agreement"], "mutant")
        rows.append({"corpus": "statevector-synthetic", "case": index, "n_qubits": n,
                     "variant": variant, "kind": "mutant" if variant in MUTANTS else "control",
                     "equivalent": fidelity >= 1 - FIDELITY_TOLERANCE, "size": 1 - fidelity,
                     "flagged": flagged, "other_pairs_flagged": control_flag,
                     "verdicts": verdicts})
    return rows


def _flags(pairs, target):
    flagged, others, verdicts = False, 0, []
    for p in pairs:
        differs = bool(p["pair_verdict"]["differs"])
        if target in p["simulators"]:
            flagged |= differs
            verdicts.append(p["pair_verdict"]["verdict"])
        else:
            others += differs
    return flagged, others, sorted(set(verdicts))


def probs_dict(p, n_bits, ordering):
    return {c.key_for(i, n_bits, ordering): float(v) for i, v in enumerate(p) if v > 1e-15}


def tv_dicts(a, b):
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def reverse_keys(d):
    out = {}
    for k, v in d.items():
        out[k[::-1]] = out.get(k[::-1], 0) + v
    return out


def swap_key_clbits(d, ordering, a=0, b=1):
    """Keys with clbits a and b exchanged (positions found from the declared ordering)."""
    out = {}
    for k, v in d.items():
        n = len(k)
        pa, pb = (n - 1 - a, n - 1 - b) if ordering == "lsb" else (a, b)
        chars = list(k)
        chars[pa], chars[pb] = chars[pb], chars[pa]
        key = "".join(chars)
        out[key] = out.get(key, 0) + v
    return out


def measured_variant(rng, variant, truth, header, lines):
    """(declared ordering, probability dict over keys in that ordering) of the variant."""
    n = int(round(math.log2(len(truth))))
    p = np.abs(truth) ** 2
    lsb = probs_dict(p, n, "lsb")
    if variant == "undeclared_reversal":
        return "lsb", reverse_keys(lsb)
    if variant == "label_flip":
        return "msb", lsb
    if variant == "qubit_swap":
        return "lsb", swap_key_clbits(lsb, "lsb")
    if variant in ("sign_flip", "deleted_gate", "global_phase", "complex64"):
        _order, vector = mutate_state(rng, variant, truth, header, lines)
        return "lsb", probs_dict(np.abs(vector) ** 2, n, "lsb")
    if variant == "declared_msb":
        return "msb", probs_dict(p, n, "msb")
    if variant == "msb_complex64_phase":
        _order, vector = mutate_state(rng, variant, truth, header, lines)
        return "msb", probs_dict(np.abs(ref.to_order(vector, "msb")) ** 2, n, "msb")
    raise ValueError(variant)


def sample_dict(rng, probs, shots):
    keys = list(probs)
    pv = np.array([probs[k] for k in keys])
    draws = rng.multinomial(int(shots), pv / pv.sum())
    return {k: int(x) for k, x in zip(keys, draws, strict=True) if x}


def measured_case(index):
    """All mutants and controls of one random circuit in measured mode, 14 backends."""
    rng = np.random.default_rng([MASTER_SEED, 2, index])
    n = int(rng.integers(2, 6))
    header, lines = random_circuit(rng, n, int(rng.integers(8, 21)))
    truth = state_of(header, lines)
    p = np.abs(truth) ** 2
    rows = []
    for v_index, variant in enumerate(MUTANTS + CONTROLS):
        ordering, probs = measured_variant(rng, variant, truth, header, lines)
        size = tv_dicts(probs, probs_dict(p, n, ordering))
        results = []
        for b in range(13):
            o = "msb" if b % 2 else "lsb"
            r = np.random.default_rng([MASTER_SEED, 3, index, v_index, b])
            results.append(c.runner_result(f"b{b:02d}", sample_dict(r, probs_dict(p, n, o), 8200),
                                           o, seed=b))
        r = np.random.default_rng([MASTER_SEED, 3, index, v_index, 13])
        results.append(c.runner_result("b13", sample_dict(r, probs, 8200), ordering, seed=13))
        report = c.analyse(results, 8200)
        flagged, others, verdicts = _flags(report["pairwise_agreement"], "b13")
        rows.append({"corpus": "measured-synthetic", "case": index, "n_qubits": n,
                     "variant": variant, "kind": "mutant" if variant in MUTANTS else "control",
                     "equivalent": size <= 1e-9, "size": size, "flagged": flagged,
                     "other_pairs_flagged": others, "verdicts": verdicts})
    return rows


def recorded_files():
    files = sorted((REPO / "experiments").glob("*/results/**/*.json"))
    files.append(REPO / "examples" / "ro-crate-export" / "results.json")
    return [f for f in files if f.is_file()]


def recorded_case(path_str):
    """Mutants of up to three backends of one recorded measured report that differ from at most
    one other backend there; a mutant is detected when a pair of the mutated backend that the
    recorded report does not flag becomes flagged."""
    path = Path(path_str)
    data = json.loads(path.read_text())
    shots = data["n_shots"]
    raws = [r for r in data["raw_results"] if "counts" in r and not r.get("error")]
    base = c.analyse(raws, shots)
    base_flags = {tuple(p["simulators"]) for p in base["pairwise_agreement"]
                  if p["pair_verdict"]["differs"]}
    flag_count = {r["simulator"]: sum(r["simulator"] in f for f in base_flags) for r in raws}
    candidates = [r["simulator"] for r in raws if flag_count[r["simulator"]] <= 1][:3]
    header_lines = [s.strip() for s in data["input_qasm"].split("\n") if s.strip()]
    gate_lines = [s for s in header_lines if not s.startswith(("OPENQASM", "include", "qreg",
                                                               "creg", "measure", "barrier"))]
    keep = [s for s in header_lines if s not in gate_lines and not s.startswith("measure")]
    header = "\n".join(keep) + "\n"
    truth = state_of(header, gate_lines)
    n = int(round(math.log2(len(truth))))
    p = np.abs(truth) ** 2
    rows = []
    name = str(path.relative_to(REPO))
    for b_index, sim in enumerate(candidates):
        res = next(r for r in raws if r["simulator"] == sim)
        ordering = res.get("qubit_ordering", "lsb")
        own_truth = probs_dict(p, n, ordering)
        for v_index, variant in enumerate(MUTANTS):
            rng = np.random.default_rng([MASTER_SEED, 4, zlib.crc32(name.encode()), b_index, v_index])
            new = dict(res)
            counts = res["counts"]
            if variant == "undeclared_reversal":
                new["counts"], implied = reverse_keys(counts), reverse_keys(own_truth)
            elif variant == "label_flip":
                new["qubit_ordering"] = "msb" if ordering == "lsb" else "lsb"
                implied = probs_dict(p, n, ordering)
                own = probs_dict(p, n, new["qubit_ordering"])
                size = tv_dicts(implied, own)
            elif variant == "qubit_swap":
                new["counts"] = swap_key_clbits(counts, ordering)
                implied = swap_key_clbits(own_truth, ordering)
            elif variant == "sign_flip":
                implied = own_truth
            else:
                _o, vector = mutate_state(rng, "deleted_gate", truth, header, gate_lines)
                implied = probs_dict(np.abs(vector) ** 2, n, ordering)
                new["counts"] = sample_dict(rng, implied, sum(counts.values()))
            if variant != "label_flip":
                size = tv_dicts(implied, own_truth)
            results = [new if r["simulator"] == sim else r for r in raws]
            report = c.analyse(results, shots)
            new_pairs = [p for p in report["pairwise_agreement"]
                         if tuple(p["simulators"]) not in base_flags]
            hit, others, verdicts = _flags(new_pairs, sim)
            rows.append({"corpus": "measured-recorded", "case": f"{name}:{sim}", "n_qubits": n,
                         "variant": variant, "kind": "mutant", "equivalent": size <= 1e-9,
                         "size": size, "flagged": hit, "other_pairs_flagged": others,
                         "verdicts": verdicts, "shots": shots})
    return rows


def _task(args):
    kind, arg = args
    if kind == "sv":
        return statevector_case(arg)
    if kind == "m":
        return measured_case(arg)
    return recorded_case(arg)


def score(rows):
    """Per corpus: detection of non-equivalent mutants (overall, by variant, by size band) and
    false flags on controls."""
    out = {}
    for corpus in sorted({r["corpus"] for r in rows}):
        rs = [r for r in rows if r["corpus"] == corpus]
        live = [r for r in rs if r["kind"] == "mutant" and not r["equivalent"]]
        controls = [r for r in rs if r["kind"] == "control"]
        entry = {"mutants": len([r for r in rs if r["kind"] == "mutant"]),
                 "equivalent_mutants": len([r for r in rs if r["kind"] == "mutant" and r["equivalent"]]),
                 "score": c.proportion(sum(r["flagged"] for r in live), len(live)),
                 "by_variant": {}, "by_size": {},
                 "equivalent_flagged": sum(r["flagged"] for r in rs if r["kind"] == "mutant"
                                           and r["equivalent"]),
                 "controls": len(controls),
                 "controls_flagged": c.proportion(sum(r["flagged"] for r in controls),
                                                  len(controls)) if controls else None,
                 "other_pairs_flagged_runs": sum(r["other_pairs_flagged"] > 0 for r in rs)}
        for v in MUTANTS + CONTROLS:
            vs = [r for r in rs if r["variant"] == v]
            if not vs:
                continue
            live_v = [r for r in vs if not r["equivalent"]] if v in MUTANTS else vs
            entry["by_variant"][v] = {"cases": len(vs), "equivalent": len(vs) - len(live_v)
                                      if v in MUTANTS else 0,
                                      "flagged": sum(r["flagged"] for r in live_v),
                                      "of": len(live_v)}
        bands = ([0, 1e-5, 1e-3, 1e-2, 0.05, 0.1, 1.01] if corpus.startswith("statevector")
                 else [0, 1e-9, 0.01, 0.02, 0.05, 0.1, 1.01])
        for lo, hi in zip(bands[:-1], bands[1:], strict=True):
            band = [r for r in live if lo < r["size"] <= hi]
            if band:
                entry["by_size"][f"({lo:g}, {min(hi, 1):g}]"] = {
                    "flagged": sum(r["flagged"] for r in band), "of": len(band)}
        out[corpus] = entry
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--sv-circuits", type=int, default=600)
    ap.add_argument("--measured-circuits", type=int, default=300)
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args(argv)
    cpus = c.set_up_process()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = ([("rec", str(f)) for f in recorded_files()]
             + [("m", i) for i in range(args.measured_circuits)]
             + [("sv", i) for i in range(args.sv_circuits)])
    rows = []
    start = time.time()
    with Pool(args.workers or len(cpus)) as pool:
        for done, rs in enumerate(pool.imap_unordered(_task, tasks), 1):
            rows.extend(rs)
            if done % 100 == 0 or done == len(tasks):
                print(f"{done}/{len(tasks)} cases, {time.time() - start:.0f} s", flush=True)
    result = {"master_seed": MASTER_SEED, "cpus": cpus, "wall_seconds": time.time() - start,
              "score": score(rows)}
    (out / "mutation.json").write_text(json.dumps(result, indent=1, default=float))
    header = ["corpus", "case", "n_qubits", "variant", "kind", "equivalent", "size", "flagged",
              "other_pairs_flagged", "verdicts"]
    lines = [",".join(header)]
    for r in sorted(rows, key=lambda r: (r["corpus"], str(r["case"]), r["variant"])):
        lines.append(",".join(f'"{"|".join(r[h])}"' if h == "verdicts" else f'"{r[h]}"'
                              if h == "case" else str(r[h]) for h in header))
    (out / "mutation_cases.csv").write_text("\n".join(lines) + "\n")
    print(f"wrote {out / 'mutation.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
