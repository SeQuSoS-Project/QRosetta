"""Write the divergence analysis of the harness_bench equivalence corpora as canonical JSON lines.

Usage: python dump_analysis.py <out.jsonl> [n_counts] [n_statevector]
The corpora and their seed are those of scripts/harness_bench/equivalence.py. Each line holds one
case: its permutation-search results for the first four backends against every backend, and the
whole report. Run in two images and diff the files.
"""
import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness_bench"))
logging.disable(logging.CRITICAL)

import equivalence  # noqa: E402
from services.analysis import divergence  # noqa: E402


def canonical(value):
    return json.dumps(value, sort_keys=True, default=repr, allow_nan=True)


def counts_cases(rng, n_cases):
    for label, results, shots in equivalence.counts_corpus(rng, n_cases):
        search = [divergence._best_counts_qubit_permutation_metrics(results[i]["counts"], results[j]["counts"])
                  for i in range(min(len(results), 4)) for j in range(len(results))]
        yield {"label": label, "search": search, "report": divergence.create_counts_report(results, shots)}


def statevector_cases(rng, n_cases):
    for label, results in equivalence.statevector_corpus(rng, n_cases):
        vectors = [divergence.parse_statevector(r["statevector"]) for r in results]
        vectors = [v / np.linalg.norm(v) for v in vectors]
        search = [divergence._best_statevector_qubit_permutation_metrics(vectors[i], vectors[j], 1e-5, 1e-6)
                  for i in range(min(len(vectors), 4)) for j in range(len(vectors))
                  if len(vectors[i]) == len(vectors[j])]
        yield {"label": label, "search": search, "report": divergence.create_divergence_report(results)}


def main():
    out = Path(sys.argv[1])
    n_counts = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    n_statevector = int(sys.argv[3]) if len(sys.argv) > 3 else 150
    rng = np.random.default_rng(20261021)
    totals = {"counts": 0, "statevector": 0}
    with out.open("w") as handle:
        for kind, cases in (("counts", counts_cases(rng, n_counts)),
                            ("statevector", statevector_cases(rng, n_statevector))):
            for case in cases:
                handle.write(canonical(case) + "\n")
                totals[kind] += 1
    print(json.dumps({"python": sys.version.split()[0], "numpy": np.__version__, **totals}))


if __name__ == "__main__":
    main()
