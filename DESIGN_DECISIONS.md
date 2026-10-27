# Design decisions

This file lists the rules that Quantum Rosetta's measurement instrument and analysis follow, each with the evidence that settled it. Several of these boundaries were moved back and forth during development; each entry records the rule in force and the measurement or failure that fixed it. A rule changes only with new empirical evidence, and that evidence is recorded here.

Dates are when the evidence was collected (YYYY-MM-DD). Where a unit test enforces a rule, the test file is named.

## Contents

- [Terms](#terms)
- [Timing and CPU](#timing-and-cpu)
- [Memory](#memory)
- [Scheduling, isolation and job handling](#scheduling-isolation-and-job-handling)
- [Simulator configuration](#simulator-configuration)
- [Sampling, seeds and statistics](#sampling-seeds-and-statistics)
- [Agreement analysis](#agreement-analysis)
- [Circuit handling and preprocessing](#circuit-handling-and-preprocessing)
- [Compile-only services](#compile-only-services)
- [Provenance and reproducibility](#provenance-and-reproducibility)
- [Security and accounts](#security-and-accounts)
- [Interface and API behaviour](#interface-and-api-behaviour)
- [Upstream behaviour not worked around](#upstream-behaviour-not-worked-around)

## Terms

A *runner* is the container that wraps one simulator SDK; a *backend* is a runner at one optimisation level. Every runner measures through the same sequence in [`shared/qrosetta_commons/helpers.py`](shared/qrosetta_commons/helpers.py) (`run_statevector_job` / `run_measured_job`):

```
check_qubits_limit -> t0 -> compile_fn -> t1              (compilation_time)
serialize_fn                                              (provenance, outside the window)
MemoryMonitor + gc.collect() -> pre_execute_fn -> probe -> t2 -> execute_fn -> t3 -> probe   (simulation_time)
postprocess_fn                                            (shaping, outside the window)
```

A runner supplies the callbacks (`compile_fn`, `execute_fn`, `pre_execute_fn`, `postprocess_fn`) and never writes the timing itself. Agreement is pairwise: every pair of backends is compared, and there is no consensus computation. Abbreviations: F = fidelity, TV = total variation distance, JS = Jensen–Shannon divergence (nats), BY = Benjamini–Yekutieli, BH = Benjamini–Hochberg, FWER = family-wise error rate.

## Timing and CPU

### Shots vs histogram

*Rule.* Drawing shots / executing is inside `t2..t3`; tallying into a histogram, `get_counts()`, relabelling keys is `postprocess_fn`. Where an SDK fuses sampling and tallying in one call (qibo `frequencies`, qrisp `run`, quimb `simulate_counts`, Aer C++ counts) it stays inside and is noted in `preprocessing_applied`.

*Evidence (2026-08-18).* Tallying alone was 9–39% of `simulation_time` for five runners. [`rosetta-api/tests/unit/test_counts_histogram_boundary.py`](rosetta-api/tests/unit/test_counts_histogram_boundary.py) fails on `get_counts(`, `Counter(`, `readout_counts` in any `execute_fn`.

### Compilation

*Rule.* Parsing, transpiling, rebasing, optimisation passes, and building the executable object (PennyLane tape + `dev.preprocess()`) are `compile_fn`.

*Evidence.* PennyLane previously built its tape inside `execute_fn`, charging optimisation passes to simulation for two backends only.

### Conversion outside the simulation call

*Rule.* The Qulacs, QuEST, qsim, Qiskit and cuQuantum adapters split the SDK call at its native routine. Conversion (`tk_to_qulacs`/`tk_to_quest` + backend checks; `QSimCircuit` + `translate_cirq_to_qsim`; Aer `_compile` + `assemble_circuits` + `generate_aer_config` in [`qrosetta_commons.aer_split`](shared/qrosetta_commons/aer_split.py)) is in `compile_fn`. `execute_fn` = state allocation + apply / `qsim_simulate_fullstate` / `qsim_sample_final` or per-shot `qsim_sample` / Aer `_execute_circuits`, with the SDK's seed handling. Result objects and global-phase restore are in `postprocess_fn` (QuEST measured keeps the phase before sampling). Each adapter pins the SDK version whose call it reproduces (`require_distribution_version`, `aer_split.require_aer`). [`rosetta-api/tests/unit/test_conversion_boundary.py`](rosetta-api/tests/unit/test_conversion_boundary.py) fails on a converting call or any loop over something other than `range()` in `execute_fn` and its callees (Qulacs measured: the readout bits through `implicit_qubit_permutation` are found in `compile_fn`). Braket and ProjectQ (disabled) are unchanged.

*Evidence (2026-10-02).* Old vs new on the [`scripts/adapter_paths/compare_paths.py`](scripts/adapter_paths/compare_paths.py) corpus (random qelib1 circuits, 1–10 qubits, opt 0–2, preprocessing on/off, measured with seeds 0/7/123456789 and mid-circuit for qsim): 0 differences in statevector bytes, counts and executed text. Cases = circuit × opt level × preprocessing, from ~350 distinct circuits of ≤ 40 gates and ≤ 10 qubits; qulacs 1,500, quest 1,500, qsim 2,200, qiskit 1,700, cuquantum 1,080 cases; many measured cases are identical refusals. A deep set of 24 statevector + 16 measured cases per backend, 500–3,000 gates, ≤ 16 qubits: 0 differences. Measured 4q × 2,200 gates, simulation ms old → new: qulacs 103 → 2.4, quest 35.9 → 2.6, qsim 49.8 → 1.9, qiskit 29.9 → 8.6, cuquantum 47.2 → 17.8. qsim measured totals −24% (record assembly now in postprocess); Qulacs QFT-16 measured total −17% (the old call copied and phase-corrected the statevector). A later timing check found that Qulacs measured still kept ~4–10 µs/gate of `_measured_bits` in the window (24.4 ms vs 3.5 ms statevector at 2,200 gates); fixed. Medians of 7 runs, 4q × 2,200 gates, simulation ms old → new: qulacs 28.1 → 2.2, quest 28.1 → 2.3, qsim 33.4 → 1.3, qiskit 36.6 → 1.9, cuquantum 49.6 → 12.5; totals within 3%. QFT-16 qsim simulation 15.1 → 4.0 ms. Before the split, 10–13 µs/gate of conversion sat inside the window.

### Warm-up caches

*Rule.* A cache the warm-up fills that would skip real work in the timed run is cleared in `pre_execute_fn` (quimb/cotengra optimisers).

*Evidence (2026-08-18).* The quimb timed run was 0.03–0.09 s cached vs 1.1–1.3 s cold at 14 qubits × 14 layers.

### Timing repeats

*Rule.* `timing_repeats` (1–10): after one warm-up, each repeat re-runs compile and execute; reported times are medians, with per-repeat samples, mean and stdev; memory and outputs come from the first repeat; the hard timeout covers all repeats.

*Evidence.* Single-sample timings cannot support performance claims: qrisp varied 8× across runs.

### CPU

*Rule.* `cpu_time_sec` = getrusage over the whole isolated process (start, imports, warm-up, timed run); `simulation_cpu_time_sec` = `process_time()` over `t2..t3`.

*Evidence.* A child that did no simulation reported 3.5 s CPU.

### Threads

*Rule.* `OMP/MKL/OPENBLAS/NUMEXPR/NUMBA_NUM_THREADS=1` for every runner in Compose and in Kubernetes Jobs; recorded as `thread_env`.

*Evidence.* Unpinned under `cpus: 0.5`, quest took 46–53 s on an 8-qubit circuit (2 ms pinned) and quimb was OOM-killed.

### CPU quota

*Rule.* Each runner container or Job has a 1.0-CPU quota (Compose `cpus: "1.0"`; Kubernetes requests 200m / limits 1000m, 5:1). Every window records `compilation_throttled_sec` / `simulation_throttled_sec` (cgroup `cpu.stat` throttled_usec read just outside the window), `simulation_involuntary_switches_samples`, `simulation_cpus`, and per process `cpu_environment` (CPU model, quota, affinity, `cpu_max_mhz` per CPU used). The UI tags a throttled run. The probe is `WindowProbe` in [`shared/qrosetta_commons/cpu.py`](shared/qrosetta_commons/cpu.py).

*Evidence (2026-10-01).* Qulacs in its own image, 10 timed runs × 3. Under 0.5 CPU, QFT-16 median 0.168 s, CV 19%, about 60% of the window throttled; unthrottled 0.060 s, CV 0.6%. QFT-12 under 0.5 CPU: CV 104% (6.8 ms vs 59 ms, the 50 ms quota stall). At 1.0 CPU single-threaded runs are never throttled (0 s, CV 0.5–2%); qrisp QFT-16 0.082 → 0.027 s.

### Hybrid cores

*Rule.* Runners are not pinned to a core type; the core is recorded (`simulation_cpus`, `cpu_environment.cpu_max_mhz`) and the user manual tells users to check it. Rootless podman has no cpuset controller, so pinning is not available locally.

*Evidence.* On an i9-13950HX, qulacs on an E-core (4.0 GHz max) vs a P-core (5.3–5.5 GHz): QFT-16 0.088 vs 0.060 s, QFT-12 12.2 vs 6.8 ms.

### Work outside the process

*Rule.* quimb's cotengra path search runs in-process: the runner maps `parse_parallel_arg('auto')` to no pool in every loaded cotengra module (cotengra 0.8.2 pinned); the search is otherwise quimb's default `auto-hq`. Every result records `simulation_cgroup_cpu_time_sec` (container CPU over the window); the UI tags a run "outside process" when it exceeds `simulation_cpu_time_sec` by ≥ 5 ms and ≥ 10%.

*Evidence (2026-10-01).* quimb QFT-16 with cotengra's default `parallel="auto"`: container CPU 4.43 s vs process CPU 0.48 s over a 4.46 s window, i.e. ~90% of the work in a forked worker whose CPU and memory were unmeasured. `AutoHQOptimizer(parallel=False)` alone was not enough: nested `random_greedy_optimize` calls inside `build_divide` create their own pool. With the module-level mapping, 6/6 runs had wall = process CPU = container CPU (e.g. 1.661/1.658/1.658 s) and no forked worker; the statevector equalled the pooled one to 1.5e-17.

## Memory

Units are MiB (1024²) throughout, although field names say `_mb`.

### Memory

*Rule.* `memory_usage_mb` = kernel VmHWM − baseline RSS over the simulation window (VmHWM reset via `/proc/self/clear_refs` on entry); `process_peak_rss_mb` = the simulating process's own VmHWM over its whole life. Fallback sampling is labelled in `memory_method`.

*Evidence (2026-08-18).* 10 ms sampling reported 0 MiB for a 32 MiB, 5 ms allocation; getrusage in a spawned child inherited the parent worker's 425 MiB.

### Mem Delta and allocator reuse

*Rule.* `memory_usage_mb` is left as the VmHWM delta; it can read near 0 when the warm-up's freed memory is reused (documented in the tooltip).

*Evidence.* A fixed `MALLOC_MMAP_THRESHOLD_=131072` made every allocation visible but slowed pennylane-default 3.3× (QFT-like 16q: 0.20 → 0.66 s), so it was rejected.

### Runner memory and nested gate calls

*Rule.* Every runner container has 1G locally (Kubernetes limit 1Gi). The API rejects circuits whose expansion makes more than 4,096 applications of user-defined gates from inside gate definitions (`MAX_NESTED_GATE_CALLS`, `limits.max_nested_gate_calls`; top-level calls not counted), as well as more than 200,000 gate applications ([`rosetta-api/services/validator.py`](rosetta-api/services/validator.py)). Bundled circuits are exempt.

*Evidence (2026-10-02).* 2-qubit binary-nested definitions, full runs (warm-up + timed) through the API, preprocessing off, `process_peak_rss_mb`: depth 11 (4,094 nested calls) PennyLane 704–709, cuquantum 585, qiskit 559; depth 12 (8,190) PennyLane 1,088–1,089, qiskit 889; depth 13 OOM-killed qiskit and both PennyLane runners at 512M. 8,192 top-level calls of one definition: PennyLane 341, cuquantum 640, qiskit 437. pytket keeps a box per application of a nested definition.

### API memory and job retention

*Rule.* The API container has 2G (Kubernetes limit 2Gi). Untruncated reports are pickled to `QROSETTA_JOB_SPILL_DIR` ([`rosetta-api/services/job_store.py`](rosetta-api/services/job_store.py)) instead of held in the worker. Batch tasks are spilled one by one as they finish, and `GET /jobs/{id}/report` streams JSON task by task. Experiments write result files per cell and keep only the fields the summary tables read; the bundle is `<spill>/<job>/bundle.zip`. Pickling, circuit preparation (the pytket round-trip), JSON encoding and ZIP building run in threads.

*Evidence.* One 18-qubit 14-backend statevector job peaks at 424 MiB in the API process; the 512 MiB worker was OOM-killed 3 times in 32 minutes under shared load and every in-memory job returned 404. 2026-10-07: 10 synthetic 18-qubit tasks (14 × 5.6 MB statevectors) added 751 MiB peak RSS before the change and 79 MiB after; 25 tasks add 80 MiB, and a 1.87 GB report download 156 MiB. Preparing a 9,900-call gate circuit blocked every request for 3.2 s locally (≈7 s at 0.5 CPU). 2026-10-21: `POST /jobs/{id}/export` streams from a spilled job: peak RSS growth for 6 tasks × 14 backends × 2^18 amplitudes with statevectors 1,575 → 106 MiB (134 → 7 s), without statevectors 461 → 89 MiB; crates content-identical on 290 cases.

## Scheduling, isolation and job handling

### One run per runner at a time

*Rule.* Each runner process executes one run at a time (`RUNNER_MAX_CONCURRENT`, default 1); `queue_wait_sec` is recorded and the hard timeout starts after the wait.

*Evidence.* Concurrent runs shared the 0.5-CPU quota (identical runs varied 2×) and two concurrent children exceeded 512 MiB (cirq SIGKILL).

### Cancelled runs and the execution slot

*Rule.* When the task awaiting `run_isolated` is cancelled, the parent SIGKILLs the child and its process group within one 0.2 s poll, waits up to `CANCEL_KILL_WAIT_SEC` (10 s) for it to be reaped, then re-raises; `ExecutionSlots` releases the slot only after that, and the cancelled run's result is discarded. Runs that are not cancelled take the unchanged path. Applies to runners and compile-only services; the one-job CLI path (Kubernetes/Slurm) has no slot. A worker killed outright (gunicorn SIGKILL after graceful_timeout, OOM kill) takes its child with it: the child's first act, before its process group, affinity, SDK import and warm-up, is `prctl(PR_SET_PDEATHSIG, SIGKILL)` plus a `getppid` check against the spawning worker's pid. The signal follows the forking thread, the executor thread that stays blocked in `_run_isolated_blocking` until the child returns or is killed. Subprocesses of the child are not killed in that case (staq and Synthetiq binaries; Quartz sets its own PDEATHSIG).

*Evidence (2026-10-27).* Before the change, cancelling a 30 s run released the slot at once and the next run started with the cancelled child alive (`rosetta-api/tests/unit/test_slot_cancellation.py`, 4 of 5 failing on the old code); after, the child is reaped 0.19–0.24 s after the cancel (Python 3.10 runner image and 3.12), and the next run never sees it. Recorded times old → new over 3 alternated rounds of 15 runs: compilation 1.098 → 1.096 ms, simulation 15.74 → 15.98 ms (median of round medians), identical result keys and statevector. With fastapi 0.115/uvicorn 0.30 a dropped client connection does not cancel the handler; a graceful-shutdown timeout does. When the worker that spawned a run was killed mid-run, the child was still alive 3 s later on the old code (6 of 6, Python 3.12 and the 3.10 qulacs image) and gone within 5 ms with the parent-death signal ([`rosetta-api/tests/unit/test_parent_death.py`](rosetta-api/tests/unit/test_parent_death.py)). Old → new over 3 alternated rounds of 15 runs with timing_repeats 3: compilation 1.052 → 1.043 ms, simulation 15.39 → 15.28 ms, whole-process CPU 160.5 → 161.1 ms (the old code's own range 160.2–161.1 ms), process peak RSS 45.39 → 45.40 MiB; the added call costs 27 µs of CPU and no memory.

### Exclusive runs and overlap

*Rule.* `exclusive` (request field / config checkbox): every backend runs in its own phase, admitted only when no other dispatch runs on the server (the gate in [`rosetta-api/services/run_registry.py`](rosetta-api/services/run_registry.py)); results record `exclusive`, `exclusive_wait_sec`. Every local result records `overlapping_runs` (own job) and `server_overlapping_runs` (other jobs). Default dispatch stays concurrent.

*Evidence (2026-10-01).* A Sequential QFT-16 next to two other jobs: qiskit 1.49× slower with `concurrent_runs=1`, 0 throttling, same `cpu_max_mhz`; busy hyperthread siblings gave 1.5–2× with all checks passing. Concurrent vs Sequential QFT-20: 2.3–3.3×, order flipped.

### concurrent_runs

*Rule.* `concurrent_runs` counts the runs of every dispatch wave in flight beside the run's own wave (`dispatch_wave`); measured sampled and native groups count each other.

*Evidence (2026-10-07).* Each group counted only its own wave.

### Overlap and phases

*Rule.* `overlapping_runs` uses the runner's `process_started_at`/`process_finished_at`. Measured runner groups share one phase plan (`effective_runner_phases`, recorded in crates).

*Evidence.* "Sequential" ran the two groups in parallel; response transfer counted as overlap.

### Kubernetes job slots

*Rule.* In Kubernetes mode (CSC Rahti) at most `K8S_MAX_CONCURRENT_JOBS` (`QROSETTA_K8S_MAX_CONCURRENT_JOBS`, 3 on Rahti) runner/compiler Jobs exist at a time across the API process (`dispatcher_k8s.JOB_SLOTS` in [`rosetta-api/services/dispatcher_k8s.py`](rosetta-api/services/dispatcher_k8s.py)); a Job is created only when a slot is free, so its deadline starts then. The wait is `queue_wait_sec`, capped at `RUNNER_QUEUE_MAX_WAIT_SEC`; reports record `k8s_job_slots`. A run that never gets a slot, or whose pod the quota refuses until its timeout (read from the Job's FailedCreate events), is `timeout` + `never_started`, not `offline`. The setting is read only from `QROSETTA_K8S_MAX_CONCURRENT_JOBS`; a bare `K8S_MAX_CONCURRENT_JOBS` is ignored.

*Evidence (2026-10-07).* The project quota caps `limits.cpu` at 4; API 500m + runner Jobs at 1000m leave room for 3 pods. With all 14 Jobs created at once the rest were refused (`exceeded quota ... limits.cpu`), retried with backoff and hit their deadline before starting; quimb and qsim were reported offline in most runs.

### Kubernetes payload and pod states

*Rule.* Payloads over 96 KiB (`PAYLOAD_ENV_MAX_BYTES`) go through the S3 pending key instead of the `QROSETTA_PAYLOAD` environment variable. Pod states are reported by cause. Compile Jobs get 2Gi. Image digests are recorded (`QROSETTA_IMAGE_DIGESTS`).

*Evidence.* Found in a review of the Kubernetes dispatch path on 2026-10-07; no measurement was recorded.

### Unfinished jobs

*Rule.* Every worker records its task (`start_job`). A worker exception fails the job with the exception type only. Cleanup evicts an unfinished job once its worker task has ended and it is older than the TTL, never one whose worker is still running. A compile-only run in which no compile produced a circuit is `failed`, like a run where all runners failed.

*Evidence (2026-10-07).* An exception in `worker_batch_suite` left the job `processing` forever and the browser polled indefinitely. A compile-only playlist whose every compile errored completed as done.

### Playlist length

*Rule.* A playlist holds at most 400 circuits (`MAX_BATCH_TASKS`, published as `limits.max_batch_tasks`). `bypass_limits` lifts it.

*Evidence (2026-10-27).* The two bundled suites together are 324 circuits: MQT Bench "Add all shown" gives 269, or 204 at the 18-qubit statevector cap, and QASMBench gives 55. A cap of 200 would have refused MQT Bench "Add all shown" on its own.

### Job storage budget

*Rule.* Stored job results may use at most `QROSETTA_JOB_SPILL_MAX_MIB` (10240) and must leave `QROSETTA_JOB_SPILL_MIN_FREE_MIB` (1024) free on the disk; both are published in `limits`. Over budget, a new run gets 503 with Retry-After. A playlist or experiment checks before writing each circuit or cell and fails with a message naming the limit, and its files are removed. A single-circuit report is always written, so jobs already running can overshoot the budget.

*Evidence.* An 18-qubit, 14-backend task stores about 78 MB, and the storage directory had no bound.

### Bundled circuits over the preparation limits

*Rule.* With preprocessing on, a bundled circuit whose recorded preparation peak ([`rosetta-api/benchmarks/preparation_peaks.json`](rosetta-api/benchmarks/preparation_peaks.json), measured by [`scripts/harness_bench/prep_peaks.py`](scripts/harness_bench/prep_peaks.py)) reaches the preparation memory limit is refused with 400 at submission, and the page names it before sending. `limits` publishes `prep_max_mib` and `prep_timeout_sec`. A circuit not in the table that exceeds either limit still fails as a job, with a message naming the limit and its value.

*Evidence (2026-10-27).* pytket 1.33.0, Python 3.12, one fresh process per circuit, two runs within 4 MiB of each other. grover-noancilla at 13, 14 and 15 qubits peaked at 598, 952 and 1,493 MiB, and above 2,048 MiB from 16 qubits. grover-v-chain at 13–16 qubits peaked at 517, 779, 1,192 and 1,861 MiB, and above 2,048 MiB from 17 qubits. Every other bundled circuit stayed at or below 392 MiB.

### API analysis threads

*Rule.* The API image sets `OMP/OPENBLAS/MKL_NUM_THREADS=1`.

*Evidence.* A measured analysis took 19.8 s with 2 BLAS threads and 1.9 s with 1.

## Simulator configuration

### Precision

*Rule.* Each runner reports `precision`. qsim, qrisp, torchquantum and the cirq measured path compute in complex64; the rest in complex128.

*Evidence.* qsim pairs sit at 1−F ≈ 1.1e-12; double-precision pairs at ≈1e-15.

### Aer method

*Rule.* Both Aer runners set `method="statevector"` and report `device`, `simulation_method`, `simulator_backend`.

*Evidence.* Automatic method selection ran the stabilizer method on Clifford circuits (GHZ-20: 0.016 MiB vs 16 MiB).

### Gate fusion

*Rule.* Not disabled; disclosed (Aer `gate_fusion` from result metadata; qsim default max_fused_gate_size 2) in `preprocessing_applied`.

*Evidence.* Aer fuses above 14 qubits at opt level 0 (qiskit grew 1.18× from 14 → 15 qubits vs qulacs 1.72×).

### No duplicate engines / cuQuantum

*Rule.* cuQuantum = qiskit-aer-gpu 0.15.1 with `cuStateVec_enable=True` on an NVIDIA GPU (Qiskit 1.4.4). Without a usable GPU it is unavailable (`GET /capabilities`, `/runners` `available:false`) and never falls back to CPU Aer. GPU passthrough is local-only (a local Compose override with `devices: [nvidia.com/gpu=all]`); Kubernetes uses `requires_gpu` + `QROSETTA_GPU_AVAILABLE`. Memory fields are host RSS; the GPU is not under the CPU quota.

*Evidence (decided 2026-09-30).* The CPU fallback was plain Aer, a second copy of the qiskit engine counted as an independent backend; there is no CPU build of cuQuantum.

## Sampling, seeds and statistics

### Seeds

*Rule.* Each runner key gets `derive_runner_seed(master, key)` ([`shared/qrosetta_commons/seeds.py`](shared/qrosetta_commons/seeds.py)), recorded as `runner_seed`; `results["seed"]` is the master. A measured run's master seed is never null: the API uses the caller's seed or generates one.

*Evidence.* A shared seed made sampled backends draw identical shots; detection at TV = 0.02 was 0.3% vs 5.7% with independent seeds.

### Counts keys

*Rule.* Keys are the circuit's classical bits as written by its own `measure` statements (never the full qubit register); flat clbit index = creg declaration order; `lsb` = clbit 0 rightmost, `msb` = leftmost; no spaces ([`shared/qrosetta_commons/counts.py`](shared/qrosetta_commons/counts.py)). Runners map the backend's bit identity back to declaration order.

*Evidence.* Six backends returned all qubits, the pytket and Qiskit parsers ordered cregs alphabetically, and Aer kept register spaces, so identical distributions scored JS = ln 2.

### Measure-all register

*Rule.* `qrosetta_commons.counts.measure_all_register` (`meas`, `meas0`, …) is placed after the declared cregs, identical for native and sampled backends.

*Evidence.* `creg c[2]` with no measure: Qiskit `0100` vs PennyLane `10`.

### Mid-circuit measurement

*Rule.* Backends that simulate it natively run it (Aer, cirq, qsim, qrisp); every other adapter returns an error. Sampling a final statevector for such a circuit is never allowed.

*Evidence.* Before: qsim/torchquantum/quimb showed no collapse, and myqlm gave 0.76/0.24 for a 50/50 bit.

### Measured verdicts

*Rule.* Each measured pair carries `measured_assessment` (`consistent_within_shot_noise`, `inconclusive_low_shots`, `ambiguous`, `distinguishable`, `not_comparable`); only `distinguishable` is a disagreement in the UI, and in measured mode the Summary groups pairs by this field alone.

*Evidence.* Shot noise at 10–20 shots was displayed as unexplained disagreement.

### Multiple testing and power

*Rule.* Benjamini–Yekutieli across the m comparable pairs (valid under the dependence of pairs sharing a backend's sample); a pair is distinguishable only if both χ² and G pass. Power and `recommended_shots_per_backend` at α/(m·c_m), df = tested bins − 1, w = TV. Outcomes with expected count < 5 are pooled; power is computed on the tested table at δ_tested = δ − min(P_pool, Q_pool) (the most TV pooling can hide; power = α′ when ≤ 0); not significant with power < 0.8 → `inconclusive_low_shots`. Default n_shots 8200. Noncentrality λ = 4·n_i·n_j/(n_i+n_j)·w² (`effective_total_shots` in [`rosetta-api/services/analysis/divergence/statistics.py`](rosetta-api/services/analysis/divergence/statistics.py)), equal to N·w² for equal shots; the marginal tests use the same.

*Evidence.* BH with raw-α power: 0.62 achieved vs 0.80 reported at 1570 shots; the per-run FDR was ~19.5% from clustered flags. BY Monte Carlo (14 backends): P(any false flag) 0–1.7%, per-pair power 0.91–0.93 at the recommended shots (4444/5435/6619/8199 for 2/4/8/16 outcomes). 2026-10-07: 8200 vs 50 shots was labelled consistent at a reported power of 0.995; the true power was 0.109. Monte Carlo rejection rates were 0.111/0.494/0.386 for 8200v50/8200v400/300v5000, against model 0.109/0.497/0.391.

### Power with unequal shots

*Rule.* λ = 4·nᵢ·nⱼ/(nᵢ+nⱼ)·w² (`effective_total_shots`).

*Evidence (2026-10-07).* 8200 vs 50 shots was called consistent at power 0.995; the true power was 0.109.

### Power after pooling

*Rule.* Power uses `power.delta_tv_tested` (see [Multiple testing and power](#multiple-testing-and-power)); with pooling, `recommended_shots_per_backend` is found by pooling the observed proportions at each candidate count (a lower bound when the support is larger than observed).

*Evidence (2026-10-01).* A 21-qubit circuit where PennyLane gives P(q20=1) = 0 and the rest 0.40 (TV 0.40) was `consistent_within_shot_noise` with power 0.994, because ~all outcomes were pooled into one bin. The default 8192 was 7 shots short of the 8199 needed for 16 outcomes with 14 backends.

### Rare outcomes

*Rule.* Rare outcomes are pooled only with each other. An undersized bin stays a column (expected ≥ 1, at least two common outcomes) or is left out (`untested_outcomes`, δ − max(P, Q)).

*Evidence.* Merging into a common bin made 6.8% of correct pairs inconclusive; now 0.

### Exact conditional test

*Rule.* 2×2 tables that fail the expected-count rule get exact hypergeometric p-values for χ² and G (`test_method` exact_conditional; equals Fisher only for equal rows). `degenerate` when both backends return the same single outcome; `not_tested` when one column is left after pooling. ANALYSIS_VERSION divergence-2026.10.08.3.

*Evidence.* Near-deterministic circuits went from 80–96% of correct pairs inconclusive to 0; false flags unchanged; known defects 100% detected.

### G-test

*Rule.* Williams' correction (`g_test.williams_q`).

*Evidence.* Uncorrected G rejected a true null in 95% of 65,536-bin tables at 1e6 shots; 15% corrected.

### Shot advice

*Rule.* No recommendation, and `resolvable_by_more_shots` null, above a Good–Turing unseen mass (share of shots in singletons) of 0.5 (`support_characterised`). Likewise when the lower bound is above δ/2, or when it comes from pooling with singletons. Recommendation = minimum × 1.1, rounded to 2 significant figures (`recommendation_margin`). Holm p-values are recorded; `significant_fwer` on distinguishable pairs.

*Evidence.* A 10 × n_shots artifact came from the pooling threshold; 67 of 728 pairs stayed inconclusive at the minimum, 0 of 728 at +10%. Earlier, at 22 qubits: recommended 167599, and a rerun gave the same inconclusive verdict with no recommendation. With one wrong backend among 14, correct-vs-correct pairs were flagged in 8–9% of runs under BY (1.5–2% with all correct).

### Single-bit marginal tests

*Rule.* A secondary, pre-specified analysis on every comparable measured pair with ≥ 2-bit keys: per classical bit a 2×2 table (counts of 0/1), chi-square + Williams G, Holm over all tested bits of all pairs at α (FWER), both required; expected count < 5 or constant in both → bit not tested. Output `marginal_assessment` + `metrics.marginal_test`; it never changes `measured_assessment` or its power calibration and never yields agreement. It is counted as a disagreement by the verdict rule (the pair's recorded `pair_verdict`, shown by the badges, the Agreement tab chip and the Summary block), in crates (`by_marginal_assessment`) and in experiment prevalence rows (`count_basis=marginal_assessment`). [`rosetta-api/services/analysis/divergence/marginals.py`](rosetta-api/services/analysis/divergence/marginals.py); ANALYSIS_VERSION divergence-2026.10.08.3.

*Evidence (added 2026-10-02).* BY was tried first. On a 22-qubit job with Qrisp wrong on 19 bits, ~228 true flags loosened BY and 5 correct-correct pairs were flagged; Holm on the same report kept all 13 Qrisp pairs and dropped the 5. Holm Monte Carlo (14 backends × 16 bits × 8200 shots, 40 runs): global null 1/40 runs with any flag; one backend +0.05 on 4 bits: 1/40 runs with a false flag on a correct pair, per-pair power 1.000.

### 1-bit keys

*Rule.* Measured pairs with 1-bit keys are compared directly (`basis_source` single_bit).

*Evidence.* They were previously labelled "after bit reversal".

### False-flag figures

*Rule.* 0.8–1.0% of runs with every backend correct. With one grossly wrong backend, 6.0–6.7% under BY and 2.7–3.3% that also pass Holm.

*Evidence.* 2000-run Monte Carlo per scenario.

## Agreement analysis

The default thresholds (fidelity 1e-5, phase 1e-6 rad, norm 1e-4, JS 0.01 nats, Hellinger 0.1) are the `AgreementThresholds` defaults in [`rosetta-api/schemas/benchmark.py`](rosetta-api/schemas/benchmark.py) and can be set per request.

### Fidelity tolerance

*Rule.* Raw fidelity is stored, never snapped; a pair agrees when F ≥ 1 − `fidelity_tolerance`; default 1e-5.

*Evidence.* `np.isclose`'s default `rtol=1e-5` had snapped every F ≥ 1−1e-5 to 1.0 while 1e-12 was recorded. 1e-5 is the tolerance that was effectively applied; experiments 1 and 2 recomputed: 0 labels changed.

### Phase tolerance

*Rule.* Default 1e-6 rad.

*Evidence.* complex64 backends showed φ ≈ 1e-8 rad on real-amplitude circuits, labelled as a global phase under 1e-12.

### Norm tolerance

*Rule.* Default 1e-4: flags genuinely unnormalised output, not complex64 rounding (~2e-6).

*Evidence.* qrisp at 5 qubits had norm 0.99999797.

### Bit order

*Rule.* Labels are set from a one-hot probe on a register with idle qubits, and statevectors are always `2**declared_qubits` long. cirq, qsim-cirq, braket, projectq are msb on both endpoints.

*Evidence.* cirq's earlier "lsb" came from tk_to_cirq dropping idle qubits.

### Label-aligned basis (both modes)

*Rule.* lsb × msb pairs are classified and tested after bit reversal, same-label pairs directly, 1-qubit pairs directly; the basis is chosen from the declared labels, never from the data. A match only in the other basis (`unaligned_basis_match`) or only after an undeclared permutation (`agree_after_qubit_permutation`) is a disagreement. Measured: a pair within the JS/Hellinger thresholds only in the other basis is `distance_exceeds_threshold` with `metrics.unaligned_basis_match`. ANALYSIS_VERSION divergence-2026.10.07.1.

*Evidence.* Measured: direct-first testing flagged 42 correct pairs (p ≈ 1e-188). Statevector: PennyLane's cu3 control/target swap mimicked a bit reversal and was labelled agree_directly against lsb backends. On 2026-10-07, msb {'01'} vs msb {'10'} had been labelled `agree_after_bit_reversal` while distinguishable.

### Permutation search implementation

*Rule.* The counts and statevector permutation searches score all permutations of a pair in one array pass from a cached index table (`_key_permutation_table`, `_qubit_permutation_gather`), with the loop's floating-point operations: Hellinger norms on freshly allocated rows (OpenBLAS `dot` can change the last bit with row alignment), JS squared as a numpy scalar. Any change to the analysis passes [`scripts/harness_bench/equivalence.py`](scripts/harness_bench/equivalence.py) with 0 differences against the previous release, else it bumps ANALYSIS_VERSION. The exhaustive search covers up to 7 qubits (`MAX_EXHAUSTIVE_QUBIT_PERMUTATION_QUBITS`); above it the result is `too_many_qubits`.

*Evidence (2026-10-21, commit b22e78b).* 200 counts + 100 statevector corpus cases bit-identical to the previous release in the API image; measured 7-bit report 49.4 → 2.9 s, statevector 7-qubit 1.87 → 0.47 s ([`scripts/harness_bench/LEDGER.md`](scripts/harness_bench/LEDGER.md)). A first version with array squaring and row-view dots differed in the last bit in 10 of 60 cases.

### Failed-run values

*Rule.* Unmeasured metrics are null in results and "—" in every table; matrices use null for pairs not compared.

*Evidence.* Failed runs printed as 0.000000 s; matrices used a -1 sentinel.

### One implementation of the verdict rule

*Rule.* Pair verdicts, per-backend counts and the Summary headline model are computed only in [`rosetta-api/services/analysis/divergence/verdicts.py`](rosetta-api/services/analysis/divergence/verdicts.py) and [`headline.py`](rosetta-api/services/analysis/divergence/headline.py). Every new report records each pair's `pair_verdict` and the report's `backend_verdicts`; the page and the figures read them. For an older or uploaded report the server computes them with the same function (`GET /jobs/{id}/summary`, `GET /history/runs/{id}/summary`, `POST /summary`). A change to the rule bumps the analysis version (divergence-2026.10.27.1).

*Evidence (2026-10-27).* The figure builder had a second, simpler copy of the rule that read only the top-level `measured_assessment`, without the page's fallbacks for older reports. The page's previous JavaScript, kept frozen as a test reference, and the Python rule gave the same verdict for all 21,837 pairs of 1,085 reports (13 recorded, 72 built by the analysis, 1,000 synthetic), with the same counts, runner statuses and headline models in all five headline kinds ([`rosetta-api/tests/unit/test_verdict_equivalence.py`](rosetta-api/tests/unit/test_verdict_equivalence.py)). On 200 reports (4,804 pairs) the analysis output differed only in the analysis version and the added fields.

### Run planning

*Rule.* One planner on the server ([`rosetta-api/services/plan.py`](rosetta-api/services/plan.py), `POST /plan`) turns a workspace into the exact requests a run sends and the problems that would make the server refuse them, as codes. The page submits the returned requests unchanged, and the command-line client uses the same endpoint, so both send identical requests for identical choices.

*Evidence (2026-10-27).* On 748 page workspaces covering every problem code, the server planner produced the same requests, refusal texts and request sizes as the page's former JavaScript planner, which was then removed.

### Fresh readiness probes

*Rule.* `GET /runners?fresh=true` (and `/compilers`) probes the services at most 6 times a minute per client, only for a signed-in account or the local lifecycle token, and reuses a result younger than 5 s. It never probes a service with a run in flight, and while an exclusive run holds or waits for the gate it returns the cached answers instead of probing.

*Evidence (2026-10-27).* Unbounded probes would add unrecorded load to the runners during other jobs' timed windows.

### Self-test known answers

*Rule.* The self-test (`GET /selftest`, evaluated by `GET /jobs/{id}/selftest-result`) runs fixed circuits with fixed settings and compares every backend with an expected answer computed by an independent numpy reference ([`rosetta-api/services/selftest/reference.py`](rosetta-api/services/selftest/reference.py)), pinned in [`rosetta-api/circuits/selftest/expected.json`](rosetta-api/circuits/selftest/expected.json). It never compares backends with each other, so it fails when every backend agrees on the same wrong answer. Statevectors must reach fidelity 1 − 1e-5 with the expected state in the backend's declared bit order; five classical-bit circuits must give their single expected key; GHZ-3 must stay on its support and within six standard deviations of balance. A virtual machine or a self-built image is a warning; emulation, an unknown image or a modified checkout is a failure.

*Evidence (2026-10-27).* The statevector circuit's expected state has fidelity at most 0.834 with any qubit reordering, 0.559 with bit reversal, at most 0.874 with a cx control and target swapped, and 0.795 with the rz sign flipped; single-precision rounding changes it by less than 1e-7. Six wrong states returned identically by every backend, which the agreement analysis labels as agreeing, and eight wrong counts-key cases all fail ([`rosetta-api/tests/unit/test_selftest_evaluate.py`](rosetta-api/tests/unit/test_selftest_evaluate.py)).

### Emulated images

*Rule.* Each runner and compiler result says whether its image ran under emulation: the machine the image's Python is built for, compared with the host's operating system and machine, which `qrosetta start` passes to the containers. The runner reads the host's values once at startup and removes them from its own environment before any simulation starts, so the simulating process sees exactly the environment it saw before. A stack started without `qrosetta start` records the host as unknown and the comparison as not made. An emulated result fails the self-test and carries a timing caveat.

*Evidence (2026-10-27).* Before, nothing recorded emulation, so the self-test skipped the check for every backend. Through the real launch path, the simulating process's environment is the one it had without the new values ([`rosetta-api/tests/unit/test_image_identity.py`](rosetta-api/tests/unit/test_image_identity.py)), and the recorded timings, memory, result fields and statevector of 45 runs per version did not change.

### Image identity and specimens

*Rule.* Each runner and compiler image records, at build time, whether it is a published release or built locally and from which commit, in a file inside the image (never an environment variable). The runner reads it once at startup and attaches it to each result after the simulation has finished. Every report and crate states whether all backends ran published images, all ran locally built ones, a mix, or unknown. A runner's dependency lock file is included in a crate only when its hash matches the hash the image itself reported.

*Evidence (2026-10-27).* Before, local results recorded the runner image as "not recorded", and crates attached lock files from the server's copy without checking them. A test captures the simulating process's environment through the real launch path and finds it identical to the runner server's, with the identity never read inside it ([`rosetta-api/tests/unit/test_image_identity.py`](rosetta-api/tests/unit/test_image_identity.py)).

### Timing caveats

*Rule.* One server function ([`rosetta-api/services/timing_caveats.py`](rosetta-api/services/timing_caveats.py)) decides every timing caveat shown with a result: throttling, work outside the measured process, runs sharing the machine, a single timed repetition, no CPU quota, mixed core speeds, a virtualised or emulated host. The page shows what it returns, and crates carry it.

*Evidence (2026-10-27).* The rules previously lived only in the page's JavaScript. Moving them gave 0 differences against that code on 351 saved and 20,000 synthetic reports ([`scripts/timing_caveats_equivalence/`](scripts/timing_caveats_equivalence/)).

### Summary headline

*Rule.* The headline is built from differing pairs only; inconclusive pairs are neither agreement nor difference. Kinds `named` / `camps` / `pairs` / `spread`. Sizes are taken against the backends not named (median and range of TV; lowest fidelity). BY-only pairs are counted apart. A chance caveat is shown for minority flags. Red only for named backends. [`rosetta-api/tests/unit/test_headline_cases.py`](rosetta-api/tests/unit/test_headline_cases.py), [`rosetta-api/tests/unit/test_headline_magnitude.py`](rosetta-api/tests/unit/test_headline_magnitude.py).

*Evidence.* Correct backends were named, a headline read as a lone ".", one said "other 7" when 13 agreed, and sizes were taken from pairs of two wrong backends.

## Circuit handling and preprocessing

With `apply_preprocessing=True` (the default) the API and the runners apply transforms some SDKs need to accept a circuit; every transform is listed in `preprocessing_applied`, API-side ones prefixed `API:`. The user manual's Preprocessing section ([`rosetta-api/static/docs.html`](rosetta-api/static/docs.html)) describes the flag.

### Statevector mode + measurements

*Rule.* The API strips terminal measurements once (recorded as `API:`) and rejects mid-circuit measurement, `reset` and `if` with 400.

*Evidence.* qiskit returned the collapsed state while others returned the pre-measurement state.

### Submit-time structure checks

*Rule.* [`rosetta-api/services/qasm_structure.py`](rosetta-api/services/qasm_structure.py) (called by `validate_request`) refuses, each with its line number:

- non-ASCII outside comments;
- a header other than exactly `OPENQASM 2.0;`;
- names that collide (one namespace for qreg/creg/gate/opaque; registers may not shadow U, CX or included qelib1 gates);
- an index out of range; an undeclared operand;
- an unknown gate, with suggestions;
- wrong arity or parameter count; a repeated qubit;
- empty statements; control characters;
- broadcasts over registers of different sizes;
- calls reaching an opaque gate;
- `/* */` comments (bundled circuits exempt);
- register names not starting a–z;
- use before declaration.

Spaced indices `q [0]` are normalised with preprocessing on (`API:` note).

*Evidence.* `qreg q[1]; qreg q[2]` merged into a different circuit, and all backends agreed on it. An unequal broadcast was rewritten; opaque calls were dropped silently; block comments were silently removed. 328 bundled files pass.

### Expanded-gate broadcast width

*Rule.* A register operand counts as a broadcast only when the whole identifier is not followed by `[`. Register sizes come from the comment-free statements.

*Evidence (2026-10-07).* `qa[0]` matched the bare register `q`. With `qreg q[22]; qreg qa[2];`, 9,998 × `x qa[0]` counted as 219,958 applications and was rejected. `// qreg q[24];` changed the counted width.

### Gate parameters

*Rule.* Every constant parameter (top level and inside gate bodies) must be a finite OpenQASM 2.0 expression with magnitude ≤ 1e6 (400 otherwise).

*Evidence.* pytket reduced rx(1e308) to rx(0) and all 14 backends agreed on the wrong state; rx(nan) gave NaN statevectors ranked fastest.

### Parameter expressions

*Rule.* A hand-written OpenQASM expression parser ([`shared/qrosetta_commons/qasm_expressions.py`](shared/qrosetta_commons/qasm_expressions.py)); Python keywords are valid parameter names.

*Evidence.* `lambda` was refused.

### Reserved gate names

*Rule.* User `gate`/`opaque` names that any runner's parser treats specially are rejected (400) in every mode ([`rosetta-api/services/reserved_gate_names.py`](rosetta-api/services/reserved_gate_names.py), read from the runner images); the pytket round-trip fails the job if a call became a barrier or a user gate lost its definition. Bundled MQT/QASMBench circuits are exempt.

*Evidence.* pytket turned `sleep`/`orderN`/`groupN` into barriers and replaced prefix-matching definitions of built-ins (`yyphase`, `fsim`, `iswap`): all 14 backends agreed on a wrong state.

### pytket in threads

*Rule.* Every pytket parse and write in the API runs under `PYTKET_LOCK` ([`rosetta-api/services/pytket_lock.py`](rosetta-api/services/pytket_lock.py)), called from `asyncio.to_thread`.

*Evidence.* pytket 1.33 keeps one global Lark parser. Two simultaneous jobs swapped gate definitions (6 of 8 trials) with every backend agreeing.

### pytket CnX names

*Rule.* After the round-trip the API renames pytket's `c4x` by operand count (cx/ccx/c3x/c4x), recorded as `API:`; wider is a RoundTripIntegrityError.

*Evidence.* pytket 1.33.0 writes every CnX as `c4x`; `c3x` became an invalid 4-operand `c4x`, rejected by 8/14 simulators and every compiler.

### Angle rounding in parsers and writers

*Rule.* tket (pytket 1.33) sets a parameter within 1e-11 half-turns of a multiple of π/4 to it (also `rz(1e-11)` → 0). The API predicts it (`qasm_expressions.tket_rounded_parameters`: top-level constants and parameters inside called definitions with each call's values; parameters tket derives while rebasing, e.g. cu1/crz half-angles, are not predicted and the note says so; the evaluator is shared with the validator) and records it as an `API:` note after the round-trip, or appends a note to runners with `builds_with_tket` when it dispatches text tket has not built. This is computed in the API, never inside a runner's timing window. Qiskit-written texts use `exact_qasm2_dumps` ([`shared/qrosetta_commons/qiskit_circuits.py`](shared/qrosetta_commons/qiskit_circuits.py); bypasses `pi_check(eps=1e-12)`); qsim's text uses `to_qasm(precision=16)`. PyZX: scientific-notation literals are rewritten as plain decimals (its parser rejects them); passes report the largest angle change from its rational phases (denominator ≤ 2^20), read through PyZX's own parser.

*Evidence (2026-10-02).* `rz(1.3e-13)` → 0 and `rz(3.14159265359)` → π in tket; `qasm2.dumps` wrote 1e-13 as 0 and π+1e-13 as π; Cirq's default precision 10 wrote `rz(1.3e-13)` as `rz(0)`; PyZX moved 0.123456789012345678 rad by 1.1e-9 rad (2.75e-9 worst over 2,000 random angles) and rejected `3.18e-06*pi`, which the round-trip writes for small angles.

### QASM edits are per statement

*Rule.* Runner-side rewrites split at `;`, `{`, `}` on comment-free text, never by line.

*Evidence.* PennyLane deleted gates sharing a line with `barrier`; qibo's regex deleted the statement after a `// barrier` comment.

### Missing qelib1 gates (qibo, quimb)

*Rule.* With preprocessing on, the qibo and quimb adapters insert the `qelib1.inc` definitions (Qiskit 2.5.2 copy in [`shared/qrosetta_commons/qelib1_qiskit.inc`](shared/qrosetta_commons/qelib1_qiskit.inc)) of the qelib1 gates their parser lacks, in the compile window (it is a transform the adapter needs), listed in `preprocessing_applied`; quimb gets `U` written as `u3`. With preprocessing off they are rejected, as before. staq uses the same helper. qibo does not get `cp`/`cu` (the round-trip never emits them; see [Upstream behaviour not worked around](#upstream-behaviour-not-worked-around)).

*Evidence (2026-10-02).* 0 failures, every gate F = 1 to 12 digits against Qiskit's Statevector on 31 qelib1 gates; through the API with preprocessing on, ch/csx/cswap/c3x 4-backend pairs all agree. qibo 0.3.1 raises TypeError executing any 2+-qubit user gate whose body uses its parameters.

### Implicit permutations

*Rule.* Swaps removed by relabelling are written back as gates in `compile_fn`: `restore_final_layout` for Qiskit transpiles, `replace_implicit_wire_swaps` for pytket passes before `tk_to_*`. TorchQuantum stays capped at level 2 (Qiskit 0.45.3 level 3 deletes swaps with no layout). [`rosetta-api/tests/unit/test_implicit_permutations.py`](rosetta-api/tests/unit/test_implicit_permutations.py).

*Evidence.* Qiskit and cuQuantum levels 2–3, PyQuil 1–2 and Cirq 2 returned permuted statevectors (72, 72, 176 and 88 cases); 0 after.

### Gate metrics

*Rule.* `gate_count`/`circuit_depth` come from `transpiled_qasm` unless the runner supplies `gate_metrics_fn` (PennyLane: executed-tape operations); `gate_metrics_basis` says which.

*Evidence.* PennyLane's `to_openqasm()` text decomposes `QubitUnitary`: QFT-12 read 1014 gates vs qiskit's 84.

### PennyLane executed text

*Rule.* `transpiled_qasm` holds the executed tape's operations only, one statement per tape operation, with qelib1 names (sx, sxdg, ch, cy, rxx, rzz, cu1, barrier). QubitUnitary and Rot are decomposed in the text only, up to global phase. Barriers are passed to `from_qasm`.

*Evidence.* The text reproduces PennyLane's statevector at levels 0, 1 and 3. Earlier, `dev.preprocess()` gave `qml.state()` explicit wires, and `to_openqasm(measure_all=False)` then wrote a `measure` per wire that never ran.

## Compile-only services

Compilers are separate from the simulators: their output is a circuit, which is shown and exported but not simulated, timed or compared. The adapters are under [`compilers/`](compilers/); the shared output checks are in [`shared/qrosetta_commons/compile_checks.py`](shared/qrosetta_commons/compile_checks.py).

### Compile-only services

*Rule.* Compilers are not runners: separate registry (`get_compiler_services` in [`rosetta-api/config.py`](rosetta-api/config.py)), output in `compiled_circuits`, never simulated, timed or compared. They run after the job's simulators, through `dispatch_to_runners` (gate, queue, hard timeout), on one recorded `compile_input` (`prepare_statevector_dispatch` of the submitted circuit); a measured circuit with mid-circuit measurement is `skipped`. `run_isolated(measured=False)` calls the processor once, without warm-up or timing. `simulate: false` (compile-only request) dispatches no simulator; the report has `simulated: false` and empty `raw_results`. Each image has `--self-test` (probe circuits, unitary check with the image's own SDK).

*Evidence (2026-10-01).* Running them beside timed runs would share the host with the measurement; a compile time would be a performance claim outside the instrument.

### Compiler pipelines offered

*Rule.* BQSKit levels 1–3 (one worker, seed 0, all-to-all, epsilon 1e-8); PyZX `full_reduce`+extract (1) and +`basic_optimization` of the extracted circuit (2); QMAP: Qiskit basis translation to u3+cx, then heuristic (0) / exact (1) mapping onto a linear chain.

*Evidence.* BQSKit level 4: 195 s on a 4-qubit, 6-gate circuit. PyZX 0.10.6 `basic_optimization(to_basic_gates())` changed the unitary of 31–90% of random 3-qubit circuits (`x; rx(0.7)` reproduces); full_reduce paths 0/450. QMAP 3.10 maps `cu3`/`cp` as `cx` without an error; after decomposition 40/40 random circuits were equivalent up to layouts, and all five live outputs of a test job were equivalent.

### Compilers not offered

*Rule.* GUOQ/wisq is not offered.

*Evidence.* Its search stops on wall-clock time only (the seed covers resynthesis partitions), so output depends on load; it needs Java 21 and a BQSKit server too.

### Compile-only qubit limit

*Rule.* A `simulate: false` request (single or playlist) is validated against `MAX_QUBITS_COMPILE` = 24, not the statevector cap; every other check is unchanged. Exposed as `max_qubits_compile` in `GET /config`. Compilers enforce `MAX_QUBITS_COMPILE` (env, default 24; [`qrosetta_commons.helpers`](shared/qrosetta_commons/helpers.py)). The API forwards all three caps to Kubernetes Jobs, and docker-compose passes them to api, runners and compilers ([`rosetta-api/tests/unit/test_qubit_cap_sources.py`](rosetta-api/tests/unit/test_qubit_cap_sources.py)).

*Evidence (decided 2026-10-07).* The 18-qubit cap protects runner memory from a 2^n statevector, which a compile-only run never builds. The limit is not unbounded: BQSKit's higher levels and Quartz (time about quadratic in gates) scale badly with width, and outputs above 10 qubits are not unitary-checked. 24 is the largest circuit the platform already accepts. Before, `compile_service` used `MAX_QUBITS_MEASURED` and Jobs received no caps.

### Compiler memory and concurrency

*Rule.* Compiler containers have 2G and 2.0 CPU with `COMPILER_MAX_CONCURRENT=2` (two single-threaded compiles at a time). BQSKit has 1: its `Compiler` binds ports 7472/7474 and a second concurrent compile failed with 'Server connection unexpectedly closed'. Compiles are not timed, so concurrency affects latency only. Kubernetes runs one compile per Job. Kubernetes compile Jobs: requests 200m/512Mi, limits 1000m/2Gi (`dispatcher_k8s.COMPILER_RESOURCES`). The project quota's `limits.memory` is 16Gi; API 2Gi + 3 × 2Gi fits.

*Evidence.* Cirq imports alone are 259 MiB per process, and the compile runs in a spawned child beside the gunicorn worker; a 12-level nested gate peaked at 432 MiB in the child and OOM-killed Cirq, staq and Q-Synth at 512M. 2026-10-02: one compile per service let a slow compile block other clients' compiles; two slots at 1G would not hold two such children beside the worker.

### Compiler basis translation

*Rule.* QMAP, Q-Synth and Quartz translate with `transpile(..., optimization_level=0, qubits_initially_zero=False)` ([`qrosetta_commons.qiskit_circuits`](shared/qrosetta_commons/qiskit_circuits.py)); every Qiskit-based equivalence check builds the operator from the u3/cx translation (`unitary_of`). Runners keep the default (they simulate from |0…0⟩).

*Evidence (2026-10-01).* The default treats an untouched qubit as a clean ancilla when decomposing MCX: 11-qubit `h q0..q2; c3x q0..q3` gave F = 0.743 for Q-Synth and Quartz, marked ok (unchecked above 10 qubits). Operator of a 2-qubit, 12-level nested gate: 602 MiB direct, 153 MiB flattened.

### Compiler output checks

*Rule.* Every BQSKit (tolerance 1e-6) and PyZX (1e-8) output up to 10 qubits is checked with Qiskit; "not checked above 10 qubits" otherwise. staq records its largest single-precision angle change. Raw SDK errors become `CompileRefused`.

*Evidence.* No separate measurement was recorded for this rule. It follows from cases recorded in other entries of this section, where a compiler returned a circuit with a different unitary and reported no error: PyZX 0.10.6 `basic_optimization(to_basic_gates())` changed the unitary of 31–90% of random 3-qubit circuits; QMAP 3.10 mapped `cu3`/`cp` as `cx`; Cirq 1.7.0 imported some `cu3` gates with a −1 phase on the control's \|1⟩ branch.

### Compiler inputs

*Rule.* BQSKit gets renamed qelib1 definitions of c3x, c3sqrtx, c4x, rc3x and u0, and wide user gates are flattened in operation order (never `Circuit.unfold`). Cirq gets rc3x's definition. QMAP exact is refused above 7 qubits, and identity-only qubits count as idle. Cirq level 1 sets final measurements aside. Compiled circuits carry no measurements. The CSV has `refusal_kind`, `refusal` and `reason`.

*Evidence (2026-10-08).* BQSKit's parser read c3x, c3sqrtx, c4x and rc3x as 4–5 qubit gates and u0 without its parameter. After the change, BQSKit levels 1–2 on those gates, nested and colliding definitions: all equivalent (process infidelity ≤ 2e-15); 30 random 4–6 qubit circuits with those gates at level 1: 0 failures. BQSKit 1.2.1's `Circuit.unfold(point)` changed the unitary when gates preceded the unfolded one (infidelity 0.146 on a 2-qubit example).

### Compiler refusals

*Rule.* An adapter raises `CompileRefused` (input it cannot compile correctly) or `OutputRejected` (output failed its check) ([`shared/qrosetta_commons/compile_errors.py`](shared/qrosetta_commons/compile_errors.py)); the record gets `refusal` + `refusal_kind`. Only those reach share links and the Summary tab; other compiler errors (tool exit status, stderr, SDK exceptions) stay out of share links.

*Evidence.* Refusal reasons were not visible on the share page or the Summary tab; error text is excluded from share links (see [Share links](#share-links)).

### Compiler gate metrics

*Rule.* Each compile record has `gate_count` (top-level statements), `circuit_depth` (greedy, barriers ignored), `gate_counts` (per name) and `multi_qubit_gate_count`; `tables/compiled_circuits.csv` in crates, `compiled_circuits.csv` + texts + compiler locks in experiment bundles. The user manual and tooltips say gate_count is not comparable across compilers.

*Evidence.* QFT-8 staq -O1 gave 40 gates vs 160–170 for others with the same 68 CX; staq -O1 79 vs Cirq 393 on one circuit.

### Compiler build provenance

*Rule.* Pip packages go in `sdk_versions`; programs an image builds from source are `native_components` (`declare_native_component` in [`shared/qrosetta_commons/compile_service.py`](shared/qrosetta_commons/compile_service.py): version, source URL + sha256, flags/patches, Quartz ECC hash). Each compiler image copies its build files (Dockerfile, `requirements.lock`, Quartz patch/generator/driver/ECC set) to `/usr/local/share/qrosetta-build/`; records carry their sha256 as `build_files`, and a crate includes the API's copy of a file only when the hash matches. `GET /compilers` reports these from each image's `/capabilities`. The Quartz ECC set is committed as a reference copy ([`compilers/quartz-compiler/Nam_complete_ECC_set.json`](compilers/quartz-compiler/Nam_complete_ECC_set.json)), checked against the Dockerfile's `ECC_SHA256` by a unit test.

*Evidence (2026-10-02).* Crates listed `staq==3.5`/`quartz==0.3.2` as pip pins, Quartz's ECC set, generator and patch were not in crates, and `GET /compilers` had no versions.

### QMAP output check

*Rule.* Every QMAP output is checked when produced: `// i` and `// o` must be full permutations, and up to 10 qubits the output read through them must have the input's unitary (Qiskit), else the compile is an error. Circuits with idle qubits are refused before mapping.

*Evidence (2026-10-01).* QMAP 3.10 writes the identity layout when a qubit is idle; an input-side idle check was bypassed with `id q[1]`, which QMAP removes before writing a wrong layout.

### PyZX input

*Rule.* creg declarations and comments are removed before PyZX parses; classical operations are refused.

*Evidence (2026-10-01).* `to_graph()` turned 3 creg bits into 3 extra qubits (`q[6]`). A comment containing "measure" was refused.

### Cirq compiler

*Rule.* Compiler id `cirq-transformers` (the runner is `cirq`); CZ target gate set only. A `cu3` with θ mod 4π in [2π, 4π) is refused at top level and inside gate bodies at any qubit count (found by walking Qiskit's parse into user definitions). The image sets `PYTHONHASHSEED=0` (all compiler images do); outputs ≤ 10 qubits are checked with Qiskit.

*Evidence.* Cirq 1.7.0 `circuit_from_qasm` imports such a `cu3` with a −1 phase on the control's |1⟩ branch; all other qelib1 gates imported correctly in a sweep; 0/200 random circuits were wrong otherwise. The sqrt-iSWAP target is not offered (QASM shows only its cx decomposition).

### staq compiler

*Rule.* Built with g++ from the sha256-pinned v3.5 tarball; -O1..-O3, no mapping. Gates of Qiskit's qelib1.inc missing from staq's library get Qiskit's definitions inserted (dependency order), listed in the passes; registers/gates named `r` or `cswap` are refused; a literal that float32 moves by > 1e-6, or below float32's smallest normal, is refused; outputs ≤ 10 qubits are accepted at process infidelity ≤ 1e-8 (value recorded).

*Evidence.* staq's lexer uses `std::stof`: angles are single precision (`rz(0.3)` → `rz(0.300000011920929)`); infidelity < 1e-14 on 360 outputs.

### Q-Synth compiler

*Rule.* `qsynth`: Qiskit → u3+cx, then `peephole_synthesis(slicing='cnot')` for cx-count (0) or cx-depth (1) on one register `q`, composed back onto the input's registers and final measurements. A slice that still timed out at its last solver call (recorded by wrapping `optimize_single_slice`) or an exhausted budget is an error. Runs in a private temp dir; python-sat 1.8.dev14 with `pip install --no-deps` (Q-Synth pins the removed 1.8.dev13).

*Evidence.* 0/50 non-equivalent, repeat runs byte-identical, < 1 s each on 3-qubit circuits.

### Quartz compiler

*Rule.* `quartz` level 0 only: Qiskit → h/x/rz/cx, then `Graph::greedy_optimize` with a Nam ECC set (3 qubits, 2 parameters, ≤ 3 gates) generated at image build and checked against a recorded sha256. Rational parameters (upstream default) with [`shift10-normalise.patch`](compilers/quartz-compiler/shift10-normalise.patch); angles go in as exact fractions of π; output = Quartz's gate lines renamed onto the input's registers (no `qasm2.dumps`). Barriers are removed, final measurements re-added, and mid-circuit measurement/reset/if refused. Quartz runs with PDEATHSIG so a timeout kills it; outputs ≤ 10 qubits are checked. Not offered: `Graph::optimize` (wall-clock bound), `rotation_merging`, the 4-gate ECC set.

*Evidence (2026-10-01).* Unpatched, 6/400 random circuits segfaulted (a bignum zero kept a leading limb, and `gcd` recursed 104k frames); patched, 0/400 crashed or were non-equivalent, repeat runs were byte-identical, and the ECC hash was identical across generations. The double-parameter build snaps angles within 1e-6 (`eps`) to π/4 multiples and deletes near-2kπ rotations, so it was rejected. `rotation_merging` ignores `x` sign flips: 79/303 non-equivalent. 4-gate set: 933 s on 32 cores, same gate counts on 8 circuits. Quartz drops `measure` silently. `qasm2.dumps` writes |θ| < 1e-12 as 0 and snaps within 1e-12 to simple π fractions. Time ≈ quadratic in gates: 3361 → 8 s, 8000 → ~50 s, 24k > 300 s.

### Synthetiq compiler

*Rule.* `synthetiq`, levels 0 (first circuit found, ≤ 1000 annealing runs; annealing energy = distance to the unitary, so T-count can rise) and 1 (lowest Synthetiq cost of up to 5 found, ≤ 2000 runs; fewer when the run cap ends the search). Clifford+T only (exact h/rz/cx translation; every rz within 1e-12 π/4-steps of a multiple, largest change listed, else CompileRefused), ≤ 3 qubits. One thread → one mt19937 stream seeded 0 per search (`seed(id + run*threads)`, one outer run); `--max-runs` from [`max-runs.patch`](compilers/synthetiq-compiler/max-runs.patch); a stop by `--time 280` with fewer circuits than asked is an error naming the limit; an empty circuit is returned without running Synthetiq (it segfaults on zero gates). Built at commit 59a0cc6 with `-O2`; Qiskit check on every output.

*Evidence (2026-10-02).* Toffoli → T-count 7 in 0.1 s; a 3-qubit run takes ~83 ms (435 runs/36 s for 1 circuit, 1451/122 s for 10). Fuzz over 60 random Clifford+T circuits: level 0 60/60 equivalent and byte-identical on repeat, level 1 59/60 (1 found 1 of 5 in 2000 runs). A follow-up check: 34 outputs equivalent; near-π/4 angles within 7.85e-10 rad had been rounded silently at the old 1e-9 tolerance, and empty circuits segfaulted.

## Provenance and reproducibility

### Provenance capture

*Rule.* `transpiled_qasm` is the circuit that executed, captured after every compile pass (pytket `get_compiled_circuit` runs a default rebase even at level 0). Serialisation runs in `serialize_fn` unless the circuit is mutated afterwards.

*Evidence (2026-08-18).* qulacs/quest/cirq/braket/projectq/qsim previously captured the pre-compile circuit.

### Image commit

*Rule.* Every image bakes `QROSETTA_IMAGE_GIT_SHA` at build (`--build-arg QROSETTA_GIT_SHA`); every runner and compiler result records `image_git_sha`; `git_sha` is the API image's. In Kubernetes mode (CSC Rahti), `QROSETTA_IMAGE_DIGESTS` (set by [`scripts/rahti_push.sh`](scripts/rahti_push.sh)) gives each image stream's digest, tag, source (pushed, or previous `:latest` retagged) and baked `image_git_sha`. Jobs run by digest, and `runner_image` records `registry/name@sha256:…`. A dirty checkout deploys as `<sha>-dirty` with a unique tag.

*Evidence.* On 2026-10-01, reports said `da8ced9-dirty` (the host checkout at boot) while the API ran 5abaa17 code and the runners older code. After a partial push, crates named `name:<HEAD>` for images built from older code.

### No source mounts on the API

*Rule.* The API reads `runners/` and `compilers/` from its image.

*Evidence (2026-10-01).* The read-only Compose mount of `./runners` over the API image's copy was unreadable by appuser under rootless podman, so crates never carried runner lock files.

### Report and crate source

*Rule.* Saved reports carry `saved_from` set by the server (`server_job` / `upload`); crates record `report_source` from the export route (`server_job`, the saved run's source, `client_supplied`), never from a report field.

*Evidence (2026-10-01).* Crates built by `POST /export` kept a forged `saved_from`, git SHA and version.

### Crates of supplied reports

*Rule.* Unless `report_source` is `server_job`: no actionStatus, versions only "as supplied", no lock files and no commit links. `#report-source` is a PropertyValue; an upload's `job_id` is kept as `source_job_id`. The repository link comes from `QROSETTA_REPOSITORY_URL`. Every File has sha256 and contentSize.

*Evidence (2026-10-08).* A client-supplied report could show a forged qiskit==9.9.9 as fact; commit links returned 404.

### Crate README

*Rule.* Every RO-Crate has `README.txt` at its root, written by [`rosetta-api/services/export_readme.py`](rosetta-api/services/export_readme.py) from the crate's own `ro-crate-metadata.json` after every other entity is in place: the report source, completeness, specimens and timing caveats as the root's PropertyValues state them, each top-level file with its description, each folder with its file count (names listed up to 40), the hash-check command and the software version and source commit. It is a File entity with `sha256` and `contentSize` like every other file and comes first in the root's `hasPart`. Nothing else in a crate changes; the same export gives the same README.

*Evidence (2026-10-27).* A crate explained itself only through JSON-LD and this repository's manual; the CLI spec (S13) asks for a reader who has neither.

### Image identity reported by the runner

*Rule.* Each runner and compiler image writes `/usr/local/share/qrosetta-image/identity` at build (`source`, `release`, `git_sha` from the build arguments `QROSETTA_IMAGE_SOURCE`, `QROSETTA_RELEASE`, `QROSETTA_GIT_SHA`; compose passes `built_locally`, a release pipeline passes `release`, a plain `docker build` leaves `unknown`) and copies its Dockerfile and `requirements.lock` to `/usr/local/share/qrosetta-build/`. The new values are build arguments and a file, never `ENV`, so the container's environment, and with it the environment the timed child inherits through `spawn`, is unchanged. The serving process reads the file, the build-file hashes, the container runtime's view (Apptainer path and sha256, podman's `/run/.containerenv`) and the `hypervisor` CPU flag once at startup ([`shared/qrosetta_commons/image_identity.py`](shared/qrosetta_commons/image_identity.py)) and adds `image_identity` and `build_files` to each result after the child has returned, beside `queue_wait_sec`; the Kubernetes and batch CLI paths add them after `run_with_uniform_measurement` returns. `runner_image` is the Job's image in Kubernetes mode, else the image the runtime showed the runner (`runner_image_basis`). Each result that ran gets `specimen` and the report `specimens`: `all_published` (one release), `all_built_locally`, `mixed`, `unknown` or `none_ran`, with per-backend detail, the image commits and a note when they differ or are `-dirty`. The roll-up uses only values the image baked. ([`rosetta-api/tests/unit/test_image_identity.py`](rosetta-api/tests/unit/test_image_identity.py), [`test_specimens.py`](rosetta-api/tests/unit/test_specimens.py))

*Evidence (2026-10-27).* Local results recorded `runner_image` "not recorded", and a crate could not say whether a backend ran a published image, a local build or a build from another commit. Through the real spawn path, the child's `os.environ` equals the serving process's environment and the child never reads the identity (`test_result_carries_identity_and_child_environment_is_unchanged`, measured and unmeasured). Images built before this change report `source` "not recorded" until rebuilt.

### Emulation recorded by the runner

*Rule.* Every runner and compiler result carries `image_identity.emulation` = `{emulated, image_arch, host_arch, host_os, method}` ([`shared/qrosetta_commons/image_identity.py`](shared/qrosetta_commons/image_identity.py)). `image_arch` is the ELF `e_machine` of the image's Python interpreter (64-bit machines only; `uname` inside an emulated container reports the emulated machine, so it cannot be used). `host_os` and `host_arch` come from `QROSETTA_HOST_OS` and `QROSETTA_HOST_ARCH`, which `qrosetta start` sets on every start from `platform.system()` / `platform.machine()` (an x86_64 Python on macOS reports `arm64` when `sysctl.proc_translated` is 1) and compose passes to every runner and compiler; `scripts/roihu/run_runner.sh` passes the node's `uname -s` / `uname -m`. The serving process takes both variables out of `os.environ` in its startup handler (`load`), before any child is spawned, and the one-job CLI paths do so right after parsing their arguments, before the self-test or the run; the values are kept in the process and stamped after the child returns, beside the rest of `image_identity`. `emulated` is `image_arch != host_arch` after aliasing (`arm64` = `aarch64`, `AMD64` = `x86_64`), and null when either is unknown, as under plain compose, Kubernetes or `safe_boot.sh` before it hands over to `qrosetta start`. The self-test's `host_emulation` check reads `cpu_environment.emulation`, else `image_identity.emulation` (PASS false, FAIL true, SKIP null; `selftest-2026.10.27.2`). `timing_caveats` adds `emulated_image` when `emulated` is true (`timing-caveats-2026.10.27.3`; no stored report has the field, so no stored report's caveats change). No in-container signal is used: in a fresh user, mount and PID namespace with its own procfs (what a rootless podman container gets), `/proc/sys/fs/binfmt_misc` is an empty directory on this host (kernel 6.12) while the host's own lists its handlers, so a qemu-user or Rosetta handler cannot be seen from inside a container and its absence proves nothing.

*Evidence (2026-10-27).* Through the real spawn path, with the two variables set before `load`, the child's `os.environ` equals the environment without them, measured and unmeasured (`test_host_environment_is_removed_before_the_child_is_spawned`). Old (main) and new code, 3 alternated rounds of 15 runs through `ExecutionSlots` (a Qiskit Aer 0.17.2 statevector processor on `run_statevector_job`, 16-qubit QFT, `timing_repeats` 3, pinned to one P-core, Python 3.12): compilation 35.55 → 35.41 ms, simulation 14.32 → 14.41 ms (the new code's round medians 14.35–14.43, the old's 14.14–14.42), whole-process CPU 714.2 → 712.5 ms, process peak RSS 136.88 → 136.89 MiB (median of round medians); result keys identical, `image_identity` differs only by `emulation`, one statevector across all 90 runs. A first series at host load 12 from other sessions read old 54.3/21.5 ms and new 36.6/15.0 ms; a control at load 3 with the same code twice gave the old/new/new-with-variables triple 34.5–35.9 / 13.9–14.5 ms, and the rerun above is the comparison. Reading the ELF header and the variables costs 37 µs, once per serving process at startup.

### Runner lock files in crates

*Rule.* A crate (and an experiment bundle) includes the server's copy of `runners/<runner>/requirements.lock` only when its sha256 equals `build_files["requirements.lock"]` in every result that runner's image returned. Otherwise the file is left out and the runner's entity, `provenance.json` `runner_lock_files` and the bundle manifest say why: no build-file hashes (image built before runners reported them), a different hash with the image's commit, no copy on the server, or no result from the image.

*Evidence (2026-10-27).* The exporter attached the API tree's lock file for every runner used and described it as the runner image's environment, with no check; in a stack of mixed builds that file did not describe the image that ran. Compilers already had the hash check (Compiler build provenance).

### Timing caveats

*Rule.* [`rosetta-api/services/timing_caveats.py`](rosetta-api/services/timing_caveats.py) derives `timing_caveats` per result and per report from recorded fields only: `shared_dispatch`, `overlapping_runs`, `server_overlapping_runs`, `throttled` and `compilation_throttled` (≥ 1% of the window), `unstable_repeats` (> 1.3× with ≥ 3 samples), `mixed_cores` (classes 10% apart), `outside_process` (≥ 5 ms and ≥ 10%), `single_timed_run`, `no_cpu_quota`, `virtualised_host`, `emulated_cpu`, `non_x86_64`, and across backends `cross_backend_core_speeds`, `cross_backend_cpu_quota`, `cross_backend_image_commits`. Each has a code, a sentence and its fields. It is the only implementation of the page's "throttled", "outside process", "unstable" and "mixed cores" tags and its "Before comparing times" list; the page renders the server's records, and asks `POST /timing-caveats` for a report stored without them. The rules carry `timing_caveats_version`, not `ANALYSIS_VERSION`: they change no agreement label, and bumping the analysis version would mark unchanged agreement evidence as changed. The publication tables keep their own unstable rule (`tables.py` / `artifact_formats.js`, under the parity test).

*Evidence (2026-10-27).* Against the JavaScript of 7e02220 ([`scripts/timing_caveats_equivalence/compare.py`](scripts/timing_caveats_equivalence/compare.py)): 351 saved reports (4,968 results, from play-test, Apptainer and Roihu runs) and 20,000 synthetic reports around every threshold (59,975 results): 0 differences in the four tags and the phrase list.

### Run completeness

*Rule.* Every finished job's report records `run_completeness` (`job_status`, `planned_tasks`, `recorded_tasks`, `tasks_with_results`, `stopped_early`, `reason`). The crate root states `#run-completeness`: `complete`, `partial`, `failed`, `not_recorded` (older reports) or `not_checked` (a report the server did not produce, such as the browser's copy exported after the server's copy expired); any value but `complete` is repeated in the root description.

*Evidence (2026-10-27).* A crate of a stopped playlist or of the browser's fallback copy read like a complete run: each execution was a Completed CreateAction and nothing stated the planned set.

### cirq statevector bits

*Rule.* cirq amplitudes can differ run to run by ~1e-17 (numpy 1.26 SIMD complex loops depend on buffer alignment). Left as is: disabling SIMD would slow cirq and bias timings. Compare replayed statevectors by fidelity, not sha256.

*Evidence.* 382/4096 amplitudes differed by ≤ 5.7e-17 on a 12-qubit circuit; bit-stable with NPY_DISABLE_CPU_FEATURES.

## Security and accounts

### Share links

*Rule.* Saved runs only; token `secrets.token_urlsafe(32)`, only its SHA-256 stored, shown once; expiry 1–90 days (default 30), ≤ 10 active per run, revocable. The token travels in the URL fragment and a POST body; the response is the `circuit_texts` allowlist ([`rosetta-api/services/circuit_texts.py`](rosetta-api/services/circuit_texts.py)) with `Cache-Control: no-store`, `Referrer-Policy: no-referrer`; 30/minute. A deactivated account, a deleted run or a deleted account ends every link.

*Evidence (designed 2026-10-01).* Jobs live 30 minutes and are not tied to an account; a GET path would put the token in access logs.

### Who may save a job

*Rule.* A job submitted with a valid token records the submitting account's user id (`JobTable` keeps it across replacements); only that account may save it (403). Anonymous jobs stay saveable by whoever holds the job id.

*Evidence.* Any account holding a job id could save it as its own run.

### Saved-run access and delete order

*Rule.* `POST /history/runs?circuit_id=` returns 404 unless the circuit belongs to the caller; this is checked before the report is stored. `delete_runs` and `delete_account` delete and flush the rows, then delete the stored reports, then commit, and roll back if either step fails. Account deletion sets `circuit_id` to NULL on other accounts' runs that name its circuits.

*Evidence (2026-10-07).* Any account holding a circuit UUID could link a run to it. On PostgreSQL, deleting that circuit's account (`DELETE /auth/me`) then failed on the foreign key after its S3 reports were already deleted, leaving run records without their reports.

### Client address

*Rule.* Rate limits key on the last X-Forwarded-For entry, or on `X-Qrosetta-Client-Ip` with `QROSETTA_PROXY_TOKEN`.

*Evidence (2026-10-07).* The API keyed on X-Real-IP, which the router passed through from the caller, and the hosted frontend set it to its own peer, so every visitor through that frontend shared one key.

### Name fields

*Rule.* One combined validator per name type (`label_type`), never nested. A version-independent code-point list; blank names are refused.

*Evidence (2026-10-08).* pydantic 2.9.2 dropped nested validators: `RunHistoryUpdate(run_name='a\x00b')` passed.

## Interface and API behaviour

### Outcome names and roles

*Rule.* Every summary (`GET /jobs/{id}/summary`, `POST /summary`, saved runs) counts `outcomes`: each pair under its `pair_verdict` value, `no_comparison` (1 when no pair was compared) and `runs_without_output` (runs whose status is not ok, plus 1 for a circuit that never reached a runner); a playlist's are sums over its tasks. `outcome_roles` gives each name's role (difference, not_established, runs_without_output, agreement), published also as `GET /config` `summary_outcomes` with the analysis version. `qrosetta run --fail-on` maps a name to its exit code by role (3, 8, 4) and holds no list of names ([`rosetta-api/tests/unit/test_summary_outcomes.py`](rosetta-api/tests/unit/test_summary_outcomes.py)).

*Evidence (2026-10-27).* CLI spec v3 critique INT-M8: a final line reading "0 differ" when nothing was compared reads as agreement. A CLI copy of the verdict-to-exit mapping would be a second implementation of part of the rule, which is computed only in `verdicts.py`.

### Runner status label

*Rule.* The live Status cell for a dispatched run reads SENT (tooltip: includes any wait behind another job, recorded as queue_wait_sec).

*Evidence.* The API cannot see when the runner's slot frees; a 2-qubit Quartz compile waited 35 s behind another client's compile while shown RUNNING.

### Figures

*Rule.* Figures use the long display names (`RUNNER_DISPLAY_NAMES` in [`rosetta-api/static/js/runner_key.js`](rosetta-api/static/js/runner_key.js) ↔ `BACKEND_DISPLAY_NAMES` in [`rosetta-api/services/publication/theme.py`](rosetta-api/services/publication/theme.py)), and render requests send the circuit name. The slide canvas is fixed at 16:9.

*Evidence (2026-10-08).* A slide figure rendered at 4149 × 1956 px (2.12:1) titled "unnamed circuit", with legends reading qsim-cirq, pennylane-lightning.

### Quirk visualizer

*Rule.* Every gate is drawn with its matrix up to phase, or the request is refused. At most 16 qubits and 1,000 columns.

*Evidence.* Only h/x/y/z/cx were drawn, and comments became gates.

### Browser state

*Rule.* Every control has `autocomplete="off"` and state is reset on `pageshow`. Jobs are kept per account (pending/stopped 6 h, finished 30 min). Expiry uses the server clock (`iat`). Two columns from 1024 px. Modal dialogs use [`modal.js`](rosetta-api/static/js/modal.js); announcements go through [`announce.js`](rosetta-api/static/js/announce.js).

*Evidence.* The bypass-limits checkbox ticked itself after a reload; stopped jobs were lost; a run leaked across accounts; pages failed WCAG checks.

### API error contract

*Rule.* Every route declares the codes it raises ([`rosetta-api/tests/unit/test_openapi_contract.py`](rosetta-api/tests/unit/test_openapi_contract.py)). 422 means a schema failure; 400 means well formed but unsupported. X-RateLimit-* headers, and Retry-After on 429. `expires_in`; `RunHistory.job_id`; JSON 413 from nginx; nginx compresses responses. Non-UTF-8 JSON bodies are 422 `json_invalid`; non-finite numbers in a client-supplied report are 400; file and page responses declare their real media types. [`scripts/api_fuzz/run_fuzz.py`](scripts/api_fuzz/run_fuzz.py) (Schemathesis, in process) checks the contract.

*Evidence (2026-10-21).* Fuzzing at 300 examples per operation, 17,412 calls: 0 findings after four fixes (media types, UTF-8 bodies, malformed supplied reports, and NaN stored in a saved run, which made every later read return 500).

### API compatibility for older CLIs

*Rule.* The routes the stable `qrosetta` commands read are held to a committed, normalised extract of `/openapi.json` ([`rosetta-api/tests/openapi_cli_baseline.json`](rosetta-api/tests/openapi_cli_baseline.json)). A change that removes a route, method, parameter or field, makes a request field required, narrows a request type or enum, changes a success status or media type, or lets a response field be missing or of a new type fails [`rosetta-api/tests/unit/test_openapi_cli_contract.py`](rosetta-api/tests/unit/test_openapi_cli_contract.py) unless the maximum of `API_LEVELS` (`GET /config` `server.api_levels`) was raised; the previous level stays served for 12 months. `GET /config`, `/runners`, `/compilers` and the circuit catalog routes document their responses with models in [`rosetta-api/schemas/listings.py`](rosetta-api/schemas/listings.py) that never filter them (`response_model` stays unset). The refresh command is in CONTRIBUTING.md.

*Evidence (2026-10-27).* CLI spec v3 S16: a pipx-installed CLI outlives server upgrades, and before this the five most-read routes documented no response schema, so a removed field would have shown up only as a CLI failure on a user's machine. Adding the documentation models left the status, headers and body bytes of 18 TestClient calls on those routes unchanged.

### Web framework versions

*Rule.* The API runs FastAPI 0.136.3 on Starlette 1.7.0, the newest Starlette that supports the image's Python 3.10 (1.8 needs 3.11). The app sets `default_response_class=JSONResponse`, so response models are written by `json.dumps` with `allow_nan=False`, and `strict_content_type=False`, so a JSON body sent without a Content-Type header is read as JSON ([`rosetta-api/tests/unit/test_web_framework.py`](rosetta-api/tests/unit/test_web_framework.py)). Runner and compiler images stay on FastAPI 0.115.0 and Starlette 0.38.6; the shared scaffolding registers its startup hook with `app.router.add_event_handler`, which both versions provide.

*Evidence (2026-10-27).* OSV lists seven advisories (CVEs) for Starlette 0.38.6. Three concern form parsing, which `/auth/token` uses (PYSEC-2026-1943, -1941, -249), and -249 (urlencoded form limits ignored) is fixed only in 1.3.1. FastAPI accepts Starlette 1.x from 0.133.0. FastAPI 0.137 turns `router.routes` into a tree, and 0.147–0.162 change how omitted, empty and null body and form values are read, so 0.136.3 is the last release before those changes. With FastAPI's default response class, 0.130 and later write response models with Pydantic's `dump_json`: a NaN becomes `null` where `json.dumps` raised (a 500), and 1e-05 is written `0.00001`. With both settings, 260 requests to the full app (every route, error bodies, form and Content-Type variants, static files, 429) differ from 0.115.0/0.38.6 only in: `Vary: Origin` on every response (Starlette 1.7 CORS); `Accept-Ranges: bytes` and 206 range responses on files; an empty login field is a 422 (missing field) instead of a 401; a bearer token with surrounding spaces is accepted; a login form of more than 1,000 fields is a 400 (the -249 fix). ZIP and PNG responses are no longer gzip-encoded by the API (Starlette 1.5 excludes those types). OpenAPI: the login form's `grant_type` pattern is anchored (`^password$`), password fields carry `format: password`, `RunHistoryResponse-Input`/`-Output` merge into `RunHistoryResponse`, `ValidationError` lists `input` and `ctx`, and the login route's 400 description names the field limit. Fuzzing at 300 examples per operation (seed 0, 20,718 calls) gives 0 findings on both versions; the status counts differ only for `POST /auth/token`, where more generated forms are 422 (empty fields, `grant_type` values that only contain `password`).

## Upstream behaviour not worked around

The SDK behaviours below are reported by the comparison as disagreement. A workaround for only these backends would bias preprocessing, so none is applied.

- PennyLane `from_qasm` swaps control and target on `QubitUnitary` (cu3, custom gates).
- qibo `cu3` is controlled(e^{-i(φ+λ)/2}·U3). qibo: expressions on gate parameters raise TypeError.
- qrisp runs `cu1` as `crz`. qrisp 0.5's `QuantumCircuit.run()` returns all shots as |0…0⟩ on 12+-qubit circuits with a spread-out distribution (`h q[0]; ch q[0],q[k]` for k=1..11; the statevector path is correct). Qrisp 0.5.2: the definitions of cu1, cu3 and c3sqrtx differ from their matrices; csx acts as crx(π/2); the `run()` outcome cutoff; statevector truncation; qelib1's four-parameter `cu` is rejected.
- torchquantum's `qiskit2tq` uses register-local indices with several qregs, so the torchquantum adapter refuses multi-qreg circuits when `apply_preprocessing=False` (the API's register merge makes them work with preprocessing on).
- quimb 1.13.0 substitutes gate parameters by substring (`g(t, t2)` gives `rz(t2)` the value `t` followed by `2`); with preprocessing on, the round-trip inlines the definition first.
- cirq-core 1.7.0 imports rc3x as a MatrixGate it cannot write.
- Qiskit 0.45.3 level 3 deletes a trailing swap without recording a layout.
- BQSKit 1.2.1's `Circuit.unfold(point)` changes the unitary when gates precede the unfolded gate.
