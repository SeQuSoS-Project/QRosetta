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

## 2026-10-21, b827905: Kubernetes client loaded only for Kubernetes dispatch

`services/dispatcher.py` used to import `dispatcher_k8s`, which loads `kubernetes` and `boto3`, even in local mode. It now imports it on the first Kubernetes-mode dispatch.

| API process, local mode | Before | After |
|---|---|---|
| `import main` (median of 5) | 1.61 s | 1.36 s |
| Peak RSS after import | 252 MiB | 223 MiB |

These were measured in the API image at 1 CPU. The before figures come from a worktree at `483191f`. Behaviour is unchanged: the dispatch and job tests pass (154 tests).

## 2026-10-21, 06fc7d2: unit suite in parallel

Adding `pytest-xdist==3.6.1` to `tests/requirements.txt` and running CI with `-n auto` cut the suite's wall time, as below. All runs were on an i9-13950HX host.

| Environment | Tests | Serial | 8 workers |
|---|---|---|---|
| API test venv (no Qiskit) | 1,597 | 98 s | 28 s, 3 runs all passing |
| Venv with Qiskit 2.5.2 | 1,649 | 101 s | 31 s, 2 runs all passing |

## 2026-10-21, d0bcab4: module preloading

The page loaded 50 ES modules discovered in 4 import levels. That took 4 sequential request waves over HTTP/2 and 7 over HTTP/1.1. index.html and share.html now list their whole static import graph as `<link rel="modulepreload">`, written by `scripts/build_modulepreload.py`. `tests/unit/test_modulepreload.py` fails when a list is stale.

Time to DOMContentLoaded, in ms, as medians of 7 runs (`scripts/frontend_bench/load_bench.mjs`, headless Chromium, nginx's cache headers):

| Page | Protocol | RTT | Cold, before → after | Warm, before → after |
|---|---|---|---|---|
| index | HTTP/2 | 50 ms | 308 → 159 | 329 → 161 |
| index | HTTP/2 | 150 ms | 822 → 352 | 825 → 354 |
| index | HTTP/1.1 | 50 ms | 626 → 588 | 602 → 535 |
| index | HTTP/1.1 | 150 ms | 1727 → 1552 | 1709 → 1534 |
| share | HTTP/2 | 150 ms | 812 → 330 | 821 → 324 |

Module scripts are deferred, so DOMContentLoaded includes the whole module graph. Over HTTP/1.1 the gain is small, because Chromium opens at most 6 connections per host. The Cloud Run front end serves HTTP/2, so the HTTP/2 rows apply there. The request count is unchanged (52), so no module is fetched twice. Warm loads still revalidate each file (`no-cache`, 304), because there are no content-hashed names that would make longer caching safe.

## 2026-10-21: probability vectors built with `np.fromiter`

`_counts_probability_vector` and the statistical-test rows used to fill numpy arrays one element at a time. They now use `np.fromiter` over the same dictionary lookups. A 14-backend measured report took 2.38 → 2.15 s at 12 bits and 3.87 → 3.57 s at 20 bits (8200 shots, medians of 5, interleaved). The machine was loaded by image builds during these runs, so only the ratio is meaningful. The equivalence check found 150 counts cases with 0 differences (`results/2026-10-21-fromiter-equivalence-counts.log`).

## 2026-10-21: timed and parallel image builds, disabled runners skipped

`scripts/safe_boot.sh` used to build 26 images one after another and print no times. It now behaves as follows:
- It times each build and writes its log to `QR_BUILD_LOG_DIR`.
- It builds `QR_BUILD_JOBS` images at a time (default 1).
- It skips runners that `config.py` marks `enabled: False` (braket, projectq), reading the flag from the freshly built API image. `QR_BUILD_DISABLED=1` builds them anyway.
- `QR_BUILD_ONLY=1` stops after building.

All runs below were on the i9-13950HX host with podman 5.8.2, in a throwaway worktree so that the real `qsimulators-*` tags were untouched. Raw times are in `results/builds/`.

| Rebuild after a `shared/` change (24 images) | Wall time |
|---|---|
| Serial, every layer before `COPY shared` cached | 96 s |
| 4 at a time, every layer before `COPY shared` cached | 46 s |
| Serial, pip layer not cached (new checkout, so new file mtimes) | 1,074 s |

In that last run TorchQuantum took 171 s, Quartz 164 s and cuQuantum 118 s.

I also checked reproducibility. A full reinstall from the lock files in that cold run gave the same `pip freeze` as the existing image for all 19 images that have pip, so the locks reproduce each specimen's Python environment.

## 2026-10-21, de91904: RO-Crate export streamed from the spilled job

`POST /jobs/{id}/export` used to load every batch task into one dict, deep-copy it, build results.json as one string and assemble the ZIP in memory. It now reads one task at a time from the spill files, writes results.json in chunks and streams the ZIP from a temporary file.

The table shows peak RSS growth during the export: VmHWM after `clear_refs`, minus the baseline. It was measured on synthetic tasks of 14 backends × 2^18 amplitudes, about 78 MB of base64 each.

| Export | Before | After |
|---|---|---|
| 1 task, statevectors off | 88 MiB, 0.1 s | 88 MiB, 0.1 s |
| 1 task, statevectors on | 307 MiB, 7.5 s | 104 MiB, 1.2 s |
| 3 tasks, statevectors on | 914 MiB, 43 s | 111 MiB, 3.6 s |
| 6 tasks, statevectors off | 461 MiB | 89 MiB |
| 6 tasks, statevectors on | 1,575 MiB, 134 s | 106 MiB, 7.1 s |
| 12 tasks, statevectors on | not run (about 3.1 GiB, extrapolated) | 112 MiB, 14 s |
| 6 measured tasks (20 bits, 14 × 8200 shots) | 198–213 MiB | 22 MiB |

Before this change, a 25-task 18-qubit playlist could not be exported within the API's 2 GiB limit. It now needs about one task's worth of memory.

The gate exported 290 cases with both versions: 240 crates and 50 error responses, built from 8 jobs produced by the real workers. Each job was exported from 5 report sources with several option sets. ZIP member names and order, member bytes and ZipInfo fields all matched, with date_time excluded: 14,624 members, 0 differences. The gate was run again after merging the fuzzing fixes, with the same result.

## 2026-10-21: rendering a playlist circuit reads one task

`POST /jobs/{id}/publication/render` and `GET /jobs/{id}/publication/artifacts`, given a `task`, used to load every spilled task of the playlist and keep one. They now read only that task. On a 25-task 18-qubit playlist, that is one task's report (about 78 MB with statevectors) instead of all 25. `tests/unit/test_render_task_loading.py` asserts that exactly one task file is read.

## 2026-10-21: end to end on the live stack

The same jobs were run through nginx on the local stack at `96ab2a8`, with 13 backends: cuQuantum was left out to keep the GPU idle. The API container ran with its compose quota of 0.5 CPU. The only change between the two sets of runs was the API image: tonight's (`96ab2a8`) or the previous one (`localhost/qsimulators-api:latest`, built from `4dc46aa`). Each case ran 3 times, using `e2e.py`. "After the last runner" is the time from the last runner's `process_finished_at` to the job reading completed, which is mostly the analysis.

| Job (60-gate random circuit, 7 qubits) | Submit to done, before → after | After the last runner, before → after |
|---|---|---|
| Measured, 8200 shots, seed 5 | 77.4–78.3 s → 10.4–10.8 s | 73.1–73.8 s → 5.8–6.2 s |
| Statevector | 7.2–7.3 s → 4.7–5.3 s | 3.7–3.9 s → 1.1–1.5 s |

One more seeded measured job was run on each API (`save_report.py`). The runners' counts were identical, and so was every field of `divergence_report`.

On the same stack, `tests/integration` passed 31 of 31 non-contract tests and, with cuQuantum removed from the contract list, 7 of 7 contract tests. Raw lines are in `results/live/`.
