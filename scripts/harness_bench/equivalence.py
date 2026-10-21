"""Compare the divergence analysis of a reference checkout with the working tree on one corpus.

Usage: python equivalence.py <ref_package_dir> [n_cases] [counts,statevector]
<ref_package_dir> holds the reference ``divergence`` package (see run.sh). Every report is
compared as canonical JSON; any difference is printed and the exit status is 1.
"""
import importlib.util
import json
import logging
import sys
from pathlib import Path

import numpy as np

logging.disable(logging.CRITICAL)

from services.analysis import divergence as new  # noqa: E402


def load_reference(package_dir):
    init = Path(package_dir) / "__init__.py"
    spec = importlib.util.spec_from_file_location("ref_divergence", init,
                                                  submodule_search_locations=[str(package_dir)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["ref_divergence"] = module
    spec.loader.exec_module(module)
    return module


def canonical(value):
    return json.dumps(value, sort_keys=True, default=repr, allow_nan=True)


def permute_key(key, permutation):
    return "".join(key[source] for source in permutation)


def counts_corpus(rng, n_cases):
    shapes = ["sparse", "dense", "ghz", "uniform", "single", "permuted", "reversed", "zeros", "floats",
              "unequal_shots"]
    for case in range(n_cases):
        n = int(rng.integers(1, 9))
        k = int(rng.choice([2, 3, 5, 14]))
        shape = shapes[case % len(shapes)]
        shots = int(rng.choice([20, 1000, 8200]))
        if shape == "ghz":
            p = np.zeros(2 ** n)
            p[0] = p[-1] = 0.5
        elif shape == "uniform":
            p = np.full(2 ** n, 1 / 2 ** n)
        elif shape == "single":
            p = np.zeros(2 ** n)
            p[int(rng.integers(0, 2 ** n))] = 1.0
        else:
            p = rng.dirichlet(np.full(2 ** n, 0.1 if shape == "sparse" else 2.0))
        results = []
        base = None
        for b in range(k):
            backend_shots = shots if shape != "unequal_shots" or b % 2 else int(rng.choice([50, 400]))
            sample = rng.multinomial(backend_shots, p)
            counts = {format(i, f"0{n}b"): int(v) for i, v in enumerate(sample) if v}
            if shape == "zeros":
                counts[format(int(rng.integers(0, 2 ** n)), f"0{n}b")] = counts.get(
                    format(0, f"0{n}b"), 0)
            if shape == "floats":
                counts = {key: value * 1.0 + 0.25 for key, value in counts.items()}
            if base is None:
                base = counts
            elif shape == "permuted" and b % 3 == 1:
                permutation = tuple(int(x) for x in rng.permutation(n))
                counts = {permute_key(key, permutation): value for key, value in base.items()}
            elif shape == "reversed" and b % 2:
                counts = {key[::-1]: value for key, value in base.items()}
            results.append({"simulator": f"sim{b}", "counts": counts,
                            "qubit_ordering": "lsb" if b % 2 else "msb", "runner_seed": b})
        yield f"counts case={case} n={n} k={k} shape={shape} shots={shots}", results, shots


def compare_counts(ref, n_cases, rng):
    failures = 0
    for label, results, shots in counts_corpus(rng, n_cases):
        for i in range(min(len(results), 4)):
            for j in range(len(results)):
                a = ref._best_counts_qubit_permutation_metrics(results[i]["counts"], results[j]["counts"])
                b = new._best_counts_qubit_permutation_metrics(results[i]["counts"], results[j]["counts"])
                if canonical(a) != canonical(b):
                    failures += 1
                    print(f"DIFF search {label} pair=({i},{j})\n  ref={a}\n  new={b}")
        a = ref.create_counts_report(results, shots)
        b = new.create_counts_report(results, shots)
        if canonical(a) != canonical(b):
            failures += 1
            print(f"DIFF report {label}")
    return failures


def random_state(rng, n, shape):
    size = 2 ** n
    if shape == "basis":
        sv = np.zeros(size, dtype=complex)
        sv[int(rng.integers(0, size))] = 1
    elif shape == "ghz":
        sv = np.zeros(size, dtype=complex)
        sv[0] = sv[-1] = 2 ** -0.5
    elif shape == "uniform":
        sv = np.full(size, size ** -0.5, dtype=complex)
    elif shape == "real":
        sv = rng.normal(size=size).astype(complex)
    else:
        sv = rng.normal(size=size) + 1j * rng.normal(size=size)
    return sv / np.linalg.norm(sv)


def statevector_corpus(rng, n_cases):
    from qrosetta_commons.helpers import encode_statevector
    shapes = ["random", "basis", "ghz", "uniform", "real", "permuted", "reversed", "phase", "complex64",
              "unnormalised"]
    for case in range(n_cases):
        n = int(rng.integers(0, 9))
        k = int(rng.choice([2, 3, 5, 14]))
        shape = shapes[case % len(shapes)]
        base = random_state(rng, n, shape if shape in ("basis", "ghz", "uniform", "real") else "random")
        results = []
        for b in range(k):
            sv = base.copy()
            if shape == "permuted" and b % 2 and n > 1:
                sv = sv.reshape([2] * n).transpose(rng.permutation(n)).reshape(-1)
            elif shape == "reversed" and b % 2 and n > 1:
                sv = sv.reshape([2] * n).transpose(list(reversed(range(n)))).reshape(-1)
            elif shape == "phase":
                sv = sv * np.exp(1j * rng.uniform(-np.pi, np.pi)) if b % 2 else sv
            elif shape == "complex64":
                sv = sv.astype(np.complex64).astype(complex)
            elif shape == "unnormalised":
                sv = sv * (1 + rng.uniform(-1e-3, 1e-3))
            elif shape == "random" and b % 3 == 2:
                sv = random_state(rng, n, "random")
            results.append({"simulator": f"sim{b}", "statevector": encode_statevector(sv),
                            "qubit_ordering": "lsb" if b % 2 else "msb"})
        yield f"statevector case={case} n={n} k={k} shape={shape}", results


def compare_statevectors(ref, n_cases, rng):
    failures = 0
    for label, results in statevector_corpus(rng, n_cases):
        vectors = [new.parse_statevector(r["statevector"]) for r in results]
        vectors = [v / np.linalg.norm(v) for v in vectors]
        for i in range(min(len(vectors), 4)):
            for j in range(len(vectors)):
                if len(vectors[i]) != len(vectors[j]):
                    continue
                a = ref._best_statevector_qubit_permutation_metrics(vectors[i], vectors[j], 1e-5, 1e-6)
                b = new._best_statevector_qubit_permutation_metrics(vectors[i], vectors[j], 1e-5, 1e-6)
                if canonical(a) != canonical(b):
                    failures += 1
                    print(f"DIFF search {label} pair=({i},{j})\n  ref={a}\n  new={b}")
        a = ref.create_divergence_report(results)
        b = new.create_divergence_report(results)
        if canonical(a) != canonical(b):
            failures += 1
            print(f"DIFF report {label}")
    return failures


def main():
    ref = load_reference(sys.argv[1])
    n_cases = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    rng = np.random.default_rng(20261021)
    kinds = sys.argv[3].split(",") if len(sys.argv) > 3 else ["counts", "statevector"]
    total = 0
    for kind, compare in (("counts", compare_counts), ("statevector", compare_statevectors)):
        if kind in kinds:
            failures = compare(ref, n_cases, rng)
            print(f"{kind}: {n_cases} cases, {failures} differences", flush=True)
            total += failures
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
