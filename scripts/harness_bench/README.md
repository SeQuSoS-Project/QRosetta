# Harness benchmarks

Speed and memory of Quantum Rosetta's own code: the API, the analysis, preparation and packaging. Simulator and compiler timings are not measured here.

`LEDGER.md` lists every change made for speed or efficiency, with before and after numbers, the environment, and the evidence that results did not change.

## Running

Both scripts run inside the API image, so they use the same Python, numpy, scipy and OpenBLAS as the deployed API. They mount the working tree read-only. `run.sh` extracts the analysis package of a reference git ref, and each script loads that package beside the working tree's.

```bash
# results of the working tree and stable-pre-roihu must be identical
scripts/harness_bench/run.sh stable-pre-roihu equivalence.py 200            # counts and statevector
scripts/harness_bench/run.sh stable-pre-roihu equivalence.py 100 statevector

# timings: reference and working tree alternate, 5 repeats each, medians
scripts/harness_bench/run.sh stable-pre-roihu bench.py 5 > results/<date>-<sha>.json
scripts/harness_bench/run.sh stable-pre-roihu bench.py 5 counts_report_7b_14b_8200
```

The following environment variables are optional:

| Variable | Default | Sets |
|---|---|---|
| `QR_BENCH_IMAGE` | `localhost/qsimulators-api:latest` | the image the scripts run in |
| `QR_BENCH_CPUS` | 1 | the container's CPU quota |
| `QR_BENCH_MEMORY` | 4g | the container's memory limit |
| `QR_BENCH_WORK` | `~/.tmp/harness_bench` | where the reference package is extracted |

## What equivalence means here

`equivalence.py` builds a seeded corpus of counts and statevector results, including the shapes below. It compares the reference and new outputs as canonical JSON, both for the permutation search on its own and for the whole report.

Counts corpus:

| Shape | Contents |
|---|---|
| sparse | Dirichlet sample, most outcomes rare |
| dense | Dirichlet sample, outcomes spread evenly |
| GHZ | two outcomes, so many exact ties |
| uniform | every outcome equally likely |
| single outcome | one outcome only |
| permuted, bit-reversed | copies of one backend with bits reordered |
| zero-count keys | keys present with a count of 0 |
| float counts | non-integer count values |
| unequal shots | backends with different shot totals |

Statevector corpus:

| Shape | Contents |
|---|---|
| random | random complex amplitudes |
| basis | one basis state |
| GHZ | two equal amplitudes |
| uniform | every amplitude equal |
| real | real amplitudes only |
| permuted, bit-reversed | copies of one backend with qubits reordered |
| global phase | copies with a phase factor |
| complex64-rounded | copies rounded to single precision |
| unnormalised | copies with norm slightly off 1 |

A change to the analysis is accepted only with 0 differences: every value must be bit-identical, not merely close.

Exact matching depends on details of numpy that a reader might not expect:
- OpenBLAS `dot` can differ in the last bit depending on how the array is aligned in memory.
- A numpy scalar raised to the power 2 can round differently from an array raised to the power 2.

The new code reproduces both of these behaviours of the old code.

## Circuit preparation

`prep_equivalence.py` prepares every bundled circuit, every algorithm template at several sizes and a set of circuits that preparation refuses, directly in a thread and through the preparation worker (`services/prep_worker.py`). Results must be equal, and a raised exception must have the same type and message. Cases that the worker stops at its memory or time limit are listed and not compared. It needs no reference package:

```bash
podman run --rm --memory 6g --cpus 2 -v "$PWD":/repo:ro -w /repo/rosetta-api \
  -e PYTHONPATH=/repo/rosetta-api:/repo/shared localhost/qsimulators-api:latest \
  python ../scripts/harness_bench/prep_equivalence.py
```
