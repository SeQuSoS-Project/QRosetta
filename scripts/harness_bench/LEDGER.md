# Harness speed and efficiency ledger

This file lists every change made to the speed or efficiency of Quantum Rosetta's own code. Each entry gives the commit, the change, before and after medians with their environment, and the evidence that results did not change.

Simulator and compiler code, their images, and the timed windows (CLAUDE.md §3.4) are never changed for speed.

Unless an entry says otherwise, timings were taken inside the API image (`localhost/qsimulators-api`: Python 3.10.20, numpy 1.26.4, scipy 1.14.0, OpenBLAS 1 thread). The container ran under a 1-CPU quota on an i9-13950HX, not pinned to one core. Reference and new code alternated, 5 samples each. Raw samples are in `results/`.

## 2026-10-21, b22e78b: permutation searches scored in one array pass

The analysis searches every qubit permutation of each pair of backends, up to 7 qubits or bits. It used to do this in a Python loop of up to 5,038 iterations per pair. It now computes every permutation from one cached index table, using the same floating-point operations as before.

| Case (14 backends, 91 pairs) | Before (s) | After (s) | Speedup |
|---|---|---|---|
| Measured report, 7 bits, 8200 shots | 49.40 | 2.93 | 16.8× |
| Measured report, 6 bits, 8200 shots | 4.33 | 0.76 | 5.7× |
| Statevector report, 7 qubits | 1.87 | 0.47 | 4.0× |
| Statevector report, 6 qubits | 0.257 | 0.069 | 3.7× |
| Measured report, 12 bits (search not run) | 1.71 | 1.67 | 1.0× |
| Statevector report, 12 qubits (search not run) | 0.008 | 0.008 | 1.0× |

On Rahti and in compose the API has 0.5 CPU, so it would take about twice these times. Before this change, a 7-bit measured analysis held the API's only worker for about 100 s.

Equivalence was checked with `equivalence.py` against `stable-pre-roihu`:
- 200 counts cases, 0 differences, in both the search results and the full report (`results/2026-10-21-b22e78b-equivalence-counts.log`);
- 100 statevector cases, 0 differences (`results/2026-10-21-b22e78b-equivalence-statevector.log`).

Two details had to match exactly:
- the Hellinger norm uses a freshly allocated vector, because OpenBLAS `dot` can change the last bit when a row view is aligned differently;
- JS is squared as a numpy scalar, because array squaring rounds differently from scalar squaring.

`ANALYSIS_VERSION` is unchanged, because the outputs are identical.

CLAUDE.md §13.6 had claimed the old search took 2.8 s at 6 qubits and 17 s at 7. Measured, it took 0.26 s and 1.87 s on the statevector side. The measured-mode search, at 4.3 s and 49 s, was the one that was expensive, and §13.6 did not mention it.

## 2026-10-21, b22e78b: submission validation off the event loop

`validate_request` is pure Python and took 0.29–0.33 s for a 125 kB circuit. It used to run on the event loop for `/compare`, `/compare_measured`, `/run_batch_suite`, `/experiments` and the Quirk route. A playlist validated each task in turn, so 100 large tasks blocked every other request, polls included, for about 30 s. Validation now runs in a worker thread. `tests/unit/test_submission_off_loop.py` holds a 1 s validation and asserts that the loop never stalls for more than 0.5 s.
